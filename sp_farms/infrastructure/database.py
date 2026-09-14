import json
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from shutil import copy2
from types import TracebackType
from typing import Self
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from sp_farms.application.accounts import AccountRepository
from sp_farms.application.device_pool import DevicePoolRepository
from sp_farms.application.device_profiles import DeviceProfileRepository
from sp_farms.application.jobs import JobRepository
from sp_farms.application.qa_profiles import QAProfileRepository
from sp_farms.application.secrets import SecretRepository
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.accounts import (
    Account,
    AccountCategory,
    AccountDeviceAssignment,
    AccountGender,
    AccountStatus,
    AccountTag,
    PermissionState,
    PreferredApp,
    SecurityState,
)
from sp_farms.domain.device_management import DeviceProfile
from sp_farms.domain.device_pool import (
    AccountWorkspaceLock,
    DevicePoolPolicy,
    SchedulingPolicy,
    SnapshotMetadataRecord,
)
from sp_farms.domain.device_restore import AccountDeviceBinding, BindingStatus
from sp_farms.domain.jobs import Job, JobEvent, JobState
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.domain.qa_profiles import (
    QADeviceAssignment,
    QAProfile,
    QAProfileAudit,
    QATargetPackage,
)
from sp_farms.domain.secrets import SecretReference, SecretType


class Base(DeclarativeBase):
    pass


class EntityMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SystemMetadata(EntityMixin, Base):
    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)


class SecretMetadata(EntityMixin, Base):
    __tablename__ = "secret_metadata"

    secret_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    vault_ref: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)

    @classmethod
    def from_reference(cls, reference: SecretReference) -> "SecretMetadata":
        return cls(
            id=reference.id,
            secret_type=reference.secret_type.value,
            owner_id=reference.owner_id,
            vault_ref=reference.vault_ref,
            created_at=reference.created_at,
            updated_at=reference.updated_at,
        )

    def to_reference(self) -> SecretReference:
        return SecretReference(
            id=self.id,
            secret_type=SecretType(self.secret_type),
            owner_id=self.owner_id,
            vault_ref=self.vault_ref,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DeviceProfileModel(EntityMixin, Base):
    __tablename__ = "device_profiles"
    __table_args__ = (Index("ux_device_profiles_identity", "provider", "external_id", unique=True),)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    friendly_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    emulator_instance: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    adb_serial: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    android_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    resolution: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    locale: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    keyboard_config: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    app_versions: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    preferred_app: Mapped[str] = mapped_column(String(30), nullable=False, default="browser")
    network_profile_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_profile(self) -> DeviceProfile:
        try:
            apps = json.loads(self.app_versions)
            if not isinstance(apps, dict):
                apps = {}
        except Exception:
            apps = {}
        return DeviceProfile(
            provider=DeviceProviderType(self.provider),
            external_id=self.external_id,
            id=self.id,
            friendly_name=self.friendly_name,
            emulator_instance=self.emulator_instance,
            adb_serial=self.adb_serial,
            android_version=self.android_version,
            model=self.model,
            resolution=self.resolution,
            dpi=self.dpi,
            language=self.language,
            locale=self.locale,
            timezone=self.timezone,
            keyboard_config=self.keyboard_config,
            app_versions=apps,
            preferred_app=PreferredApp(self.preferred_app)
            if self.preferred_app in PreferredApp._value2member_map_
            else PreferredApp.BROWSER,
            network_profile_ref=self.network_profile_ref,
            last_heartbeat=_optional_utc(self.last_heartbeat),
            alias=self.alias,
            notes=self.notes,
            created_at=_optional_utc(self.created_at),
            updated_at=_optional_utc(self.updated_at),
        )


class AccountDeviceBindingModel(EntityMixin, Base):
    __tablename__ = "account_device_bindings"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    device_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("device_profiles.id", ondelete="CASCADE"), nullable=False
    )
    preferred_app: Mapped[str] = mapped_column(String(30), nullable=False, default="browser")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_binding(self) -> AccountDeviceBinding:
        return AccountDeviceBinding(
            id=self.id,
            account_id=self.account_id,
            device_profile_id=self.device_profile_id,
            preferred_app=PreferredApp(self.preferred_app)
            if self.preferred_app in PreferredApp._value2member_map_
            else PreferredApp.BROWSER,
            status=BindingStatus(self.status)
            if self.status in BindingStatus._value2member_map_
            else BindingStatus.ACTIVE,
            last_used_at=_optional_utc(self.last_used_at),
            created_at=_optional_utc(self.created_at),
            updated_at=_optional_utc(self.updated_at),
        )


