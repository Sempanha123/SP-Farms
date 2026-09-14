from dataclasses import dataclass, field
from enum import StrEnum


class MediaFormatPreset(StrEnum):
    ORIGINAL = "original"
    FEED_SQUARE = "feed_square_1_1"
    FEED_PORTRAIT = "feed_portrait_4_5"
    REEL_STORY = "reel_story_9_16"
    LANDSCAPE = "landscape_16_9"
    WEB_COMPACT = "web_compact"


@dataclass(frozen=True, slots=True)
class FFmpegDiagnostics:
    is_available: bool
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    version: str | None = None
    codecs: tuple[str, ...] = ()
    status_message: str = "Not detected"


@dataclass(frozen=True, slots=True)
class MediaInspection:
    file_path: str
    file_size_bytes: int
    mime_type: str
    media_type: str  # IMAGE, VIDEO, AUDIO, OTHER
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    bitrate_kbps: int | None = None
    aspect_ratio: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_audio: bool = False
    color_space: str | None = None
    has_gps_metadata: bool = False
    exif_summary: dict[str, str] = field(default_factory=dict)

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "Unknown"

    @property
    def formatted_size(self) -> str:
        size = self.file_size_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    @property
    def formatted_duration(self) -> str:
        if self.duration_seconds is None:
            return "—"
        total = int(self.duration_seconds)
        mins, secs = divmod(total, 60)
        return f"{mins:02d}:{secs:02d}"


@dataclass(frozen=True, slots=True)
class NormalizationOptions:
    preset: MediaFormatPreset = MediaFormatPreset.WEB_COMPACT
    max_width: int = 1920
    max_height: int = 1080
    strip_metadata: bool = True
    target_format: str | None = None  # None = match source or standard web
    quality: int = 85  # 1-100


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    source_path: str
    output_path: str
    output_size_bytes: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    metadata_stripped: bool
    success: bool
    error_message: str | None = None
