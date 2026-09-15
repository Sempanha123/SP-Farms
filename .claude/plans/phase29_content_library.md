# Plan: Phase 29 — Content Library

## Objective
Implement Phase 29 (Content Library) per `SP-Farms-FULL-57-PHASES/phase29.txt`:
Reusable media and content storage, metadata extraction, hash duplicate detection, thumbnail cache, caption templates, hashtag sets, content items, search/filtering/folders/archive, drag/drop UI, and comprehensive test suite.

---

## 1. Architecture & Domain Layer
- **`sp_farms/domain/content.py`**:
  - Pure domain dataclasses with slots and immutability:
    - `MediaType` (StrEnum: `IMAGE`, `VIDEO`, `AUDIO`, `OTHER`)
    - `ContentStatus` (StrEnum: `DRAFT`, `READY`, `ARCHIVED`)
    - `MediaMetadata`: mime_type, file_size_bytes, width, height, duration_seconds, aspect_ratio, sha256_hash.
    - `MediaAsset`: id, file_path, file_name, metadata, thumbnail_path, folder, tags, is_favorite, is_archived, created_at, updated_at.
    - `CaptionTemplate`: id, name, content, variables, tags, is_favorite, created_at, updated_at with `.render(variables: dict[str, str])`.
    - `HashtagSet`: id, name, tags, category, is_favorite, created_at, updated_at with `.formatted_string()`.
    - `ContentItem`: id, title, body, media_asset_ids, hashtag_set_ids, caption_template_id, status, tags, folder, created_at, updated_at.

---

## 2. Database Migration & Persistence
- **`migrations/versions/0011_content_library.py`** (down_revision: `0010_audit_events`):
  - `media_assets` table with compound indexes on `(sha256_hash)`, `(folder)`, `(is_archived)`, `(is_favorite)`.
  - `caption_templates` table.
  - `hashtag_sets` table.
  - `content_items` table with foreign keys and indexes.
- **`sp_farms/application/content_repository.py`**:
  - `ContentRepositoryPort` typed protocol specifying all CRUD, search, filter, and pagination methods.
- **`sp_farms/infrastructure/database.py`**:
  - SQLAlchemy entity records: `MediaAssetRecord`, `CaptionTemplateRecord`, `HashtagSetRecord`, `ContentItemRecord`.
  - `SqlAlchemyContentRepository` adapter implementing `ContentRepositoryPort`.

---

## 3. Application Service
- **`sp_farms/application/content_service.py`**:
  - `ContentService`:
    - `import_media(source_path: Path, folder: str = "default", tags: Sequence[str] = (), is_favorite: bool = False, allow_duplicate: bool = False) -> tuple[MediaAsset, bool]`:
      - Computes streaming SHA-256 hash.
      - Checks duplicate by hash; if existing and not allow_duplicate, returns `(existing, False)`.
      - Copies source file into managed content store (`content_dir / assets / <hash_prefix> / <id>_<filename>`).
      - Extracts metadata (mime, width, height, aspect ratio, duration) safely without requiring external binaries.
      - Generates thumbnail (`content_dir / thumbnails / <id>.png`).
      - Persists `MediaAsset` entity via UnitOfWork.
    - CRUD & management for `CaptionTemplate`, `HashtagSet`, and `ContentItem`.
    - Batch tag, batch folder assignment, archive, unarchive, favorite toggle.
    - Search & multi-predicate query across assets and content.

---

## 4. UI Presentation & Integration
- **`sp_farms/app/content_workspace.py`**:
  - `ContentWorkspace(QWidget)`:
    - Tab 1: **Media Library**
      - Filter rail: All Media, Images, Videos, Favorites, Archived, Folders list.
      - Search bar + Tag filter chips.
      - Dense `CompactTable` with thumbnail column, name, dimensions, size, tags, folder, date added, favorite status.
      - Drag & Drop support: `dragEnterEvent` & `dropEvent` with non-blocking import worker via `QThreadPool`.
      - Context actions: Toggle Favorite, Move to Folder, Add Tags, Copy Path, Archive, Delete.
    - Tab 2: **Caption Templates & Hashtags**
      - Management of reusable caption snippets and hashtag packages.
    - Tab 3: **Content Items (Drafts & Composites)**
      - Assembled post items referencing media and templates.
    - **`MediaInspectorPanel`**:
      - Large thumbnail/preview previewer.
      - Detailed metadata table (hash, dimensions, aspect ratio, exact size, file type).
      - In-place metadata editing (folder, tags, notes).
- **`sp_farms/app/main_window.py`**:
  - Replace `UnavailableWorkspace("Content", ...)` with `ContentWorkspace`.
  - Wire route and global shortcut.
- **`sp_farms/application/context.py` & `sp_farms/bootstrap.py`**:
  - Register `ContentService` in `ApplicationContext` and wire through bootstrap.

---

## 5. Verification & Tests
- **`tests/test_content_library.py`**:
  - Media import and file hashing.
  - Duplicate detection prevention and allow_duplicate flag.
  - Metadata extraction (image dimensions, aspect ratio, mime detection).
  - Thumbnail generation and cache verification.
  - CaptionTemplate rendering and HashtagSet formatting.
  - ContentItem CRUD and relationships.
  - Tagging, folder grouping, archiving, and search query filters.
  - UI model filtering and inspector rendering in headless Qt test harness.
- **Regression suite**: Full test suite (`pytest tests/`).
- **Lint & Types**: `ruff check`, `mypy sp_farms`.
- **Docs & Git**:
  - Update `docs/PROGRESS.md` and `docs/DECISIONS.md`.
  - Commit: `phase(29): content library`.
  - Push: `git push origin ai/full-production-build`.
