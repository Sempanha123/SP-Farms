from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.qa_profiles import (
    QABridgeStatus,
    QADeviceAssignment,
    QAProfile,
    QAProfileAudit,
    QATargetPackage,
)
from sp_farms.domain.result import Result


class QAProfileRepository(Protocol):
    def list_profiles(self) -> Sequence[QAProfile]: ...

    def get_profile(self, profile_id: str) -> QAProfile | None: ...

    def save_profile(self, profile: QAProfile) -> None: ...

    def delete_profile(self, profile_id: str) -> None: ...

    def list_targets(self) -> Sequence[QATargetPackage]: ...

    def get_target(self, package_id: str) -> QATargetPackage | None: ...

    def save_target(self, target: QATargetPackage) -> None: ...

    def get_assignment(self, provider: str, external_id: str) -> QADeviceAssignment | None: ...

    def save_assignment(self, assignment: QADeviceAssignment) -> None: ...

    def add_audit(self, audit: QAProfileAudit) -> None: ...


class QAProfileReloadBridge(Protocol):
    def push(
        self,
        serial: str,
        profile: QAProfile,
        package_id: str,
    ) -> Result[QABridgeStatus]: ...

    def reload(self, serial: str) -> Result[QABridgeStatus]: ...

    def verify(self, serial: str) -> Result[QABridgeStatus]: ...

    def restore(self, serial: str) -> Result[QABridgeStatus]: ...
