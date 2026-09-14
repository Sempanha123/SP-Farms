from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sp_farms.domain.devices import DeviceInfo


class AdbError(Exception):
    pass


class AdbExecutableNotFoundError(AdbError):
    pass


class AdbTimeoutError(AdbError):
    pass


class AdbDeviceNotFoundError(AdbError):
    pass


class AdbUnauthorizedError(AdbError):
    pass


class AdbOfflineError(AdbError):
    pass


class AdbCommandError(AdbError):
    def __init__(self, message: str, returncode: int, stderr: str = "") -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


@dataclass(frozen=True, slots=True)
class AdbCommandResult:
    stdout: str
    stderr: str
    returncode: int


class AdbPort(Protocol):
    def list_devices(self) -> Sequence[DeviceInfo]: ...

    def run_command(
        self,
        args: Sequence[str],
        serial: str | None = None,
        timeout: float = 30.0,
    ) -> AdbCommandResult: ...

    def shell(
        self,
        serial: str,
        command: str,
        timeout: float = 30.0,
    ) -> str: ...

    def get_device_info(self, serial: str) -> DeviceInfo: ...

    def heartbeat(self, serial: str) -> bool: ...
