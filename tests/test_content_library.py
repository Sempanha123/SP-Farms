from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.content_workspace import ContentWorkspace
from sp_farms.application.content_service import (
    ContentService,
    calculate_aspect_ratio,
)
from sp_farms.domain.content import (
    CaptionTemplate,
    ContentStatus,
    HashtagSet,
    MediaAsset,
    MediaMetadata,
    MediaType,
)
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import (
    Database,
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
def temp_env() -> Generator[tuple[Database, ContentService, Path], None, None]:
    temp_dir = TemporaryDirectory()
    base_path = Path(temp_dir.name)
    db_path = base_path / "test_content.db"
    db = Database(db_path)
    migrations_path = Path(__file__).resolve().parents[1] / "migrations"
    run_migrations(db, migrations_path)

    clock = SystemClock()
    storage_dir = base_path / "content"
    service = ContentService(
        unit_of_work=db.unit_of_work,
        content_repository_factory=SqlAlchemyContentRepository,
        clock=clock,
        storage_dir=storage_dir,
    )
    yield db, service, base_path
    db.close()
    temp_dir.cleanup()


# -----------------------------------------------------------------------------
# Domain Tests
# -----------------------------------------------------------------------------


def test_media_metadata_formatting() -> None:
    meta1 = MediaMetadata("image/jpeg", 500, "hash1", 1920, 1080)
    assert meta1.formatted_size == "500 B"
    assert meta1.resolution_label == "1920x1080"

    meta2 = MediaMetadata("video/mp4", 1024 * 1024 * 5, "hash2", 1280, 720, 15.5)
    assert meta2.formatted_size == "5.0 MB"
    assert meta2.resolution_label == "1280x720"


def test_media_asset_creation_and_updates() -> None:
    meta = MediaMetadata("image/png", 2048, "hash_abc", 800, 600)
    asset = MediaAsset.create(
        file_path="/path/test.png",
        file_name="test.png",
        media_type=MediaType.IMAGE,
        metadata=meta,
        folder="promos",
        tags=["fresh", "promo", "fresh"],  # Should be deduplicated & sorted
        is_favorite=True,
    )
    assert asset.folder == "promos"
    assert asset.tags == ("fresh", "promo")
    assert asset.is_favorite is True
    assert asset.is_archived is False

    updated = asset.with_updates(folder="campaign1", is_favorite=False, is_archived=True)
    assert updated.folder == "campaign1"
    assert updated.is_favorite is False
    assert updated.is_archived is True
    assert updated.id == asset.id


def test_caption_template_rendering() -> None:
    template = CaptionTemplate.create(
        name="Flash Sale",
        content="Don't miss out! Get {discount}% off our {product} today only! Visit {link}",
        variables=["discount", "product", "link"],
        tags=["promo", "sale"],
    )
    rendered = template.render(
        {
            "discount": "25",
            "product": "Organic Honey",
            "link": "https://spfarms.example/honey",
        }
    )
    assert (
        rendered
        == "Don't miss out! Get 25% off our Organic Honey today only! Visit https://spfarms.example/honey"
    )


def test_hashtag_set_normalization() -> None:
    hset = HashtagSet.create(
        name="Farm Life",
        hashtags=["nature", "#organic", " farming ", "#nature"],
        category="agriculture",
    )
    assert hset.hashtags == ("#nature", "#organic", "#farming")
    assert hset.category == "agriculture"


def test_aspect_ratio_detection() -> None:
    assert calculate_aspect_ratio(1920, 1080) == "16:9"
    assert calculate_aspect_ratio(1080, 1920) == "9:16"
    assert calculate_aspect_ratio(1000, 1000) == "1:1"
    assert calculate_aspect_ratio(800, 1000) == "4:5"
    assert calculate_aspect_ratio(1024, 768) == "4:3"
    assert calculate_aspect_ratio(None, 1080) is None


# -----------------------------------------------------------------------------
# Service & Repository Tests
# -----------------------------------------------------------------------------


def test_import_media_with_hash_deduplication(
    temp_env: tuple[Database, ContentService, Path],
) -> None:
    _, service, base_path = temp_env
    dummy_file = base_path / "sample_image.png"
    dummy_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"A" * 100)

    # First import -> creates asset
    asset1, is_new1 = service.import_media(
        dummy_file,
        folder="banners",
        tags=["spring", "sale"],
        is_favorite=True,
    )
    assert is_new1 is True
    assert asset1.file_name == "sample_image.png"
    assert asset1.folder == "banners"
    assert "spring" in asset1.tags
    assert asset1.is_favorite is True
    assert Path(asset1.file_path).exists()

    # Second import with identical content -> returns existing asset
    asset2, is_new2 = service.import_media(dummy_file, allow_duplicate=False)
    assert is_new2 is False
    assert asset2.id == asset1.id

    # Third import with allow_duplicate=True -> creates new asset
    asset3, is_new3 = service.import_media(dummy_file, allow_duplicate=True)
    assert is_new3 is True
    assert asset3.id != asset1.id


