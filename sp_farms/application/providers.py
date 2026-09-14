from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from sp_farms.domain.devices import DeviceInfo
from sp_farms.domain.providers import DeviceProviderType, EmulatorInstance, ProviderCapabilities


class ProviderError(Exception):
    """Base exception for device provider operations."""


class ProviderExecutableNotFoundError(ProviderError):
    """Raised when the provider executable or CLI tool cannot be found."""


class ProviderInstanceNotFoundError(ProviderError):
    """Raised when an instance index or name does not exist."""


class ProviderOperationTimeoutError(ProviderError):
    """Raised when a start/stop/restart or execution operation times out."""


class DeviceProviderPort(Protocol):
    @property
    def provider_type(self) -> DeviceProviderType: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def is_available(self) -> bool: ...

    def list_instances(self) -> Sequence[EmulatorInstance]: ...

    def start_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None: ...

    def stop_instance(self, index_or_name: int | str, timeout: float = 30.0) -> None: ...

    def restart_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None: ...

    def get_adb_serial(self, index: int) -> str: ...

    def launch_app(self, index_or_name: int | str, package_name: str) -> None: ...

    def take_screenshot(self, index_or_name: int | str, destination: Path) -> Path: ...

    def collect_logs(self, index_or_name: int | str, lines: int = 100) -> str: ...

    def health_check(self, index_or_name: int | str) -> DeviceInfo | None: ...

    def diagnostics(self) -> dict[str, object]: ...
