import base64
import json
import logging
import os
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sp_farms.domain.licensing import (
    FeatureFlag,
    LicenseInfo,
    LicensePayload,
    LicenseStatus,
    ProductEdition,
)

logger = logging.getLogger(__name__)

# Default Embedded Public Key (RFC 8032 Ed25519 Raw 32-byte public key encoded in Base64)
# Note: ONLY public key material is present here. No private signing keys!
DEFAULT_PUBLIC_KEY_B64 = "MCowBQYDK2VwAyEA9rQe7pW4qN6vL4W2V2Y+rXQe7pW4qN6vL4W2V2Y+rXQ="


class LicensingService:
    """Manages cryptographic license validation, grace periods, and feature gating."""

    def __init__(
        self,
        public_key_pem_or_b64: str | bytes | None = None,
        dev_mode_override: bool | None = None,
    ) -> None:
        self.dev_mode = (
            dev_mode_override
            if dev_mode_override is not None
            else bool(os.getenv("SP_FARMS_DEV_MODE", "0") in ("1", "true", "True"))
        )
        self._public_key = self._load_public_key(public_key_pem_or_b64 or DEFAULT_PUBLIC_KEY_B64)
        self._current_license: LicenseInfo = self._default_license()

    def _default_license(self) -> LicenseInfo:
        if self.dev_mode:
            return LicenseInfo(
                status=LicenseStatus.DEV_MODE,
                edition=ProductEdition.DEV,
                message="Running in Development Mode (all features unlocked)",
                is_valid=True,
            )
        return LicenseInfo(
            status=LicenseStatus.UNLICENSED,
            edition=ProductEdition.FREE,
            message="Community Free Edition (limited to 5 accounts, 2 devices)",
            is_valid=True,
        )

    def _load_public_key(self, key_data: str | bytes) -> Ed25519PublicKey | None:
        try:
            if isinstance(key_data, str):
                if "BEGIN PUBLIC KEY" in key_data:
                    return serialization.load_pem_public_key(key_data.encode("utf-8"))  # type: ignore
                # Raw base64 DER or key bytes
                raw = base64.b64decode(key_data)
                try:
                    return serialization.load_der_public_key(raw)  # type: ignore
                except Exception:
                    return Ed25519PublicKey.from_public_bytes(raw[:32])
            elif isinstance(key_data, bytes):
                try:
                    return serialization.load_pem_public_key(key_data)  # type: ignore
                except Exception:
                    return Ed25519PublicKey.from_public_bytes(key_data[:32])
        except Exception as e:
            logger.warning("Could not initialize license public key: %s", e)
            return None
        return None

    def get_license_info(self) -> LicenseInfo:
        """Return the currently effective license status and permissions."""
        if self.dev_mode:
            return LicenseInfo(
                status=LicenseStatus.DEV_MODE,
                edition=ProductEdition.DEV,
                message="Developer Mode Active",
                is_valid=True,
            )
        return self._current_license

    def can_use_feature(self, feature: FeatureFlag | str) -> bool:
        return self.get_license_info().has_feature(feature)

    def load_license_key(
        self,
        license_string: str,
        current_time: datetime | None = None,
    ) -> LicenseInfo:
        """Parse and cryptographically verify a license key string."""
        now = current_time or datetime.now(UTC)

        if self.dev_mode:
            self._current_license = LicenseInfo(
                status=LicenseStatus.DEV_MODE,
                edition=ProductEdition.DEV,
                message="Developer Mode Override Active",
                is_valid=True,
            )
            return self._current_license

        raw = license_string.strip()
        if not raw:
            self._current_license = self._default_license()
            return self._current_license

        parts = raw.split(".")
        if len(parts) != 2:
            self._current_license = LicenseInfo(
                status=LicenseStatus.CORRUPTED,
                edition=ProductEdition.FREE,
                message="Malformed license key format",
                is_valid=False,
            )
            return self._current_license

        payload_b64, signature_b64 = parts[0], parts[1]

        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
            signature = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
            data = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            self._current_license = LicenseInfo(
                status=LicenseStatus.CORRUPTED,
                edition=ProductEdition.FREE,
                message=f"Failed decoding license payload: {e}",
                is_valid=False,
            )
            return self._current_license

        # Cryptographic Signature Verification
        if self._public_key is not None:
            try:
                self._public_key.verify(signature, payload_bytes)
            except InvalidSignature:
                self._current_license = LicenseInfo(
                    status=LicenseStatus.INVALID_SIGNATURE,
                    edition=ProductEdition.FREE,
                    message="Digital signature verification failed: forged or tampered license",
                    is_valid=False,
                )
                return self._current_license
            except Exception as e:
                self._current_license = LicenseInfo(
                    status=LicenseStatus.INVALID_SIGNATURE,
                    edition=ProductEdition.FREE,
                    message=f"Signature check error: {e}",
                    is_valid=False,
                )
                return self._current_license

        # Parse Payload
        try:
            issued_at = datetime.fromisoformat(data["issued_at"])
            expires_at = (
                datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
            )
            edition = ProductEdition(data.get("edition", "pro"))
            feature_flags = tuple(FeatureFlag(f) for f in data.get("feature_flags", ()))
            grace_days = int(data.get("grace_period_days", 7))

            payload = LicensePayload(
                license_id=str(data.get("license_id", "")),
                licensee_name=str(data.get("licensee_name", "")),
                licensee_email=str(data.get("licensee_email", "")),
                edition=edition,
                issued_at=issued_at,
                expires_at=expires_at,
                max_accounts=int(data.get("max_accounts", 100)),
                max_devices=int(data.get("max_devices", 20)),
                feature_flags=feature_flags,
                grace_period_days=grace_days,
                metadata=dict(data.get("metadata", {})),
            )
        except Exception as e:
            self._current_license = LicenseInfo(
                status=LicenseStatus.CORRUPTED,
                edition=ProductEdition.FREE,
                message=f"Corrupt license schema: {e}",
                is_valid=False,
            )
            return self._current_license

        # Check Expiry & Grace Period
        if expires_at is not None and now > expires_at:
            grace_deadline = expires_at + timedelta(days=grace_days)
            if now <= grace_deadline:
                self._current_license = LicenseInfo(
                    status=LicenseStatus.GRACE_PERIOD,
                    edition=edition,
                    payload=payload,
                    message=(
                        f"License expired on {expires_at.date()}. "
                        f"Grace period active until {grace_deadline.date()}."
                    ),
                    is_valid=True,
                )
                return self._current_license

            self._current_license = LicenseInfo(
                status=LicenseStatus.EXPIRED,
                edition=ProductEdition.FREE,
                payload=payload,
                message=f"License expired on {expires_at.date()}. Please renew.",
                is_valid=False,
            )
            return self._current_license

        # Valid active license
        self._current_license = LicenseInfo(
            status=LicenseStatus.ACTIVE,
            edition=edition,
            payload=payload,
            message=f"Active {edition.upper()} License for {payload.licensee_name}",
            is_valid=True,
        )
        return self._current_license
