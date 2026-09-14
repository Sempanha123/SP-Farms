import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from sp_farms.app.media_preview import MediaPreviewDialog
from sp_farms.application.job_service import JobService
from sp_farms.application.media_prep_job import MediaPrepJobHandler
from sp_farms.application.media_prep_service import (
    MediaInspectionService,
    MediaPreparationService,
    detect_ffmpeg_environment,
)
from sp_farms.application.worker import (
    CancellationToken,
    JobCancelledError,
    JobExecutionContext,
)
from sp_farms.domain.media_prep import (
    FFmpegDiagnostics,
    MediaFormatPreset,
    NormalizationOptions,
)
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import Database, SqlAlchemyJobRepository, run_migrations


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


def create_test_image(file_path: Path, width: int = 800, height: int = 600) -> Path:
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor("forestgreen"))
    img.save(str(file_path))
    return file_path


def test_ffmpeg_environment_detection() -> None:
    diag = detect_ffmpeg_environment()
    assert isinstance(diag, FFmpegDiagnostics)
    # Status message must be populated
    assert diag.status_message != ""
    if diag.is_available:
        assert diag.ffmpeg_path is not None


def test_media_inspection_image() -> None:
    with TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "sample.png"
        create_test_image(img_path, width=1200, height=800)

        inspector = MediaInspectionService()
        insp = inspector.inspect_file(img_path)

        assert insp.media_type == "IMAGE"
        assert insp.width == 1200
        assert insp.height == 800
        assert insp.aspect_ratio == "3:2"
        assert insp.resolution_label == "1200x800"
        assert insp.file_size_bytes > 0
        assert "KB" in insp.formatted_size or "B" in insp.formatted_size


def test_media_inspection_unsupported_or_missing() -> None:
    inspector = MediaInspectionService()

    # Missing file
    with pytest.raises(FileNotFoundError):
        inspector.inspect_file("non_existent_file_path.xyz")

    # Non-media text file
    with TemporaryDirectory() as tmp:
        txt_path = Path(tmp) / "note.txt"
        txt_path.write_text("hello world")

        insp = inspector.inspect_file(txt_path)
        assert insp.media_type == "OTHER"
        assert insp.mime_type == "text/plain"
        assert insp.width is None


def test_missing_ffmpeg_video_fallback() -> None:
    # Diagnostic without ffmpeg
    missing_diag = FFmpegDiagnostics(
        is_available=False,
        status_message="FFmpeg not installed",
    )
    with TemporaryDirectory() as tmp:
        vid_path = Path(tmp) / "clip.mp4"
        vid_path.write_bytes(b"\x00\x00\x00\x18ftypisom")

        inspector = MediaInspectionService(ffmpeg_diag=missing_diag)
        insp = inspector.inspect_file(vid_path)

        assert insp.media_type == "VIDEO"
        assert insp.width is None
        assert insp.video_codec is None

        prep = MediaPreparationService(output_dir=tmp, ffmpeg_diag=missing_diag)
        res = prep.normalize_media(vid_path)
        assert not res.success
        assert "FFmpeg is not available" in (res.error_message or "")


def test_safe_normalization_non_destructive_policy() -> None:
    with TemporaryDirectory() as tmp:
        src_path = Path(tmp) / "original.png"
        create_test_image(src_path, width=1600, height=1200)
        orig_bytes = src_path.read_bytes()

        prep = MediaPreparationService(output_dir=tmp)

        # Attempt to normalize with same output filename as source
        opts = NormalizationOptions(
            preset=MediaFormatPreset.FEED_SQUARE,
            max_width=500,
            max_height=500,
        )
        res = prep.normalize_media(src_path, options=opts, output_filename="original.png")

        assert res.success
        # Must NOT overwrite original
        assert Path(res.output_path).resolve() != src_path.resolve()
        assert src_path.read_bytes() == orig_bytes
        assert res.width == 500
        assert res.height == 500
        assert Path(res.output_path).exists()


def test_media_prep_job_execution() -> None:
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        db_path = base / "job_test.db"
        db = Database(db_path)
        try:
            run_migrations(db, Path(__file__).resolve().parents[1] / "migrations")

            clock = SystemClock()
            job_service = JobService(
                unit_of_work=db.unit_of_work,
                repository_factory=SqlAlchemyJobRepository,
                clock=clock,
            )

            src_img = base / "banner.png"
            create_test_image(src_img, width=1920, height=1080)

            out_dir = base / "prepared"
            prep_service = MediaPreparationService(output_dir=out_dir)
            handler = MediaPrepJobHandler(prep_service)

            # Submit background job
            payload = json.dumps(
                {
                    "source_path": str(src_img),
                    "preset": "feed_square_1_1",
                    "max_width": 600,
                    "max_height": 600,
                }
            )
            job, _ = job_service.create_job(
                job_type="media_prep",
                target_type="media_file",
                target_id=payload,
            )

            token = CancellationToken()
            context = JobExecutionContext(
                job=job,
                token=token,
                service=job_service,
                clock=clock,
                heartbeat_callback=lambda: None,
            )

            # Execute handler
            handler(context)

            # Check job progress recorded
            updated = job_service.get_job(job.id)
            assert updated is not None
            assert updated.progress == 100

            # Check prepared file output
            files = list(out_dir.glob("*.png"))
            assert len(files) == 1
        finally:
            db.close()


def test_media_prep_job_cancellation() -> None:
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        src_img = base / "photo.png"
        create_test_image(src_img, width=400, height=400)

        prep_service = MediaPreparationService(output_dir=base / "prep")
        handler = MediaPrepJobHandler(prep_service)

        db_path = base / "cancel_test.db"
        db = Database(db_path)
        try:
            run_migrations(db, Path(__file__).resolve().parents[1] / "migrations")
            clock = SystemClock()
            job_service = JobService(
                unit_of_work=db.unit_of_work,
                repository_factory=SqlAlchemyJobRepository,
                clock=clock,
            )
            job, _ = job_service.create_job(
                job_type="media_prep",
                target_type="media_file",
                target_id=json.dumps({"source_path": str(src_img)}),
            )

            token = CancellationToken()
            token.cancel()  # Pre-cancel

            context = JobExecutionContext(
                job=job,
                token=token,
                service=job_service,
                clock=clock,
                heartbeat_callback=lambda: None,
            )

            with pytest.raises(JobCancelledError):
                handler(context)
        finally:
            db.close()


def test_media_preview_dialog_ui(qapp: QApplication) -> None:
    with TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "dialog_sample.png"
        create_test_image(img_path, width=640, height=480)

        inspector = MediaInspectionService()
        prep = MediaPreparationService(output_dir=tmp)

        dlg = MediaPreviewDialog(
            file_path=img_path,
            inspection_service=inspector,
            prep_service=prep,
        )

        assert dlg.lbl_file.text() == "dialog_sample.png"
        assert dlg.lbl_res.text() == "640x480"
        assert dlg.lbl_aspect.text() == "4:3"
        assert dlg.stack.currentWidget() == dlg.image_scroll
        dlg.close()
