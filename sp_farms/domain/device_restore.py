from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sp_farms.domain.accounts import PreferredApp

FACEBOOK_PACKAGE = "com.facebook.katana"
FACEBOOK_LITE_PACKAGE = "com.facebook.lite"
CHROME_PACKAGE = "com.android.chrome"
AOSP_BROWSER_PACKAGE = "com.android.browser"

PREFERRED_APP_PACKAGES: dict[PreferredApp, str] = {
    PreferredApp.FACEBOOK: FACEBOOK_PACKAGE,
    PreferredApp.FACEBOOK_LITE: FACEBOOK_LITE_PACKAGE,
    PreferredApp.BROWSER: CHROME_PACKAGE,
}


class BindingStatus(StrEnum):
    ACTIVE = "active"
    UNASSIGNED = "unassigned"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class AccountDeviceBinding:
    account_id: str
    device_profile_id: str
    preferred_app: PreferredApp = PreferredApp.BROWSER
    status: BindingStatus = BindingStatus.ACTIVE
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class RestoreWorkspaceResult:
    success: bool
    account_id: str
    status: str
    message: str
    device_name: str = ""
    adb_serial: str = ""
    target_package: str = ""
    auth_state: str = "unknown"
    security_state: str = "unknown"
    reauth_required: bool = False
    details: dict[str, str] = field(default_factory=dict)
