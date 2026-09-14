import base64
import json
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sp_farms.application.licensing_service import LicensingService
from sp_farms.domain.licensing import (
    FeatureFlag,
    LicenseStatus,
    ProductEdition,
)


def generate_test_license(
    private_key: Ed25519PrivateKey,
    license_id: str = "lic-1001",
    licensee_name: str = "Acme Corp",
    licensee_email: str = "admin@acme.com",
    edition: ProductEdition = ProductEdition.PRO,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    max_accounts: int = 50,
    max_devices: int = 15,
    feature_flags: tuple[str, ...] = ("automation_appium", "hybrid_publishing"),
    grace_period_days: int = 7,
) -> str:
    payload = {
        "license_id": license_id,
        "licensee_name": licensee_name,
        "licensee_email": licensee_email,
        "edition": edition.value,
        "issued_at": (issued_at or datetime.now(UTC)).isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "max_accounts": max_accounts,
        "max_devices": max_devices,
        "feature_flags": list(feature_flags),
        "grace_period_days": grace_period_days,
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = private_key.sign(payload_bytes)

    b64_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    b64_sig = base64.urlsafe_b64encode(sig).decode("ascii")
    return f"{b64_payload}.{b64_sig}"


def test_valid_signed_license_verification():
    private_key = Ed25519PrivateKey.generate()
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    service = LicensingService(
        public_key_pem_or_b64=public_key_pem,
        dev_mode_override=False,
    )

    valid_key = generate_test_license(
        private_key=private_key,
        edition=ProductEdition.VIP,
        max_accounts=500,
        max_devices=100,
        feature_flags=(
            FeatureFlag.AUTOMATION_APPIUM.value,
            FeatureFlag.AI_CAPTIONS.value,
            FeatureFlag.PLUGINS_RUNTIME.value,
        ),
    )

    info = service.load_license_key(valid_key)
    assert info.status == LicenseStatus.ACTIVE
    assert info.edition == ProductEdition.VIP
    assert info.is_valid is True
    assert info.max_accounts_allowed() == 500
    assert info.max_devices_allowed() == 100
    assert info.has_feature(FeatureFlag.AUTOMATION_APPIUM) is True
    assert info.has_feature(FeatureFlag.AI_CAPTIONS) is True
    assert info.has_feature(FeatureFlag.ADVANCED_ANALYTICS) is False


def test_tampered_license_signature_rejection():
    private_key = Ed25519PrivateKey.generate()
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    service = LicensingService(
        public_key_pem_or_b64=public_key_pem,
        dev_mode_override=False,
    )

    valid_key = generate_test_license(private_key=private_key)
    payload_b64, sig_b64 = valid_key.split(".")

    # Tamper with payload (change max accounts)
    payload_data = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
    payload_data["max_accounts"] = 99999
    tampered_payload_bytes = json.dumps(payload_data).encode("utf-8")
    tampered_b64 = base64.urlsafe_b64encode(tampered_payload_bytes).decode("ascii")

    tampered_key = f"{tampered_b64}.{sig_b64}"

    info = service.load_license_key(tampered_key)
    assert info.status == LicenseStatus.INVALID_SIGNATURE
    assert info.is_valid is False


def test_license_expiration_and_grace_period():
    private_key = Ed25519PrivateKey.generate()
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    service = LicensingService(
        public_key_pem_or_b64=public_key_pem,
        dev_mode_override=False,
    )

    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    expired_date = now - timedelta(days=2)  # Expired 2 days ago, grace is 7 days

    grace_key = generate_test_license(
        private_key=private_key,
        expires_at=expired_date,
        grace_period_days=7,
    )

    info_grace = service.load_license_key(grace_key, current_time=now)
    assert info_grace.status == LicenseStatus.GRACE_PERIOD
    assert info_grace.is_valid is True
    assert "grace period" in info_grace.message.lower()

    # Expired past grace period (e.g. 10 days ago)
    long_expired_date = now - timedelta(days=10)
    expired_key = generate_test_license(
        private_key=private_key,
        expires_at=long_expired_date,
        grace_period_days=7,
    )

    info_expired = service.load_license_key(expired_key, current_time=now)
    assert info_expired.status == LicenseStatus.EXPIRED
    assert info_expired.is_valid is False


def test_development_mode_override():
    service = LicensingService(dev_mode_override=True)
    info = service.get_license_info()

    assert info.status == LicenseStatus.DEV_MODE
    assert info.edition == ProductEdition.DEV
    assert info.is_valid is True
    assert info.max_accounts_allowed() >= 99999
    assert info.max_devices_allowed() >= 99999
    # Every feature flag must be unlocked in dev mode
    for flag in FeatureFlag:
        assert service.can_use_feature(flag) is True


def test_no_private_keys_in_source():
    """Verify that only public key material exists in licensing service."""
    import inspect

    import sp_farms.application.licensing_service as lic_mod

    src = inspect.getsource(lic_mod)
    assert "PRIVATE KEY" not in src
    assert "Ed25519PrivateKey" not in src
    assert "generate()" not in src
