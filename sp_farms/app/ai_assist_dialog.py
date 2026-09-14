from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.application.caption_ai_service import CaptionAIService
from sp_farms.domain.caption_ai import (
    AIAssistRequest,
    AIOperationType,
    SupportedLanguage,
    ToneStyle,
)


class AiAssistDialog(QDialog):
    """Interactive modal for multilingual translation, tone adjustments, and caption assist."""

    suggestion_applied = Signal(str)

    def __init__(
        self,
        caption_ai_service: CaptionAIService,
        initial_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = caption_ai_service
        self._initial_text = initial_text
        self._last_variants: tuple[str, ...] = ()
        self._last_hashtags: tuple[str, ...] = ()

        self.setWindowTitle("SP-Farms — Multilingual AI Writing Assistant")
        self.resize(800, 560)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel("AI Writing Assistant & Multilingual Translation")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2d3748;")
        lbl_sub = QLabel("Human review required. All outputs are proposals for operator approval.")
        lbl_sub.setStyleSheet("color: #718096; font-size: 12px;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        self.chip_status = StatusChip("Ready", "active")
        header.addWidget(self.chip_status)

        self.btn_api_key = SecondaryButton("Vault API Key...")
        self.btn_api_key.clicked.connect(self._on_configure_key)
        header.addWidget(self.btn_api_key)
        layout.addLayout(header)

        # Controls panel
        controls_panel = Panel()
        ctrl_layout = QHBoxLayout(controls_panel)
        ctrl_layout.setContentsMargins(12, 10, 12, 10)

        ctrl_form = QFormLayout()

        self.cmb_operation = QComboBox()
        self.cmb_operation.addItem("Translate", AIOperationType.TRANSLATE)
        self.cmb_operation.addItem("Rewrite Copy", AIOperationType.REWRITE)
        self.cmb_operation.addItem("Tone Variants", AIOperationType.TONE_VARIANTS)
        self.cmb_operation.addItem("Spelling & Grammar Polish", AIOperationType.SPELLING_CLEANUP)
        self.cmb_operation.addItem("Hashtag Suggestions", AIOperationType.HASHTAG_SUGGESTIONS)
        self.cmb_operation.currentIndexChanged.connect(self._on_operation_changed)
        ctrl_form.addRow("Operation:", self.cmb_operation)

        self.cmb_target_lang = QComboBox()
        self.cmb_target_lang.addItem("Khmer (ភាសាខ្មែរ)", SupportedLanguage.KHMER)
        self.cmb_target_lang.addItem("English", SupportedLanguage.ENGLISH)
        self.cmb_target_lang.addItem("Thai (ภาษาไทย)", SupportedLanguage.THAI)
        self.cmb_target_lang.addItem("Vietnamese (Tiếng Việt)", SupportedLanguage.VIETNAMESE)
        ctrl_form.addRow("Target Language:", self.cmb_target_lang)

        self.cmb_tone = QComboBox()
        self.cmb_tone.addItem("Casual", ToneStyle.CASUAL)
        self.cmb_tone.addItem("Professional", ToneStyle.PROFESSIONAL)
        self.cmb_tone.addItem("Promotional", ToneStyle.PROMOTIONAL)
        self.cmb_tone.addItem("Friendly", ToneStyle.FRIENDLY)
        self.cmb_tone.addItem("Urgent", ToneStyle.URGENT)
        ctrl_form.addRow("Tone Style:", self.cmb_tone)

        ctrl_layout.addLayout(ctrl_form)
        ctrl_layout.addStretch()

        self.btn_generate = PrimaryButton("✨ Generate Proposal")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.clicked.connect(self._on_generate)
        ctrl_layout.addWidget(self.btn_generate)

        layout.addWidget(controls_panel)

        # Split pane: Original vs Proposal
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Original text
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_lbl = QLabel("Source Caption:")
        left_lbl.setStyleSheet("font-weight: bold; color: #4a5568;")
        self.txt_source = QPlainTextEdit()
        self.txt_source.setPlainText(self._initial_text)
        self.txt_source.setPlaceholderText("Enter or paste caption to translate or polish...")
        left_layout.addWidget(left_lbl)
        left_layout.addWidget(self.txt_source)

        # Right: AI Result
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_lbl = QLabel("AI Proposal (Review & Edit):")
        right_lbl.setStyleSheet("font-weight: bold; color: #4a5568;")
        self.txt_proposal = QPlainTextEdit()
        self.txt_proposal.setPlaceholderText("Generated proposal will appear here...")
        right_layout.addWidget(right_lbl)
        right_layout.addWidget(self.txt_proposal)

        self.list_variants = QListWidget()
        self.list_variants.setMaximumHeight(100)
        self.list_variants.setVisible(False)
        self.list_variants.itemClicked.connect(self._on_variant_selected)
        right_layout.addWidget(self.list_variants)

        splitter.addWidget(left_box)
        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Explanation label
        self.lbl_explanation = QLabel("")
        self.lbl_explanation.setStyleSheet("color: #718096; font-style: italic; font-size: 11px;")
        layout.addWidget(self.lbl_explanation)

        # Footer action buttons
        footer = QHBoxLayout()
        self.lbl_safety = QLabel("🔒 Safe Mode: AI never publishes automatically.")
        self.lbl_safety.setStyleSheet("color: #38a169; font-size: 11px;")
        footer.addWidget(self.lbl_safety)
        footer.addStretch()

        self.btn_apply = PrimaryButton("Apply to Caption")
        self.btn_apply.clicked.connect(self._on_apply)
        btn_cancel = SecondaryButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        footer.addWidget(btn_cancel)
        footer.addWidget(self.btn_apply)
        layout.addLayout(footer)

        self._on_operation_changed()

    def _refresh_status(self) -> None:
        has_key = bool(self._service.get_ai_api_key())
        if has_key:
            self.chip_status.setText("Vault Key Active")
            self.chip_status.setProperty("status", "active")
        else:
            self.chip_status.setText("Offline / Simulated")
            self.chip_status.setProperty("status", "neutral")

    def _on_operation_changed(self) -> None:
        op = self.cmb_operation.currentData()
        is_translate = op == AIOperationType.TRANSLATE
        is_rewrite_or_tone = op in (AIOperationType.REWRITE, AIOperationType.TONE_VARIANTS)
        self.cmb_target_lang.setEnabled(is_translate)
        self.cmb_tone.setEnabled(is_rewrite_or_tone)
        self.list_variants.setVisible(op == AIOperationType.TONE_VARIANTS)

    def _on_generate(self) -> None:
        text = self.txt_source.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "AI Assist", "Please provide source text to process.")
            return

        op: AIOperationType = self.cmb_operation.currentData()
        target_lang: SupportedLanguage = self.cmb_target_lang.currentData()
        tone: ToneStyle = self.cmb_tone.currentData()

        request = AIAssistRequest(
            operation=op,
            text=text,
            target_language=target_lang,
            tone=tone,
        )

        try:
            response = self._service.assist(request)
            self.txt_proposal.setPlainText(response.suggested_text)
            self.lbl_explanation.setText(f"{response.explanation} (Model: {response.model_name})")

            if response.variants:
                self._last_variants = response.variants
                self.list_variants.clear()
                for v in response.variants:
                    self.list_variants.addItem(v)
                self.list_variants.setVisible(True)
            else:
                self.list_variants.setVisible(False)

        except Exception as ex:
            QMessageBox.critical(self, "AI Assist Error", str(ex))

    def _on_variant_selected(self, item: QListWidgetItem) -> None:
        self.txt_proposal.setPlainText(item.text())

    def _on_apply(self) -> None:
        final_text = self.txt_proposal.toPlainText().strip()
        if not final_text:
            QMessageBox.information(
                self, "AI Assist", "No proposal has been generated or accepted."
            )
            return
        self.suggestion_applied.emit(final_text)
        self.accept()

    def _on_configure_key(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Configure AI Provider Key (Vault)")
        dlg.resize(450, 180)
        d_layout = QVBoxLayout(dlg)

        info = QLabel(
            "API keys are stored strictly in the OS Keyring (Windows Credential Manager).\n"
            "They are never saved in plaintext database tables or export files."
        )
        info.setStyleSheet("color: #718096; font-size: 12px;")
        d_layout.addWidget(info)

        txt_key = QPlainTextEdit()
        txt_key.setPlaceholderText("sk-...")
        txt_key.setMaximumHeight(60)
        d_layout.addWidget(txt_key)

        btn_box = QHBoxLayout()
        btn_save = PrimaryButton("Save to Vault")
        btn_remove = SecondaryButton("Clear Key")
        btn_cancel = SecondaryButton("Cancel")

        def save() -> None:
            val = txt_key.toPlainText().strip()
            if not val:
                QMessageBox.warning(dlg, "Key", "Key cannot be empty.")
                return
            self._service.set_ai_api_key(val)
            self._refresh_status()
            dlg.accept()

        def remove() -> None:
            self._service.remove_ai_api_key()
            self._refresh_status()
            dlg.accept()

        btn_save.clicked.connect(save)
        btn_remove.clicked.connect(remove)
        btn_cancel.clicked.connect(dlg.reject)

        btn_box.addWidget(btn_remove)
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        d_layout.addLayout(btn_box)

        dlg.exec()
