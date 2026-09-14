from collections.abc import Iterable
from dataclasses import replace

from sp_farms.application.account_onboarding import AuthorizedAccountConnector
from sp_farms.application.account_service import AccountService
from sp_farms.domain.account_onboarding import (
    AccountOnboardingRequest,
    OnboardingSource,
    export_account_metadata,
    parse_onboarding_document,
    validate_onboarding_request,
)
from sp_farms.domain.accounts import Account


class AccountOnboardingService:
    def __init__(
        self,
        accounts: AccountService,
        connectors: Iterable[AuthorizedAccountConnector] = (),
    ) -> None:
        self._accounts = accounts
        self._connectors = {connector.source: connector for connector in connectors}

    def onboard(self, request: AccountOnboardingRequest) -> Account:
        normalized = validate_onboarding_request(request)
        if normalized.source in {
            OnboardingSource.OFFICIAL_FACEBOOK,
            OnboardingSource.AUTHORIZED_SESSION,
        }:
            raise ValueError("Connected account onboarding requires a configured connector")
        return self._save(normalized)

    def import_metadata(self, payload: str) -> Account:
        return self._save(parse_onboarding_document(payload))

    def connect(self, source: OnboardingSource) -> Account:
        connector = self._connectors.get(source)
        if connector is None:
            raise ValueError(f"No connector is configured for {source.value}")
        request = validate_onboarding_request(connector.fetch_authorized_metadata())
        if request.source is not source:
            raise ValueError("Connector returned metadata for a different source")
        return self._save(request)

    def export_metadata(self, account_id: str) -> str:
        return export_account_metadata(self._accounts.get_account(account_id))

    def _save(self, request: AccountOnboardingRequest) -> Account:
        account = self._accounts.new_account(
            request.display_name,
            request.platform_uid,
            request.primary_email,
        )
        return self._accounts.save_account(
            replace(
                account,
                first_name=request.first_name,
                last_name=request.last_name,
                avatar_ref=request.avatar_ref,
                birthday=request.birthday,
                gender=request.gender,
                recovery_email=request.recovery_email,
                phone=request.phone,
                country=request.country,
                locale=request.locale,
                timezone=request.timezone,
                account_created_at=request.account_created_at,
                status=request.status,
                two_factor_enabled=request.two_factor_enabled,
                notes=request.notes,
                preferred_app=request.preferred_app,
                last_login_at=request.last_login_at,
                last_verified_at=request.last_verified_at,
                page_count=request.page_count,
                group_count=request.group_count,
                permission_state=request.permission_state,
                security_state=request.security_state,
            )
        )
