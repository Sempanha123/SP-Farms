from typing import Protocol

from sp_farms.domain.account_onboarding import AccountOnboardingRequest, OnboardingSource


class AuthorizedAccountConnector(Protocol):
    source: OnboardingSource

    def fetch_authorized_metadata(self) -> AccountOnboardingRequest: ...
