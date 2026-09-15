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
from sp_farms.application.analytics_repository import AnalyticsRepositoryPort
from sp_farms.application.approval_repository import ApprovalRepositoryPort
from sp_farms.application.audit_repository import AuditRepository
from sp_farms.application.automation_builder import AutomationPresetRepositoryPort
from sp_farms.application.campaign_repository import CampaignRepositoryPort
from sp_farms.application.content_repository import ContentRepositoryPort
from sp_farms.application.device_analytics_repository import DeviceAnalyticsRepositoryPort
from sp_farms.application.device_pool import DevicePoolRepository
from sp_farms.application.device_profiles import DeviceProfileRepository
from sp_farms.application.jobs import JobRepository
from sp_farms.application.publish_repository import PublishRepositoryPort
from sp_farms.application.qa_profiles import QAProfileRepository
from sp_farms.application.scheduler_repository import ScheduledItemRepositoryPort
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
from sp_farms.domain.analytics import AggregatedMetrics, PostAnalyticsSnapshot
from sp_farms.domain.approvals import (
    ApprovalActionType,
    ApprovalPolicyRule,
    ApprovalRequest,
    ApprovalStatus,
)
from sp_farms.domain.audit import AuditEvent, AuditResult
from sp_farms.domain.automation_builder import (
    AutomationPreset,
    AutomationPresetStep,
    AutomationStepType,
    TargetSelectionRules,
)
from sp_farms.domain.campaigns import (
    ApprovalPolicy,
    Campaign,
    CampaignStatus,
    CampaignTarget,
    RetryPolicy,
    SchedulePolicy,
    SchedulePolicyType,
    TargetStatus,
)
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.content import (
    CaptionTemplate,
    ContentItem,
    ContentStatus,
    HashtagSet,
    MediaAsset,
    MediaMetadata,
    MediaType,
)
from sp_farms.domain.device_analytics import (
    DeviceOperationalEvent,
    OperationalEventType,
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
from sp_farms.domain.publishing import (
    PublishAttempt,
    PublishErrorCode,
    PublishStatus,
)
from sp_farms.domain.qa_profiles import (
    QADeviceAssignment,
    QAProfile,
    QAProfileAudit,
    QATargetPackage,
)
from sp_farms.domain.scheduler import (
    ScheduledItem,
    ScheduledItemStatus,
    SchedulePriority,
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
        providers = tuple(p.strip() for p in self.preferred_provider_order.split(",") if p.strip())
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
    __table_args__ = (
        Index("ix_accounts_display_name", "display_name"),
        Index("ix_accounts_status", "status"),
        Index("ix_accounts_category_id", "category_id"),
    )

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
    __table_args__ = (
        Index("ix_jobs_target", "target_type", "target_id"),
        Index("ix_jobs_state_created", "state", "created_at"),
    )

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


class AuditEventModel(EntityMixin, Base):
    __tablename__ = "audit_events"

    initiator: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (Index("ix_audit_events_target", "target_type", "target_id"),)

    @classmethod
    def from_event(cls, event: AuditEvent) -> "AuditEventModel":
        return cls(
            id=event.id,
            initiator=event.initiator,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            timestamp=_as_utc(event.timestamp),
            result=event.result.value,
            error_code=event.error_code,
            error_message=event.error_message,
            retry_count=event.retry_count,
            job_id=event.job_id,
            details=json.dumps(event.details, ensure_ascii=False),
            created_at=_as_utc(event.timestamp),
            updated_at=_as_utc(event.timestamp),
        )

    def to_event(self) -> AuditEvent:
        parsed_details = {}
        if self.details:
            try:
                parsed_details = json.loads(self.details)
            except Exception:
                parsed_details = {}
        return AuditEvent(
            id=self.id,
            initiator=self.initiator,
            action=self.action,
            target_type=self.target_type,
            target_id=self.target_id,
            timestamp=_as_utc(self.timestamp),
            result=AuditResult(self.result),
            error_code=self.error_code,
            error_message=self.error_message,
            retry_count=self.retry_count,
            job_id=self.job_id,
            details=parsed_details,
        )


class MediaAssetModel(EntityMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (Index("ix_media_assets_type_archived", "media_type", "is_archived"),)

    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    folder: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)

    @classmethod
    def from_asset(cls, asset: MediaAsset) -> "MediaAssetModel":
        return cls(
            id=asset.id,
            file_path=asset.file_path,
            file_name=asset.file_name,
            media_type=asset.media_type.value,
            thumbnail_path=asset.thumbnail_path,
            folder=asset.folder,
            tags_json=json.dumps(list(asset.tags)),
            is_favorite=asset.is_favorite,
            is_archived=asset.is_archived,
            mime_type=asset.metadata.mime_type,
            file_size_bytes=asset.metadata.file_size_bytes,
            sha256_hash=asset.metadata.sha256_hash,
            width=asset.metadata.width,
            height=asset.metadata.height,
            duration_seconds=asset.metadata.duration_seconds,
            aspect_ratio=asset.metadata.aspect_ratio,
            created_at=_as_utc(asset.created_at),
            updated_at=_as_utc(asset.updated_at),
        )

    def to_asset(self) -> MediaAsset:
        try:
            tags = tuple(json.loads(self.tags_json))
        except Exception:
            tags = ()
        meta = MediaMetadata(
            mime_type=self.mime_type,
            file_size_bytes=self.file_size_bytes,
            sha256_hash=self.sha256_hash,
            width=self.width,
            height=self.height,
            duration_seconds=self.duration_seconds,
            aspect_ratio=self.aspect_ratio,
        )
        return MediaAsset(
            id=self.id,
            file_path=self.file_path,
            file_name=self.file_name,
            media_type=MediaType(self.media_type),
            metadata=meta,
            thumbnail_path=self.thumbnail_path,
            folder=self.folder,
            tags=tags,
            is_favorite=self.is_favorite,
            is_archived=self.is_archived,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class CaptionTemplateModel(EntityMixin, Base):
    __tablename__ = "caption_templates"

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @classmethod
    def from_template(cls, template: CaptionTemplate) -> "CaptionTemplateModel":
        return cls(
            id=template.id,
            name=template.name,
            content=template.content,
            variables_json=json.dumps(list(template.variables)),
            tags_json=json.dumps(list(template.tags)),
            is_favorite=template.is_favorite,
            created_at=_as_utc(template.created_at),
            updated_at=_as_utc(template.updated_at),
        )

    def to_template(self) -> CaptionTemplate:
        try:
            vars_list = tuple(json.loads(self.variables_json))
        except Exception:
            vars_list = ()
        try:
            tags = tuple(json.loads(self.tags_json))
        except Exception:
            tags = ()
        return CaptionTemplate(
            id=self.id,
            name=self.name,
            content=self.content,
            variables=vars_list,
            tags=tags,
            is_favorite=self.is_favorite,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class HashtagSetModel(EntityMixin, Base):
    __tablename__ = "hashtag_sets"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @classmethod
    def from_set(cls, hashtag_set: HashtagSet) -> "HashtagSetModel":
        return cls(
            id=hashtag_set.id,
            name=hashtag_set.name,
            hashtags_json=json.dumps(list(hashtag_set.hashtags)),
            category=hashtag_set.category,
            is_favorite=hashtag_set.is_favorite,
            created_at=_as_utc(hashtag_set.created_at),
            updated_at=_as_utc(hashtag_set.updated_at),
        )

    def to_set(self) -> HashtagSet:
        try:
            tags = tuple(json.loads(self.hashtags_json))
        except Exception:
            tags = ()
        return HashtagSet(
            id=self.id,
            name=self.name,
            hashtags=tags,
            category=self.category,
            is_favorite=self.is_favorite,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class ContentItemModel(EntityMixin, Base):
    __tablename__ = "content_items"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_asset_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hashtag_set_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    caption_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    folder: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @classmethod
    def from_item(cls, item: ContentItem) -> "ContentItemModel":
        return cls(
            id=item.id,
            title=item.title,
            body=item.body,
            media_asset_ids_json=json.dumps(list(item.media_asset_ids)),
            hashtag_set_ids_json=json.dumps(list(item.hashtag_set_ids)),
            caption_template_id=item.caption_template_id,
            status=item.status.value,
            folder=item.folder,
            tags_json=json.dumps(list(item.tags)),
            is_favorite=item.is_favorite,
            is_archived=item.is_archived,
            created_at=_as_utc(item.created_at),
            updated_at=_as_utc(item.updated_at),
        )

    def to_item(self) -> ContentItem:
        try:
            media_ids = tuple(json.loads(self.media_asset_ids_json))
        except Exception:
            media_ids = ()
        try:
            hash_ids = tuple(json.loads(self.hashtag_set_ids_json))
        except Exception:
            hash_ids = ()
        try:
            tags = tuple(json.loads(self.tags_json))
        except Exception:
            tags = ()
        return ContentItem(
            id=self.id,
            title=self.title,
            body=self.body,
            media_asset_ids=media_ids,
            hashtag_set_ids=hash_ids,
            caption_template_id=self.caption_template_id,
            status=ContentStatus(self.status),
            folder=self.folder,
            tags=tags,
            is_favorite=self.is_favorite,
            is_archived=self.is_archived,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class CampaignModel(EntityMixin, Base):
    __tablename__ = "campaigns"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    post_type: Mapped[str] = mapped_column(String(20), nullable=False, default="FEED", index=True)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_asset_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    schedule_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    approval_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    retry_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    @classmethod
    def from_campaign(cls, c: Campaign) -> "CampaignModel":
        sched_dict = {
            "policy_type": c.schedule_policy.policy_type.value,
            "scheduled_at": c.schedule_policy.scheduled_at.isoformat()
            if c.schedule_policy.scheduled_at
            else None,
            "stagger_interval_seconds": c.schedule_policy.stagger_interval_seconds,
        }
        retry_dict = {
            "max_attempts": c.retry_policy.max_attempts,
            "backoff_seconds": c.retry_policy.backoff_seconds,
            "allow_retry_on_network_error": c.retry_policy.allow_retry_on_network_error,
        }
        return cls(
            id=c.id,
            title=c.title,
            content_item_id=c.content_item_id,
            post_type=c.post_type.value,
            caption=c.caption,
            media_asset_ids_json=json.dumps(list(c.media_asset_ids)),
            status=c.status.value,
            schedule_policy_json=json.dumps(sched_dict),
            approval_policy=c.approval_policy.value,
            retry_policy_json=json.dumps(retry_dict),
            tags_json=json.dumps(list(c.tags)),
            notes=c.notes,
            created_at=_as_utc(c.created_at),
            updated_at=_as_utc(c.updated_at),
            archived_at=_optional_utc(c.archived_at),
        )

    def to_campaign(self, targets: Sequence[CampaignTarget] = ()) -> Campaign:
        try:
            media_ids = tuple(json.loads(self.media_asset_ids_json))
        except Exception:
            media_ids = ()
        try:
            tags = tuple(json.loads(self.tags_json))
        except Exception:
            tags = ()
        try:
            sched_data = json.loads(self.schedule_policy_json)
            sched_at = (
                datetime.fromisoformat(sched_data["scheduled_at"])
                if sched_data.get("scheduled_at")
                else None
            )
            schedule_policy = SchedulePolicy(
                policy_type=SchedulePolicyType(
                    sched_data.get("policy_type", SchedulePolicyType.IMMEDIATE.value)
                ),
                scheduled_at=_optional_utc(sched_at),
                stagger_interval_seconds=int(sched_data.get("stagger_interval_seconds", 0)),
            )
        except Exception:
            schedule_policy = SchedulePolicy()

        try:
            retry_data = json.loads(self.retry_policy_json)
            retry_policy = RetryPolicy(
                max_attempts=int(retry_data.get("max_attempts", 3)),
                backoff_seconds=int(retry_data.get("backoff_seconds", 60)),
                allow_retry_on_network_error=bool(
                    retry_data.get("allow_retry_on_network_error", True)
                ),
            )
        except Exception:
            retry_policy = RetryPolicy()

        return Campaign(
            id=self.id,
            title=self.title,
            content_item_id=self.content_item_id,
            post_type=PostType(self.post_type),
            caption=self.caption,
            media_asset_ids=media_ids,
            status=CampaignStatus(self.status),
            schedule_policy=schedule_policy,
            approval_policy=ApprovalPolicy(self.approval_policy),
            retry_policy=retry_policy,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
            targets=tuple(targets),
            tags=tags,
            notes=self.notes,
            archived_at=_optional_utc(self.archived_at),
        )


class CampaignTargetModel(EntityMixin, Base):
    __tablename__ = "campaign_targets"

    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    destination_type: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_id: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_post_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_target(cls, t: CampaignTarget) -> "CampaignTargetModel":
        return cls(
            id=t.id,
            campaign_id=t.campaign_id,
            destination_type=t.destination_type.value,
            destination_id=t.destination_id,
            destination_name=t.destination_name,
            status=t.status.value,
            attempt_count=t.attempt_count,
            published_post_id=t.published_post_id,
            error_message=t.error_message,
            executed_at=_optional_utc(t.executed_at),
            scheduled_at=_optional_utc(t.scheduled_at),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def to_target(self) -> CampaignTarget:
        return CampaignTarget(
            id=self.id,
            campaign_id=self.campaign_id,
            destination_type=PublishDestinationType(self.destination_type),
            destination_id=self.destination_id,
            destination_name=self.destination_name,
            status=TargetStatus(self.status),
            attempt_count=self.attempt_count,
            published_post_id=self.published_post_id,
            error_message=self.error_message,
            executed_at=_optional_utc(self.executed_at),
            scheduled_at=_optional_utc(self.scheduled_at),
        )


class ScheduledItemModel(EntityMixin, Base):
    __tablename__ = "scheduled_items"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    content_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    destination_type: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    destination_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    post_type: Mapped[str] = mapped_column(String(20), nullable=False, default="FEED")
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_asset_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    timezone_name: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    @classmethod
    def from_item(cls, item: ScheduledItem) -> "ScheduledItemModel":
        return cls(
            id=item.id,
            title=item.title,
            campaign_id=item.campaign_id,
            content_item_id=item.content_item_id,
            destination_type=item.destination_type.value,
            destination_id=item.destination_id,
            destination_name=item.destination_name,
            scheduled_at=_as_utc(item.scheduled_at),
            post_type=item.post_type.value,
            caption=item.caption,
            media_asset_ids_json=json.dumps(list(item.media_asset_ids)),
            status=item.status.value,
            priority=item.priority.value,
            timezone_name=item.timezone_name,
            retry_count=item.retry_count,
            max_retries=item.max_retries,
            error_message=item.error_message,
            executed_at=_optional_utc(item.executed_at),
            tags_json=json.dumps(list(item.tags)),
            created_at=_as_utc(item.created_at),
            updated_at=_as_utc(item.updated_at),
        )

    def to_item(self) -> ScheduledItem:
        try:
            media_ids = tuple(json.loads(self.media_asset_ids_json))
        except Exception:
            media_ids = ()
        try:
            tags = tuple(json.loads(self.tags_json))
        except Exception:
            tags = ()

        return ScheduledItem(
            id=self.id,
            title=self.title,
            campaign_id=self.campaign_id,
            content_item_id=self.content_item_id,
            destination_type=PublishDestinationType(self.destination_type),
            destination_id=self.destination_id,
            destination_name=self.destination_name,
            scheduled_at=_as_utc(self.scheduled_at),
            post_type=PostType(self.post_type),
            caption=self.caption,
            media_asset_ids=media_ids,
            status=ScheduledItemStatus(self.status),
            priority=SchedulePriority(self.priority),
            timezone_name=self.timezone_name,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            error_message=self.error_message,
            executed_at=_optional_utc(self.executed_at),
            tags=tags,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
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

    def list_accounts(
        self, include_archived: bool = False, limit: int | None = None, offset: int = 0
    ) -> Sequence[Account]:
        query = self._session.query(AccountModel)
        if not include_archived:
            query = query.filter(AccountModel.archived_at.is_(None))
        query = query.order_by(AccountModel.display_name)
        if offset > 0:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        models = query.all()
        if not models:
            return ()

        account_ids = [m.id for m in models]
        tags_by_account: dict[str, list[str]] = {aid: [] for aid in account_ids}
        devices_by_account: dict[str, AccountDeviceAssignment] = {}

        chunk_size = 500
        for i in range(0, len(account_ids), chunk_size):
            chunk = account_ids[i : i + chunk_size]
            tag_rows = (
                self._session.query(
                    AccountTagAssignmentModel.account_id, AccountTagAssignmentModel.tag_id
                )
                .filter(AccountTagAssignmentModel.account_id.in_(chunk))
                .order_by(AccountTagAssignmentModel.tag_id)
                .all()
            )
            for acc_id, tag_id in tag_rows:
                tags_by_account[acc_id].append(tag_id)

            dev_rows = (
                self._session.query(AccountDeviceAssignmentModel)
                .filter(AccountDeviceAssignmentModel.account_id.in_(chunk))
                .all()
            )
            for dev in dev_rows:
                devices_by_account[dev.account_id] = AccountDeviceAssignment(
                    dev.account_id, dev.provider, dev.external_id
                )

        result: list[Account] = []
        for model in models:
            result.append(
                Account(
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
                    tag_ids=tuple(tags_by_account.get(model.id, ())),
                    notes=model.notes,
                    assigned_device=devices_by_account.get(model.id),
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
            )
        return tuple(result)

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

    def save_accounts_batch(self, accounts: Sequence[Account]) -> None:
        session = self._session
        for account in accounts:
            model = session.get(AccountModel, account.id)
            values = _account_values(account)
            if model is None:
                session.add(AccountModel(**values))
            else:
                for key, value in values.items():
                    setattr(model, key, value)
        session.flush()

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
            self._session.query(AccountWorkspaceLockModel).filter_by(device_key=device_key).first()
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

    def list_snapshots_for_account(self, account_id: str) -> Sequence[SnapshotMetadataRecord]:
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

    def update_snapshot_last_restored(self, snapshot_id: str, restored_at: datetime) -> None:
        model = self._session.get(AccountWorkspaceSnapshotModel, snapshot_id)
        if model is not None:
            model.last_restored_at = _as_utc(restored_at)
            self._session.flush()

    def get_policy(self, name: str) -> DevicePoolPolicy | None:
        model = self._session.query(DevicePoolPolicyModel).filter_by(name=name).one_or_none()
        return model.to_policy() if model else None

    def get_active_policy(self) -> DevicePoolPolicy | None:
        model = self._session.query(DevicePoolPolicyModel).filter_by(is_active=True).first()
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


class SqlAlchemyAuditRepository(AuditRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyAuditRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def add(self, event: AuditEvent) -> None:
        session = self._session
        session.add(AuditEventModel.from_event(event))
        session.flush()

    def get(self, event_id: str) -> AuditEvent | None:
        model = self._session.get(AuditEventModel, event_id)
        return model.to_event() if model else None

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        result: AuditResult | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        action: str | None = None,
    ) -> Sequence[AuditEvent]:
        query = self._session.query(AuditEventModel)
        if result is not None:
            query = query.filter(AuditEventModel.result == result.value)
        if target_type is not None:
            query = query.filter(AuditEventModel.target_type == target_type)
        if target_id is not None:
            query = query.filter(AuditEventModel.target_id == target_id)
        if action is not None:
            query = query.filter(AuditEventModel.action == action)
        models = query.order_by(AuditEventModel.timestamp.desc()).offset(offset).limit(limit).all()
        return tuple(m.to_event() for m in models)

    def list_errors(
        self,
        limit: int = 100,
        offset: int = 0,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> Sequence[AuditEvent]:
        query = self._session.query(AuditEventModel).filter(
            AuditEventModel.result == AuditResult.FAILURE.value
        )
        if target_type is not None:
            query = query.filter(AuditEventModel.target_type == target_type)
        if target_id is not None:
            query = query.filter(AuditEventModel.target_id == target_id)
        models = query.order_by(AuditEventModel.timestamp.desc()).offset(offset).limit(limit).all()
        return tuple(m.to_event() for m in models)

    def prune(self, older_than: datetime) -> int:
        utc_cutoff = _as_utc(older_than)
        deleted_count = (
            self._session.query(AuditEventModel)
            .filter(AuditEventModel.timestamp < utc_cutoff)
            .delete(synchronize_session=False)
        )
        self._session.flush()
        return int(deleted_count)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemyContentRepository(ContentRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyContentRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    # Media Assets
    def add_asset(self, asset: MediaAsset) -> None:
        session = self._session
        session.add(MediaAssetModel.from_asset(asset))
        session.flush()

    def update_asset(self, asset: MediaAsset) -> None:
        session = self._session
        model = session.get(MediaAssetModel, asset.id)
        if model is not None:
            model.file_path = asset.file_path
            model.file_name = asset.file_name
            model.media_type = asset.media_type.value
            model.thumbnail_path = asset.thumbnail_path
            model.folder = asset.folder
            model.tags_json = json.dumps(list(asset.tags))
            model.is_favorite = asset.is_favorite
            model.is_archived = asset.is_archived
            model.mime_type = asset.metadata.mime_type
            model.file_size_bytes = asset.metadata.file_size_bytes
            model.sha256_hash = asset.metadata.sha256_hash
            model.width = asset.metadata.width
            model.height = asset.metadata.height
            model.duration_seconds = asset.metadata.duration_seconds
            model.aspect_ratio = asset.metadata.aspect_ratio
            model.updated_at = _as_utc(asset.updated_at)
            session.flush()

    def get_asset(self, asset_id: str) -> MediaAsset | None:
        model = self._session.get(MediaAssetModel, asset_id)
        return model.to_asset() if model else None

    def get_asset_by_hash(self, sha256_hash: str) -> MediaAsset | None:
        model = (
            self._session.query(MediaAssetModel)
            .filter(MediaAssetModel.sha256_hash == sha256_hash)
            .first()
        )
        return model.to_asset() if model else None

    def list_assets(
        self,
        folder: str | None = None,
        media_type: MediaType | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = False,
        tag: str | None = None,
        search_query: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[MediaAsset]:
        query = self._session.query(MediaAssetModel)
        if folder is not None:
            query = query.filter(MediaAssetModel.folder == folder)
        if media_type is not None:
            query = query.filter(MediaAssetModel.media_type == media_type.value)
        if is_favorite is not None:
            query = query.filter(MediaAssetModel.is_favorite == is_favorite)
        if is_archived is not None:
            query = query.filter(MediaAssetModel.is_archived == is_archived)
        if tag is not None:
            # Simple JSON contains query
            query = query.filter(MediaAssetModel.tags_json.contains(f'"{tag}"'))
        if search_query:
            pattern = f"%{search_query}%"
            query = query.filter(
                (MediaAssetModel.file_name.ilike(pattern))
                | (MediaAssetModel.tags_json.ilike(pattern))
            )
        models = query.order_by(MediaAssetModel.created_at.desc()).offset(offset).limit(limit).all()
        return tuple(m.to_asset() for m in models)

    def delete_asset(self, asset_id: str) -> bool:
        model = self._session.get(MediaAssetModel, asset_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    def count_assets(
        self,
        folder: str | None = None,
        is_archived: bool | None = False,
    ) -> int:
        query = self._session.query(MediaAssetModel)
        if folder is not None:
            query = query.filter(MediaAssetModel.folder == folder)
        if is_archived is not None:
            query = query.filter(MediaAssetModel.is_archived == is_archived)
        return int(query.count())

    def list_folders(self) -> Sequence[str]:
        rows = (
            self._session.query(MediaAssetModel.folder)
            .distinct()
            .order_by(MediaAssetModel.folder)
            .all()
        )
        return tuple(r[0] for r in rows if r[0])

    # Caption Templates
    def add_caption_template(self, template: CaptionTemplate) -> None:
        session = self._session
        session.add(CaptionTemplateModel.from_template(template))
        session.flush()

    def update_caption_template(self, template: CaptionTemplate) -> None:
        session = self._session
        model = session.get(CaptionTemplateModel, template.id)
        if model is not None:
            model.name = template.name
            model.content = template.content
            model.variables_json = json.dumps(list(template.variables))
            model.tags_json = json.dumps(list(template.tags))
            model.is_favorite = template.is_favorite
            model.updated_at = _as_utc(template.updated_at)
            session.flush()

    def get_caption_template(self, template_id: str) -> CaptionTemplate | None:
        model = self._session.get(CaptionTemplateModel, template_id)
        return model.to_template() if model else None

    def list_caption_templates(
        self,
        is_favorite: bool | None = None,
        tag: str | None = None,
        search_query: str | None = None,
    ) -> Sequence[CaptionTemplate]:
        query = self._session.query(CaptionTemplateModel)
        if is_favorite is not None:
            query = query.filter(CaptionTemplateModel.is_favorite == is_favorite)
        if tag is not None:
            query = query.filter(CaptionTemplateModel.tags_json.contains(f'"{tag}"'))
        if search_query:
            pattern = f"%{search_query}%"
            query = query.filter(
                (CaptionTemplateModel.name.ilike(pattern))
                | (CaptionTemplateModel.content.ilike(pattern))
            )
        models = query.order_by(CaptionTemplateModel.name.asc()).all()
        return tuple(m.to_template() for m in models)

    def delete_caption_template(self, template_id: str) -> bool:
        model = self._session.get(CaptionTemplateModel, template_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    # Hashtag Sets
    def add_hashtag_set(self, hashtag_set: HashtagSet) -> None:
        session = self._session
        session.add(HashtagSetModel.from_set(hashtag_set))
        session.flush()

    def update_hashtag_set(self, hashtag_set: HashtagSet) -> None:
        session = self._session
        model = session.get(HashtagSetModel, hashtag_set.id)
        if model is not None:
            model.name = hashtag_set.name
            model.hashtags_json = json.dumps(list(hashtag_set.hashtags))
            model.category = hashtag_set.category
            model.is_favorite = hashtag_set.is_favorite
            model.updated_at = _as_utc(hashtag_set.updated_at)
            session.flush()

    def get_hashtag_set(self, set_id: str) -> HashtagSet | None:
        model = self._session.get(HashtagSetModel, set_id)
        return model.to_set() if model else None

    def list_hashtag_sets(
        self,
        category: str | None = None,
        is_favorite: bool | None = None,
        search_query: str | None = None,
    ) -> Sequence[HashtagSet]:
        query = self._session.query(HashtagSetModel)
        if category is not None:
            query = query.filter(HashtagSetModel.category == category)
        if is_favorite is not None:
            query = query.filter(HashtagSetModel.is_favorite == is_favorite)
        if search_query:
            pattern = f"%{search_query}%"
            query = query.filter(
                (HashtagSetModel.name.ilike(pattern))
                | (HashtagSetModel.hashtags_json.ilike(pattern))
            )
        models = query.order_by(HashtagSetModel.name.asc()).all()
        return tuple(m.to_set() for m in models)

    def delete_hashtag_set(self, set_id: str) -> bool:
        model = self._session.get(HashtagSetModel, set_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    # Content Items
    def add_content_item(self, item: ContentItem) -> None:
        session = self._session
        session.add(ContentItemModel.from_item(item))
        session.flush()

    def update_content_item(self, item: ContentItem) -> None:
        session = self._session
        model = session.get(ContentItemModel, item.id)
        if model is not None:
            model.title = item.title
            model.body = item.body
            model.media_asset_ids_json = json.dumps(list(item.media_asset_ids))
            model.hashtag_set_ids_json = json.dumps(list(item.hashtag_set_ids))
            model.caption_template_id = item.caption_template_id
            model.status = item.status.value
            model.folder = item.folder
            model.tags_json = json.dumps(list(item.tags))
            model.is_favorite = item.is_favorite
            model.is_archived = item.is_archived
            model.updated_at = _as_utc(item.updated_at)
            session.flush()

    def get_content_item(self, item_id: str) -> ContentItem | None:
        model = self._session.get(ContentItemModel, item_id)
        return model.to_item() if model else None

    def list_content_items(
        self,
        folder: str | None = None,
        status: str | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = False,
        search_query: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[ContentItem]:
        query = self._session.query(ContentItemModel)
        if folder is not None:
            query = query.filter(ContentItemModel.folder == folder)
        if status is not None:
            query = query.filter(ContentItemModel.status == status)
        if is_favorite is not None:
            query = query.filter(ContentItemModel.is_favorite == is_favorite)
        if is_archived is not None:
            query = query.filter(ContentItemModel.is_archived == is_archived)
        if search_query:
            pattern = f"%{search_query}%"
            query = query.filter(
                (ContentItemModel.title.ilike(pattern))
                | (ContentItemModel.body.ilike(pattern))
                | (ContentItemModel.tags_json.ilike(pattern))
            )
        models = (
            query.order_by(ContentItemModel.created_at.desc()).offset(offset).limit(limit).all()
        )
        return tuple(m.to_item() for m in models)

    def delete_content_item(self, item_id: str) -> bool:
        model = self._session.get(ContentItemModel, item_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemyCampaignRepository(CampaignRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyCampaignRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def save_campaign(self, campaign: Campaign) -> Campaign:
        session = self._session
        model = session.get(CampaignModel, campaign.id)
        if model is None:
            model = CampaignModel.from_campaign(campaign)
            session.add(model)
        else:
            model.title = campaign.title
            model.content_item_id = campaign.content_item_id
            model.post_type = campaign.post_type.value
            model.caption = campaign.caption
            model.media_asset_ids_json = json.dumps(list(campaign.media_asset_ids))
            model.status = campaign.status.value
            sched_dict = {
                "policy_type": campaign.schedule_policy.policy_type.value,
                "scheduled_at": campaign.schedule_policy.scheduled_at.isoformat()
                if campaign.schedule_policy.scheduled_at
                else None,
                "stagger_interval_seconds": campaign.schedule_policy.stagger_interval_seconds,
            }
            model.schedule_policy_json = json.dumps(sched_dict)
            model.approval_policy = campaign.approval_policy.value
            retry_dict = {
                "max_attempts": campaign.retry_policy.max_attempts,
                "backoff_seconds": campaign.retry_policy.backoff_seconds,
                "allow_retry_on_network_error": campaign.retry_policy.allow_retry_on_network_error,
            }
            model.retry_policy_json = json.dumps(retry_dict)
            model.tags_json = json.dumps(list(campaign.tags))
            model.notes = campaign.notes
            model.updated_at = _as_utc(campaign.updated_at)
            model.archived_at = _optional_utc(campaign.archived_at)
        session.flush()

        # Update targets
        for target in campaign.targets:
            self.save_target(target)

        return self.get_campaign(campaign.id) or campaign

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        model = self._session.get(CampaignModel, campaign_id)
        if model is None:
            return None
        targets = self.list_targets(campaign_id)
        return model.to_campaign(targets)

    def list_campaigns(
        self,
        status: CampaignStatus | None = None,
        search: str | None = None,
        include_archived: bool = False,
    ) -> Sequence[Campaign]:
        query = self._session.query(CampaignModel)
        if not include_archived:
            query = query.filter(CampaignModel.status != CampaignStatus.ARCHIVED.value)
        if status is not None:
            query = query.filter(CampaignModel.status == status.value)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                (CampaignModel.title.ilike(pattern))
                | (CampaignModel.caption.ilike(pattern))
                | (CampaignModel.tags_json.ilike(pattern))
            )
        models = query.order_by(CampaignModel.created_at.desc()).all()
        result: list[Campaign] = []
        for m in models:
            targets = self.list_targets(m.id)
            result.append(m.to_campaign(targets))
        return tuple(result)

    def delete_campaign(self, campaign_id: str) -> bool:
        model = self._session.get(CampaignModel, campaign_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    def save_target(self, target: CampaignTarget) -> CampaignTarget:
        session = self._session
        model = session.get(CampaignTargetModel, target.id)
        if model is None:
            model = CampaignTargetModel.from_target(target)
            session.add(model)
        else:
            model.destination_type = target.destination_type.value
            model.destination_id = target.destination_id
            model.destination_name = target.destination_name
            model.status = target.status.value
            model.attempt_count = target.attempt_count
            model.published_post_id = target.published_post_id
            model.error_message = target.error_message
            model.executed_at = _optional_utc(target.executed_at)
            model.scheduled_at = _optional_utc(target.scheduled_at)
            model.updated_at = datetime.now(UTC)
        session.flush()
        return model.to_target()

    def get_target(self, target_id: str) -> CampaignTarget | None:
        model = self._session.get(CampaignTargetModel, target_id)
        return model.to_target() if model else None

    def list_targets(self, campaign_id: str) -> Sequence[CampaignTarget]:
        models = (
            self._session.query(CampaignTargetModel)
            .filter_by(campaign_id=campaign_id)
            .order_by(CampaignTargetModel.created_at.asc())
            .all()
        )
        return tuple(m.to_target() for m in models)

    def delete_target(self, target_id: str) -> bool:
        model = self._session.get(CampaignTargetModel, target_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class SqlAlchemySchedulerRepository(ScheduledItemRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemySchedulerRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def save_item(self, item: ScheduledItem) -> ScheduledItem:
        session = self._session
        model = session.get(ScheduledItemModel, item.id)
        if model is None:
            model = ScheduledItemModel.from_item(item)
            session.add(model)
        else:
            model.title = item.title
            model.campaign_id = item.campaign_id
            model.content_item_id = item.content_item_id
            model.destination_type = item.destination_type.value
            model.destination_id = item.destination_id
            model.destination_name = item.destination_name
            model.scheduled_at = _as_utc(item.scheduled_at)
            model.post_type = item.post_type.value
            model.caption = item.caption
            model.media_asset_ids_json = json.dumps(list(item.media_asset_ids))
            model.status = item.status.value
            model.priority = item.priority.value
            model.timezone_name = item.timezone_name
            model.retry_count = item.retry_count
            model.max_retries = item.max_retries
            model.error_message = item.error_message
            model.executed_at = _optional_utc(item.executed_at)
            model.tags_json = json.dumps(list(item.tags))
            model.updated_at = datetime.now(UTC)
        session.flush()
        return model.to_item()

    def get_item(self, item_id: str) -> ScheduledItem | None:
        model = self._session.get(ScheduledItemModel, item_id)
        return model.to_item() if model else None

    def list_items(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        destination_id: str | None = None,
        status: ScheduledItemStatus | None = None,
        limit: int = 200,
    ) -> Sequence[ScheduledItem]:
        query = self._session.query(ScheduledItemModel)
        if from_time is not None:
            query = query.filter(ScheduledItemModel.scheduled_at >= _as_utc(from_time))
        if to_time is not None:
            query = query.filter(ScheduledItemModel.scheduled_at <= _as_utc(to_time))
        if destination_id is not None:
            query = query.filter(ScheduledItemModel.destination_id == destination_id)
        if status is not None:
            query = query.filter(ScheduledItemModel.status == status.value)
        models = query.order_by(ScheduledItemModel.scheduled_at.asc()).limit(limit).all()
        return tuple(m.to_item() for m in models)

    def delete_item(self, item_id: str) -> bool:
        model = self._session.get(ScheduledItemModel, item_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    def list_due_items(self, now: datetime, limit: int = 50) -> Sequence[ScheduledItem]:
        utc_now = _as_utc(now)
        models = (
            self._session.query(ScheduledItemModel)
            .filter(
                ScheduledItemModel.status == ScheduledItemStatus.QUEUED.value,
                ScheduledItemModel.scheduled_at <= utc_now,
            )
            .order_by(ScheduledItemModel.scheduled_at.asc())
            .limit(limit)
            .all()
        )
        return tuple(m.to_item() for m in models)

    def list_missed_items(
        self, now: datetime, grace_period_minutes: int = 15
    ) -> Sequence[ScheduledItem]:
        cutoff = _as_utc(now) - timedelta(minutes=grace_period_minutes)
        models = (
            self._session.query(ScheduledItemModel)
            .filter(
                ScheduledItemModel.status == ScheduledItemStatus.QUEUED.value,
                ScheduledItemModel.scheduled_at < cutoff,
            )
            .order_by(ScheduledItemModel.scheduled_at.asc())
            .all()
        )
        return tuple(m.to_item() for m in models)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class ApprovalRequestModel(Base, EntityMixin):
    __tablename__ = "approval_requests"

    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_request(cls, request: ApprovalRequest) -> "ApprovalRequestModel":
        return cls(
            id=request.id,
            action_type=request.action_type.value,
            target_id=request.target_id,
            target_name=request.target_name,
            summary=request.summary,
            payload=json.dumps(dict(request.payload)),
            campaign_id=request.campaign_id,
            job_id=request.job_id,
            status=request.status.value,
            requested_by=request.requested_by,
            reviewed_by=request.reviewed_by,
            review_notes=request.review_notes,
            expires_at=_optional_utc(request.expires_at),
            decided_at=_optional_utc(request.decided_at),
            created_at=_as_utc(request.created_at),
            updated_at=_as_utc(request.updated_at),
        )

    def to_request(self) -> ApprovalRequest:
        try:
            payload = json.loads(self.payload) if self.payload else {}
        except Exception:
            payload = {}
        return ApprovalRequest(
            id=self.id,
            action_type=ApprovalActionType(self.action_type),
            target_id=self.target_id,
            target_name=self.target_name,
            summary=self.summary,
            payload=payload,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            status=ApprovalStatus(self.status),
            requested_by=self.requested_by,
            reviewed_by=self.reviewed_by,
            review_notes=self.review_notes,
            expires_at=_optional_utc(self.expires_at),
            decided_at=_optional_utc(self.decided_at),
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class ApprovalPolicyRuleModel(Base, EntityMixin):
    __tablename__ = "approval_policy_rules"

    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_pattern: Mapped[str] = mapped_column(String(255), nullable=False, default="*")
    require_reason: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_pending_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @classmethod
    def from_rule(cls, rule: ApprovalPolicyRule) -> "ApprovalPolicyRuleModel":
        now = datetime.now(UTC)
        return cls(
            id=rule.id,
            action_type=rule.action_type.value,
            target_pattern=rule.target_pattern,
            require_reason=rule.require_reason,
            max_pending_hours=rule.max_pending_hours,
            enabled=rule.enabled,
            created_at=now,
            updated_at=now,
        )

    def to_rule(self) -> ApprovalPolicyRule:
        return ApprovalPolicyRule(
            id=self.id,
            action_type=ApprovalActionType(self.action_type),
            target_pattern=self.target_pattern,
            require_reason=self.require_reason,
            max_pending_hours=self.max_pending_hours,
            enabled=self.enabled,
        )


class SqlAlchemyApprovalRepository(ApprovalRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyApprovalRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def save_request(self, request: ApprovalRequest) -> ApprovalRequest:
        model = self._session.get(ApprovalRequestModel, request.id)
        if model is None:
            model = ApprovalRequestModel.from_request(request)
            self._session.add(model)
        else:
            model.action_type = request.action_type.value
            model.target_id = request.target_id
            model.target_name = request.target_name
            model.summary = request.summary
            model.payload = json.dumps(dict(request.payload))
            model.campaign_id = request.campaign_id
            model.job_id = request.job_id
            model.status = request.status.value
            model.requested_by = request.requested_by
            model.reviewed_by = request.reviewed_by
            model.review_notes = request.review_notes
            model.expires_at = _optional_utc(request.expires_at)
            model.decided_at = _optional_utc(request.decided_at)
            model.updated_at = _as_utc(request.updated_at)
        self._session.flush()
        return model.to_request()

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        model = self._session.get(ApprovalRequestModel, request_id)
        return model.to_request() if model is not None else None

    def list_requests(
        self,
        status: ApprovalStatus | None = None,
        action_type: ApprovalActionType | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[ApprovalRequest]:
        query = self._session.query(ApprovalRequestModel)
        if status is not None:
            query = query.filter(ApprovalRequestModel.status == status.value)
        if action_type is not None:
            query = query.filter(ApprovalRequestModel.action_type == action_type.value)
        if campaign_id is not None:
            query = query.filter(ApprovalRequestModel.campaign_id == campaign_id)
        if job_id is not None:
            query = query.filter(ApprovalRequestModel.job_id == job_id)
        models = (
            query.order_by(ApprovalRequestModel.created_at.desc()).offset(offset).limit(limit).all()
        )
        return tuple(m.to_request() for m in models)

    def delete_request(self, request_id: str) -> None:
        model = self._session.get(ApprovalRequestModel, request_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def save_policy_rule(self, rule: ApprovalPolicyRule) -> ApprovalPolicyRule:
        model = self._session.get(ApprovalPolicyRuleModel, rule.id)
        if model is None:
            model = ApprovalPolicyRuleModel.from_rule(rule)
            self._session.add(model)
        else:
            model.action_type = rule.action_type.value
            model.target_pattern = rule.target_pattern
            model.require_reason = rule.require_reason
            model.max_pending_hours = rule.max_pending_hours
            model.enabled = rule.enabled
            model.updated_at = _as_utc(datetime.now(UTC))
        self._session.flush()
        return model.to_rule()

    def list_policy_rules(self) -> Sequence[ApprovalPolicyRule]:
        models = (
            self._session.query(ApprovalPolicyRuleModel)
            .order_by(ApprovalPolicyRuleModel.action_type.asc())
            .all()
        )
        return tuple(m.to_rule() for m in models)

    def delete_policy_rule(self, rule_id: str) -> None:
        model = self._session.get(ApprovalPolicyRuleModel, rule_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class PublishAttemptModel(Base):
    __tablename__ = "publish_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    destination_type: Mapped[str] = mapped_column(String(32), nullable=False)
    destination_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination_name: Mapped[str] = mapped_column(String(255), nullable=False)
    post_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    method_used: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    scheduled_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_attempt(cls, attempt: PublishAttempt) -> "PublishAttemptModel":
        return cls(
            id=attempt.id,
            destination_type=attempt.destination_type.value,
            destination_id=attempt.destination_id,
            destination_name=attempt.destination_name,
            post_type=attempt.post_type.value,
            payload=json.dumps(dict(attempt.payload)),
            status=attempt.status.value,
            method_used=attempt.method_used.value,
            scheduled_item_id=attempt.scheduled_item_id,
            campaign_id=attempt.campaign_id,
            job_id=attempt.job_id,
            external_post_id=attempt.external_post_id,
            error_code=attempt.error_code.value if attempt.error_code else None,
            error_message=attempt.error_message,
            is_retryable=attempt.is_retryable,
            retry_count=attempt.retry_count,
            duration_ms=attempt.duration_ms,
            idempotency_key=attempt.idempotency_key,
            created_at=_as_utc(attempt.created_at),
            updated_at=_as_utc(attempt.updated_at),
        )

    def to_attempt(self) -> PublishAttempt:
        try:
            dest_type = PublishDestinationType(self.destination_type)
        except Exception:
            dest_type = PublishDestinationType.PAGE

        try:
            p_type = PostType(self.post_type)
        except Exception:
            p_type = PostType.FEED

        try:
            stat = PublishStatus(self.status)
        except Exception:
            stat = PublishStatus.FAILED

        try:
            from sp_farms.domain.publishing import PublishMethod

            method_u = PublishMethod(self.method_used)
        except Exception:
            method_u = PublishMethod.API

        err_code = None
        if self.error_code:
            try:
                err_code = PublishErrorCode(self.error_code)
            except Exception:
                err_code = PublishErrorCode.UNKNOWN

        try:
            payload_dict = json.loads(self.payload)
        except Exception:
            payload_dict = {}

        return PublishAttempt(
            id=self.id,
            destination_type=dest_type,
            destination_id=self.destination_id,
            destination_name=self.destination_name,
            post_type=p_type,
            payload=payload_dict,
            status=stat,
            method_used=method_u,
            scheduled_item_id=self.scheduled_item_id,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            external_post_id=self.external_post_id,
            error_code=err_code,
            error_message=self.error_message,
            is_retryable=self.is_retryable,
            retry_count=self.retry_count,
            duration_ms=self.duration_ms,
            idempotency_key=self.idempotency_key,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class SqlAlchemyPublishRepository(PublishRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyPublishRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def save(self, attempt: PublishAttempt) -> None:
        model = self._session.get(PublishAttemptModel, attempt.id)
        if model is None:
            model = PublishAttemptModel.from_attempt(attempt)
            self._session.add(model)
        else:
            model.destination_type = attempt.destination_type.value
            model.destination_id = attempt.destination_id
            model.destination_name = attempt.destination_name
            model.post_type = attempt.post_type.value
            model.payload = json.dumps(dict(attempt.payload))
            model.status = attempt.status.value
            model.scheduled_item_id = attempt.scheduled_item_id
            model.campaign_id = attempt.campaign_id
            model.job_id = attempt.job_id
            model.external_post_id = attempt.external_post_id
            model.error_code = attempt.error_code.value if attempt.error_code else None
            model.error_message = attempt.error_message
            model.is_retryable = attempt.is_retryable
            model.retry_count = attempt.retry_count
            model.duration_ms = attempt.duration_ms
            model.idempotency_key = attempt.idempotency_key
            model.updated_at = _as_utc(attempt.updated_at)
        self._session.flush()

    def get(self, attempt_id: str) -> PublishAttempt | None:
        model = self._session.get(PublishAttemptModel, attempt_id)
        return model.to_attempt() if model is not None else None

    def get_by_idempotency_key(self, key: str) -> PublishAttempt | None:
        model = (
            self._session.query(PublishAttemptModel).filter_by(idempotency_key=key).one_or_none()
        )
        return model.to_attempt() if model is not None else None

    def list_recent(
        self,
        limit: int = 50,
        status: PublishStatus | None = None,
        destination_id: str | None = None,
        campaign_id: str | None = None,
    ) -> Sequence[PublishAttempt]:
        query = self._session.query(PublishAttemptModel)
        if status is not None:
            query = query.filter(PublishAttemptModel.status == status.value)
        if destination_id is not None:
            query = query.filter(PublishAttemptModel.destination_id == destination_id)
        if campaign_id is not None:
            query = query.filter(PublishAttemptModel.campaign_id == campaign_id)
        models = query.order_by(PublishAttemptModel.created_at.desc()).limit(limit).all()
        return tuple(m.to_attempt() for m in models)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class AnalyticsSnapshotModel(Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_post_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination_name: Mapped[str] = mapped_column(String(255), nullable=False)
    post_type: Mapped[str] = mapped_column(String(32), nullable=False)
    publish_attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shares_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    views_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reach_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    @classmethod
    def from_snapshot(cls, snapshot: PostAnalyticsSnapshot) -> "AnalyticsSnapshotModel":
        now = datetime.now(UTC)
        return cls(
            id=snapshot.id,
            external_post_id=snapshot.external_post_id,
            account_id=snapshot.account_id,
            destination_id=snapshot.destination_id,
            destination_name=snapshot.destination_name,
            post_type=snapshot.post_type.value,
            publish_attempt_id=snapshot.publish_attempt_id,
            likes_count=snapshot.likes_count,
            comments_count=snapshot.comments_count,
            shares_count=snapshot.shares_count,
            views_count=snapshot.views_count,
            impressions_count=snapshot.impressions_count,
            reach_count=snapshot.reach_count,
            synced_at=_as_utc(snapshot.synced_at),
            created_at=now,
            updated_at=now,
        )

    def to_snapshot(self) -> PostAnalyticsSnapshot:
        try:
            p_type = PostType(self.post_type)
        except Exception:
            p_type = PostType.FEED
        return PostAnalyticsSnapshot(
            id=self.id,
            external_post_id=self.external_post_id,
            account_id=self.account_id,
            destination_id=self.destination_id,
            destination_name=self.destination_name,
            post_type=p_type,
            publish_attempt_id=self.publish_attempt_id,
            likes_count=self.likes_count,
            comments_count=self.comments_count,
            shares_count=self.shares_count,
            views_count=self.views_count,
            impressions_count=self.impressions_count,
            reach_count=self.reach_count,
            synced_at=_as_utc(self.synced_at),
        )


class SqlAlchemyAnalyticsRepository(AnalyticsRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyAnalyticsRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def save_snapshot(self, snapshot: PostAnalyticsSnapshot) -> None:
        model = self._session.get(AnalyticsSnapshotModel, snapshot.id)
        if model is None:
            model = AnalyticsSnapshotModel.from_snapshot(snapshot)
            self._session.add(model)
        else:
            model.external_post_id = snapshot.external_post_id
            model.account_id = snapshot.account_id
            model.destination_id = snapshot.destination_id
            model.destination_name = snapshot.destination_name
            model.post_type = snapshot.post_type.value
            model.publish_attempt_id = snapshot.publish_attempt_id
            model.likes_count = snapshot.likes_count
            model.comments_count = snapshot.comments_count
            model.shares_count = snapshot.shares_count
            model.views_count = snapshot.views_count
            model.impressions_count = snapshot.impressions_count
            model.reach_count = snapshot.reach_count
            model.synced_at = _as_utc(snapshot.synced_at)
        self._session.flush()

    def get_snapshot(self, snapshot_id: str) -> PostAnalyticsSnapshot | None:
        model = self._session.get(AnalyticsSnapshotModel, snapshot_id)
        return model.to_snapshot() if model is not None else None

    def get_latest_by_post(self, external_post_id: str) -> PostAnalyticsSnapshot | None:
        model = (
            self._session.query(AnalyticsSnapshotModel)
            .filter_by(external_post_id=external_post_id)
            .order_by(AnalyticsSnapshotModel.synced_at.desc())
            .first()
        )
        return model.to_snapshot() if model is not None else None

    def list_snapshots(
        self,
        destination_id: str | None = None,
        account_id: str | None = None,
        post_type: PostType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[PostAnalyticsSnapshot]:
        query = self._session.query(AnalyticsSnapshotModel)
        if destination_id is not None:
            query = query.filter(AnalyticsSnapshotModel.destination_id == destination_id)
        if account_id is not None:
            query = query.filter(AnalyticsSnapshotModel.account_id == account_id)
        if post_type is not None:
            query = query.filter(AnalyticsSnapshotModel.post_type == post_type.value)
        if since is not None:
            query = query.filter(AnalyticsSnapshotModel.synced_at >= _as_utc(since))

        models = query.order_by(AnalyticsSnapshotModel.synced_at.desc()).limit(limit).all()
        return tuple(m.to_snapshot() for m in models)

    def get_aggregated_metrics(
        self,
        destination_id: str | None = None,
        account_id: str | None = None,
        since: datetime | None = None,
    ) -> AggregatedMetrics:
        query = self._session.query(AnalyticsSnapshotModel)
        if destination_id is not None:
            query = query.filter(AnalyticsSnapshotModel.destination_id == destination_id)
        if account_id is not None:
            query = query.filter(AnalyticsSnapshotModel.account_id == account_id)
        if since is not None:
            query = query.filter(AnalyticsSnapshotModel.synced_at >= _as_utc(since))

        models = query.all()
        return AggregatedMetrics(
            total_posts=len(models),
            total_likes=sum(m.likes_count for m in models),
            total_comments=sum(m.comments_count for m in models),
            total_shares=sum(m.shares_count for m in models),
            total_views=sum(m.views_count for m in models),
            total_impressions=sum(m.impressions_count for m in models),
            total_reach=sum(m.reach_count for m in models),
        )

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class DeviceOperationalEventModel(Base):
    __tablename__ = "device_operational_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    @classmethod
    def from_event(cls, ev: DeviceOperationalEvent) -> "DeviceOperationalEventModel":
        return cls(
            id=ev.id,
            device_key=ev.device_key,
            provider=ev.provider,
            event_type=ev.event_type.value,
            duration_seconds=ev.duration_seconds,
            error_code=ev.error_code,
            error_message=ev.error_message,
            metadata_json=json.dumps(ev.metadata),
            created_at=_as_utc(ev.created_at),
        )

    def to_event(self) -> DeviceOperationalEvent:
        try:
            meta = json.loads(self.metadata_json)
        except Exception:
            meta = {}
        ev_type = (
            OperationalEventType(self.event_type)
            if self.event_type in OperationalEventType._value2member_map_
            else OperationalEventType.HEARTBEAT
        )
        return DeviceOperationalEvent(
            id=self.id,
            device_key=self.device_key,
            provider=self.provider,
            event_type=ev_type,
            duration_seconds=self.duration_seconds,
            error_code=self.error_code,
            error_message=self.error_message,
            metadata=meta,
            created_at=_as_utc(self.created_at),
        )


class SqlAlchemyDeviceAnalyticsRepository(DeviceAnalyticsRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyDeviceAnalyticsRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def record_event(self, event: DeviceOperationalEvent) -> None:
        model = DeviceOperationalEventModel.from_event(event)
        self._session.add(model)
        self._session.flush()

    def record_events(self, events: Sequence[DeviceOperationalEvent]) -> None:
        for ev in events:
            self._session.add(DeviceOperationalEventModel.from_event(ev))
        self._session.flush()

    def list_events(
        self,
        device_key: str | None = None,
        provider: str | None = None,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> Sequence[DeviceOperationalEvent]:
        query = self._session.query(DeviceOperationalEventModel)
        if device_key is not None:
            query = query.filter(DeviceOperationalEventModel.device_key == device_key)
        if provider is not None:
            query = query.filter(DeviceOperationalEventModel.provider == provider)
        if since is not None:
            query = query.filter(DeviceOperationalEventModel.created_at >= _as_utc(since))
        models = query.order_by(DeviceOperationalEventModel.created_at.desc()).limit(limit).all()
        return tuple(m.to_event() for m in models)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class AutomationPresetModel(Base):
    __tablename__ = "automation_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_built_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    @classmethod
    def from_preset(cls, preset: AutomationPreset) -> Self:
        return cls(
            id=preset.id,
            name=preset.name,
            description=preset.description,
            target_rules_json=json.dumps(
                {
                    "account_ids": list(preset.target_rules.account_ids),
                    "account_category": preset.target_rules.account_category,
                    "account_tags": list(preset.target_rules.account_tags),
                    "only_healthy_accounts": preset.target_rules.only_healthy_accounts,
                    "only_accounts_with_device": preset.target_rules.only_accounts_with_device,
                    "only_valid_auth": preset.target_rules.only_valid_auth,
                    "device_policy": preset.target_rules.device_policy,
                    "provider_preference": list(preset.target_rules.provider_preference),
                    "max_concurrent_devices": preset.target_rules.max_concurrent_devices,
                    "stop_device_after_release": preset.target_rules.stop_device_after_release,
                    "destination_ids": list(preset.target_rules.destination_ids),
                    "destination_types": list(preset.target_rules.destination_types),
                    "exclude_destination_ids": list(preset.target_rules.exclude_destination_ids),
                    "only_destinations_with_permissions": (
                        preset.target_rules.only_destinations_with_permissions
                    ),
                }
            ),
            tags_json=json.dumps(list(preset.tags)),
            is_built_in=preset.is_built_in,
            version=preset.version,
            created_at=_as_utc(preset.created_at),
            updated_at=_as_utc(preset.updated_at),
        )

    def to_preset(self, steps: Sequence[AutomationPresetStep] = ()) -> AutomationPreset:
        try:
            r_data = json.loads(self.target_rules_json)
        except Exception:
            r_data = {}

        target_rules = TargetSelectionRules(
            account_ids=tuple(r_data.get("account_ids", ())),
            account_category=r_data.get("account_category"),
            account_tags=tuple(r_data.get("account_tags", ())),
            only_healthy_accounts=bool(r_data.get("only_healthy_accounts", True)),
            only_accounts_with_device=bool(r_data.get("only_accounts_with_device", False)),
            only_valid_auth=bool(r_data.get("only_valid_auth", True)),
            device_policy=str(r_data.get("device_policy", "bound_first")),
            provider_preference=tuple(
                r_data.get("provider_preference", ("ldplayer", "mumu", "physical"))
            ),
            max_concurrent_devices=int(r_data.get("max_concurrent_devices", 4)),
            stop_device_after_release=bool(r_data.get("stop_device_after_release", False)),
            destination_ids=tuple(r_data.get("destination_ids", ())),
            destination_types=tuple(r_data.get("destination_types", ("page",))),
            exclude_destination_ids=tuple(r_data.get("exclude_destination_ids", ())),
            only_destinations_with_permissions=bool(
                r_data.get("only_destinations_with_permissions", True)
            ),
        )

        try:
            tags = tuple(json.loads(self.tags_json))
        except Exception:
            tags = ()

        return AutomationPreset(
            id=self.id,
            name=self.name,
            description=self.description,
            target_rules=target_rules,
            steps=tuple(sorted(steps, key=lambda s: s.order)),
            tags=tags,
            is_built_in=self.is_built_in,
            version=self.version,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class AutomationPresetStepModel(Base):
    __tablename__ = "automation_preset_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    preset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("automation_presets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    configuration_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    continue_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="no_retry")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)

    @classmethod
    def from_step(cls, step: AutomationPresetStep) -> Self:
        return cls(
            id=step.id,
            preset_id=step.preset_id,
            step_type=step.step_type.value,
            enabled=step.enabled,
            step_order=step.order,
            configuration_json=json.dumps(dict(step.configuration)),
            requires_approval=step.requires_approval,
            continue_on_error=step.continue_on_error,
            retry_policy=step.retry_policy,
            timeout_seconds=step.timeout_seconds,
        )

    def to_step(self) -> AutomationPresetStep:
        try:
            st = AutomationStepType(self.step_type)
        except Exception:
            st = AutomationStepType.HEALTH_CHECK

        try:
            cfg = json.loads(self.configuration_json)
        except Exception:
            cfg = {}

        return AutomationPresetStep(
            id=self.id,
            preset_id=self.preset_id,
            step_type=st,
            enabled=self.enabled,
            order=self.step_order,
            configuration=cfg,
            requires_approval=self.requires_approval,
            continue_on_error=self.continue_on_error,
            retry_policy=self.retry_policy,
            timeout_seconds=self.timeout_seconds,
        )


class SqlAlchemyAutomationPresetRepository(AutomationPresetRepositoryPort):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyAutomationPresetRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work
        self._fallback_session: Session | None = None

    def save_preset(self, preset: AutomationPreset) -> None:
        model = self._session.get(AutomationPresetModel, preset.id)
        if model is None:
            model = AutomationPresetModel.from_preset(preset)
            self._session.add(model)
        else:
            model.name = preset.name
            model.description = preset.description
            model.target_rules_json = AutomationPresetModel.from_preset(preset).target_rules_json
            model.tags_json = json.dumps(list(preset.tags))
            model.is_built_in = preset.is_built_in
            model.version = preset.version
            model.updated_at = _as_utc(preset.updated_at)

        # Sync steps: remove old steps for preset and insert fresh ones
        self._session.query(AutomationPresetStepModel).filter(
            AutomationPresetStepModel.preset_id == preset.id
        ).delete(synchronize_session=False)

        for step in preset.steps:
            self._session.add(AutomationPresetStepModel.from_step(step))

        self._session.flush()
        if self._unit_of_work.session is None and self._fallback_session is not None:
            self._fallback_session.commit()

    def get_preset(self, preset_id: str) -> AutomationPreset | None:
        model = self._session.get(AutomationPresetModel, preset_id)
        if model is None:
            return None
        step_models = (
            self._session.query(AutomationPresetStepModel)
            .filter(AutomationPresetStepModel.preset_id == preset_id)
            .order_by(AutomationPresetStepModel.step_order.asc())
            .all()
        )
        return model.to_preset(tuple(sm.to_step() for sm in step_models))

    def get_preset_by_name(self, name: str) -> AutomationPreset | None:
        model = (
            self._session.query(AutomationPresetModel)
            .filter(AutomationPresetModel.name == name)
            .first()
        )
        if model is None:
            return None
        step_models = (
            self._session.query(AutomationPresetStepModel)
            .filter(AutomationPresetStepModel.preset_id == model.id)
            .order_by(AutomationPresetStepModel.step_order.asc())
            .all()
        )
        return model.to_preset(tuple(sm.to_step() for sm in step_models))

    def list_presets(self) -> Sequence[AutomationPreset]:
        models = (
            self._session.query(AutomationPresetModel)
            .order_by(AutomationPresetModel.name.asc())
            .all()
        )
        result: list[AutomationPreset] = []
        for m in models:
            step_models = (
                self._session.query(AutomationPresetStepModel)
                .filter(AutomationPresetStepModel.preset_id == m.id)
                .order_by(AutomationPresetStepModel.step_order.asc())
                .all()
            )
            result.append(m.to_preset(tuple(sm.to_step() for sm in step_models)))
        return tuple(result)

    def delete_preset(self, preset_id: str) -> bool:
        model = self._session.get(AutomationPresetModel, preset_id)
        if model is not None:
            self._session.query(AutomationPresetStepModel).filter(
                AutomationPresetStepModel.preset_id == preset_id
            ).delete(synchronize_session=False)
            self._session.delete(model)
            self._session.flush()
            if self._unit_of_work.session is None and self._fallback_session is not None:
                self._fallback_session.commit()
            return True
        return False

    @property
    def _session(self) -> Session:
        if self._unit_of_work.session is not None:
            return self._unit_of_work.session
        if self._fallback_session is None:
            self._fallback_session = self._unit_of_work._session_factory()
        return self._fallback_session


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
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA temp_store=MEMORY")
    finally:
        cursor.close()
