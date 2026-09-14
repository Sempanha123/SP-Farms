import json
import logging
from typing import TYPE_CHECKING

from sp_farms.domain.media_prep import (
    MediaFormatPreset,
    NormalizationOptions,
)

if TYPE_CHECKING:
    from sp_farms.application.media_prep_service import MediaPreparationService
    from sp_farms.application.worker import JobExecutionContext

logger = logging.getLogger(__name__)


class MediaPrepJobHandler:
    """Worker JobHandler that processes background media normalization without blocking UI."""

    def __init__(self, prep_service: "MediaPreparationService") -> None:
        self._prep_service = prep_service

    def __call__(self, context: "JobExecutionContext") -> None:
        context.check_cancelled()
        context.record_progress(10)

        # Decode target / payload
        payload_data = {}
        target = context.job.target_id
        if target:
            try:
                payload_data = json.loads(target)
            except Exception:
                payload_data = {"source_path": target}

        source_path = payload_data.get("source_path")
        if not source_path:
            raise ValueError("Media prep job missing 'source_path' in payload")

        preset_str = payload_data.get("preset", "web_compact")
        try:
            preset = MediaFormatPreset(preset_str)
        except ValueError:
            preset = MediaFormatPreset.WEB_COMPACT

        opts = NormalizationOptions(
            preset=preset,
            max_width=int(payload_data.get("max_width", 1920)),
            max_height=int(payload_data.get("max_height", 1080)),
            strip_metadata=bool(payload_data.get("strip_metadata", True)),
            target_format=payload_data.get("target_format"),
            quality=int(payload_data.get("quality", 85)),
        )

        context.record_progress(30)
        context.check_cancelled()

        result = self._prep_service.normalize_media(
            source_path=source_path,
            options=opts,
            output_filename=payload_data.get("output_filename"),
        )

        context.record_progress(90)
        context.check_cancelled()

        if not result.success:
            raise RuntimeError(f"Media normalization failed: {result.error_message}")

        context.record_progress(100)