class AccountWorkspaceLockModel(Base):
    __tablename__ = "account_workspace_locks"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    device_key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_lock(self) -> AccountWorkspaceLock:
        return AccountWorkspaceLock(
            account_id=self.account_id,
            device_key=self.device_key,
            job_id=self.job_id,
            acquired_at=_as_utc(self.acquired_at),
            expires_at=_as_utc(self.expires_at),
            heartbeat=_as_utc(self.heartbeat),
        )


class AccountWorkspaceSnapshotModel(Base):
    __tablename__ = "account_workspace_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    device_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    preferred_app: Mapped[str] = mapped_column(String(30), nullable=False, default="browser")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_restored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_record(self) -> SnapshotMetadataRecord:
        return SnapshotMetadataRecord(
            id=self.id,
            account_id=self.account_id,
            path=self.path,
            size_bytes=self.size_bytes,
            schema_version=self.schema_version,
            checksum=self.checksum,
            device_profile_id=self.device_profile_id,
            preferred_app=self.preferred_app,
            notes=self.notes,
            created_at=_as_utc(self.created_at),
            last_restored_at=_optional_utc(self.last_restored_at),
        )


class DevicePoolPolicyModel(Base):
    __tablename__ = "device_pool_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    policy: Mapped[str] = mapped_column(String(50), nullable=False, default="bound_device_first")
    preferred_provider_order: Mapped[str] = mapped_column(
        String(255), nullable=False, default="ldplayer,mumu,physical"
    )
    allow_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_concurrent_restores: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_policy(self) -> DevicePoolPolicy:
        providers = tuple(
            p.strip() for p in self.preferred_provider_order.split(",") if p.strip()
        )
        return DevicePoolPolicy(
            id=self.id,
            name=self.name,
            policy=SchedulingPolicy(self.policy)
            if self.policy in SchedulingPolicy._value2member_map_
            else SchedulingPolicy.BOUND_DEVICE_FIRST,
            preferred_provider_order=providers or ("ldplayer", "mumu", "physical"),
            allow_fallback=self.allow_fallback,
            max_concurrent_restores=self.max_concurrent_restores,
            is_active=self.is_active,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class QAProfileModel(EntityMixin, Base):
    __tablename__ = "qa_profiles"

    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    market_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    product: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    hardware: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    board: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    bootloader: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    build_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    test_android_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_serial_number: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_imei: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_meid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_gsf_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_advertising_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_mac: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_bluetooth_mac: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_wifi_ssid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_wifi_bssid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_network_generation: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    test_imsi: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_sim_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_mobile_number: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_esim_eid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_sim_operator: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_sim_operator_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    test_sim_country_iso: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    @classmethod
    def from_profile(cls, profile: QAProfile) -> "QAProfileModel":
        return cls(**_qa_profile_values(profile))

    def update_from_profile(self, profile: QAProfile) -> None:
        for key, value in _qa_profile_values(profile).items():
            setattr(self, key, value)

    def to_profile(self) -> QAProfile:
        values = {
            key: getattr(self, key)
            for key in QAProfile.__dataclass_fields__
            if key not in {"created_at", "updated_at"}
        }
        return QAProfile(
            **values,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class QATargetPackageModel(Base):
    __tablename__ = "qa_target_packages"

    package_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ownership_note: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_verified: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    test_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("qa_profiles.id", ondelete="SET NULL")
    )

    def to_target(self) -> QATargetPackage:
        return QATargetPackage(
            package_id=self.package_id,
            display_name=self.display_name,
            ownership_note=self.ownership_note,
            enabled=self.enabled,
            last_verified=_as_utc(self.last_verified),
            test_profile_id=self.test_profile_id,
        )


class QADeviceAssignmentModel(EntityMixin, Base):
    __tablename__ = "qa_device_assignments"
    __table_args__ = (
        Index("ux_qa_device_assignments_identity", "provider", "external_id", unique=True),
    )

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("qa_profiles.id", ondelete="CASCADE"), nullable=False
    )


class QAProfileAuditModel(EntityMixin, Base):
    __tablename__ = "qa_profile_audits"

    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    package_id: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_id: Mapped[str | None] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(100), nullable=False)


class AccountCategoryModel(EntityMixin, Base):
    __tablename__ = "account_categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=False)


class AccountTagModel(EntityMixin, Base):
    __tablename__ = "account_tags"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=False)


