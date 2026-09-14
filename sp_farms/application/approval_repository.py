"""Port protocol for persisting approval requests and review policy rules."""

from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.approvals import (
    ApprovalActionType,
    ApprovalPolicyRule,
    ApprovalRequest,
    ApprovalStatus,
)


class ApprovalRepositoryPort(Protocol):
    """Repository port for approval requests and policies."""

    def save_request(self, request: ApprovalRequest) -> ApprovalRequest: ...

    def get_request(self, request_id: str) -> ApprovalRequest | None: ...

    def list_requests(
        self,
        status: ApprovalStatus | None = None,
        action_type: ApprovalActionType | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[ApprovalRequest]: ...

    def delete_request(self, request_id: str) -> None: ...

    def save_policy_rule(self, rule: ApprovalPolicyRule) -> ApprovalPolicyRule: ...

    def list_policy_rules(self) -> Sequence[ApprovalPolicyRule]: ...

    def delete_policy_rule(self, rule_id: str) -> None: ...
