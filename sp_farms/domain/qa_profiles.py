from dataclasses import asdict, dataclass, replace
from datetime import datetime
from json import dumps, loads
from re import fullmatch
from typing import Any
from uuid import uuid4

QA_PROFILE_SCHEMA_VERSION = 1
_PACKAGE_PATTERN = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+"


@dataclass(frozen=True, slots=True)
class QAProfile:
    id: str
    profile_name: str
    manufacturer: str = ""
    model: str = ""
    market_name: str = ""
    product: str = ""
    hardware: str = ""
    board: str = ""
    bootloader: str = ""
    build_fingerprint: str = ""
    test_android_id: str = ""
    test_serial_number: str = ""
    test_imei: str = ""
    test_meid: str = ""
    test_gsf_id: str = ""
    test_advertising_id: str = ""
    test_mac: str = ""
    test_bluetooth_mac: str = ""
    test_wifi_ssid: str = ""
    test_wifi_bssid: str = ""
    test_network_generation: str = ""
    test_imsi: str = ""
    test_sim_id: str = ""
    test_mobile_number: str = ""
    test_esim_eid: str = ""
    test_sim_operator: str = ""
    test_sim_operator_name: str = ""
    test_sim_country_iso: str = ""
    timezone: str = "UTC"
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, profile_name: str, now: datetime) -> "QAProfile":
        return cls(
            id=str(uuid4()),
            profile_name=validate_profile_name(profile_name),
            created_at=now,
            updated_at=now,
        )

    def renamed_copy(self, profile_name: str, now: datetime) -> "QAProfile":
        return replace(
            self,
            id=str(uuid4()),
            profile_name=validate_profile_name(profile_name),
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return {"schema_version": QA_PROFILE_SCHEMA_VERSION, "profile": data}

    def to_json(self) -> str:
        return dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "QAProfile":
        try:
            document = loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid QA profile JSON") from exc
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise ValueError("Unsupported QA profile schema version")
        raw = document.get("profile")
        if not isinstance(raw, dict):
            raise ValueError("QA profile payload must be an object")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"Unknown QA profile fields: {', '.join(sorted(unknown))}")
        _validate_profile_types(raw)
        values = dict(raw)
        for key in ("created_at", "updated_at"):
            if values.get(key) is not None:
                values[key] = datetime.fromisoformat(values[key])
        profile = cls(**values)
        validate_profile(profile)
        return profile


@dataclass(frozen=True, slots=True)
class QATargetPackage:
    package_id: str
    display_name: str
    ownership_note: str
    enabled: bool
    last_verified: datetime
    test_profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class QADeviceAssignment:
    provider: str
    external_id: str
    profile_id: str


@dataclass(frozen=True, slots=True)
class QAProfileAudit:
    id: str
    actor: str
    operation: str
    provider: str
    external_id: str
    package_id: str
    profile_id: str | None
    timestamp: datetime
    result: str


@dataclass(frozen=True, slots=True)
class QABridgeStatus:
    serial: str
    profile_id: str | None
    package_id: str | None
    loaded: bool
    message: str


def validate_profile_name(value: str) -> str:
    name = value.strip()
    if not name or len(name) > 100:
        raise ValueError("Profile name must contain 1-100 characters")
    return name


def validate_package_id(value: str) -> str:
    package_id = value.strip()
    if len(package_id) > 255 or fullmatch(_PACKAGE_PATTERN, package_id) is None:
        raise ValueError("Invalid Android package ID")
    return package_id


def validate_profile(profile: QAProfile) -> None:
    validate_profile_name(profile.profile_name)
    if profile.latitude is not None and not -90 <= profile.latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    if profile.longitude is not None and not -180 <= profile.longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180")


def _validate_profile_types(raw: dict[str, Any]) -> None:
    string_fields = set(QAProfile.__dataclass_fields__) - {
        "latitude",
        "longitude",
        "created_at",
        "updated_at",
    }
    for key in string_fields:
        if key in raw and not isinstance(raw[key], str):
            raise ValueError(f"QA profile field '{key}' must be a string")
    for key in ("latitude", "longitude"):
        if key in raw and raw[key] is not None and not isinstance(raw[key], (int, float)):
            raise ValueError(f"QA profile field '{key}' must be numeric")
    for key in ("created_at", "updated_at"):
        if key in raw and raw[key] is not None and not isinstance(raw[key], str):
            raise ValueError(f"QA profile field '{key}' must be an ISO timestamp")
