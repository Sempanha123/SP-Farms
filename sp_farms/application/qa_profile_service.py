from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from random import Random
from uuid import uuid4

from sp_farms.application.ports import Clock
from sp_farms.application.qa_profiles import QAProfileReloadBridge, QAProfileRepository
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.qa_profiles import (
    QABridgeStatus,
    QADeviceAssignment,
    QAProfile,
    QAProfileAudit,
    QATargetPackage,
    validate_package_id,
    validate_profile,
)
from sp_farms.domain.result import AppError, Result

RESTRICTED_MESSAGE = (
    "QA identity override is restricted to applications you own or are authorized to test."
)
_RESTRICTED_PACKAGES = {
    "com.facebook.katana",
    "com.facebook.lite",
    "com.instagram.android",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.google.android.apps.authenticator2",
}
_RESTRICTED_PREFIXES = (
    "com.facebook.",
    "com.instagram.",
    "com.paypal.",
    "com.venmo.",
    "com.revolut.",
    "com.chase.",
    "com.bankofamerica.",
)


class QAProfileService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        repository_factory: Callable[[UnitOfWork], QAProfileRepository],
        bridge: QAProfileReloadBridge,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._bridge = bridge
        self._clock = clock

    def list_profiles(self) -> Sequence[QAProfile]:
        with self._unit_of_work_factory() as unit:
            return self._repository_factory(unit).list_profiles()

    def new_profile(self, profile_name: str) -> QAProfile:
        return QAProfile.create(profile_name, self._clock.now())

    def create_profile(self, profile_name: str) -> QAProfile:
        return self.save_profile(self.new_profile(profile_name))

    def save_profile(self, profile: QAProfile) -> QAProfile:
        validate_profile(profile)
        now = self._clock.now()
        saved = replace(
            profile,
            created_at=profile.created_at or now,
            updated_at=now,
        )
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).save_profile(saved)
            unit.commit()
        return saved

    def clone_profile(self, profile_id: str, profile_name: str) -> QAProfile:
        source = self.get_profile(profile_id)
        clone = source.renamed_copy(profile_name, self._clock.now())
        return self.save_profile(clone)

    def randomize_compatibility_fields(
        self,
        profile_id: str,
        seed: int | None = None,
    ) -> QAProfile:
        profile = self.get_profile(profile_id)
        random = Random(seed)
        manufacturers = (
            ("Google", "Pixel 8", "shiba", "shiba", "shiba"),
            ("Samsung", "SM-S921B", "e1s", "s5e9945", "s5e9945"),
            ("Xiaomi", "23127PN0CG", "houji", "qcom", "kalama"),
        )
        manufacturer, model, product, hardware, board = random.choice(manufacturers)
        updated = replace(
            profile,
            manufacturer=manufacturer,
            model=model,
            market_name=model,
            product=product,
            hardware=hardware,
            board=board,
        )
        return self.save_profile(updated)

    def delete_profile(self, profile_id: str) -> None:
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).delete_profile(profile_id)
            unit.commit()

    def get_profile(self, profile_id: str) -> QAProfile:
        with self._unit_of_work_factory() as unit:
            profile = self._repository_factory(unit).get_profile(profile_id)
        if profile is None:
            raise ValueError(f"QA profile '{profile_id}' not found")
        return profile

    def export_profile(self, profile_id: str, destination: Path) -> None:
        destination.write_text(self.get_profile(profile_id).to_json(), encoding="utf-8")

    def import_profile(self, source: Path) -> QAProfile:
        profile = QAProfile.from_json(source.read_text(encoding="utf-8"))
        if any(current.id == profile.id for current in self.list_profiles()):
            profile = replace(profile, id=str(uuid4()))
        return self.save_profile(profile)

    def list_targets(self) -> Sequence[QATargetPackage]:
        with self._unit_of_work_factory() as unit:
            return self._repository_factory(unit).list_targets()

    def allow_target(
        self,
        package_id: str,
        display_name: str,
        ownership_note: str,
        profile_id: str | None = None,
    ) -> QATargetPackage:
        package = validate_package_id(package_id)
        if self._is_restricted(package):
            raise ValueError(RESTRICTED_MESSAGE)
        note = ownership_note.strip()
        if not note:
            raise ValueError("Ownership/authorization note is required")
        target = QATargetPackage(
            package_id=package,
            display_name=display_name.strip() or package,
            ownership_note=note,
            enabled=True,
            last_verified=self._clock.now(),
            test_profile_id=profile_id,
        )
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).save_target(target)
            unit.commit()
        return target

    def assign(self, provider: str, external_id: str, profile_id: str) -> None:
        self.get_profile(profile_id)
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).save_assignment(
                QADeviceAssignment(provider, external_id, profile_id)
            )
            unit.commit()

    def get_assignment(self, provider: str, external_id: str) -> QADeviceAssignment | None:
        with self._unit_of_work_factory() as unit:
            return self._repository_factory(unit).get_assignment(provider, external_id)

    def push(
        self,
        serial: str,
        provider: str,
        external_id: str,
        profile_id: str,
        package_id: str,
        reload_profile: bool = False,
    ) -> Result[QABridgeStatus]:
        allowed = self._authorized_target(package_id)
        if not allowed.is_success:
            return Result.failure(allowed.error)
        profile = self.get_profile(profile_id)
        result = self._bridge.push(serial, profile, package_id)
        operation = "push"
        if result.is_success and reload_profile:
            result = self._bridge.reload(serial)
            operation = "push_reload"
        self._audit(operation, provider, external_id, package_id, profile.id, result)
        return result

    def verify(
        self,
        serial: str,
        provider: str,
        external_id: str,
        package_id: str,
    ) -> Result[QABridgeStatus]:
        allowed = self._authorized_target(package_id)
        if not allowed.is_success:
            return Result.failure(allowed.error)
        result = self._bridge.verify(serial)
        profile_id = result.value.profile_id if result.is_success else None
        self._audit("verify", provider, external_id, package_id, profile_id, result)
        return result

    def restore(
        self,
        serial: str,
        provider: str,
        external_id: str,
        package_id: str,
    ) -> Result[QABridgeStatus]:
        allowed = self._authorized_target(package_id)
        if not allowed.is_success:
            return Result.failure(allowed.error)
        result = self._bridge.restore(serial)
        self._audit("restore", provider, external_id, package_id, None, result)
        return result

    def _authorized_target(self, package_id: str) -> Result[QATargetPackage]:
        try:
            package = validate_package_id(package_id)
        except ValueError as exc:
            return Result.failure(AppError("qa.invalid_package", str(exc), exc))
        if self._is_restricted(package):
            return Result.failure(AppError("qa.target_restricted", RESTRICTED_MESSAGE))
        with self._unit_of_work_factory() as unit:
            target = self._repository_factory(unit).get_target(package)
        if target is None or not target.enabled:
            return Result.failure(AppError("qa.target_not_allowed", RESTRICTED_MESSAGE))
        return Result.success(target)

    @staticmethod
    def _is_restricted(package_id: str) -> bool:
        value = package_id.lower()
        return value in _RESTRICTED_PACKAGES or value.startswith(_RESTRICTED_PREFIXES)

    def _audit(
        self,
        operation: str,
        provider: str,
        external_id: str,
        package_id: str,
        profile_id: str | None,
        result: Result[QABridgeStatus],
    ) -> None:
        outcome = "success" if result.is_success else result.error.code
        audit = QAProfileAudit(
            id=str(uuid4()),
            actor="operator",
            operation=operation,
            provider=provider,
            external_id=external_id,
            package_id=package_id,
            profile_id=profile_id,
            timestamp=self._clock.now(),
            result=outcome,
        )
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).add_audit(audit)
            unit.commit()
