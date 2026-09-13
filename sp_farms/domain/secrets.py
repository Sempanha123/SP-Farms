from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SecretType(StrEnum):
    PASSWORD = "password"
    ACCESS_TOKEN = "access_token"
    COOKIE = "cookie"
    API_KEY = "api_key"
    RECOVERY_SECRET = "recovery_secret"
    NETWORK_CREDENTIAL = "network_credential"


@dataclass(frozen=True, slots=True)
class SecretReference:
    id: str
    secret_type: SecretType
    owner_id: str
    vault_ref: str
    created_at: datetime
    updated_at: datetime
