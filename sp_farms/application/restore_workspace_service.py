from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from sp_farms.application.device_profiles import DeviceProfileRepository
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.accounts import PermissionState, PreferredApp, SecurityState
from sp_farms.domain.device_management import DeviceProfile
from sp_farms.domain.device_restore import (
    AOSP_BROWSER_PACKAGE,
    CHROME_PACKAGE,
    PREFERRED_APP_PACKAGES,
    AccountDeviceBinding,
    BindingStatus,
    RestoreWorkspaceResult,
)
from sp_farms.domain.providers import DeviceProviderType

if TYPE_CHECKING:
    from sp_farms.application.account_service import AccountService
    from sp_farms.application.adb import AdbPort
    from sp_farms.application.device_service import DeviceService
    from sp_farms.application.providers import DeviceProviderPort


class RestoreWorkspaceService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        repository_factory: Callable[[UnitOfWork], DeviceProfileRepository],
        account_service: "AccountService",
        device_service: "DeviceService",
        adb: "AdbPort",
        clock: Clock,
        providers: Sequence["DeviceProviderPort"] | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work_factory
        self._repo_factory = repository_factory
        self._accounts = account_service
        self._devices = device_service
        self._adb = adb
        self._clock = clock
        self._providers_map: dict[DeviceProviderType, DeviceProviderPort] = {}
        if providers:
            for p in providers:
                self._providers_map[p.provider_type] = p

    def get_binding(self, account_id: str) -> AccountDeviceBinding | None:
        with self._unit_of_work() as uow:
            return self._repo_factory(uow).get_binding(account_id)

    def get_profile(self, profile_id: str) -> DeviceProfile | None:
        with self._unit_of_work() as uow:
            return self._repo_factory(uow).get_by_id(profile_id)

    def get_profile_by_device(
        self, provider: DeviceProviderType, external_id: str
    ) -> DeviceProfile | None:
        with self._unit_of_work() as uow:
            return self._repo_factory(uow).get(provider, external_id)

    def list_profiles(self) -> Sequence[DeviceProfile]:
        with self._unit_of_work() as uow:
            return self._repo_factory(uow).list_all()

    def save_profile(self, profile: DeviceProfile) -> DeviceProfile:
        with self._unit_of_work() as uow:
            repo = self._repo_factory(uow)
            repo.save(profile)
            uow.commit()
        return self.get_profile_by_device(profile.provider, profile.external_id) or profile

    def bind_device(
        self,
        account_id: str,
        provider: DeviceProviderType,
        external_id: str,
        preferred_app: PreferredApp | None = None,
    ) -> AccountDeviceBinding:
        account = self._accounts.get_account(account_id)

        # 1. Resolve or create DeviceProfile
        profile = self.get_profile_by_device(provider, external_id)
        if profile is None:
            # Query live device info if possible
            managed = next(
                (
                    d
                    for d in self._devices.discover()
                    if d.provider == provider
                    and (
                        d.external_id == external_id
                        or str(d.selector) == str(external_id)
                        or d.adb_serial == external_id
                    )
                ),
                None,
            )
            adb_serial = (
                managed.adb_serial
                if managed
                else (external_id if "emulator" in external_id or ":" in external_id else "")
            )
            profile = DeviceProfile(
                provider=provider,
                external_id=external_id,
                friendly_name=managed.display_name
                if managed
                else f"{provider.value}:{external_id}",
                emulator_instance=str(managed.selector) if managed else external_id,
                adb_serial=managed.adb_serial if managed else adb_serial,
                android_version=managed.android_version or "" if managed else "",
                model=managed.name if managed else "",
                resolution=f"{managed.resolution[0]}x{managed.resolution[1]}"
                if managed and managed.resolution
                else "",
                preferred_app=preferred_app or account.preferred_app,
                last_heartbeat=self._clock.now(),
            )
            profile = self.save_profile(profile)

        selected_app = preferred_app or account.preferred_app

        # 2. Save binding
        binding = AccountDeviceBinding(
            account_id=account_id,
            device_profile_id=profile.id,
            preferred_app=selected_app,
            status=BindingStatus.ACTIVE,
            last_used_at=None,
            created_at=self._clock.now(),
            updated_at=self._clock.now(),
        )

        with self._unit_of_work() as uow:
            repo = self._repo_factory(uow)
            repo.save_binding(binding)
            uow.commit()

        # 3. Synchronize account service device assignment
        self._accounts.assign_device(account_id, provider.value, external_id)

        return binding

    def restore_workspace(self, account_id: str) -> RestoreWorkspaceResult:
        # Step 1: Resolve account and binding
        try:
            account = self._accounts.get_account(account_id)
        except ValueError:
            return RestoreWorkspaceResult(
                success=False,
                account_id=account_id,
                status="account_not_found",
                message=f"Account '{account_id}' was not found.",
            )

        binding = self.get_binding(account_id)
        if binding is None:
            # Check if account has an assigned device from AccountService
            if account.assigned_device is not None:
                provider_type = DeviceProviderType(account.assigned_device.provider)
                binding = self.bind_device(
                    account_id,
                    provider_type,
                    account.assigned_device.external_id,
                    account.preferred_app,
                )
            else:
                return RestoreWorkspaceResult(
                    success=False,
                    account_id=account_id,
                    status="unassigned",
                    message="No device profile is bound to this account.",
                    security_state=account.security_state.value,
                )

        profile = self.get_profile(binding.device_profile_id)
        if profile is None:
            return RestoreWorkspaceResult(
                success=False,
                account_id=account_id,
                status="profile_not_found",
                message=f"Bound device profile '{binding.device_profile_id}' does not exist.",
            )

        # Step 2: Start assigned emulator if needed
        provider = self._providers_map.get(profile.provider)
        discovered = self._devices.discover()
        device = next(
            (
                d
                for d in discovered
                if d.provider == profile.provider
                and (
                    d.external_id == profile.external_id
                    or str(d.selector) == str(profile.emulator_instance)
                    or d.adb_serial == profile.adb_serial
                )
            ),
            None,
        )

        adb_serial = profile.adb_serial or (device.adb_serial if device else profile.external_id)

        if device is None or not device.is_online:
            if provider is not None and provider.capabilities.can_start_stop:
                selector = (
                    device.selector
                    if device
                    else (
                        int(profile.emulator_instance)
                        if profile.emulator_instance.isdigit()
                        else profile.emulator_instance
                    )
                )
                try:
                    provider.start_instance(selector)
                except Exception as exc:
                    return RestoreWorkspaceResult(
                        success=False,
                        account_id=account_id,
                        status="device_start_failed",
                        message=f"Failed to start device instance: {exc}",
                        device_name=profile.display_name,
                        adb_serial=adb_serial,
                    )
            elif profile.provider == DeviceProviderType.PHYSICAL:
                return RestoreWorkspaceResult(
                    success=False,
                    account_id=account_id,
                    status="device_offline",
                    message=(
                        f"Physical device '{profile.display_name}' is offline. "
                        "Please connect via USB/Wi-Fi."
                    ),
                    device_name=profile.display_name,
                    adb_serial=adb_serial,
                )

        # Step 3: Wait for / verify ADB
        if not self._adb.heartbeat(adb_serial):
            return RestoreWorkspaceResult(
                success=False,
                account_id=account_id,
                status="adb_unreachable",
                message=f"Device '{profile.display_name}' is not reachable via ADB ({adb_serial}).",
                device_name=profile.display_name,
                adb_serial=adb_serial,
            )

        # Step 4: Validate app availability
        target_app = binding.preferred_app or account.preferred_app
        target_package = PREFERRED_APP_PACKAGES.get(target_app, CHROME_PACKAGE)

        try:
            pkg_list = self._adb.shell(adb_serial, f"pm list packages {target_package}")
            is_installed = f"package:{target_package}" in pkg_list
        except Exception:
            is_installed = False

        if not is_installed and target_app == PreferredApp.BROWSER:
            # Fallback check for AOSP Browser
            try:
                fallback_list = self._adb.shell(
                    adb_serial, f"pm list packages {AOSP_BROWSER_PACKAGE}"
                )
                if f"package:{AOSP_BROWSER_PACKAGE}" in fallback_list:
                    target_package = AOSP_BROWSER_PACKAGE
                    is_installed = True
            except Exception:
                is_installed = False

        if not is_installed:
            return RestoreWorkspaceResult(
                success=False,
                account_id=account_id,
                status="missing_app",
                message=(
                    f"Target app '{target_package}' ({target_app.value}) is not "
                    f"installed on device '{profile.display_name}'."
                ),
                device_name=profile.display_name,
                adb_serial=adb_serial,
                target_package=target_package,
                security_state=account.security_state.value,
            )

        # Step 5: Apply harmless saved preferences where supported
        details: dict[str, str] = {}
        if profile.timezone:
            try:
                self._adb.shell(adb_serial, f"setprop persist.sys.timezone {profile.timezone}")
                details["timezone"] = profile.timezone
            except Exception:
                pass

        # Step 6: Launch selected app
        app_launched = False
        selector = (
            device.selector
            if device
            else (
                int(profile.emulator_instance)
                if profile.emulator_instance.isdigit()
                else profile.emulator_instance
            )
        )
        if provider is not None and provider.capabilities.can_launch_apps:
            try:
                provider.launch_app(selector, target_package)
                app_launched = True
            except Exception:
                app_launched = False

        if not app_launched:
            # Fallback to adb monkey launcher
            try:
                self._adb.shell(
                    adb_serial, f"monkey -p {target_package} -c android.intent.category.LAUNCHER 1"
                )
                app_launched = True
            except Exception as exc:
                return RestoreWorkspaceResult(
                    success=False,
                    account_id=account_id,
                    status="launch_failed",
                    message=f"Failed to launch app '{target_package}': {exc}",
                    device_name=profile.display_name,
                    adb_serial=adb_serial,
                    target_package=target_package,
                )

        # Step 7 & 8: Auth / security state and re-auth guidance
        reauth_required = (
            account.security_state in (SecurityState.REVIEW_REQUIRED, SecurityState.COMPROMISED)
            or account.permission_state == PermissionState.REVOKED
        )

        auth_desc = "active" if account.status.value == "active" else account.status.value
        if reauth_required:
            message = (
                f"Restored workspace for {account.display_name} on {profile.display_name}. "
                f"Security action required: {account.security_state.value}. Please re-authenticate."
            )
        else:
            message = f"Restored workspace for {account.display_name} on {profile.display_name}."

        # Step 9: Update last-used and heartbeat
        now = self._clock.now()
        updated_binding = replace(binding, last_used_at=now, updated_at=now)
        updated_profile = replace(profile, last_heartbeat=now, updated_at=now)

        with self._unit_of_work() as uow:
            repo = self._repo_factory(uow)
            repo.save_binding(updated_binding)
            repo.save(updated_profile)
            uow.commit()

        # Update account login time
        updated_account = replace(account, last_login_at=now, updated_at=now)
        self._accounts.save_account(updated_account)

        return RestoreWorkspaceResult(
            success=True,
            account_id=account_id,
            status="restored",
            message=message,
            device_name=profile.display_name,
            adb_serial=adb_serial,
            target_package=target_package,
            auth_state=auth_desc,
            security_state=account.security_state.value,
            reauth_required=reauth_required,
            details=details,
        )
