from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.composer_dialog import ComposerDialog
from sp_farms.application.composer_service import ComposerService
from sp_farms.application.content_service import ContentService
from sp_farms.domain.accounts import Account
from sp_farms.domain.assets import AssetHealthState, Group, Page
from sp_farms.domain.composer import (
    DraftPost,
    PostType,
    PublishDestination,
    PublishDestinationType,
    validate_draft_post,
)
from sp_farms.domain.content import ContentItem, ContentStatus, MediaAsset, MediaMetadata, MediaType
from sp_farms.infrastructure.assets_repository import SqlAlchemyAssetRepository
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyContentRepository,
    run_migrations,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


@pytest.fixture
def test_env() -> Generator[tuple[Database, ContentService, ComposerService, Path], None, None]:
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "composer_test.db"
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        database = Database(db_path)
        run_migrations(database, Path(__file__).resolve().parents[1] / "migrations")
        clock = SystemClock()

        content_service = ContentService(
            unit_of_work=database.unit_of_work,
            content_repository_factory=SqlAlchemyContentRepository,
            clock=clock,
            storage_dir=storage_dir,
        )

        composer_service = ComposerService(
            unit_of_work=database.unit_of_work,
            content_repo_factory=SqlAlchemyContentRepository,
            asset_repo_factory=SqlAlchemyAssetRepository,
            clock=clock,
        )

        yield database, content_service, composer_service, tmp_path
        database.close()


def test_draft_post_creation_and_validation() -> None:
    # 1. Empty draft validation
    empty_draft = DraftPost.create(title="Empty")
    issues = validate_draft_post(empty_draft)
    assert any(i.field == "caption" and i.severity == "error" for i in issues)
    assert any(i.field == "destination" and i.severity == "error" for i in issues)

    # 2. Valid Feed draft
    page_dest = PublishDestination(
        id="page_1",
        name="Test Page",
        destination_type=PublishDestinationType.PAGE,
        account_id="acc_1",
        native_id="123456",
        can_publish_reels=True,
        can_publish_stories=True,
        supports_first_comment=True,
        supports_location=True,
    )

    valid_draft = DraftPost.create(
        title="Promo",
        post_type=PostType.FEED,
        destination=page_dest,
        caption="Check out our fresh harvest! #organic",
        location_name="Sacramento, CA",
        first_comment="Order link: https://example.com",
    )
    issues = validate_draft_post(valid_draft)
    assert len(issues) == 0


def test_destination_capability_rules() -> None:
    group_dest = PublishDestination(
        id="group_1",
        name="Community Group",
        destination_type=PublishDestinationType.GROUP,
        account_id="acc_1",
        native_id="987654",
        can_publish_reels=False,
        can_publish_stories=False,
        supports_first_comment=False,
        supports_location=False,
    )

    # Group cannot publish Reels
    reel_draft = DraftPost.create(
        title="Reel on Group",
        post_type=PostType.REEL,
        destination=group_dest,
        caption="Reel video",
        media_asset_ids=["asset_video_1"],
    )
    media_map = {"asset_video_1": "VIDEO"}
    issues = validate_draft_post(reel_draft, media_types_by_id=media_map)
    assert any("does not support Reel publishing" in i.message for i in issues)

    # Group cannot have first comment
    comment_draft = DraftPost.create(
        title="Group with comment",
        post_type=PostType.FEED,
        destination=group_dest,
        caption="Normal group post",
        first_comment="First comment not supported here",
    )
    issues = validate_draft_post(comment_draft)
    assert any(i.field == "first_comment" and i.severity == "error" for i in issues)


def test_reel_and_story_media_constraints() -> None:
    page_dest = PublishDestination(
        id="page_1",
        name="Farm Page",
        destination_type=PublishDestinationType.PAGE,
        account_id="acc_1",
        native_id="123",
        can_publish_reels=True,
        can_publish_stories=True,
    )

    # Reel without media
    reel_no_media = DraftPost.create(
        title="Empty Reel",
        post_type=PostType.REEL,
        destination=page_dest,
        caption="Watch this!",
    )
    issues = validate_draft_post(reel_no_media)
    assert any("Reels require exactly one video asset" in i.message for i in issues)

    # Reel with image media
    reel_with_image = DraftPost.create(
        title="Image Reel",
        post_type=PostType.REEL,
        destination=page_dest,
        caption="Watch this!",
        media_asset_ids=["asset_img_1"],
    )
    issues = validate_draft_post(reel_with_image, media_types_by_id={"asset_img_1": "IMAGE"})
    assert any("Reel media must be a video file" in i.message for i in issues)

    # Valid Reel
    valid_reel = DraftPost.create(
        title="Valid Reel",
        post_type=PostType.REEL,
        destination=page_dest,
        caption="Farm work reel #trending",
        media_asset_ids=["asset_vid_1"],
    )
    issues = validate_draft_post(valid_reel, media_types_by_id={"asset_vid_1": "VIDEO"})
    assert len(issues) == 0


