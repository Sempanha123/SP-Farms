from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class TokenHealthState(StrEnum):
    HEALTHY = "healthy"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    REVOKED = "revoked"
    MISSING = "missing"


class AuthState(StrEnum):
    AUTHENTICATED = "authenticated"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNLINKED = "unlinked"
    CHALLENGE_REQUIRED = "challenge_required"


class SecurityEventCategory(StrEnum):
    AUTHENTICATION = "authentication"
    TOKEN_LIFECYCLE = "token_lifecycle"
    PERMISSIONS = "permissions"
    SESSION_HEALTH = "session_health"
    VAULT_INTEGRITY = "vault_integrity"
    BACKUP_ENCRYPTION = "backup_encryption"


class SecuritySeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    id: str
    category: SecurityEventCategory
    severity: SecuritySeverity
    title: str
    description: str
    remediation: str
    created_at: datetime
    account_id: str | None = None
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class AccountSecurityAudit:
    account_id: str
    display_name: str
    platform_uid: str
    auth_state: AuthState
    token_health: TokenHealthState
    token_expires_at: datetime | None
    days_until_expiration: int | None
    two_factor_enabled: bool
    session_stale: bool
    last_verified_at: datetime | None
    granted_scopes: tuple[str, ...]
    missing_scopes: tuple[str, ...]
    vault_synced: bool
    backup_encrypted: bool
    security_score: int
    warnings: tuple[str, ...] = field(default_factory=tuple)
    remediation_steps: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_action_required(self) -> bool:
        return (
            self.auth_state
            in (
                AuthState.EXPIRED,
                AuthState.REVOKED,
                AuthState.CHALLENGE_REQUIRED,
            )
            or self.token_health in (TokenHealthState.EXPIRED, TokenHealthState.REVOKED)
            or not self.two_factor_enabled
            or self.session_stale
        )


@dataclass(frozen=True, slots=True)
class SystemSecurityReport:
    total_accounts: int
    secure_accounts: int
    warning_accounts: int
    critical_accounts: int
    expiring_tokens_count: int
    expired_tokens_count: int
    missing_2fa_count: int
    stale_sessions_count: int
    vault_healthy: bool
    backup_encryption_state: str
    system_score: int
    recent_events: tuple[SecurityEvent, ...] = field(default_factory=tuple)


def calculate_security_score(
    has_2fa: bool,
    token_health: TokenHealthState,
    session_stale: bool,
    vault_synced: bool,
    missing_scopes_count: int,
    auth_state: AuthState,
) -> int:
    score = 100
    if not has_2fa:
        score -= 25
    if token_health == TokenHealthState.EXPIRED:
        score -= 35
    elif token_health == TokenHealthState.EXPIRING_SOON:
        score -= 15
    elif token_health == TokenHealthState.REVOKED:
        score -= 40
    elif token_health == TokenHealthState.MISSING:
        score -= 20

    if session_stale:
        score -= 15
    if not vault_synced:
        score -= 15
    if missing_scopes_count > 0:
        score -= min(15, missing_scopes_count * 5)
    if auth_state == AuthState.CHALLENGE_REQUIRED:
        score -= 30

    return max(0, min(100, score))