def test_asset_listing_filtering_and_search(
    temp_env: tuple[Database, ContentService, Path],
) -> None:
    _, service, base_path = temp_env
    f1 = base_path / "hero.png"
    f1.write_bytes(b"hero_data_123")
    f2 = base_path / "video.mp4"
    f2.write_bytes(b"video_data_456")

    a1, _ = service.import_media(f1, folder="hero_folder", tags=["main", "header"])
    a2, _ = service.import_media(f2, folder="video_folder", tags=["promo"])

    # List all
    all_assets = service.list_assets()
    assert len(all_assets) >= 2

    # Filter by folder
    hero_assets = service.list_assets(folder="hero_folder")
    assert len(hero_assets) == 1
    assert hero_assets[0].id == a1.id

    # Filter by tag
    promo_assets = service.list_assets(tag="promo")
    assert len(promo_assets) == 1
    assert promo_assets[0].id == a2.id

    # Search query
    searched = service.list_assets(search_query="hero")
    assert any(a.id == a1.id for a in searched)


def test_asset_favorite_archive_and_delete(
    temp_env: tuple[Database, ContentService, Path],
) -> None:
    _, service, base_path = temp_env
    f = base_path / "temp_to_delete.png"
    f.write_bytes(b"temp_image_data")

    asset, _ = service.import_media(f)
    assert asset.is_favorite is False
    assert asset.is_archived is False

    # Toggle favorite
    fav_asset = service.toggle_asset_favorite(asset.id)
    assert fav_asset is not None
    assert fav_asset.is_favorite is True

    # Archive
    arch_asset = service.archive_asset(asset.id)
    assert arch_asset is not None
    assert arch_asset.is_archived is True

    # Unarchive
    unarch_asset = service.unarchive_asset(asset.id)
    assert unarch_asset is not None
    assert unarch_asset.is_archived is False

    # Delete with file removal
    file_path = Path(asset.file_path)
    assert file_path.exists()
    deleted = service.delete_asset(asset.id, remove_files=True)
    assert deleted is True
    assert not file_path.exists()
    assert service.get_asset(asset.id) is None


def test_caption_template_and_hashtag_sets_lifecycle(
    temp_env: tuple[Database, ContentService, Path],
) -> None:
    _, service, _ = temp_env

    # Template
    template = service.create_caption_template(
        name="Daily Greeting",
        content="Good morning everyone from {location}!",
        variables=["location"],
    )
    assert template.name == "Daily Greeting"
    fetched_template = service.get_caption_template(template.id)
    assert fetched_template is not None
    assert fetched_template.variables == ("location",)

    # Hashtag Set
    hset = service.create_hashtag_set(
        name="Morning Routine",
        hashtags=["morning", "coffee", "farm"],
        category="daily",
    )
    assert len(hset.hashtags) == 3
    fetched_hset = service.get_hashtag_set(hset.id)
    assert fetched_hset is not None
    assert fetched_hset.name == "Morning Routine"

    # Content Item Composing
    item = service.create_content_item(
        title="Good Morning Post",
        body="Good morning everyone from the farm! Enjoy the sunshine!",
        hashtag_set_ids=[hset.id],
        caption_template_id=template.id,
        status=ContentStatus.READY,
    )
    assert item.title == "Good Morning Post"
    assert item.status == ContentStatus.READY

    # Deletions
    assert service.delete_caption_template(template.id) is True
    assert service.delete_hashtag_set(hset.id) is True
    assert service.delete_content_item(item.id) is True


# -----------------------------------------------------------------------------
# UI Component Tests
# -----------------------------------------------------------------------------


def test_content_workspace_ui_initialization(
    qapp: QApplication,
    temp_env: tuple[Database, ContentService, Path],
) -> None:
    _, service, base_path = temp_env
    # Add dummy assets
    f = base_path / "ui_test.jpg"
    f.write_bytes(b"ui_test_data")
    service.import_media(f, folder="ui_folder", tags=["ui", "test"])

    workspace = ContentWorkspace(service)
    assert workspace.tabs.count() == 3
    assert workspace.table_model.rowCount() >= 1

    # Check metrics
    assert int(workspace.metrics.value_labels[0].text()) >= 1

    # Check proxy model filtering
    workspace.search_input.setText("ui_test")
    assert workspace.proxy_model.rowCount() >= 1
    workspace.search_input.setText("non_existent_random_filename_123")
    assert workspace.proxy_model.rowCount() == 0

    workspace.search_input.clear()
    workspace.type_filter.setCurrentText("Images")
    assert workspace.proxy_model.rowCount() >= 1

    # Inspector selection
    workspace.table.selectRow(0)
    workspace._on_selection_changed()
    assert workspace.inspector.name_label.text() != "—"
