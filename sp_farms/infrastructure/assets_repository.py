import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from sp_farms.application.asset_repository import AssetRepository
from sp_farms.domain.assets import AssetHealthState, Group, Page
from sp_farms.infrastructure.database import Base, _as_utc, _optional_as_utc


class FacebookPageModel(Base):
    __tablename__ = "facebook_pages"
    __table_args__ = (
        UniqueConstraint("account_id", "page_id", name="uq_facebook_pages_account_page"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tasks: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    access_token_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    can_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    followers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    health: Mapped[str] = mapped_column(String(50), nullable=False, default="healthy")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_entity(cls, page: Page) -> "FacebookPageModel":
        return cls(
            id=page.id,
            account_id=page.account_id,
            page_id=page.page_id,
            name=page.name,
            category=page.category,
            tasks=json.dumps(list(page.tasks)),
            access_token_ref=page.access_token_ref,
            can_publish=page.can_publish,
            followers_count=page.followers_count,
            likes_count=page.likes_count,
            link=page.link,
            health=page.health.value,
            last_synced_at=page.last_synced_at,
            created_at=page.created_at,
            updated_at=page.updated_at,
        )

    def update_from_entity(self, page: Page) -> None:
        self.name = page.name
        self.category = page.category
        self.tasks = json.dumps(list(page.tasks))
        self.access_token_ref = page.access_token_ref
        self.can_publish = page.can_publish
        self.followers_count = page.followers_count
        self.likes_count = page.likes_count
        self.link = page.link
        self.health = page.health.value
        self.last_synced_at = page.last_synced_at
        self.updated_at = page.updated_at

    def to_entity(self) -> Page:
        raw_tasks = json.loads(self.tasks) if self.tasks else []
        return Page(
            id=self.id,
            account_id=self.account_id,
            page_id=self.page_id,
            name=self.name,
            category=self.category,
            tasks=tuple(str(t) for t in raw_tasks),
            access_token_ref=self.access_token_ref,
            can_publish=self.can_publish,
            followers_count=self.followers_count,
            likes_count=self.likes_count,
            link=self.link,
            health=AssetHealthState(self.health),
            last_synced_at=_optional_as_utc(self.last_synced_at),
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class FacebookGroupModel(Base):
    __tablename__ = "facebook_groups"
    __table_args__ = (
        UniqueConstraint("account_id", "group_id", name="uq_facebook_groups_account_group"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    privacy: Mapped[str] = mapped_column(String(50), nullable=False, default="PUBLIC")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="MEMBER")
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_post: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health: Mapped[str] = mapped_column(String(50), nullable=False, default="healthy")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_entity(cls, group: Group) -> "FacebookGroupModel":
        return cls(
            id=group.id,
            account_id=group.account_id,
            group_id=group.group_id,
            name=group.name,
            privacy=group.privacy,
            role=group.role,
            member_count=group.member_count,
            can_post=group.can_post,
            health=group.health.value,
            last_synced_at=group.last_synced_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def update_from_entity(self, group: Group) -> None:
        self.name = group.name
        self.privacy = group.privacy
        self.role = group.role
        self.member_count = group.member_count
        self.can_post = group.can_post
        self.health = group.health.value
        self.last_synced_at = group.last_synced_at
        self.updated_at = group.updated_at

    def to_entity(self) -> Group:
        return Group(
            id=self.id,
            account_id=self.account_id,
            group_id=self.group_id,
            name=self.name,
            privacy=self.privacy,
            role=self.role,
            member_count=self.member_count,
            can_post=self.can_post,
            health=AssetHealthState(self.health),
            last_synced_at=_optional_as_utc(self.last_synced_at),
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class SqlAlchemyAssetRepository(AssetRepository):
    """SQLAlchemy implementation of AssetRepository supporting both UnitOfWork and Session."""

    def __init__(self, session_or_uow: Any) -> None:
        if isinstance(session_or_uow, Session):
            self._session_obj: Session | None = session_or_uow
            self._uow: Any | None = None
        else:
            self._session_obj = None
            self._uow = session_or_uow

    @property
    def _session(self) -> Session:
        if self._uow is not None:
            if hasattr(self._uow, "_active_session"):
                sess = self._uow._active_session()
                if isinstance(sess, Session):
                    return sess
            if hasattr(self._uow, "session") and isinstance(self._uow.session, Session):
                return self._uow.session
        assert self._session_obj is not None
        return self._session_obj

    def save_page(self, page: Page) -> None:
        model = (
            self._session.query(FacebookPageModel)
            .filter_by(account_id=page.account_id, page_id=page.page_id)
            .one_or_none()
        )
        if model is None:
            self._session.add(FacebookPageModel.from_entity(page))
        else:
            model.update_from_entity(page)
        self._session.flush()

    def get_page(self, id: str) -> Page | None:
        model = self._session.get(FacebookPageModel, id)
        return model.to_entity() if model else None

    def get_page_by_meta_id(self, account_id: str, page_id: str) -> Page | None:
        model = (
            self._session.query(FacebookPageModel)
            .filter_by(account_id=account_id, page_id=page_id)
            .one_or_none()
        )
        return model.to_entity() if model else None

    def list_pages_by_account(self, account_id: str) -> list[Page]:
        return self.list_all_pages(account_id=account_id)

    def list_all_pages(self, account_id: str | None = None) -> list[Page]:
        query = self._session.query(FacebookPageModel)
        if account_id is not None:
            query = query.filter_by(account_id=account_id)
        models = query.order_by(FacebookPageModel.name).all()
        return [m.to_entity() for m in models]

    def delete_page(self, id: str) -> None:
        model = self._session.get(FacebookPageModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def save_group(self, group: Group) -> None:
        model = (
            self._session.query(FacebookGroupModel)
            .filter_by(account_id=group.account_id, group_id=group.group_id)
            .one_or_none()
        )
        if model is None:
            self._session.add(FacebookGroupModel.from_entity(group))
        else:
            model.update_from_entity(group)
        self._session.flush()

    def get_group(self, id: str) -> Group | None:
        model = self._session.get(FacebookGroupModel, id)
        return model.to_entity() if model else None

    def get_group_by_meta_id(self, account_id: str, group_id: str) -> Group | None:
        model = (
            self._session.query(FacebookGroupModel)
            .filter_by(account_id=account_id, group_id=group_id)
            .one_or_none()
        )
        return model.to_entity() if model else None

    def list_groups_by_account(self, account_id: str) -> list[Group]:
        return self.list_all_groups(account_id=account_id)

    def list_all_groups(self, account_id: str | None = None) -> list[Group]:
        query = self._session.query(FacebookGroupModel)
        if account_id is not None:
            query = query.filter_by(account_id=account_id)
        models = query.order_by(FacebookGroupModel.name).all()
        return [m.to_entity() for m in models]

    def delete_group(self, id: str) -> None:
        model = self._session.get(FacebookGroupModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def mark_missing_pages_stale(self, account_id: str, active_page_ids: Sequence[str]) -> int:
        query = self._session.query(FacebookPageModel).filter(
            FacebookPageModel.account_id == account_id
        )
        if active_page_ids:
            query = query.filter(~FacebookPageModel.page_id.in_(active_page_ids))

        stale_models = query.all()
        for m in stale_models:
            m.health = AssetHealthState.STALE.value
        if stale_models:
            self._session.flush()
        return len(stale_models)

    def mark_missing_groups_stale(self, account_id: str, active_group_ids: Sequence[str]) -> int:
        query = self._session.query(FacebookGroupModel).filter(
            FacebookGroupModel.account_id == account_id
        )
        if active_group_ids:
            query = query.filter(~FacebookGroupModel.group_id.in_(active_group_ids))

        stale_models = query.all()
        for m in stale_models:
            m.health = AssetHealthState.STALE.value
        if stale_models:
            self._session.flush()
        return len(stale_models)
