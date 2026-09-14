from collections.abc import Callable, Sequence
from dataclasses import replace
from uuid import uuid4

from sp_farms.application.accounts import AccountRepository
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.accounts import (
    Account,
    AccountCategory,
    AccountDeviceAssignment,
    AccountHealth,
    AccountTag,
    calculate_account_health,
    validate_account,
    validate_label,
)


class AccountService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        repository_factory: Callable[[UnitOfWork], AccountRepository],
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._clock = clock

    def list_accounts(self, include_archived: bool = False) -> Sequence[Account]:
        with self._unit_of_work_factory() as unit:
            return self._repository_factory(unit).list_accounts(include_archived)

    def get_account(self, account_id: str) -> Account:
        with self._unit_of_work_factory() as unit:
            account = self._repository_factory(unit).get_account(account_id)
        if account is None:
            raise ValueError(f"Account '{account_id}' not found")
        return account

    def create_account(
        self,
        display_name: str,
        platform_uid: str,
        primary_email: str,
    ) -> Account:
        account = Account.create(
            display_name,
            platform_uid,
            primary_email,
            self._clock.now(),
        )
        return self.save_account(account)

    def save_account(self, account: Account) -> Account:
        validate_account(account)
        now = self._clock.now()
        saved = replace(
            account,
            created_at=account.created_at or now,
            updated_at=now,
        )
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).save_account(saved)
            unit.commit()
        return saved

    def archive_account(self, account_id: str) -> Account:
        archived = self.get_account(account_id).archive(self._clock.now())
        return self.save_account(archived)

    def create_category(self, name: str, color: str = "neutral") -> AccountCategory:
        category = AccountCategory(str(uuid4()), validate_label(name), color)
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).save_category(category)
            unit.commit()
        return category

    def list_categories(self) -> Sequence[AccountCategory]:
        with self._unit_of_work_factory() as unit:
            return self._repository_factory(unit).list_categories()

    def create_tag(self, name: str, color: str = "neutral") -> AccountTag:
        tag = AccountTag(str(uuid4()), validate_label(name), color)
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).save_tag(tag)
            unit.commit()
        return tag

    def list_tags(self) -> Sequence[AccountTag]:
        with self._unit_of_work_factory() as unit:
            return self._repository_factory(unit).list_tags()

    def set_tags(self, account_id: str, tag_ids: Sequence[str]) -> Account:
        with self._unit_of_work_factory() as unit:
            repository = self._repository_factory(unit)
            repository.set_tags(account_id, tag_ids)
            unit.commit()
        return self.get_account(account_id)

    def assign_device(
        self,
        account_id: str,
        provider: str,
        external_id: str,
    ) -> Account:
        self.get_account(account_id)
        with self._unit_of_work_factory() as unit:
            self._repository_factory(unit).assign_device(
                AccountDeviceAssignment(account_id, provider, external_id)
            )
            unit.commit()
        return self.get_account(account_id)

    def health(self, account_id: str) -> AccountHealth:
        return calculate_account_health(self.get_account(account_id))
