from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.domain.media_prep import (
    MediaFormatPreset,
    MediaInspection,
    NormalizationOptions,
)

if TYPE_CHECKING:
    from sp_farms.application.media_prep_service import (
        MediaInspectionService,
        MediaPreparationService,
    )


class MediaPreviewDialog(QDialog):
    """Media inspection and preparation modal with image/video playback."""

    def __init__(
        self,
        file_path: Path | str,
        inspection_service: "MediaInspectionService",
        prep_service: "MediaPreparationService",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Media Preview & Preparation")
        self.resize(880, 620)
        self._file_path = Path(file_path)
        self._inspection_service = inspection_service
        self._prep_service = prep_service
        self._inspection: MediaInspection | None = None

        # Multimedia objects
        self._player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None
        self._video_widget: QVideoWidget | None = None

        self._build_ui()
        self._load_media()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Player / Image Display
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.stack = QStackedWidget()

        # Image view
        self.image_scroll = QScrollArea()
        self.image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label = QLabel("Loading image...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        self.image_scroll.setWidgetResizable(True)
        self.stack.addWidget(self.image_scroll)

        # Video view
        self.video_container = QWidget()
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(4)

        self._video_widget = QVideoWidget()
        video_layout.addWidget(self._video_widget, 1)

        # Controls bar
        ctrl_bar = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedWidth(64)
        self.play_btn.clicked.connect(self._toggle_playback)
        ctrl_bar.addWidget(self.play_btn)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 1000)
        self.time_slider.sliderMoved.connect(self._on_seek)
        ctrl_bar.addWidget(self.time_slider)

        self.time_label = QLabel("00:00 / 00:00")
        ctrl_bar.addWidget(self.time_label)

        video_layout.addLayout(ctrl_bar)
        self.stack.addWidget(self.video_container)

        # Unsupported fallback view
        self.fallback_label = QLabel("No preview available")
        self.fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.fallback_label)

        left_layout.addWidget(self.stack, 1)
        splitter.addWidget(left_container)

        # Right Column: Inspector Panel & Normalization Actions
        right_panel = Panel()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        meta_title = QLabel("Media Metadata")
        meta_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(meta_title)

        self.status_chip = StatusChip("Ready", state="neutral")
        right_layout.addWidget(self.status_chip)

        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(6)
        self.lbl_file = QLabel("-")
        self.lbl_file.setWordWrap(True)
        self.lbl_size = QLabel("-")
        self.lbl_type = QLabel("-")
        self.lbl_res = QLabel("-")
        self.lbl_aspect = QLabel("-")
        self.lbl_duration = QLabel("-")
        self.lbl_bitrate = QLabel("-")
        self.lbl_codec = QLabel("-")

        self.form_layout.addRow("File:", self.lbl_file)
        self.form_layout.addRow("Size:", self.lbl_size)
        self.form_layout.addRow("Type:", self.lbl_type)
        self.form_layout.addRow("Resolution:", self.lbl_res)
        self.form_layout.addRow("Aspect Ratio:", self.lbl_aspect)
        self.form_layout.addRow("Duration:", self.lbl_duration)
        self.form_layout.addRow("Bitrate:", self.lbl_bitrate)
        self.form_layout.addRow("Codecs:", self.lbl_codec)
        right_layout.addLayout(self.form_layout)

        right_layout.addSpacing(10)
        prep_title = QLabel("Safe Normalization")
        prep_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(prep_title)

        prep_desc = QLabel("Output is non-destructive and creates a new prepared asset.")
        prep_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        prep_desc.setWordWrap(True)
        right_layout.addWidget(prep_desc)

        preset_box = QHBoxLayout()
        preset_box.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        for p in MediaFormatPreset:
            self.preset_combo.addItem(p.value, p)
        preset_box.addWidget(self.preset_combo)
        right_layout.addLayout(preset_box)

        self.btn_normalize = PrimaryButton("Normalize Asset")
        self.btn_normalize.clicked.connect(self._on_normalize)
        right_layout.addWidget(self.btn_normalize)

        right_layout.addStretch()

        btn_close = SecondaryButton("Close")
        btn_close.clicked.connect(self.accept)
        right_layout.addWidget(btn_close)

        splitter.addWidget(right_panel)
        splitter.setSizes([540, 340])
        root_layout.addWidget(splitter)

    def _load_media(self) -> None:
        try:
            self._inspection = self._inspection_service.inspect_file(self._file_path)
        except Exception as e:
            self.fallback_label.setText(f"Inspection error: {e}")
            self.stack.setCurrentWidget(self.fallback_label)
            return

        insp = self._inspection
        self.lbl_file.setText(self._file_path.name)
        self.lbl_size.setText(insp.formatted_size)
        self.lbl_type.setText(insp.mime_type)
        self.lbl_res.setText(insp.resolution_label)
        self.lbl_aspect.setText(insp.aspect_ratio or "—")
        self.lbl_duration.setText(insp.formatted_duration)
        self.lbl_bitrate.setText(f"{insp.bitrate_kbps} kbps" if insp.bitrate_kbps else "—")

        codecs = []
        if insp.video_codec:
            codecs.append(f"V:{insp.video_codec}")
        if insp.audio_codec:
            codecs.append(f"A:{insp.audio_codec}")
        self.lbl_codec.setText(", ".join(codecs) if codecs else "—")

        if insp.media_type == "IMAGE":
            self._setup_image()
        elif insp.media_type == "VIDEO":
            self._setup_video()
        else:
            self.fallback_label.setText(f"No visual preview for {insp.media_type}")
            self.stack.setCurrentWidget(self.fallback_label)

    def _setup_image(self) -> None:
        pix = QPixmap(str(self._file_path))
        if not pix.isNull():
            # Fit inside viewing area
            scaled = pix.scaled(
                QSize(500, 480),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to render image")
        self.stack.setCurrentWidget(self.image_scroll)

    def _setup_video(self) -> None:
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        if self._video_widget:
            self._player.setVideoOutput(self._video_widget)

        self._player.positionChanged.connect(self._on_player_position_changed)
        self._player.durationChanged.connect(self._on_player_duration_changed)
        self._player.setSource(QUrl.fromLocalFile(str(self._file_path)))
        self.stack.setCurrentWidget(self.video_container)

    def _toggle_playback(self) -> None:
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self.play_btn.setText("Play")
        else:
            self._player.play()
            self.play_btn.setText("Pause")

    def _on_player_position_changed(self, pos: int) -> None:
        if not self._player:
            return
        dur = self._player.duration()
        if dur > 0:
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(int((pos / dur) * 1000))
            self.time_slider.blockSignals(False)

            cur_sec = pos // 1000
            tot_sec = dur // 1000
            self.time_label.setText(
                f"{cur_sec // 60:02d}:{cur_sec % 60:02d} / {tot_sec // 60:02d}:{tot_sec % 60:02d}"
            )

    def _on_player_duration_changed(self, dur: int) -> None:
        tot_sec = dur // 1000
        self.time_label.setText(f"00:00 / {tot_sec // 60:02d}:{tot_sec % 60:02d}")

    def _on_seek(self, value: int) -> None:
        if not self._player:
            return
        dur = self._player.duration()
        if dur > 0:
            target_pos = int((value / 1000) * dur)
            self._player.setPosition(target_pos)

    def _on_normalize(self) -> None:
        preset_val = self.preset_combo.currentData()
        opts = NormalizationOptions(
            preset=preset_val,
            strip_metadata=True,
        )
        res = self._prep_service.normalize_media(self._file_path, options=opts)
        if res.success:
            msg = (
                f"Media normalized non-destructively:\n"
                f"{res.output_path}\n({res.width}x{res.height})"
            )
            QMessageBox.information(
                self,
                "Normalization Complete",
                msg,
            )
            self.status_chip.update_state("success", "Normalized")
        else:
            QMessageBox.warning(
                self,
                "Normalization Failed",
                f"Normalization failed:\n{res.error_message}",
            )
            self.status_chip.update_state("error", "Failed")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._player:
            self._player.stop()
        super().closeEvent(event)