class AccountModel(EntityMixin, Base):
    __tablename__ = "accounts"

    avatar_ref: Mapped[str | None] = mapped_column(String(500))
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform_uid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    birthday: Mapped[date | None] = mapped_column(Date())
    gender: Mapped[str | None] = mapped_column(String(30))
    primary_email: Mapped[str] = mapped_column(String(320), nullable=False)
    recovery_email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    locale: Mapped[str] = mapped_column(String(50), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    account_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("account_categories.id", ondelete="SET NULL")
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_app: Mapped[str] = mapped_column(String(30), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    group_count: Mapped[int] = mapped_column(Integer, nullable=False)
    permission_state: Mapped[str] = mapped_column(String(30), nullable=False)
    security_state: Mapped[str] = mapped_column(String(30), nullable=False)


class AccountTagAssignmentModel(Base):
    __tablename__ = "account_tag_assignments"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account_tags.id", ondelete="CASCADE"), primary_key=True
    )


class AccountDeviceAssignmentModel(EntityMixin, Base):
    __tablename__ = "account_device_assignments"
    __table_args__ = (
        Index(
            "ux_account_device_assignments_device",
            "provider",
            "external_id",
            unique=True,
        ),
    )

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)


class JobModel(EntityMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_target", "target_type", "target_id"),)

    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @classmethod
    def from_job(cls, job: Job) -> "JobModel":
        return cls(
            id=job.id,
            job_type=job.job_type,
            target_type=job.target_type,
            target_id=job.target_id,
            state=job.state.value,
            progress=job.progress,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            idempotency_key=job.idempotency_key,
            error_code=job.error_code,
            error_message=job.error_message,
            next_retry_at=job.next_retry_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def update_from_job(self, job: Job) -> None:
        self.job_type = job.job_type
        self.target_type = job.target_type
        self.target_id = job.target_id
        self.state = job.state.value
        self.progress = job.progress
        self.attempt_count = job.attempt_count
        self.max_attempts = job.max_attempts
        self.idempotency_key = job.idempotency_key
        self.error_code = job.error_code
        self.error_message = job.error_message
        self.next_retry_at = job.next_retry_at
        self.updated_at = job.updated_at

    def to_job(self) -> Job:
        return Job(
            id=self.id,
            job_type=self.job_type,
            target_type=self.target_type,
            target_id=self.target_id,
            state=JobState(self.state),
            progress=self.progress,
            attempt_count=self.attempt_count,
            max_attempts=self.max_attempts,
            idempotency_key=self.idempotency_key,
            error_code=self.error_code,
            error_message=self.error_message,
            next_retry_at=_optional_as_utc(self.next_retry_at),
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class JobEventModel(EntityMixin, Base):
    __tablename__ = "job_events"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    @classmethod
    def from_event(cls, job_event: JobEvent) -> "JobEventModel":
        return cls(
            id=job_event.id,
            job_id=job_event.job_id,
            from_state=job_event.from_state.value if job_event.from_state else None,
            to_state=job_event.to_state.value,
            message=job_event.message,
            created_at=job_event.created_at,
            updated_at=job_event.created_at,
        )

    def to_event(self) -> JobEvent:
        return JobEvent(
            id=self.id,
            job_id=self.job_id,
            from_state=JobState(self.from_state) if self.from_state else None,
            to_state=JobState(self.to_state),
            message=self.message,
            created_at=_as_utc(self.created_at),
        )


def _account_values(account: Account) -> dict[str, object]:
    return {
        "id": account.id,
        "avatar_ref": account.avatar_ref,
        "display_name": account.display_name,
        "first_name": account.first_name,
        "last_name": account.last_name,
        "platform_uid": account.platform_uid,
        "birthday": account.birthday,
        "gender": account.gender.value if account.gender else None,
        "primary_email": account.primary_email,
        "recovery_email": account.recovery_email,
        "phone": account.phone,
        "country": account.country,
        "locale": account.locale,
        "timezone": account.timezone,
        "account_created_at": account.account_created_at,
        "status": account.status.value,
        "two_factor_enabled": account.two_factor_enabled,
        "category_id": account.category_id,
        "notes": account.notes,
        "preferred_app": account.preferred_app.value,
        "last_login_at": account.last_login_at,
        "last_verified_at": account.last_verified_at,
        "page_count": account.page_count,
        "group_count": account.group_count,
        "permission_state": account.permission_state.value,
        "security_state": account.security_state.value,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
        "archived_at": account.archived_at,
    }


def _qa_profile_values(profile: QAProfile) -> dict[str, object]:
    return {
        key: getattr(profile, key) for key in QAProfile.__dataclass_fields__ if key != "updated_at"
    } | {"updated_at": profile.updated_at}


def _optional_utc(value: datetime | None) -> datetime | None:
    return _as_utc(value) if value is not None else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _optional_as_utc(value: datetime | None) -> datetime | None:
    return _as_utc(value) if value is not None else None


class SqlAlchemyDeviceProfileRepository(DeviceProfileRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyDeviceProfileRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def get(self, provider: DeviceProviderType, external_id: str) -> DeviceProfile | None:
        model = (
            self._session.query(DeviceProfileModel)
            .filter_by(provider=provider.value, external_id=external_id)
            .one_or_none()
        )
        return model.to_profile() if model else None

    def get_by_id(self, profile_id: str) -> DeviceProfile | None:
        model = self._session.get(DeviceProfileModel, profile_id)
        return model.to_profile() if model else None

    def list_all(self) -> Sequence[DeviceProfile]:
        models = self._session.query(DeviceProfileModel).order_by(DeviceProfileModel.id).all()
        return tuple(model.to_profile() for model in models)

    def save(self, profile: DeviceProfile) -> None:
        model = None
        if profile.id:
            model = self._session.get(DeviceProfileModel, profile.id)
        if model is None:
            model = (
                self._session.query(DeviceProfileModel)
                .filter_by(provider=profile.provider.value, external_id=profile.external_id)
                .one_or_none()
            )

        apps_json = json.dumps(profile.app_versions)
        if model is None:
            kwargs: dict[str, object] = {
                "id": profile.id or str(uuid4()),
                "provider": profile.provider.value,
                "external_id": profile.external_id,
                "alias": profile.alias or profile.friendly_name,
                "notes": profile.notes,
                "friendly_name": profile.friendly_name or profile.alias,
                "emulator_instance": profile.emulator_instance,
                "adb_serial": profile.adb_serial,
                "android_version": profile.android_version,
                "model": profile.model,
                "resolution": profile.resolution,
                "dpi": profile.dpi,
                "language": profile.language,
                "locale": profile.locale,
                "timezone": profile.timezone,
                "keyboard_config": profile.keyboard_config,
                "app_versions": apps_json,
                "preferred_app": profile.preferred_app.value,
                "network_profile_ref": profile.network_profile_ref,
                "last_heartbeat": profile.last_heartbeat,
            }
            self._session.add(DeviceProfileModel(**kwargs))
        else:
            model.alias = profile.alias or profile.friendly_name
            model.notes = profile.notes
            model.friendly_name = profile.friendly_name or profile.alias
            model.emulator_instance = profile.emulator_instance
            model.adb_serial = profile.adb_serial
            model.android_version = profile.android_version
            model.model = profile.model
            model.resolution = profile.resolution
            model.dpi = profile.dpi
            model.language = profile.language
            model.locale = profile.locale
            model.timezone = profile.timezone
            model.keyboard_config = profile.keyboard_config
            model.app_versions = apps_json
            model.preferred_app = profile.preferred_app.value
            model.network_profile_ref = profile.network_profile_ref
            model.last_heartbeat = profile.last_heartbeat

    def get_binding(self, account_id: str) -> AccountDeviceBinding | None:
        model = (
            self._session.query(AccountDeviceBindingModel)
            .filter_by(account_id=account_id)
            .one_or_none()
        )
        return model.to_binding() if model else None

    def save_binding(self, binding: AccountDeviceBinding) -> None:
        model = (
            self._session.query(AccountDeviceBindingModel)
            .filter_by(account_id=binding.account_id)
            .one_or_none()
        )
        if model is None:
            kwargs: dict[str, object] = {
                "account_id": binding.account_id,
                "device_profile_id": binding.device_profile_id,
                "preferred_app": binding.preferred_app.value,
                "status": binding.status.value,
                "last_used_at": binding.last_used_at,
            }
            if binding.id:
                kwargs["id"] = binding.id
            self._session.add(AccountDeviceBindingModel(**kwargs))
        else:
            model.device_profile_id = binding.device_profile_id
            model.preferred_app = binding.preferred_app.value
            model.status = binding.status.value
            model.last_used_at = binding.last_used_at

    def list_bindings(self) -> Sequence[AccountDeviceBinding]:
        models = (
            self._session.query(AccountDeviceBindingModel)
            .order_by(AccountDeviceBindingModel.created_at)
            .all()
        )
        return tuple(model.to_binding() for model in models)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemyAccountRepository(AccountRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyAccountRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def list_accounts(self, include_archived: bool = False) -> Sequence[Account]:
        query = self._session.query(AccountModel)
        if not include_archived:
            query = query.filter(AccountModel.archived_at.is_(None))
        return tuple(self._to_account(model) for model in query.order_by(AccountModel.display_name))

    def get_account(self, account_id: str) -> Account | None:
        model = self._session.get(AccountModel, account_id)
        return self._to_account(model) if model else None

    def save_account(self, account: Account) -> None:
        model = self._session.get(AccountModel, account.id)
        values = _account_values(account)
        if model is None:
            self._session.add(AccountModel(**values))
        else:
            for key, value in values.items():
                setattr(model, key, value)

    def list_categories(self) -> Sequence[AccountCategory]:
        models = self._session.query(AccountCategoryModel).order_by(AccountCategoryModel.name)
        return tuple(AccountCategory(model.id, model.name, model.color) for model in models)

    def save_category(self, category: AccountCategory) -> None:
        model = self._session.get(AccountCategoryModel, category.id)
        if model is None:
            self._session.add(
                AccountCategoryModel(id=category.id, name=category.name, color=category.color)
            )
        else:
            model.name = category.name
            model.color = category.color

    def list_tags(self) -> Sequence[AccountTag]:
        models = self._session.query(AccountTagModel).order_by(AccountTagModel.name)
        return tuple(AccountTag(model.id, model.name, model.color) for model in models)

    def save_tag(self, tag: AccountTag) -> None:
        model = self._session.get(AccountTagModel, tag.id)
        if model is None:
            self._session.add(AccountTagModel(id=tag.id, name=tag.name, color=tag.color))
        else:
            model.name = tag.name
            model.color = tag.color

    def set_tags(self, account_id: str, tag_ids: Sequence[str]) -> None:
        self._session.query(AccountTagAssignmentModel).filter_by(account_id=account_id).delete()
        self._session.add_all(
            AccountTagAssignmentModel(account_id=account_id, tag_id=tag_id)
            for tag_id in dict.fromkeys(tag_ids)
        )

    def assign_device(self, assignment: AccountDeviceAssignment) -> None:
        device_owner = (
            self._session.query(AccountDeviceAssignmentModel)
            .filter_by(provider=assignment.provider, external_id=assignment.external_id)
            .one_or_none()
        )
        if device_owner is not None and device_owner.account_id != assignment.account_id:
            self._session.delete(device_owner)
            self._session.flush()
        model = (
            self._session.query(AccountDeviceAssignmentModel)
            .filter_by(account_id=assignment.account_id)
            .one_or_none()
        )
        if model is None:
            self._session.add(
                AccountDeviceAssignmentModel(
                    account_id=assignment.account_id,
                    provider=assignment.provider,
                    external_id=assignment.external_id,
                )
            )
        else:
            model.provider = assignment.provider
            model.external_id = assignment.external_id

    def _to_account(self, model: AccountModel) -> Account:
        tag_ids = tuple(
            row[0]
            for row in self._session.query(AccountTagAssignmentModel.tag_id)
            .filter_by(account_id=model.id)
            .order_by(AccountTagAssignmentModel.tag_id)
            .all()
        )
        device = (
            self._session.query(AccountDeviceAssignmentModel)
            .filter_by(account_id=model.id)
            .one_or_none()
        )
        assignment = (
            AccountDeviceAssignment(model.id, device.provider, device.external_id)
            if device
            else None
        )
        return Account(
            id=model.id,
            avatar_ref=model.avatar_ref,
            display_name=model.display_name,
            first_name=model.first_name,
            last_name=model.last_name,
            platform_uid=model.platform_uid,
            birthday=model.birthday,
            gender=AccountGender(model.gender) if model.gender else None,
            primary_email=model.primary_email,
            recovery_email=model.recovery_email,
            phone=model.phone,
            country=model.country,
            locale=model.locale,
            timezone=model.timezone,
            account_created_at=_optional_utc(model.account_created_at),
            status=AccountStatus(model.status),
            two_factor_enabled=model.two_factor_enabled,
            category_id=model.category_id,
            tag_ids=tag_ids,
            notes=model.notes,
            assigned_device=assignment,
            preferred_app=PreferredApp(model.preferred_app),
            last_login_at=_optional_utc(model.last_login_at),
            last_verified_at=_optional_utc(model.last_verified_at),
            page_count=model.page_count,
            group_count=model.group_count,
            permission_state=PermissionState(model.permission_state),
            security_state=SecurityState(model.security_state),
            created_at=_as_utc(model.created_at),
            updated_at=_as_utc(model.updated_at),
            archived_at=_optional_utc(model.archived_at),
        )

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemyQAProfileRepository(QAProfileRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyQAProfileRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def list_profiles(self) -> Sequence[QAProfile]:
        models = self._session.query(QAProfileModel).order_by(QAProfileModel.profile_name).all()
        return tuple(model.to_profile() for model in models)

    def get_profile(self, profile_id: str) -> QAProfile | None:
        model = self._session.get(QAProfileModel, profile_id)
        return model.to_profile() if model else None

    def save_profile(self, profile: QAProfile) -> None:
        model = self._session.get(QAProfileModel, profile.id)
        if model is None:
            self._session.add(QAProfileModel.from_profile(profile))
        else:
            model.update_from_profile(profile)

    def delete_profile(self, profile_id: str) -> None:
        model = self._session.get(QAProfileModel, profile_id)
        if model is not None:
            self._session.delete(model)

    def list_targets(self) -> Sequence[QATargetPackage]:
        models = (
            self._session.query(QATargetPackageModel)
            .order_by(QATargetPackageModel.package_id)
            .all()
        )
        return tuple(model.to_target() for model in models)

    def get_target(self, package_id: str) -> QATargetPackage | None:
        model = self._session.get(QATargetPackageModel, package_id)
        return model.to_target() if model else None

    def save_target(self, target: QATargetPackage) -> None:
        model = self._session.get(QATargetPackageModel, target.package_id)
        if model is None:
            self._session.add(
                QATargetPackageModel(
                    package_id=target.package_id,
                    display_name=target.display_name,
                    ownership_note=target.ownership_note,
                    enabled=target.enabled,
                    last_verified=target.last_verified,
                    test_profile_id=target.test_profile_id,
                )
            )
        else:
            model.display_name = target.display_name
            model.ownership_note = target.ownership_note
            model.enabled = target.enabled
            model.last_verified = target.last_verified
            model.test_profile_id = target.test_profile_id

    def get_assignment(self, provider: str, external_id: str) -> QADeviceAssignment | None:
        model = (
            self._session.query(QADeviceAssignmentModel)
            .filter_by(provider=provider, external_id=external_id)
            .one_or_none()
        )
        if model is None:
            return None
        return QADeviceAssignment(model.provider, model.external_id, model.profile_id)

    def save_assignment(self, assignment: QADeviceAssignment) -> None:
        model = (
            self._session.query(QADeviceAssignmentModel)
            .filter_by(provider=assignment.provider, external_id=assignment.external_id)
            .one_or_none()
        )
        if model is None:
            self._session.add(
                QADeviceAssignmentModel(
                    provider=assignment.provider,
                    external_id=assignment.external_id,
                    profile_id=assignment.profile_id,
                )
            )
        else:
            model.profile_id = assignment.profile_id

    def add_audit(self, audit: QAProfileAudit) -> None:
        self._session.add(
            QAProfileAuditModel(
                id=audit.id,
                actor=audit.actor,
                operation=audit.operation,
                provider=audit.provider,
                external_id=audit.external_id,
                package_id=audit.package_id,
                profile_id=audit.profile_id,
                result=audit.result,
                created_at=audit.timestamp,
                updated_at=audit.timestamp,
            )
        )

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemyJobRepository(JobRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyJobRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def add(self, job: Job) -> None:
        session = self._session
        model = session.get(JobModel, job.id)
        if model is None:
            session.add(JobModel.from_job(job))
        else:
            model.update_from_job(job)

    def get(self, job_id: str) -> Job | None:
        model = self._session.get(JobModel, job_id)
        return model.to_job() if model else None

    def find_by_idempotency_key(self, key: str) -> Job | None:
        model = self._session.query(JobModel).filter_by(idempotency_key=key).one_or_none()
        return model.to_job() if model else None

    def list_all(self) -> Sequence[Job]:
        models = self._session.query(JobModel).order_by(JobModel.created_at.desc()).all()
        return tuple(model.to_job() for model in models)

    def list_active(self) -> Sequence[Job]:
        terminal = tuple(state.value for state in JobState if state.is_terminal)
        models = self._session.query(JobModel).filter(JobModel.state.not_in(terminal)).all()
        return tuple(model.to_job() for model in models)

    def add_event(self, job_event: JobEvent) -> None:
        self._session.flush()
        self._session.add(JobEventModel.from_event(job_event))

    def list_events(self, job_id: str) -> Sequence[JobEvent]:
        models = (
            self._session.query(JobEventModel)
            .filter_by(job_id=job_id)
            .order_by(JobEventModel.created_at, text("job_events.rowid"))
            .all()
        )
        return tuple(model.to_event() for model in models)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemyDevicePoolRepository(DevicePoolRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyDevicePoolRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def acquire_lock(
        self,
        account_id: str,
        device_key: str,
        job_id: str | None,
        now: datetime,
        ttl_seconds: int = 300,
    ) -> AccountWorkspaceLock | None:
        session = self._session
        utc_now = _as_utc(now)
        expires_at = utc_now + timedelta(seconds=ttl_seconds)

        existing_device_locks = (
            session.query(AccountWorkspaceLockModel)
            .filter(AccountWorkspaceLockModel.device_key == device_key)
            .all()
        )
        for dlock in existing_device_locks:
            if dlock.account_id != account_id:
                if _as_utc(dlock.expires_at) > utc_now:
                    return None
                else:
                    session.delete(dlock)
                    session.flush()

        lock = session.get(AccountWorkspaceLockModel, account_id)
        if lock is not None:
            if _as_utc(lock.expires_at) > utc_now and lock.device_key != device_key:
                return None
            lock.device_key = device_key
            lock.job_id = job_id
            lock.acquired_at = utc_now
            lock.expires_at = expires_at
            lock.heartbeat = utc_now
        else:
            lock = AccountWorkspaceLockModel(
                account_id=account_id,
                device_key=device_key,
                job_id=job_id,
                acquired_at=utc_now,
                expires_at=expires_at,
                heartbeat=utc_now,
            )
            session.add(lock)

        session.flush()
        return lock.to_lock()

    def get_lock_by_account(self, account_id: str) -> AccountWorkspaceLock | None:
        model = self._session.get(AccountWorkspaceLockModel, account_id)
        return model.to_lock() if model else None

    def get_lock_by_device(self, device_key: str) -> AccountWorkspaceLock | None:
        model = (
            self._session.query(AccountWorkspaceLockModel)
            .filter_by(device_key=device_key)
            .first()
        )
        return model.to_lock() if model else None

    def list_active_locks(self, now: datetime) -> Sequence[AccountWorkspaceLock]:
        utc_now = _as_utc(now)
        models = (
            self._session.query(AccountWorkspaceLockModel)
            .filter(AccountWorkspaceLockModel.expires_at > utc_now)
            .order_by(AccountWorkspaceLockModel.acquired_at.desc())
            .all()
        )
        return tuple(m.to_lock() for m in models)

    def release_lock(self, account_id: str) -> bool:
        model = self._session.get(AccountWorkspaceLockModel, account_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    def release_stale_locks(self, now: datetime) -> int:
        utc_now = _as_utc(now)
        stale = (
            self._session.query(AccountWorkspaceLockModel)
            .filter(AccountWorkspaceLockModel.expires_at <= utc_now)
            .all()
        )
        count = len(stale)
        for m in stale:
            self._session.delete(m)
        if count > 0:
            self._session.flush()
        return count

    def refresh_lock(
        self,
        account_id: str,
        now: datetime,
        ttl_seconds: int = 300,
    ) -> bool:
        utc_now = _as_utc(now)
        model = self._session.get(AccountWorkspaceLockModel, account_id)
        if model is None or _as_utc(model.expires_at) <= utc_now:
            return False
        model.heartbeat = utc_now
        model.expires_at = utc_now + timedelta(seconds=ttl_seconds)
        self._session.flush()
        return True

    def save_snapshot_record(self, record: SnapshotMetadataRecord) -> None:
        session = self._session
        model = session.get(AccountWorkspaceSnapshotModel, record.id)
        if model is None:
            session.add(
                AccountWorkspaceSnapshotModel(
                    id=record.id,
                    account_id=record.account_id,
                    path=record.path,
                    size_bytes=record.size_bytes,
                    schema_version=record.schema_version,
                    checksum=record.checksum,
                    device_profile_id=record.device_profile_id,
                    preferred_app=record.preferred_app,
                    notes=record.notes,
                    created_at=_as_utc(record.created_at),
                    last_restored_at=_optional_utc(record.last_restored_at),
                )
            )
        else:
            model.path = record.path
            model.size_bytes = record.size_bytes
            model.schema_version = record.schema_version
            model.checksum = record.checksum
            model.device_profile_id = record.device_profile_id
            model.preferred_app = record.preferred_app
            model.notes = record.notes
            model.last_restored_at = _optional_utc(record.last_restored_at)
        session.flush()

    def get_snapshot_record(self, snapshot_id: str) -> SnapshotMetadataRecord | None:
        model = self._session.get(AccountWorkspaceSnapshotModel, snapshot_id)
        return model.to_record() if model else None

    def list_snapshots_for_account(
        self, account_id: str
    ) -> Sequence[SnapshotMetadataRecord]:
        models = (
            self._session.query(AccountWorkspaceSnapshotModel)
            .filter_by(account_id=account_id)
            .order_by(AccountWorkspaceSnapshotModel.created_at.desc())
            .all()
        )
        return tuple(m.to_record() for m in models)

    def list_all_snapshots(self) -> Sequence[SnapshotMetadataRecord]:
        models = (
            self._session.query(AccountWorkspaceSnapshotModel)
            .order_by(AccountWorkspaceSnapshotModel.created_at.desc())
            .all()
        )
        return tuple(m.to_record() for m in models)

    def delete_snapshot_record(self, snapshot_id: str) -> bool:
        model = self._session.get(AccountWorkspaceSnapshotModel, snapshot_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    def update_snapshot_last_restored(
        self, snapshot_id: str, restored_at: datetime
    ) -> None:
        model = self._session.get(AccountWorkspaceSnapshotModel, snapshot_id)
        if model is not None:
            model.last_restored_at = _as_utc(restored_at)
            self._session.flush()

    def get_policy(self, name: str) -> DevicePoolPolicy | None:
        model = self._session.query(DevicePoolPolicyModel).filter_by(name=name).one_or_none()
        return model.to_policy() if model else None

    def get_active_policy(self) -> DevicePoolPolicy | None:
        model = (
            self._session.query(DevicePoolPolicyModel)
            .filter_by(is_active=True)
            .first()
        )
        return model.to_policy() if model else None

    def save_policy(self, policy: DevicePoolPolicy) -> None:
        session = self._session
        model = session.get(DevicePoolPolicyModel, policy.id)
        provider_order_str = ",".join(policy.preferred_provider_order)
        if model is None:
            session.add(
                DevicePoolPolicyModel(
                    id=policy.id,
                    name=policy.name,
                    policy=policy.policy.value,
                    preferred_provider_order=provider_order_str,
                    allow_fallback=policy.allow_fallback,
                    max_concurrent_restores=policy.max_concurrent_restores,
                    is_active=policy.is_active,
                    created_at=_as_utc(policy.created_at),
                    updated_at=_as_utc(policy.updated_at),
                )
            )
        else:
            model.name = policy.name
            model.policy = policy.policy.value
            model.preferred_provider_order = provider_order_str
            model.allow_fallback = policy.allow_fallback
            model.max_concurrent_restores = policy.max_concurrent_restores
            model.is_active = policy.is_active
            model.updated_at = _as_utc(policy.updated_at)
        session.flush()

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemySecretRepository(SecretRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemySecretRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def list_by_owner_ids(
        self, owner_ids: Sequence[str] | None = None
    ) -> Sequence[SecretReference]:
        query = self._session.query(SecretMetadata)
        if owner_ids is not None:
            query = query.filter(SecretMetadata.owner_id.in_(owner_ids))
        models = query.all()
        return tuple(m.to_reference() for m in models)

    def save(self, reference: SecretReference) -> None:
        session = self._session
        model = session.get(SecretMetadata, reference.id)
        if model is None:
            session.add(SecretMetadata.from_reference(reference))
        else:
            model.secret_type = reference.secret_type.value
            model.owner_id = reference.owner_id
            model.vault_ref = reference.vault_ref
            model.updated_at = reference.updated_at
        session.flush()

    def delete(self, reference_id: str) -> None:
        model = self._session.get(SecretMetadata, reference_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            URL.create("sqlite", database=str(path)),
            connect_args={"timeout": 30},
        )
        event.listen(self.engine, "connect", _configure_sqlite)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def unit_of_work(self) -> "SqlAlchemyUnitOfWork":
        return SqlAlchemyUnitOfWork(self.session_factory)

    def close(self) -> None:
        self.engine.dispose()


class SqlAlchemyUnitOfWork(AbstractContextManager["SqlAlchemyUnitOfWork"]):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exception_type is not None:
            self.rollback()
        self.session.close()
        self.session = None

    def commit(self) -> None:
        self._active_session().commit()

    def rollback(self) -> None:
        self._active_session().rollback()

    def _active_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("Unit of work is not active")
        return self.session


def run_migrations(database: Database, migrations_path: Path) -> Path | None:
    config = Config(str(migrations_path.parent / "alembic.ini"))
    config.set_main_option("script_location", str(migrations_path))
    script = ScriptDirectory.from_config(config)
    current = _current_revision(database.engine)
    target = script.get_current_head()
    backup = None

    if current is not None and current != target:
        backup = _backup_database(database.path)

    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return backup


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _backup_database(path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    copy2(path, backup)
    return backup


def _configure_sqlite(dbapi_connection: object, connection_record: object) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
    finally:
        cursor.close()
