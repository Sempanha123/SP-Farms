import contextlib
import json
import logging
import mimetypes
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from sp_farms.domain.media_prep import (
    FFmpegDiagnostics,
    MediaFormatPreset,
    MediaInspection,
    NormalizationOptions,
    NormalizationResult,
)

logger = logging.getLogger(__name__)


def detect_ffmpeg_environment(custom_bin_dir: Path | str | None = None) -> FFmpegDiagnostics:
    """Locate ffmpeg and ffprobe on system PATH or fallback search locations."""
    search_dirs: list[Path] = []
    if custom_bin_dir:
        search_dirs.append(Path(custom_bin_dir))

    # Common Windows fallback paths
    common_windows_paths = [
        Path(r"C:\ffmpeg\bin"),
        Path(r"C:\Program Files\ffmpeg\bin"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
    ]
    search_dirs.extend([p for p in common_windows_paths if p.exists()])

    # Check PATH first
    ffmpeg_exe = shutil.which("ffmpeg")
    ffprobe_exe = shutil.which("ffprobe")

    if not ffmpeg_exe:
        for d in search_dirs:
            candidate = d / "ffmpeg.exe"
            if candidate.exists():
                ffmpeg_exe = str(candidate)
                break

    if not ffprobe_exe:
        for d in search_dirs:
            candidate = d / "ffprobe.exe"
            if candidate.exists():
                ffprobe_exe = str(candidate)
                break

    if not ffmpeg_exe:
        return FFmpegDiagnostics(
            is_available=False,
            status_message="FFmpeg executable not found in PATH or standard directories",
        )

    # Probe version and codecs
    version: str | None = None
    codecs: list[str] = []
    try:
        ver_res = subprocess.run(
            [ffmpeg_exe, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if ver_res.returncode == 0 and ver_res.stdout:
            first_line = ver_res.stdout.splitlines()[0]
            version = first_line.replace("ffmpeg version ", "").strip()
    except Exception as e:
        logger.debug("Failed to get ffmpeg version: %s", e)

    try:
        codec_res = subprocess.run(
            [ffmpeg_exe, "-codecs"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if codec_res.returncode == 0 and codec_res.stdout:
            for line in codec_res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].startswith("D") or parts[0].startswith("E"):
                    codecs.append(parts[1])
    except Exception as e:
        logger.debug("Failed to get ffmpeg codecs: %s", e)

    return FFmpegDiagnostics(
        is_available=True,
        ffmpeg_path=ffmpeg_exe,
        ffprobe_path=ffprobe_exe,
        version=version,
        codecs=tuple(sorted(set(codecs))),
        status_message=f"Available ({version or 'Unknown version'})",
    )


class MediaInspectionService:
    def __init__(self, ffmpeg_diag: FFmpegDiagnostics | None = None) -> None:
        self._ffmpeg = ffmpeg_diag or detect_ffmpeg_environment()

    def inspect_file(self, file_path: Path | str) -> MediaInspection:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Media file does not exist: {path}")

        size = path.stat().st_size
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "application/octet-stream"

        if mime.startswith("image/"):
            media_type = "IMAGE"
            return self._inspect_image(path, size, mime)
        elif mime.startswith("video/"):
            media_type = "VIDEO"
            return self._inspect_video(path, size, mime)
        elif mime.startswith("audio/"):
            media_type = "AUDIO"
            return MediaInspection(
                file_path=str(path),
                file_size_bytes=size,
                mime_type=mime,
                media_type=media_type,
                has_audio=True,
            )
        return MediaInspection(
            file_path=str(path),
            file_size_bytes=size,
            mime_type=mime,
            media_type="OTHER",
        )

    def _inspect_image(self, path: Path, size: int, mime: str) -> MediaInspection:
        width: int | None = None
        height: int | None = None
        aspect_ratio: str | None = None

        try:
            from PySide6.QtGui import QImageReader

            reader = QImageReader(str(path))
            if reader.canRead():
                qsize = reader.size()
                if qsize.isValid():
                    width = qsize.width()
                    height = qsize.height()
        except Exception:
            pass

        if width and height and width > 0 and height > 0:
            frac = Fraction(width, height).limit_denominator(20)
            ratio = width / height
            if abs(ratio - 16 / 9) < 0.05:
                aspect_ratio = "16:9"
            elif abs(ratio - 9 / 16) < 0.05:
                aspect_ratio = "9:16"
            elif abs(ratio - 1.0) < 0.02:
                aspect_ratio = "1:1"
            elif abs(ratio - 4 / 5) < 0.05:
                aspect_ratio = "4:5"
            elif abs(ratio - 4 / 3) < 0.05:
                aspect_ratio = "4:3"
            else:
                aspect_ratio = f"{frac.numerator}:{frac.denominator}"

        return MediaInspection(
            file_path=str(path),
            file_size_bytes=size,
            mime_type=mime,
            media_type="IMAGE",
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
        )

    def _inspect_video(self, path: Path, size: int, mime: str) -> MediaInspection:
        width: int | None = None
        height: int | None = None
        duration: float | None = None
        video_codec: str | None = None
        audio_codec: str | None = None
        has_audio = False
        bitrate_kbps: int | None = None

        if self._ffmpeg.is_available and self._ffmpeg.ffprobe_path:
            try:
                cmd = [
                    self._ffmpeg.ffprobe_path,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
                if res.returncode == 0 and res.stdout:
                    info = json.loads(res.stdout)
                    streams = info.get("streams", [])
                    fmt = info.get("format", {})

                    if "duration" in fmt:
                        with contextlib.suppress(ValueError):
                            duration = float(fmt["duration"])
                    if "bit_rate" in fmt:
                        with contextlib.suppress(ValueError):
                            bitrate_kbps = int(int(fmt["bit_rate"]) / 1000)

                    for stream in streams:
                        codec_type = stream.get("codec_type")
                        if codec_type == "video" and width is None:
                            width = stream.get("width")
                            height = stream.get("height")
                            video_codec = stream.get("codec_name")
                        elif codec_type == "audio":
                            has_audio = True
                            if not audio_codec:
                                audio_codec = stream.get("codec_name")
            except Exception as e:
                logger.debug("ffprobe failed on %s: %s", path, e)

        aspect_ratio: str | None = None
        if width and height and width > 0 and height > 0:
            ratio = width / height
            if abs(ratio - 16 / 9) < 0.05:
                aspect_ratio = "16:9"
            elif abs(ratio - 9 / 16) < 0.05:
                aspect_ratio = "9:16"
            elif abs(ratio - 1.0) < 0.02:
                aspect_ratio = "1:1"
            elif abs(ratio - 4 / 5) < 0.05:
                aspect_ratio = "4:5"
            else:
                frac = Fraction(width, height).limit_denominator(20)
                aspect_ratio = f"{frac.numerator}:{frac.denominator}"

        return MediaInspection(
            file_path=str(path),
            file_size_bytes=size,
            mime_type=mime,
            media_type="VIDEO",
            width=width,
            height=height,
            duration_seconds=duration,
            bitrate_kbps=bitrate_kbps,
            aspect_ratio=aspect_ratio,
            video_codec=video_codec,
            audio_codec=audio_codec,
            has_audio=has_audio,
        )


class MediaPreparationService:
    """Non-destructive media normalization and preparation."""

    def __init__(
        self,
        output_dir: Path | str,
        ffmpeg_diag: FFmpegDiagnostics | None = None,
        inspection_service: MediaInspectionService | None = None,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._ffmpeg = ffmpeg_diag or detect_ffmpeg_environment()
        self._inspector = inspection_service or MediaInspectionService(self._ffmpeg)

    def normalize_media(
        self,
        source_path: Path | str,
        options: NormalizationOptions | None = None,
        output_filename: str | None = None,
    ) -> NormalizationResult:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            return NormalizationResult(
                source_path=str(source),
                output_path="",
                output_size_bytes=0,
                width=None,
                height=None,
                duration_seconds=None,
                metadata_stripped=False,
                success=False,
                error_message=f"Source file not found: {source}",
            )

        opts = options or NormalizationOptions()
        inspection = self._inspector.inspect_file(source)

        if inspection.media_type == "IMAGE":
            return self._normalize_image(source, inspection, opts, output_filename)
        elif inspection.media_type == "VIDEO":
            return self._normalize_video(source, inspection, opts, output_filename)

        return NormalizationResult(
            source_path=str(source),
            output_path="",
            output_size_bytes=0,
            width=None,
            height=None,
            duration_seconds=None,
            metadata_stripped=False,
            success=False,
            error_message=f"Unsupported media type for normalization: {inspection.mime_type}",
        )

    def _normalize_image(
        self,
        source: Path,
        inspection: MediaInspection,
        opts: NormalizationOptions,
        output_filename: str | None,
    ) -> NormalizationResult:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage

        stem = source.stem
        ext = opts.target_format or source.suffix.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext == ".jpeg":
            ext = ".jpg"

        out_name = output_filename or f"{stem}_normalized{ext}"
        out_path = self._output_dir / out_name

        # Enforce non-destructive policy: Never overwrite original file
        if out_path.resolve() == source.resolve():
            out_path = self._output_dir / f"{stem}_prepared{ext}"

        try:
            img = QImage(str(source))
            if img.isNull():
                return NormalizationResult(
                    source_path=str(source),
                    output_path="",
                    output_size_bytes=0,
                    width=None,
                    height=None,
                    duration_seconds=None,
                    metadata_stripped=False,
                    success=False,
                    error_message="Failed to load image with QImage",
                )

            # Resize if exceeds max_width or max_height
            cur_w = img.width()
            cur_h = img.height()
            target_w = cur_w
            target_h = cur_h

            if opts.preset == MediaFormatPreset.FEED_SQUARE:
                target_w = min(cur_w, cur_h, opts.max_width)
                target_h = target_w
            elif opts.preset == MediaFormatPreset.REEL_STORY:
                # 9:16 target max
                target_w = min(cur_w, 1080)
                target_h = min(cur_h, 1920)
            else:
                if cur_w > opts.max_width or cur_h > opts.max_height:
                    scaled = img.scaled(
                        opts.max_width,
                        opts.max_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    img = scaled
                    target_w = img.width()
                    target_h = img.height()

            success = img.save(str(out_path), quality=opts.quality)
            if not success:
                return NormalizationResult(
                    source_path=str(source),
                    output_path="",
                    output_size_bytes=0,
                    width=None,
                    height=None,
                    duration_seconds=None,
                    metadata_stripped=False,
                    success=False,
                    error_message=f"Failed to save normalized image to {out_path}",
                )

            out_size = out_path.stat().st_size
            return NormalizationResult(
                source_path=str(source),
                output_path=str(out_path),
                output_size_bytes=out_size,
                width=target_w,
                height=target_h,
                duration_seconds=None,
                metadata_stripped=opts.strip_metadata,
                success=True,
            )
        except Exception as e:
            return NormalizationResult(
                source_path=str(source),
                output_path="",
                output_size_bytes=0,
                width=None,
                height=None,
                duration_seconds=None,
                metadata_stripped=False,
                success=False,
                error_message=str(e),
            )

    def _normalize_video(
        self,
        source: Path,
        inspection: MediaInspection,
        opts: NormalizationOptions,
        output_filename: str | None,
    ) -> NormalizationResult:
        if not self._ffmpeg.is_available or not self._ffmpeg.ffmpeg_path:
            return NormalizationResult(
                source_path=str(source),
                output_path="",
                output_size_bytes=0,
                width=inspection.width,
                height=inspection.height,
                duration_seconds=inspection.duration_seconds,
                metadata_stripped=False,
                success=False,
                error_message="FFmpeg is not available to normalize video",
            )

        stem = source.stem
        out_name = output_filename or f"{stem}_normalized.mp4"
        out_path = self._output_dir / out_name

        # Enforce non-destructive policy
        if out_path.resolve() == source.resolve():
            out_path = self._output_dir / f"{stem}_prepared.mp4"

        cmd = [
            self._ffmpeg.ffmpeg_path,
            "-y",  # Overwrite output only
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]

        if opts.strip_metadata:
            cmd.extend(["-map_metadata", "-1"])

        cmd.append(str(out_path))

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
            if res.returncode != 0:
                return NormalizationResult(
                    source_path=str(source),
                    output_path="",
                    output_size_bytes=0,
                    width=inspection.width,
                    height=inspection.height,
                    duration_seconds=inspection.duration_seconds,
                    metadata_stripped=False,
                    success=False,
                    error_message=f"FFmpeg error: {res.stderr[-300:] if res.stderr else 'unknown'}",
                )

            out_size = out_path.stat().st_size
            # Re-inspect output for actual dimensions
            out_insp = self._inspector.inspect_file(out_path)
            return NormalizationResult(
                source_path=str(source),
                output_path=str(out_path),
                output_size_bytes=out_size,
                width=out_insp.width,
                height=out_insp.height,
                duration_seconds=out_insp.duration_seconds,
                metadata_stripped=opts.strip_metadata,
                success=True,
            )
        except Exception as e:
            return NormalizationResult(
                source_path=str(source),
                output_path="",
                output_size_bytes=0,
                width=inspection.width,
                height=inspection.height,
                duration_seconds=inspection.duration_seconds,
                metadata_stripped=False,
                success=False,
                error_message=str(e),
            )