def test_draft_save_and_load_roundtrip(
    test_env: tuple[Database, ContentService, ComposerService, Path],
) -> None:
    _, _, composer_service, _ = test_env

    page_dest = PublishDestination(
        id="page_100",
        name="Official Page",
        destination_type=PublishDestinationType.PAGE,
        account_id="acc_99",
        native_id="meta_100",
    )

    future_time = datetime.now(UTC) + timedelta(days=2)
    draft = DraftPost.create(
        title="Spring Planting Announcement",
        post_type=PostType.FEED,
        destination=page_dest,
        caption="Spring is here! We are planting heirloom tomatoes today.",
        media_asset_ids=["asset_1", "asset_2"],
        thumbnail_asset_id="asset_1",
        location_name="Sonoma Valley, CA",
        first_comment="Pre-order open at our farm stand!",
        scheduled_at=future_time,
        requires_approval=True,
    )

    saved_item = composer_service.save_draft(draft)
    assert isinstance(saved_item, ContentItem)
    assert saved_item.id == draft.id
    assert saved_item.status == ContentStatus.DRAFT
    assert "needs_approval" in saved_item.tags

    loaded = composer_service.load_draft(saved_item.id)
    assert loaded is not None
    assert loaded.id == draft.id
    assert loaded.title == "Spring Planting Announcement"
    assert loaded.post_type == PostType.FEED
    assert loaded.destination is not None
    assert loaded.destination.id == "page_100"
    assert loaded.destination.name == "Official Page"
    assert loaded.caption == "Spring is here! We are planting heirloom tomatoes today."
    assert loaded.media_asset_ids == ("asset_1", "asset_2")
    assert loaded.thumbnail_asset_id == "asset_1"
    assert loaded.location_name == "Sonoma Valley, CA"
    assert loaded.first_comment == "Pre-order open at our farm stand!"
    assert loaded.requires_approval is True
    assert loaded.scheduled_at is not None
    assert abs((loaded.scheduled_at - future_time).total_seconds()) < 1.0


def test_duplicate_caption_detection(
    test_env: tuple[Database, ContentService, ComposerService, Path],
) -> None:
    _, content_service, composer_service, _ = test_env

    # Populate an existing library post
    content_service.create_content_item(
        title="Existing Post",
        body="Fresh organic strawberries now available at the farm stand every weekend!",
    )

    # Exact match check
    exact_warning = composer_service.check_duplicate(
        "Fresh organic strawberries now available at the farm stand every weekend!"
    )
    assert exact_warning.is_duplicate is True
    assert exact_warning.similarity_score == 1.0
    assert "Exact duplicate" in exact_warning.reason

    # High similarity (>85%) check
    similar_warning = composer_service.check_duplicate(
        "Fresh organic strawberries now available at the farm stand every weekend."
    )
    assert similar_warning.is_duplicate is True
    assert similar_warning.similarity_score > 0.85

    # Completely different content
    diff_warning = composer_service.check_duplicate(
        "New tractors arrived for the autumn harvest preparation."
    )
    assert diff_warning.is_duplicate is False


def test_authorized_destinations_discovery(
    test_env: tuple[Database, ContentService, ComposerService, Path],
) -> None:
    database, _, composer_service, _ = test_env
    now = datetime.now(UTC)

    # Pre-seed account for foreign key constraint
    acc = Account.create(
        display_name="Farm Admin",
        platform_uid="fb-uid-100",
        primary_email="admin@spfarms.local",
        now=now,
    )
    with database.unit_of_work() as uow:
        SqlAlchemyAccountRepository(uow).save_account(acc)
        uow.commit()

    # Seed pages and groups
    with database.unit_of_work() as uow:
        repo = SqlAlchemyAssetRepository(uow)
        p = Page(
            id="page_local_1",
            account_id=acc.id,
            page_id="111222",
            name="Green Fields Page",
            access_token_ref="sec_1",
            tasks=("MANAGE", "CREATE_CONTENT"),
            category="Agriculture",
            followers_count=500,
            health=AssetHealthState.HEALTHY,
        )
        g = Group(
            id="group_local_1",
            account_id=acc.id,
            group_id="333444",
            name="Organic Farmers Group",
            member_count=1200,
            privacy="CLOSED",
            health=AssetHealthState.HEALTHY,
        )
        repo.save_page(p)
        repo.save_group(g)
        uow.commit()

    destinations = composer_service.get_authorized_destinations()
    assert len(destinations) == 2

    page_d = next(d for d in destinations if d.destination_type == PublishDestinationType.PAGE)
    assert "Green Fields Page" in page_d.name
    assert page_d.can_publish_reels is True
    assert page_d.supports_first_comment is True

    group_d = next(d for d in destinations if d.destination_type == PublishDestinationType.GROUP)
    assert "Organic Farmers Group" in group_d.name
    assert group_d.can_publish_reels is False
    assert group_d.supports_first_comment is False


def test_composer_dialog_ui_lifecycle(
    qapp: QApplication,
    test_env: tuple[Database, ContentService, ComposerService, Path],
) -> None:
    _, content_service, composer_service, tmp_path = test_env

    # Seed an asset
    dummy_img = tmp_path / "img.png"
    dummy_img.write_bytes(b"dummy image")
    asset = MediaAsset(
        id="asset_test_1",
        file_path=str(dummy_img),
        file_name="sample_seed.png",
        media_type=MediaType.IMAGE,
        metadata=MediaMetadata(
            mime_type="image/png",
            file_size_bytes=100,
            sha256_hash="abc",
            width=800,
            height=600,
            aspect_ratio="4:3",
        ),
    )
    with content_service._uow() as uow:
        repo = content_service._repo_factory(uow)
        repo.add_asset(asset)
        uow.commit()

    dialog = ComposerDialog(
        composer_service=composer_service,
        content_service=content_service,
    )
    assert dialog.windowTitle() == "SP-Farms — Post & Reel Composer"
    assert dialog.txt_title.text() == ""
    assert dialog.txt_caption.toPlainText() == ""
    assert dialog.lbl_preview_comment.isVisible() is False

    # Simulate typing caption
    sample_text = "Exciting news from SP-Farms!"
    dialog.txt_caption.setPlainText(sample_text)
    assert f"{len(sample_text)} chars" in dialog.lbl_char_count.text()
    assert "Exciting news" in dialog.lbl_preview_caption.text()

    # Simulate post type toggle
    dialog.cmb_post_type.setCurrentIndex(1)  # Reel
    assert dialog.chip_preview_type.text() == "Reel"

    dialog.close()
