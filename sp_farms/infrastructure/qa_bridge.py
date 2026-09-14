from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path
from tempfile import NamedTemporaryFile

from sp_farms.application.adb import AdbPort
from sp_farms.application.qa_profiles import QAProfileReloadBridge
from sp_farms.domain.qa_profiles import QABridgeStatus, QAProfile
from sp_farms.domain.result import AppError, Result

BRIDGE_VERSION = 1
REMOTE_DIRECTORY = "/data/local/tmp/sp_farms_qa"
REMOTE_PROFILE_PATH = f"{REMOTE_DIRECTORY}/profile.json"
REMOTE_STATUS_PATH = f"{REMOTE_DIRECTORY}/status.json"
RELOAD_ACTION = "com.spfarms.qa.action.RELOAD_PROFILE_V1"


class AdbQAProfileReloadBridge(QAProfileReloadBridge):
    def __init__(self, adb: AdbPort, temporary_directory: Path | None = None) -> None:
        self._adb = adb
        self._temporary_directory = temporary_directory

    def push(
        self,
        serial: str,
        profile: QAProfile,
        package_id: str,
    ) -> Result[QABridgeStatus]:
        local_path: Path | None = None
        try:
            payload = profile.to_dict()
            payload["bridge_version"] = BRIDGE_VERSION
            payload["target_package"] = package_id
            with NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="sp-farms-qa-",
                dir=self._temporary_directory,
                delete=False,
                encoding="utf-8",
            ) as temporary:
                temporary.write(dumps(payload, indent=2, sort_keys=True))
                local_path = Path(temporary.name)
            self._adb.shell(serial, f"mkdir -p {REMOTE_DIRECTORY}")
            pushed = self._adb.run_command(
                ["push", str(local_path), REMOTE_PROFILE_PATH],
                serial=serial,
            )
            if pushed.returncode != 0:
                raise RuntimeError(pushed.stderr or "ADB push failed")
            self._adb.shell(serial, f"chmod 600 {REMOTE_PROFILE_PATH}")
            exists = self._adb.shell(serial, f"test -f {REMOTE_PROFILE_PATH} && echo OK")
            if exists.strip() != "OK":
                raise RuntimeError("Remote QA profile verification failed")
            return Result.success(
                QABridgeStatus(serial, profile.id, package_id, False, "Profile pushed")
            )
        except Exception as exc:
            return Result.failure(AppError("qa.push_failed", str(exc), exc))
        finally:
            if local_path is not None:
                local_path.unlink(missing_ok=True)

    def reload(self, serial: str) -> Result[QABridgeStatus]:
        try:
            output = self._adb.shell(
                serial,
                f"am broadcast -a {RELOAD_ACTION}",
            )
            if "result=0" not in output.lower() and "broadcast completed" not in output.lower():
                raise RuntimeError("QA module did not acknowledge reload")
            return Result.success(QABridgeStatus(serial, None, None, True, "Reload accepted"))
        except Exception as exc:
            return Result.failure(AppError("qa.reload_failed", str(exc), exc))

    def verify(self, serial: str) -> Result[QABridgeStatus]:
        try:
            raw = self._adb.shell(serial, f"cat {REMOTE_STATUS_PATH}")
            status = loads(raw)
            if not isinstance(status, dict) or status.get("bridge_version") != BRIDGE_VERSION:
                raise RuntimeError("Unsupported or missing QA bridge status")
            loaded = status.get("loaded")
            profile_id = status.get("profile_id")
            package_id = status.get("target_package")
            if not isinstance(loaded, bool):
                raise RuntimeError("Invalid QA bridge status")
            if profile_id is not None and not isinstance(profile_id, str):
                raise RuntimeError("Invalid QA bridge profile ID")
            if package_id is not None and not isinstance(package_id, str):
                raise RuntimeError("Invalid QA bridge target package")
            return Result.success(
                QABridgeStatus(serial, profile_id, package_id, loaded, "Status verified")
            )
        except Exception as exc:
            return Result.failure(AppError("qa.verify_failed", str(exc), exc))

    def restore(self, serial: str) -> Result[QABridgeStatus]:
        try:
            self._adb.shell(serial, f"rm -f {REMOTE_PROFILE_PATH}")
            reloaded = self.reload(serial)
            if not reloaded.is_success:
                return reloaded
            return Result.success(QABridgeStatus(serial, None, None, False, "Defaults restored"))
        except Exception as exc:
            return Result.failure(AppError("qa.restore_failed", str(exc), exc))


@dataclass
class FakeQAProfileReloadBridge(QAProfileReloadBridge):
    fail_operation: str | None = None

    def __post_init__(self) -> None:
        self.active: dict[str, QABridgeStatus] = {}
        self.history: list[tuple[str, str]] = []

    def push(
        self,
        serial: str,
        profile: QAProfile,
        package_id: str,
    ) -> Result[QABridgeStatus]:
        failed = self._failure("push")
        if failed is not None:
            return failed
        status = QABridgeStatus(serial, profile.id, package_id, False, "Profile pushed")
        self.active[serial] = status
        self.history.append(("push", serial))
        return Result.success(status)

    def reload(self, serial: str) -> Result[QABridgeStatus]:
        failed = self._failure("reload")
        if failed is not None:
            return failed
        current = self.active.get(serial)
        if current is None:
            return Result.failure(AppError("qa.reload_failed", "No profile has been pushed"))
        status = QABridgeStatus(
            serial,
            current.profile_id,
            current.package_id,
            True,
            "Reload accepted",
        )
        self.active[serial] = status
        self.history.append(("reload", serial))
        return Result.success(status)

    def verify(self, serial: str) -> Result[QABridgeStatus]:
        failed = self._failure("verify")
        if failed is not None:
            return failed
        current = self.active.get(serial)
        if current is None:
            return Result.failure(AppError("qa.verify_failed", "No active QA profile"))
        self.history.append(("verify", serial))
        return Result.success(current)

    def restore(self, serial: str) -> Result[QABridgeStatus]:
        failed = self._failure("restore")
        if failed is not None:
            return failed
        self.active.pop(serial, None)
        self.history.append(("restore", serial))
        return Result.success(QABridgeStatus(serial, None, None, False, "Defaults restored"))

    def _failure(self, operation: str) -> Result[QABridgeStatus] | None:
        if self.fail_operation != operation:
            return None
        return Result.failure(AppError(f"qa.{operation}_failed", "Simulated bridge failure"))
