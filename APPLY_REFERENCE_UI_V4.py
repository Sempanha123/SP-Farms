from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "sp_farms" / "app"

PAYLOAD_THEME = 'from dataclasses import dataclass\nfrom enum import StrEnum\n\n\nclass ThemeMode(StrEnum):\n    LIGHT = "light"\n    DARK = "dark"\n\n\n@dataclass(frozen=True, slots=True)\nclass ThemePalette:\n    window: str\n    surface: str\n    surface_alt: str\n    border: str\n    text: str\n    muted_text: str\n    accent: str\n    accent_hover: str\n    accent_text: str\n    warning: str\n    danger: str\n    success: str\n    info: str\n    selection: str\n\n\nLIGHT_PALETTE = ThemePalette(\n    window="#F4F5F2",\n    surface="#FFFFFF",\n    surface_alt="#ECEFEC",\n    border="#CCD1CC",\n    text="#171C19",\n    muted_text="#667069",\n    accent="#F4C915",\n    accent_hover="#FFD92D",\n    accent_text="#16170F",\n    warning="#D99B18",\n    danger="#D84D53",\n    success="#22B967",\n    info="#2D76DF",\n    selection="#FFF3A9",\n)\n\n# Reference-locked SP-Farms palette.\nDARK_PALETTE = ThemePalette(\n    window="#0D1113",\n    surface="#121719",\n    surface_alt="#181E21",\n    border="#333D41",\n    text="#F2F4F4",\n    muted_text="#98A2A7",\n    accent="#F4C915",\n    accent_hover="#FFD92D",\n    accent_text="#15160E",\n    warning="#E3A629",\n    danger="#F05D63",\n    success="#25D06F",\n    info="#4388F0",\n    selection="#37361D",\n)\n\n\ndef palette(mode: ThemeMode) -> ThemePalette:\n    return LIGHT_PALETTE if mode is ThemeMode.LIGHT else DARK_PALETTE\n\n\ndef style_sheet(mode: ThemeMode) -> str:\n    c = palette(mode)\n    dark = mode is ThemeMode.DARK\n    top = "#101518" if dark else "#FAFBF9"\n    raised = "#161C1F" if dark else "#FFFFFF"\n    soft = "#151A1D" if dark else "#F5F7F5"\n    hover = "#20272A" if dark else "#E8ECE9"\n    row_line = "#252D30" if dark else "#DDE2DE"\n    header = "#171E21" if dark else "#E9EEEA"\n    success_bg = "#153523" if dark else "#E6F7ED"\n    warning_bg = "#342A16" if dark else "#FFF4D9"\n    error_bg = "#361C20" if dark else "#FDECEE"\n    active_bg = "#172D4E" if dark else "#EBF2FF"\n    yellow_soft = "#2C2913" if dark else "#FFF8D2"\n    flow_done = "#183B27" if dark else "#E4F7EB"\n    flow_next = "#2E2A13" if dark else "#FFF5C8"\n    disabled = "#111618" if dark else "#ECEFEC"\n\n    return f"""\nQWidget {{\n    background: {c.window};\n    color: {c.text};\n    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;\n    font-size: 12px;\n}}\n\nQFrame[panel="true"], QDialog {{\n    background: {c.surface};\n    border: 1px solid {c.border};\n    border-radius: 8px;\n}}\n\nQFrame[softPanel="true"] {{\n    background: {soft};\n    border: 1px solid {c.border};\n    border-radius: 8px;\n}}\n\nQFrame[flowPanel="true"] {{\n    background: {raised};\n    border: 1px solid #62551B;\n    border-radius: 8px;\n}}\n\nQFrame[metric="true"] {{\n    min-height: 58px;\n    background: {raised};\n    border: 1px solid {c.border};\n    border-radius: 8px;\n}}\n\nQLabel {{\n    background: transparent;\n    border: 0;\n}}\n\nQLabel[muted="true"] {{\n    color: {c.muted_text};\n}}\n\nQLabel[heading="true"] {{\n    font-size: 16px;\n    font-weight: 700;\n}}\n\nQLabel[sectionTitle="true"] {{\n    font-size: 13px;\n    font-weight: 700;\n}}\n\nQLabel[metricValue="true"] {{\n    font-size: 19px;\n    font-weight: 750;\n}}\n\nQLabel[flowArrow="true"] {{\n    color: {c.muted_text};\n    font-size: 16px;\n    font-weight: 700;\n}}\n\nQLabel[previewTitle="true"] {{\n    font-size: 13px;\n    font-weight: 700;\n}}\n\nQLabel#brand {{\n    font-size: 20px;\n    font-weight: 800;\n}}\n\nQLabel#brandVersion, QLabel#brandSubtitle {{\n    color: {c.muted_text};\n}}\n\nQLabel#brandSubtitle {{\n    font-size: 10px;\n}}\n\nQWidget#topNavigation {{\n    background: {top};\n    border-bottom: 1px solid {c.border};\n}}\n\nQWidget#topClock {{\n    background: transparent;\n}}\n\nQLabel#clockTime {{\n    font-size: 14px;\n    font-weight: 750;\n}}\n\nQLabel#clockDate {{\n    color: {c.muted_text};\n    font-size: 10px;\n}}\n\nQLabel#brandMark {{\n    color: #07130C;\n    background: #3ECF72;\n    border: 1px solid #57DF88;\n    border-radius: 9px;\n    font-size: 19px;\n    font-weight: 900;\n}}\n\nQPushButton {{\n    min-height: 29px;\n    padding: 0 10px;\n    border: 1px solid {c.border};\n    border-radius: 7px;\n    background: {c.surface_alt};\n}}\n\nQPushButton:hover {{\n    background: {hover};\n    border-color: #59656A;\n}}\n\nQPushButton:pressed {{\n    background: {c.surface};\n}}\n\nQPushButton:disabled {{\n    color: #626A6E;\n    background: {disabled};\n    border-color: #293034;\n}}\n\nQPushButton:focus {{\n    border: 2px solid {c.accent};\n    outline: none;\n}}\n\nQPushButton[primary="true"] {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[primary="true"]:hover {{\n    background: {c.accent_hover};\n    border-color: {c.accent_hover};\n}}\n\nQPushButton[successAction="true"] {{\n    color: #07160D;\n    background: {c.success};\n    border-color: {c.success};\n    font-weight: 700;\n}}\n\nQPushButton[infoAction="true"] {{\n    color: white;\n    background: {c.info};\n    border-color: {c.info};\n    font-weight: 700;\n}}\n\nQPushButton[danger="true"] {{\n    color: {c.danger};\n    border-color: #6E373B;\n    background: #241719;\n}}\n\nQPushButton[nav="true"] {{\n    min-height: 34px;\n    padding: 0 13px;\n    background: {c.surface_alt};\n    font-weight: 600;\n}}\n\nQPushButton[nav="true"]:checked {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[localNav="true"] {{\n    min-width: 102px;\n    background: transparent;\n    border-color: transparent;\n}}\n\nQPushButton[localNav="true"]:checked {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[actionNav="true"] {{\n    text-align: left;\n    background: transparent;\n    border-color: transparent;\n}}\n\nQPushButton[actionNav="true"]:checked {{\n    color: {c.accent_text};\n    background: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[flowStep="true"] {{\n    min-height: 46px;\n    min-width: 116px;\n    padding: 4px 9px;\n    text-align: left;\n    background: {soft};\n    border-color: {c.border};\n    border-radius: 8px;\n    font-weight: 650;\n}}\n\nQPushButton[flowStep="true"]:hover {{\n    background: {yellow_soft};\n    border-color: {c.accent};\n}}\n\nQPushButton[flowState="done"] {{\n    color: {c.success};\n    background: {flow_done};\n    border-color: #2B7047;\n}}\n\nQPushButton[flowState="next"] {{\n    color: {c.accent};\n    background: {flow_next};\n    border-color: #6A5D1C;\n}}\n\nQPushButton[quickAction="true"] {{\n    min-height: 46px;\n    text-align: left;\n    padding: 5px 10px;\n    background: {raised};\n    border-radius: 8px;\n}}\n\nQPushButton[quickAction="true"]:hover {{\n    background: {hover};\n    border-color: {c.accent};\n}}\n\nQLineEdit, QComboBox, QSpinBox, QDateTimeEdit, QTextEdit {{\n    min-height: 29px;\n    padding: 0 8px;\n    background: {c.surface};\n    border: 1px solid {c.border};\n    border-radius: 7px;\n    selection-background-color: {c.info};\n}}\n\nQLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDateTimeEdit:hover, QTextEdit:hover {{\n    border-color: #505C61;\n}}\n\nQLineEdit:focus, QComboBox:focus, QSpinBox:focus,\nQDateTimeEdit:focus, QTextEdit:focus {{\n    border: 2px solid {c.accent};\n}}\n\nQTextEdit {{\n    padding: 6px;\n}}\n\nQCheckBox {{\n    spacing: 5px;\n}}\n\nQCheckBox::indicator {{\n    width: 14px;\n    height: 14px;\n    border: 1px solid #667177;\n    border-radius: 3px;\n}}\n\nQCheckBox::indicator:checked {{\n    background: {c.accent};\n    border-color: {c.accent};\n}}\n\nQGroupBox {{\n    margin-top: 10px;\n    padding: 10px 8px 8px 8px;\n    background: {soft};\n    border: 1px solid {c.border};\n    border-radius: 8px;\n    font-weight: 650;\n}}\n\nQGroupBox::title {{\n    subcontrol-origin: margin;\n    left: 9px;\n    padding: 0 5px;\n    background: {c.window};\n}}\n\nQTableView, QListView, QListWidget, QTreeView {{\n    background: {c.surface};\n    alternate-background-color: {soft};\n    border: 1px solid {c.border};\n    border-radius: 7px;\n    gridline-color: {c.border};\n    selection-background-color: {c.selection};\n    selection-color: {c.text};\n    outline: 0;\n}}\n\nQTableView::item {{\n    padding: 2px 5px;\n    border-bottom: 1px solid {row_line};\n}}\n\nQTableView::item:selected, QListView::item:selected {{\n    border-left: 2px solid {c.accent};\n}}\n\nQListView::item, QListWidget::item {{\n    padding: 6px;\n    border-bottom: 1px solid {row_line};\n}}\n\nQHeaderView::section {{\n    min-height: 28px;\n    padding: 0 6px;\n    background: {header};\n    border: 0;\n    border-right: 1px solid {c.border};\n    border-bottom: 1px solid {c.border};\n    font-weight: 650;\n}}\n\nQLabel[chip="true"] {{\n    padding: 2px 7px;\n    border: 1px solid {c.border};\n    border-radius: 8px;\n    font-weight: 600;\n}}\n\nQLabel[state="success"] {{\n    color: {c.success};\n    background: {success_bg};\n    border-color: #28633F;\n}}\n\nQLabel[state="warning"] {{\n    color: {c.warning};\n    background: {warning_bg};\n    border-color: #695527;\n}}\n\nQLabel[state="error"] {{\n    color: {c.danger};\n    background: {error_bg};\n    border-color: #70343A;\n}}\n\nQLabel[state="active"] {{\n    color: #78A8FF;\n    background: {active_bg};\n    border-color: #315A95;\n}}\n\nQLabel[state="neutral"] {{\n    color: {c.muted_text};\n}}\n\nQTabWidget::pane {{\n    border: 1px solid {c.border};\n    border-radius: 7px;\n}}\n\nQTabBar::tab {{\n    min-height: 29px;\n    padding: 0 12px;\n    margin-right: 2px;\n    background: {c.surface_alt};\n    border: 1px solid {c.border};\n    border-radius: 6px;\n}}\n\nQTabBar::tab:hover {{\n    background: {hover};\n}}\n\nQTabBar::tab:selected {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQTabWidget#contextTabs QTabBar::tab {{\n    min-width: 150px;\n    min-height: 31px;\n    margin: 1px 4px 1px 0;\n    text-align: left;\n}}\n\nQProgressBar {{\n    min-height: 12px;\n    background: {soft};\n    border: 1px solid {c.border};\n    border-radius: 6px;\n    text-align: center;\n}}\n\nQProgressBar::chunk {{\n    background: {c.success};\n    border-radius: 5px;\n}}\n\nQScrollArea {{\n    border: 0;\n    background: transparent;\n}}\n\nQSplitter::handle {{\n    background: {c.window};\n    width: 4px;\n    height: 4px;\n}}\n\nQSplitter::handle:hover {{\n    background: {c.accent};\n}}\n\nQMenu, QToolTip {{\n    background: {c.surface};\n    color: {c.text};\n    border: 1px solid {c.border};\n}}\n\nQMenu::item {{\n    padding: 6px 22px 6px 10px;\n}}\n\nQMenu::item:selected {{\n    background: {c.selection};\n}}\n\nQScrollBar:vertical {{\n    width: 9px;\n    background: transparent;\n}}\n\nQScrollBar::handle:vertical {{\n    background: #485156;\n    border-radius: 4px;\n    min-height: 22px;\n}}\n\nQScrollBar:horizontal {{\n    height: 9px;\n    background: transparent;\n}}\n\nQScrollBar::handle:horizontal {{\n    background: #485156;\n    border-radius: 4px;\n    min-width: 22px;\n}}\n"""\n'
PAYLOAD_WIDGETS = 'from collections.abc import Sequence\n\nfrom PySide6.QtCore import QDateTime, QTimer, Qt\nfrom PySide6.QtGui import QColor\nfrom PySide6.QtWidgets import (\n    QFrame,\n    QHBoxLayout,\n    QLabel,\n    QPushButton,\n    QTableView,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.theme import ThemeMode, palette\n\n\nclass Panel(QFrame):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setProperty("panel", True)\n\n\nclass SoftPanel(QFrame):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setProperty("softPanel", True)\n\n\nclass PrimaryButton(QPushButton):\n    def __init__(self, text: str, parent: QWidget | None = None) -> None:\n        super().__init__(text, parent)\n        self.setProperty("primary", True)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass DestructiveButton(QPushButton):\n    def __init__(self, text: str, parent: QWidget | None = None) -> None:\n        super().__init__(text, parent)\n        self.setProperty("danger", True)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass SecondaryButton(QPushButton):\n    def __init__(self, text: str, parent: QWidget | None = None) -> None:\n        super().__init__(text, parent)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass QuickActionButton(QPushButton):\n    def __init__(\n        self,\n        title: str,\n        subtitle: str = "",\n        icon: str = "›",\n        parent: QWidget | None = None,\n    ) -> None:\n        text = f"{icon}  {title}"\n        if subtitle:\n            text += f"\\n    {subtitle}"\n        super().__init__(text, parent)\n        self.setProperty("quickAction", True)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass FlowStepButton(QPushButton):\n    def __init__(\n        self,\n        number: int,\n        title: str,\n        detail: str = "",\n        parent: QWidget | None = None,\n    ) -> None:\n        text = f"{number}  {title}"\n        if detail:\n            text += f"\\n    {detail}"\n        super().__init__(text, parent)\n        self.setProperty("flowStep", True)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n    def set_flow_state(self, state: str) -> None:\n        self.setProperty("flowState", state)\n        self.style().unpolish(self)\n        self.style().polish(self)\n\n\nclass StatusChip(QLabel):\n    _COLORS = {\n        "success": "success",\n        "warning": "warning",\n        "error": "danger",\n        "neutral": "muted_text",\n        "active": "info",\n    }\n    _STATE_ICONS = {\n        "success": "✓",\n        "warning": "▲",\n        "error": "✖",\n        "danger": "✖",\n        "active": "●",\n        "info": "●",\n        "neutral": "○",\n        "paused": "⏸",\n        "running": "▶",\n    }\n\n    def __init__(\n        self,\n        text: str,\n        state: str = "neutral",\n        mode: ThemeMode | None = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(text, parent)\n        self.setProperty("chip", True)\n        self.update_state(state=state, text=text, mode=mode)\n\n    def update_state(\n        self,\n        state: str,\n        text: str | None = None,\n        mode: ThemeMode | None = None,\n    ) -> None:\n        raw_text = text if text is not None else self.text()\n        icon = self._STATE_ICONS.get(state.lower(), "")\n        display_text = raw_text\n        if icon and not any(raw_text.startswith(ic) for ic in self._STATE_ICONS.values()):\n            display_text = f"{icon} {raw_text}"\n        self.setText(display_text)\n        self.setProperty("state", state)\n        self.setAccessibleName(f"Status: {raw_text}")\n        self.setAccessibleDescription(f"Current status is {state} ({raw_text})")\n        if mode is not None:\n            colors = palette(mode)\n            color = getattr(colors, self._COLORS.get(state, "muted_text"))\n            self.setStyleSheet(f"color: {color}; border-color: {color};")\n        self.style().unpolish(self)\n        self.style().polish(self)\n\n\nclass ClockWidget(QWidget):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setObjectName("topClock")\n        layout = QHBoxLayout(self)\n        layout.setContentsMargins(8, 0, 0, 0)\n        layout.setSpacing(8)\n\n        sun = QLabel("☀")\n        sun.setStyleSheet("font-size: 20px; color: #F4C915;")\n        layout.addWidget(sun)\n\n        stack = QVBoxLayout()\n        stack.setContentsMargins(0, 0, 0, 0)\n        stack.setSpacing(0)\n        self.date_label = QLabel()\n        self.date_label.setObjectName("clockDate")\n        self.time_label = QLabel()\n        self.time_label.setObjectName("clockTime")\n        stack.addWidget(self.date_label)\n        stack.addWidget(self.time_label)\n        layout.addLayout(stack)\n\n        self._timer = QTimer(self)\n        self._timer.timeout.connect(self._refresh)\n        self._timer.start(1000)\n        self._refresh()\n\n    def _refresh(self) -> None:\n        now = QDateTime.currentDateTime()\n        self.date_label.setText(now.toString("ddd, MMM d, yyyy"))\n        self.time_label.setText(now.toString("hh:mm AP"))\n\n\nclass SectionHeader(QWidget):\n    def __init__(\n        self,\n        title: str,\n        subtitle: str = "",\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        layout = QHBoxLayout(self)\n        layout.setContentsMargins(0, 0, 0, 0)\n        stack = QVBoxLayout()\n        stack.setSpacing(0)\n        heading = QLabel(title)\n        heading.setProperty("heading", True)\n        stack.addWidget(heading)\n        if subtitle:\n            detail = QLabel(subtitle)\n            detail.setProperty("muted", True)\n            stack.addWidget(detail)\n        layout.addLayout(stack)\n        layout.addStretch()\n\n\nclass EmptyState(Panel):\n    def __init__(\n        self,\n        title: str,\n        message: str,\n        action_text: str | None = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(16, 14, 16, 14)\n        layout.setSpacing(6)\n        icon = QLabel("◇")\n        icon.setProperty("muted", True)\n        icon.setStyleSheet("font-size: 20px;")\n        layout.addWidget(icon)\n        heading = QLabel(title)\n        heading.setProperty("sectionTitle", True)\n        detail = QLabel(message)\n        detail.setProperty("muted", True)\n        detail.setWordWrap(True)\n        layout.addWidget(heading)\n        layout.addWidget(detail)\n        if action_text:\n            action = PrimaryButton(action_text)\n            layout.addWidget(action, alignment=Qt.AlignmentFlag.AlignLeft)\n\n\nclass CompactTable(QTableView):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setAlternatingRowColors(True)\n        self.setShowGrid(False)\n        self.verticalHeader().setDefaultSectionSize(34)\n        self.verticalHeader().hide()\n        self.horizontalHeader().setStretchLastSection(True)\n\n\nclass MetricRow(QWidget):\n    def __init__(\n        self,\n        metrics: Sequence[tuple[str, str]] = (),\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self._layout = QHBoxLayout(self)\n        self._layout.setContentsMargins(0, 0, 0, 0)\n        self._layout.setSpacing(7)\n        self.value_labels: list[QLabel] = []\n        self.name_labels: list[QLabel] = []\n        if metrics:\n            self.set_metrics(metrics)\n\n    def set_metrics(self, metrics: Sequence[tuple[str, str]]) -> None:\n        if not self.value_labels or len(self.value_labels) != len(metrics):\n            while self._layout.count():\n                item = self._layout.takeAt(0)\n                widget = item.widget() if item else None\n                if widget is not None:\n                    widget.deleteLater()\n            self.value_labels.clear()\n            self.name_labels.clear()\n            for label, value in metrics:\n                panel = Panel()\n                panel.setProperty("metric", True)\n                panel_layout = QVBoxLayout(panel)\n                panel_layout.setContentsMargins(11, 7, 11, 7)\n                panel_layout.setSpacing(2)\n                value_label = QLabel(value)\n                value_label.setProperty("metricValue", True)\n                self.value_labels.append(value_label)\n                name_label = QLabel(label)\n                name_label.setProperty("muted", True)\n                self.name_labels.append(name_label)\n                panel_layout.addWidget(value_label)\n                panel_layout.addWidget(name_label)\n                self._layout.addWidget(panel)\n        else:\n            for idx, (label, value) in enumerate(metrics):\n                self.value_labels[idx].setText(value)\n                self.name_labels[idx].setText(label)\n\n\ndef apply_icon_tint(widget: QWidget, mode: ThemeMode) -> None:\n    widget.setProperty("iconTint", QColor(palette(mode).muted_text))\n'
PAYLOAD_HOME = 'from __future__ import annotations\n\nfrom PySide6.QtCore import Signal\nfrom PySide6.QtWidgets import (\n    QGridLayout,\n    QHBoxLayout,\n    QLabel,\n    QListWidget,\n    QListWidgetItem,\n    QPushButton,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.widgets import (\n    FlowStepButton,\n    MetricRow,\n    Panel,\n    PrimaryButton,\n    QuickActionButton,\n    StatusChip,\n)\nfrom sp_farms.application.context import ApplicationContext\nfrom sp_farms.domain.device_management import ManagedDevice\nfrom sp_farms.domain.jobs import JobState\n\n\nclass HomeDashboard(QWidget):\n    """Reference-inspired operator dashboard with an obvious end-to-end flow."""\n\n    route_requested = Signal(str)\n\n    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setObjectName("homeDashboard")\n        self._context = context\n        self._devices: tuple[ManagedDevice, ...] = ()\n        self._build_ui()\n        self.refresh()\n\n    def _build_ui(self) -> None:\n        root = QVBoxLayout(self)\n        root.setContentsMargins(10, 9, 10, 8)\n        root.setSpacing(8)\n\n        header = QHBoxLayout()\n        title_stack = QVBoxLayout()\n        title_stack.setSpacing(0)\n        title = QLabel("Dashboard Overview")\n        title.setProperty("heading", True)\n        title_stack.addWidget(title)\n        subtitle = QLabel("System health, active work, recent activity, and quick actions")\n        subtitle.setProperty("muted", True)\n        title_stack.addWidget(subtitle)\n        header.addLayout(title_stack)\n        header.addStretch()\n        refresh = PrimaryButton("↻ Refresh")\n        refresh.clicked.connect(self.refresh)\n        header.addWidget(refresh)\n        root.addLayout(header)\n\n        self.metrics = MetricRow(\n            (\n                ("Total Accounts", "0"),\n                ("Online Devices", "0"),\n                ("Running Tasks", "0"),\n                ("Queue", "0"),\n                ("Success", "0"),\n                ("Failed", "0"),\n            )\n        )\n        root.addWidget(self.metrics)\n\n        flow_panel = Panel()\n        flow_panel.setProperty("flowPanel", True)\n        flow = QHBoxLayout(flow_panel)\n        flow.setContentsMargins(9, 7, 9, 7)\n        flow.setSpacing(5)\n        flow_title = QLabel("QUICK FLOW")\n        flow_title.setProperty("sectionTitle", True)\n        flow.addWidget(flow_title)\n\n        flow_defs = (\n            ("Account", "Select / health", "Accounts"),\n            ("Device + Network", "Resolve binding", "Devices"),\n            ("Restore", "Workspace + app", "Accounts"),\n            ("Action", "Post / Reel / task", "Content"),\n            ("Monitor", "Queue + results", "Automation"),\n        )\n        self.flow_buttons: list[FlowStepButton] = []\n        for index, (name, detail, route) in enumerate(flow_defs, start=1):\n            button = FlowStepButton(index, name, detail)\n            button.clicked.connect(\n                lambda checked=False, target=route: self.route_requested.emit(target)\n            )\n            self.flow_buttons.append(button)\n            flow.addWidget(button, stretch=1)\n            if index < len(flow_defs):\n                arrow = QLabel("→")\n                arrow.setProperty("flowArrow", True)\n                flow.addWidget(arrow)\n        root.addWidget(flow_panel)\n\n        body = QGridLayout()\n        body.setSpacing(8)\n\n        quick = Panel()\n        quick_layout = QVBoxLayout(quick)\n        quick_layout.setContentsMargins(10, 9, 10, 9)\n        quick_layout.setSpacing(6)\n        quick_title = QLabel("Quick Actions")\n        quick_title.setProperty("sectionTitle", True)\n        quick_layout.addWidget(quick_title)\n\n        quick_grid = QGridLayout()\n        quick_grid.setSpacing(6)\n        actions = (\n            ("Accounts", "Manage & restore", "👤", "Accounts"),\n            ("Compose", "Post / Reel / Story", "✦", "Content"),\n            ("Automation", "Quick presets", "⚡", "Automation"),\n            ("Devices", "LDPlayer / MuMu / Android", "▣", "Devices"),\n            ("Analytics", "Performance & reliability", "▥", "Analytics"),\n            ("Security", "Auth / 2FA / sessions", "🛡", "Security"),\n            ("Errors", "Failures & audit trail", "!", "Error Center"),\n            ("Settings", "App & integrations", "⚙", "Settings"),\n        )\n        for i, (title, subtitle, icon, route) in enumerate(actions):\n            button = QuickActionButton(title, subtitle, icon)\n            button.clicked.connect(\n                lambda checked=False, target=route: self.route_requested.emit(target)\n            )\n            quick_grid.addWidget(button, i // 2, i % 2)\n        quick_layout.addLayout(quick_grid)\n        quick_layout.addStretch()\n        body.addWidget(quick, 0, 0)\n\n        health = Panel()\n        health_layout = QVBoxLayout(health)\n        health_layout.setContentsMargins(10, 9, 10, 9)\n        health_layout.setSpacing(6)\n        health_title = QLabel("System Status")\n        health_title.setProperty("sectionTitle", True)\n        health_layout.addWidget(health_title)\n\n        self.device_health = StatusChip("No devices", "neutral")\n        self.job_health = StatusChip("No jobs", "neutral")\n        self.account_health = StatusChip("No accounts", "neutral")\n        self.queue_health = StatusChip("Queue clear", "success")\n        health_layout.addWidget(self.device_health)\n        health_layout.addWidget(self.job_health)\n        health_layout.addWidget(self.account_health)\n        health_layout.addWidget(self.queue_health)\n        health_layout.addStretch()\n\n        open_devices = QPushButton("Open Device Manager")\n        open_devices.clicked.connect(lambda: self.route_requested.emit("Devices"))\n        health_layout.addWidget(open_devices)\n        open_auto = QPushButton("Open Automation")\n        open_auto.clicked.connect(lambda: self.route_requested.emit("Automation"))\n        health_layout.addWidget(open_auto)\n        body.addWidget(health, 0, 1)\n\n        jobs = Panel()\n        jobs_layout = QVBoxLayout(jobs)\n        jobs_layout.setContentsMargins(10, 9, 10, 9)\n        jobs_layout.setSpacing(6)\n        jobs_header = QHBoxLayout()\n        jobs_title = QLabel("Recent Activities")\n        jobs_title.setProperty("sectionTitle", True)\n        jobs_header.addWidget(jobs_title)\n        jobs_header.addStretch()\n        jobs_open = QPushButton("View Queue")\n        jobs_open.clicked.connect(lambda: self.route_requested.emit("Automation"))\n        jobs_header.addWidget(jobs_open)\n        jobs_layout.addLayout(jobs_header)\n\n        self.recent_jobs = QListWidget()\n        self.recent_jobs.setObjectName("homeRecentJobs")\n        self.recent_jobs.setUniformItemSizes(True)\n        jobs_layout.addWidget(self.recent_jobs, stretch=1)\n        body.addWidget(jobs, 1, 0)\n\n        devices = Panel()\n        device_layout = QVBoxLayout(devices)\n        device_layout.setContentsMargins(10, 9, 10, 9)\n        device_layout.setSpacing(6)\n        device_head = QHBoxLayout()\n        device_title = QLabel("Device Snapshot")\n        device_title.setProperty("sectionTitle", True)\n        device_head.addWidget(device_title)\n        device_head.addStretch()\n        manage = QPushButton("Manage")\n        manage.clicked.connect(lambda: self.route_requested.emit("Devices"))\n        device_head.addWidget(manage)\n        device_layout.addLayout(device_head)\n\n        self.device_list = QListWidget()\n        self.device_list.setObjectName("homeDeviceSnapshot")\n        self.device_list.setUniformItemSizes(True)\n        device_layout.addWidget(self.device_list, stretch=1)\n        body.addWidget(devices, 1, 1)\n\n        body.setColumnStretch(0, 3)\n        body.setColumnStretch(1, 2)\n        body.setRowStretch(1, 1)\n        root.addLayout(body, stretch=1)\n\n    def set_devices(self, devices: tuple[ManagedDevice, ...]) -> None:\n        self._devices = devices\n        self.refresh()\n\n    @staticmethod\n    def _state_text(state: object) -> str:\n        value = getattr(state, "value", None)\n        return str(value if value is not None else state).replace("_", " ").title()\n\n    def refresh(self) -> None:\n        accounts = (\n            tuple(self._context.account_service.list_accounts())\n            if self._context.account_service is not None\n            else ()\n        )\n        jobs = (\n            tuple(self._context.job_service.list_jobs())\n            if self._context.job_service is not None\n            else ()\n        )\n        online = sum(bool(device.is_online) for device in self._devices)\n        running = sum(job.state is JobState.RUNNING for job in jobs)\n        queued = sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs)\n        succeeded = sum(job.state is JobState.SUCCEEDED for job in jobs)\n        failed = sum(job.state is JobState.FAILED for job in jobs)\n\n        values = (len(accounts), online, running, queued, succeeded, failed)\n        for label, value in zip(self.metrics.value_labels, values, strict=True):\n            label.setText(str(value))\n\n        self.device_health.update_state(\n            "success" if online else "neutral",\n            f"Devices: {online}/{len(self._devices)} online",\n        )\n        self.job_health.update_state(\n            "error" if failed else "active" if running else "success",\n            f"Jobs: {running} running · {failed} failed",\n        )\n        self.account_health.update_state(\n            "success" if accounts else "neutral",\n            f"Accounts: {len(accounts)} connected",\n        )\n        self.queue_health.update_state(\n            "warning" if queued else "success",\n            f"Queue: {queued} waiting" if queued else "Queue is clear",\n        )\n\n        flow_states = (\n            "done" if accounts else "next",\n            "done" if online else ("next" if accounts else ""),\n            "done" if running or succeeded else ("next" if online else ""),\n            "done" if running else ("next" if online else ""),\n            "done" if succeeded or failed else ("next" if running else ""),\n        )\n        for button, state in zip(self.flow_buttons, flow_states, strict=True):\n            button.set_flow_state(state)\n\n        self.recent_jobs.clear()\n        recent = list(jobs[-8:])\n        if not recent:\n            self.recent_jobs.addItem("No recent jobs · use Quick Automation when ready.")\n        else:\n            for job in reversed(recent):\n                state = self._state_text(getattr(job, "state", "unknown"))\n                job_type = str(\n                    getattr(job, "job_type", None)\n                    or getattr(job, "type", None)\n                    or "Job"\n                ).replace("_", " ")\n                short_id = str(getattr(job, "id", ""))[:8]\n                self.recent_jobs.addItem(\n                    QListWidgetItem(f"{state:12}  {job_type}  {short_id}")\n                )\n\n        self.device_list.clear()\n        if not self._devices:\n            self.device_list.addItem("No devices discovered · open Device Manager.")\n        else:\n            for device in self._devices[:8]:\n                provider = getattr(getattr(device, "provider", None), "value", "device")\n                account = device.assigned_account or "Unassigned"\n                net = device.network_state or "System"\n                self.device_list.addItem(\n                    f"{\'●\' if device.is_online else \'○\'} {device.display_name} "\n                    f"· {provider} · {account} · {net}"\n                )\n'
PAYLOAD_QUICK = 'from __future__ import annotations\n\nfrom PySide6.QtCore import Signal\nfrom PySide6.QtWidgets import (\n    QCheckBox,\n    QComboBox,\n    QFormLayout,\n    QHBoxLayout,\n    QLabel,\n    QLineEdit,\n    QListWidget,\n    QMessageBox,\n    QPushButton,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.automation_builder_workspace import DryRunDialog\nfrom sp_farms.app.widgets import FlowStepButton, Panel, PrimaryButton, SecondaryButton, StatusChip\nfrom sp_farms.application.automation_builder import AutomationBuilderService\nfrom sp_farms.domain.automation_builder import AutomationPreset\n\n\nclass QuickAutomationWorkspace(QWidget):\n    """Farm-Reel-simple front end on the existing real automation service."""\n\n    advanced_requested = Signal()\n\n    def __init__(\n        self,\n        service: AutomationBuilderService,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self._service = service\n        self.setObjectName("quickAutomationWorkspace")\n        self._build_ui()\n        self.refresh_presets()\n\n    def _build_ui(self) -> None:\n        root = QVBoxLayout(self)\n        root.setContentsMargins(10, 9, 10, 9)\n        root.setSpacing(8)\n\n        header = QHBoxLayout()\n        stack = QVBoxLayout()\n        stack.setSpacing(0)\n        title = QLabel("Quick Automation")\n        title.setProperty("heading", True)\n        stack.addWidget(title)\n        subtitle = QLabel("Preset → targets → dry run → start → monitor")\n        subtitle.setProperty("muted", True)\n        stack.addWidget(subtitle)\n        header.addLayout(stack)\n        header.addStretch()\n        advanced = SecondaryButton("Advanced Builder")\n        advanced.clicked.connect(self.advanced_requested.emit)\n        header.addWidget(advanced)\n        root.addLayout(header)\n\n        flow_panel = Panel()\n        flow_panel.setProperty("flowPanel", True)\n        flow = QHBoxLayout(flow_panel)\n        flow.setContentsMargins(8, 7, 8, 7)\n        flow.setSpacing(5)\n        self.flow_buttons = [\n            FlowStepButton(1, "Preset", "Choose workflow"),\n            FlowStepButton(2, "Targets", "Accounts / assets"),\n            FlowStepButton(3, "Dry Run", "Zero side effects"),\n            FlowStepButton(4, "Start", "Create jobs"),\n            FlowStepButton(5, "Monitor", "Job Queue"),\n        ]\n        for index, button in enumerate(self.flow_buttons):\n            flow.addWidget(button, stretch=1)\n            if index < len(self.flow_buttons) - 1:\n                arrow = QLabel("→")\n                arrow.setProperty("flowArrow", True)\n                flow.addWidget(arrow)\n        root.addWidget(flow_panel)\n\n        body = QHBoxLayout()\n        body.setSpacing(8)\n\n        settings = Panel()\n        settings_layout = QVBoxLayout(settings)\n        settings_layout.setContentsMargins(11, 10, 11, 10)\n        settings_layout.setSpacing(8)\n        form = QFormLayout()\n        form.setHorizontalSpacing(12)\n        form.setVerticalSpacing(7)\n\n        self.preset_combo = QComboBox()\n        self.preset_combo.currentIndexChanged.connect(self._refresh_summary)\n        form.addRow("Workflow:", self.preset_combo)\n\n        self.use_preset_targets = QCheckBox("Use targets saved in preset")\n        self.use_preset_targets.setChecked(True)\n        self.use_preset_targets.toggled.connect(self._target_mode_changed)\n        form.addRow("Targets:", self.use_preset_targets)\n\n        self.account_ids = QLineEdit()\n        self.account_ids.setPlaceholderText("account-id-1, account-id-2")\n        self.account_ids.setEnabled(False)\n        self.account_ids.textChanged.connect(self._refresh_flow)\n        form.addRow("Accounts:", self.account_ids)\n\n        self.destination_ids = QLineEdit()\n        self.destination_ids.setPlaceholderText("page-id-1, destination-id-2")\n        self.destination_ids.setEnabled(False)\n        self.destination_ids.textChanged.connect(self._refresh_flow)\n        form.addRow("Destinations:", self.destination_ids)\n\n        settings_layout.addLayout(form)\n        self.status = StatusChip("Ready", "success")\n        settings_layout.addWidget(self.status)\n\n        actions = QHBoxLayout()\n        refresh = QPushButton("↻ Refresh")\n        refresh.clicked.connect(self.refresh_presets)\n        actions.addWidget(refresh)\n        actions.addStretch()\n\n        dry_run = SecondaryButton("Dry Run")\n        dry_run.setProperty("infoAction", True)\n        dry_run.clicked.connect(self._dry_run)\n        actions.addWidget(dry_run)\n\n        run = PrimaryButton("▶ Start Workflow")\n        run.setProperty("successAction", True)\n        run.clicked.connect(self._run)\n        actions.addWidget(run)\n        settings_layout.addLayout(actions)\n        body.addWidget(settings, stretch=3)\n\n        preview = Panel()\n        preview_layout = QVBoxLayout(preview)\n        preview_layout.setContentsMargins(10, 9, 10, 9)\n        preview_layout.setSpacing(6)\n        preview_title = QLabel("Selected Actions")\n        preview_title.setProperty("sectionTitle", True)\n        preview_layout.addWidget(preview_title)\n        self.summary = QLabel("Select a preset.")\n        self.summary.setProperty("muted", True)\n        self.summary.setWordWrap(True)\n        preview_layout.addWidget(self.summary)\n        self.steps = QListWidget()\n        self.steps.setObjectName("quickAutomationSteps")\n        preview_layout.addWidget(self.steps, stretch=1)\n        body.addWidget(preview, stretch=2)\n\n        root.addLayout(body, stretch=1)\n        self._refresh_flow()\n\n    def refresh_presets(self) -> None:\n        current_id = self.preset_combo.currentData()\n        self.preset_combo.blockSignals(True)\n        self.preset_combo.clear()\n        for preset in self._service.list_presets():\n            suffix = " · Built-in" if preset.is_built_in else ""\n            self.preset_combo.addItem(f"{preset.name}{suffix}", preset.id)\n        if current_id:\n            for index in range(self.preset_combo.count()):\n                if self.preset_combo.itemData(index) == current_id:\n                    self.preset_combo.setCurrentIndex(index)\n                    break\n        self.preset_combo.blockSignals(False)\n        self._refresh_summary()\n\n    def _selected_preset(self) -> AutomationPreset | None:\n        preset_id = self.preset_combo.currentData()\n        return self._service.get_preset(str(preset_id)) if preset_id else None\n\n    @staticmethod\n    def _parse_ids(text: str) -> list[str]:\n        return [value.strip() for value in text.replace("\\n", ",").split(",") if value.strip()]\n\n    def _targets(self) -> tuple[list[str] | None, list[str] | None]:\n        if self.use_preset_targets.isChecked():\n            return None, None\n        return self._parse_ids(self.account_ids.text()), self._parse_ids(\n            self.destination_ids.text()\n        )\n\n    def _target_mode_changed(self, checked: bool) -> None:\n        self.account_ids.setEnabled(not checked)\n        self.destination_ids.setEnabled(not checked)\n        self._refresh_flow()\n\n    def _refresh_flow(self) -> None:\n        preset_ready = self._selected_preset() is not None\n        target_ready = self.use_preset_targets.isChecked() or bool(\n            self._parse_ids(self.account_ids.text())\n        )\n        states = (\n            "done" if preset_ready else "next",\n            "done" if target_ready else ("next" if preset_ready else ""),\n            "next" if preset_ready and target_ready else "",\n            "",\n            "",\n        )\n        for button, state in zip(self.flow_buttons, states, strict=True):\n            button.set_flow_state(state)\n\n    def _refresh_summary(self) -> None:\n        preset = self._selected_preset()\n        self.steps.clear()\n        if preset is None:\n            self.summary.setText("No presets are available.")\n            self.status.update_state("warning", "No preset")\n            self._refresh_flow()\n            return\n\n        enabled = sorted((step for step in preset.steps if step.enabled), key=lambda step: step.order)\n        approvals = sum(step.requires_approval for step in enabled)\n        self.summary.setText(\n            f"{preset.description}\\n\\n{len(enabled)} enabled steps · "\n            f"{approvals} approval-gated · max "\n            f"{preset.target_rules.max_concurrent_devices} devices."\n        )\n        for step in enabled:\n            title = step.step_type.value.replace("_", " ").title()\n            approval = " · approval" if step.requires_approval else ""\n            self.steps.addItem(f"{step.order:02d}. {title}{approval}")\n\n        errors = self._service.validate_preset(preset)\n        self.status.update_state(\n            "warning" if errors else "success",\n            f"{len(errors)} validation issue(s)" if errors else "Preset ready",\n        )\n        self._refresh_flow()\n\n    def _dry_run(self) -> None:\n        preset = self._selected_preset()\n        if preset is None:\n            QMessageBox.warning(self, "Quick Automation", "Select a preset first.")\n            return\n        accounts, destinations = self._targets()\n        if not self.use_preset_targets.isChecked() and not accounts:\n            QMessageBox.warning(\n                self,\n                "Quick Automation",\n                "Enter at least one authorized account ID or use preset targets.",\n            )\n            return\n        report = self._service.generate_dry_run_report(\n            preset,\n            target_accounts=accounts,\n            target_destinations=destinations,\n        )\n        self.flow_buttons[2].set_flow_state("done")\n        self.flow_buttons[3].set_flow_state("next")\n        DryRunDialog(report, self).exec()\n\n    def _run(self) -> None:\n        preset = self._selected_preset()\n        if preset is None:\n            QMessageBox.warning(self, "Quick Automation", "Select a preset first.")\n            return\n        accounts, destinations = self._targets()\n        if not self.use_preset_targets.isChecked() and not accounts:\n            QMessageBox.warning(\n                self,\n                "Quick Automation",\n                "Enter at least one authorized account ID or use preset targets.",\n            )\n            return\n\n        answer = QMessageBox.question(\n            self,\n            "Start workflow?",\n            f"Start \'{preset.name}\' now?",\n            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,\n            QMessageBox.StandardButton.No,\n        )\n        if answer != QMessageBox.StandardButton.Yes:\n            return\n\n        success, message, job_ids = self._service.execute_preset(\n            preset,\n            target_accounts=accounts,\n            target_destinations=destinations,\n            initiator="operator_quick_mode",\n        )\n        if success:\n            self.status.update_state("active", f"Started · {len(job_ids)} job(s)")\n            self.flow_buttons[3].set_flow_state("done")\n            self.flow_buttons[4].set_flow_state("next")\n            QMessageBox.information(\n                self,\n                "Workflow started",\n                f"{message}\\n\\nCreated jobs: {len(job_ids)}",\n            )\n        else:\n            self.status.update_state("error", "Could not start")\n            QMessageBox.warning(self, "Workflow not started", message)\n'
PAYLOAD_WORKSPACES = 'from collections.abc import Sequence\nfrom typing import TYPE_CHECKING\n\nfrom PySide6.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal\nfrom PySide6.QtGui import QStandardItemModel\nfrom PySide6.QtWidgets import (\n    QCheckBox,\n    QComboBox,\n    QFormLayout,\n    QHBoxLayout,\n    QHeaderView,\n    QLabel,\n    QLineEdit,\n    QListView,\n    QPushButton,\n    QSplitter,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.widgets import (\n    CompactTable,\n    MetricRow,\n    Panel,\n    PrimaryButton,\n    SecondaryButton,\n    StatusChip,\n)\nfrom sp_farms.domain.device_management import ManagedDevice\nfrom sp_farms.domain.jobs import Job, JobState\n\nif TYPE_CHECKING:\n    from sp_farms.app.device_manager import DeviceManagerView\n    from sp_farms.application.job_service import JobService\n\n\nclass RailFilterProxy(QSortFilterProxyModel):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self._search = ""\n        self._mode = "all"\n\n    def set_search(self, value: str) -> None:\n        self._search = value.strip().lower()\n        self.invalidateFilter()\n\n    def set_mode(self, value: str) -> None:\n        self._mode = value.strip().lower()\n        self.invalidateFilter()\n\n    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]\n        source = self.sourceModel()\n        if source is None:\n            return True\n        index = source.index(source_row, 0, source_parent)\n        device = source.data(index, Qt.ItemDataRole.UserRole)\n        if not isinstance(device, ManagedDevice):\n            return True\n\n        mode = self._mode\n        if mode == "online" and not device.is_online:\n            return False\n        if mode == "offline" and device.is_online:\n            return False\n        if mode in {"ldplayer", "mumu", "physical"} and device.provider.value != mode:\n            return False\n\n        haystack = " ".join(\n            (\n                device.display_name,\n                device.provider.value,\n                device.adb_serial,\n                device.assigned_account or "",\n                device.network_state or "",\n            )\n        ).lower()\n        return not self._search or self._search in haystack\n\n\nclass DeviceRail(Panel):\n    devices_route_requested = Signal()\n    automation_route_requested = Signal()\n    settings_route_requested = Signal()\n\n    def __init__(\n        self,\n        model: QAbstractItemModel | None = None,\n        controller: "DeviceManagerView | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("deviceRail")\n        self.setMinimumWidth(245)\n        self.setMaximumWidth(300)\n        self._controller = controller\n        self._model = model\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(8, 8, 8, 8)\n        layout.setSpacing(6)\n\n        header = QHBoxLayout()\n        title = QLabel("Device Manager")\n        title.setProperty("heading", True)\n        header.addWidget(title)\n        header.addStretch()\n        self.online_chip = StatusChip("0 Online", "neutral")\n        header.addWidget(self.online_chip)\n        layout.addLayout(header)\n\n        control_row = QHBoxLayout()\n        self.refresh_btn = SecondaryButton("↻ Refresh")\n        self.add_btn = PrimaryButton("+ Add Device")\n        control_row.addWidget(self.refresh_btn)\n        control_row.addWidget(self.add_btn)\n        layout.addLayout(control_row)\n\n        self.search = QLineEdit()\n        self.search.setPlaceholderText("Search devices...")\n        layout.addWidget(self.search)\n\n        filters = QHBoxLayout()\n        self.mode_filter = QComboBox()\n        self.mode_filter.addItems(\n            ("All Devices", "Online", "Offline", "LDPlayer", "MuMu", "Physical")\n        )\n        self.show_ip = QCheckBox("Show IP")\n        filters.addWidget(self.mode_filter, stretch=1)\n        filters.addWidget(self.show_ip)\n        layout.addLayout(filters)\n\n        self.proxy = RailFilterProxy(self)\n        if model is not None:\n            self.proxy.setSourceModel(model)\n        self.list_view = QListView()\n        self.list_view.setObjectName("deviceRailList")\n        self.list_view.setUniformItemSizes(True)\n        self.list_view.setModel(self.proxy)\n        layout.addWidget(self.list_view, stretch=1)\n\n        preview = Panel()\n        preview_layout = QVBoxLayout(preview)\n        preview_layout.setContentsMargins(8, 7, 8, 7)\n        preview_layout.setSpacing(5)\n\n        preview_head = QHBoxLayout()\n        self.preview_name = QLabel("No device selected")\n        self.preview_name.setProperty("sectionTitle", True)\n        preview_head.addWidget(self.preview_name)\n        preview_head.addStretch()\n        self.preview_state = StatusChip("Offline", "neutral")\n        preview_head.addWidget(self.preview_state)\n        preview_layout.addLayout(preview_head)\n\n        form = QFormLayout()\n        form.setContentsMargins(0, 0, 0, 0)\n        form.setHorizontalSpacing(7)\n        form.setVerticalSpacing(3)\n        self.preview_provider = QLabel("—")\n        self.preview_account = QLabel("—")\n        self.preview_network = QLabel("—")\n        self.preview_usage = QLabel("—")\n        self.preview_adb = QLabel("—")\n        for label in (\n            self.preview_provider,\n            self.preview_account,\n            self.preview_network,\n            self.preview_usage,\n            self.preview_adb,\n        ):\n            label.setProperty("muted", True)\n        form.addRow("Device:", self.preview_provider)\n        form.addRow("Account:", self.preview_account)\n        form.addRow("Network:", self.preview_network)\n        form.addRow("CPU / RAM:", self.preview_usage)\n        form.addRow("ADB:", self.preview_adb)\n        preview_layout.addLayout(form)\n\n        self.open_device_btn = PrimaryButton("▣ Open Device Manager")\n        self.open_device_btn.clicked.connect(self.devices_route_requested.emit)\n        preview_layout.addWidget(self.open_device_btn)\n\n        local_actions = QHBoxLayout()\n        self.start_btn = PrimaryButton("Start")\n        self.stop_btn = SecondaryButton("Stop")\n        self.restart_btn = SecondaryButton("Restart")\n        local_actions.addWidget(self.start_btn)\n        local_actions.addWidget(self.stop_btn)\n        local_actions.addWidget(self.restart_btn)\n        preview_layout.addLayout(local_actions)\n\n        artifact_row = QHBoxLayout()\n        self.package_input = QLineEdit()\n        self.package_input.setPlaceholderText("App package")\n        self.launch_btn = SecondaryButton("Launch")\n        self.screenshot_btn = SecondaryButton("Shot")\n        artifact_row.addWidget(self.package_input, stretch=1)\n        artifact_row.addWidget(self.launch_btn)\n        artifact_row.addWidget(self.screenshot_btn)\n        preview_layout.addLayout(artifact_row)\n        layout.addWidget(preview)\n\n        quick_title = QLabel("Quick Actions")\n        quick_title.setProperty("sectionTitle", True)\n        layout.addWidget(quick_title)\n\n        self.start_all_btn = QPushButton("▶  Start All Devices")\n        self.stop_all_btn = QPushButton("■  Stop All Devices")\n        self.devices_btn = QPushButton("▣  Full Device Manager")\n        self.automation_btn = QPushButton("⚡  Automation Builder")\n        self.network_btn = QPushButton("⌁  Network Settings")\n        for button in (\n            self.start_all_btn,\n            self.stop_all_btn,\n            self.devices_btn,\n            self.automation_btn,\n            self.network_btn,\n        ):\n            button.setProperty("quickAction", True)\n            layout.addWidget(button)\n\n        self.search.textChanged.connect(self.proxy.set_search)\n        self.mode_filter.currentTextChanged.connect(\n            lambda text: self.proxy.set_mode(\n                {\n                    "All Devices": "all",\n                    "Online": "online",\n                    "Offline": "offline",\n                    "LDPlayer": "ldplayer",\n                    "MuMu": "mumu",\n                    "Physical": "physical",\n                }.get(text, "all")\n            )\n        )\n        self.refresh_btn.clicked.connect(self._refresh)\n        self.add_btn.clicked.connect(self.devices_route_requested.emit)\n        self.devices_btn.clicked.connect(self.devices_route_requested.emit)\n        self.automation_btn.clicked.connect(self.automation_route_requested.emit)\n        self.network_btn.clicked.connect(self.settings_route_requested.emit)\n        self.list_view.selectionModel().selectionChanged.connect(self._selection_changed)\n        self.show_ip.toggled.connect(self._selection_changed)\n        self.package_input.textChanged.connect(self._selection_changed)\n        self.start_btn.clicked.connect(lambda: self._run("start"))\n        self.stop_btn.clicked.connect(lambda: self._run("stop"))\n        self.restart_btn.clicked.connect(lambda: self._run("restart"))\n        self.launch_btn.clicked.connect(lambda: self._run("launch_app"))\n        self.screenshot_btn.clicked.connect(lambda: self._artifact("screenshot"))\n        self.start_all_btn.clicked.connect(lambda: self._run_all("start"))\n        self.stop_all_btn.clicked.connect(lambda: self._run_all("stop"))\n\n        if model is not None:\n            model.modelReset.connect(self._model_reset)\n            model.rowsInserted.connect(self._model_reset)\n            model.rowsRemoved.connect(self._model_reset)\n        self._model_reset()\n        self._selection_changed()\n\n    def _selected_device(self) -> ManagedDevice | None:\n        index = self.list_view.currentIndex()\n        if not index.isValid():\n            return None\n        device = self.proxy.data(index, Qt.ItemDataRole.UserRole)\n        return device if isinstance(device, ManagedDevice) else None\n\n    def _all_devices(self) -> tuple[ManagedDevice, ...]:\n        devices: list[ManagedDevice] = []\n        if self._model is None:\n            return ()\n        for row in range(self._model.rowCount()):\n            device = self._model.data(self._model.index(row, 0), Qt.ItemDataRole.UserRole)\n            if isinstance(device, ManagedDevice):\n                devices.append(device)\n        return tuple(devices)\n\n    def _refresh(self) -> None:\n        if self._controller is not None:\n            self._controller.refresh()\n\n    def _model_reset(self) -> None:\n        devices = self._all_devices()\n        online = sum(device.is_online for device in devices)\n        self.online_chip.update_state(\n            "success" if online else "neutral",\n            f"{online} Online",\n        )\n        self.start_all_btn.setEnabled(\n            bool(devices)\n            and any(device.capabilities.can_start_stop and not device.is_online for device in devices)\n        )\n        self.stop_all_btn.setEnabled(\n            any(device.capabilities.can_start_stop and device.is_online for device in devices)\n        )\n        self._selection_changed()\n\n    def _selection_changed(self) -> None:\n        device = self._selected_device()\n        if device is None:\n            self.preview_name.setText("No device selected")\n            self.preview_state.update_state("neutral", "Offline")\n            self.preview_provider.setText("—")\n            self.preview_account.setText("—")\n            self.preview_network.setText("—")\n            self.preview_usage.setText("—")\n            self.preview_adb.setText("—")\n            for button in (\n                self.start_btn,\n                self.stop_btn,\n                self.restart_btn,\n                self.launch_btn,\n                self.screenshot_btn,\n            ):\n                button.setEnabled(False)\n            return\n\n        self.preview_name.setText(device.display_name)\n        self.preview_state.update_state(\n            "success" if device.is_online else "error",\n            "Running" if device.is_online else "Offline",\n        )\n        self.preview_provider.setText(\n            f"{device.provider.value} · Android {device.android_version or \'—\'}"\n        )\n        self.preview_account.setText(device.assigned_account or "Unassigned")\n        network = device.network_state or "System"\n        if not self.show_ip.isChecked() and "ip" in network.lower():\n            network = "Connected"\n        self.preview_network.setText(network)\n        cpu = f"{device.cpu_usage:.0f}%" if device.cpu_usage is not None else "—"\n        ram = f"{device.ram_usage_mb} MB" if device.ram_usage_mb is not None else "—"\n        self.preview_usage.setText(f"{cpu} / {ram}")\n        self.preview_adb.setText(device.adb_serial or "No ADB serial")\n\n        caps = device.capabilities\n        self.start_btn.setEnabled(caps.can_start_stop and not device.is_online)\n        self.stop_btn.setEnabled(caps.can_start_stop and device.is_online)\n        self.restart_btn.setEnabled(caps.can_restart and device.is_online)\n        self.launch_btn.setEnabled(\n            caps.can_launch_apps and device.is_online and bool(self.package_input.text().strip())\n        )\n        self.screenshot_btn.setEnabled(caps.can_take_screenshot and device.is_online)\n\n    def _run(self, action: str) -> None:\n        device = self._selected_device()\n        if device is not None and self._controller is not None:\n            package = self.package_input.text().strip() if action == "launch_app" else None\n            self._controller.run_devices(action, (device,), package)\n\n    def _run_all(self, action: str) -> None:\n        if self._controller is None:\n            return\n        devices = tuple(\n            device\n            for device in self._all_devices()\n            if device.capabilities.can_start_stop\n            and ((action == "start" and not device.is_online) or (action == "stop" and device.is_online))\n        )\n        if devices:\n            self._controller.run_devices(action, devices)\n\n    def _artifact(self, action: str) -> None:\n        device = self._selected_device()\n        if device is not None and self._controller is not None:\n            self._controller.collect_device_artifacts(action, (device,))\n\n\nclass ManagementWorkspace(QWidget):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setObjectName("managementWorkspace")\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(0, 0, 0, 0)\n        layout.setSpacing(8)\n        layout.addWidget(\n            MetricRow((("Accounts", "0"), ("Active", "0"), ("Needs attention", "0")))\n        )\n\n        toolbar = Panel()\n        toolbar_layout = QHBoxLayout(toolbar)\n        toolbar_layout.setContentsMargins(10, 7, 10, 7)\n        toolbar_layout.addWidget(QLineEdit("Search accounts, pages, or groups"), stretch=1)\n        toolbar_layout.addWidget(QPushButton("Filter"))\n        toolbar_layout.addWidget(PrimaryButton("Add account"))\n        layout.addWidget(toolbar)\n\n        table = CompactTable()\n        table.setObjectName("managementTable")\n        model = QStandardItemModel(0, 6, table)\n        model.setHorizontalHeaderLabels(\n            ("Account", "Status", "Device", "Network", "Last active", "Actions")\n        )\n        table.setModel(model)\n        header = table.horizontalHeader()\n        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)\n        for column in range(1, 6):\n            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)\n        layout.addWidget(table, stretch=1)\n\n\nclass JobQueueDrawer(Panel):\n    automation_route_requested = Signal()\n\n    def __init__(\n        self,\n        service: "JobService | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("jobQueueDrawer")\n        self.setMinimumWidth(250)\n        self.setMaximumWidth(340)\n        self._service = service\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(10, 10, 10, 10)\n        heading = QLabel("Job Queue")\n        heading.setProperty("sectionTitle", True)\n        layout.addWidget(heading)\n        self.status = StatusChip("0 running", "neutral")\n        layout.addWidget(self.status)\n        self.summary = QLabel("Queue is clear")\n        self.summary.setProperty("muted", True)\n        self.summary.setWordWrap(True)\n        layout.addWidget(self.summary)\n        open_queue = PrimaryButton("Open Automation")\n        open_queue.clicked.connect(self.automation_route_requested.emit)\n        layout.addWidget(open_queue)\n        layout.addStretch()\n        self.refresh()\n\n    def refresh(self) -> tuple[Job, ...]:\n        jobs = tuple(self._service.list_jobs()) if self._service is not None else ()\n        running = sum(job.state is JobState.RUNNING for job in jobs)\n        queued = sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs)\n        failed = sum(job.state is JobState.FAILED for job in jobs)\n        self.status.update_state(\n            "error" if failed else "active" if running else "neutral",\n            f"{running} running",\n        )\n        self.summary.setText(f"{queued} queued • {failed} failed" if jobs else "Queue is clear")\n        return jobs\n\n\nclass WorkspaceLayout(QWidget):\n    devices_route_requested = Signal()\n    automation_route_requested = Signal()\n    settings_route_requested = Signal()\n\n    def __init__(\n        self,\n        device_model: QAbstractItemModel | None = None,\n        content: QWidget | None = None,\n        device_controller: "DeviceManagerView | None" = None,\n        job_service: "JobService | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        root = QVBoxLayout(self)\n        root.setContentsMargins(6, 6, 6, 0)\n        root.setSpacing(5)\n\n        splitter = QSplitter(Qt.Orientation.Horizontal)\n        splitter.setObjectName("workspaceSplitter")\n        splitter.setChildrenCollapsible(False)\n\n        self.device_rail = DeviceRail(device_model, device_controller)\n        self.device_rail.devices_route_requested.connect(self.devices_route_requested.emit)\n        self.device_rail.automation_route_requested.connect(self.automation_route_requested.emit)\n        self.device_rail.settings_route_requested.connect(self.settings_route_requested.emit)\n        splitter.addWidget(self.device_rail)\n        splitter.addWidget(content or ManagementWorkspace())\n\n        self.job_queue = JobQueueDrawer(job_service)\n        self.job_queue.automation_route_requested.connect(self.automation_route_requested.emit)\n        splitter.addWidget(self.job_queue)\n\n        splitter.setStretchFactor(0, 0)\n        splitter.setStretchFactor(1, 1)\n        splitter.setStretchFactor(2, 0)\n        splitter.setSizes([265, 1120, 280])\n        root.addWidget(splitter, stretch=1)\n\n        status = QWidget()\n        status.setObjectName("statusBarContent")\n        status_layout = QHBoxLayout(status)\n        status_layout.setContentsMargins(10, 4, 10, 4)\n        status_layout.setSpacing(11)\n\n        brand = QLabel("SP-FARMS")\n        brand.setStyleSheet("font-weight: 800;")\n        status_layout.addWidget(brand)\n        status_layout.addWidget(QLabel("|"))\n\n        self.footer_labels: dict[str, QLabel] = {}\n        for key, value in (\n            ("Total", "0"),\n            ("Online", "0"),\n            ("Running", "0"),\n            ("Success", "0"),\n            ("Failed", "0"),\n            ("Queue", "0"),\n            ("CPU", "0%"),\n            ("RAM", "0 MB"),\n        ):\n            block = QHBoxLayout()\n            block.setSpacing(3)\n            name = QLabel(key)\n            name.setProperty("muted", True)\n            number = QLabel(value)\n            number.setProperty("footerValue", True)\n            self.footer_labels[key] = number\n            block.addWidget(name)\n            block.addWidget(number)\n            status_layout.addLayout(block)\n\n        status_layout.addStretch()\n        status_layout.addWidget(QLabel("Automate Smarter • Manage Bigger"))\n        root.addWidget(status)\n\n        if device_controller is not None:\n            device_controller.devices_changed.connect(self._update_device_status)\n\n    def refresh_jobs(self) -> None:\n        jobs = self.job_queue.refresh()\n        self._update_job_status(jobs)\n\n    def _update_job_status(self, jobs: Sequence[Job]) -> None:\n        self.footer_labels["Success"].setText(\n            str(sum(job.state is JobState.SUCCEEDED for job in jobs))\n        )\n        self.footer_labels["Failed"].setText(\n            str(sum(job.state is JobState.FAILED for job in jobs))\n        )\n        self.footer_labels["Queue"].setText(\n            str(sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs))\n        )\n\n    def _update_device_status(self, devices: object) -> None:\n        if not isinstance(devices, tuple):\n            return\n        managed = tuple(device for device in devices if isinstance(device, ManagedDevice))\n        online = tuple(device for device in managed if device.is_online)\n        self.footer_labels["Total"].setText(str(len(managed)))\n        self.footer_labels["Online"].setText(str(len(online)))\n        self.footer_labels["Running"].setText(str(len(online)))\n        cpu = [device.cpu_usage for device in managed if device.cpu_usage is not None]\n        ram = [device.ram_usage_mb for device in managed if device.ram_usage_mb is not None]\n        self.footer_labels["CPU"].setText(f"{sum(cpu) / len(cpu):.0f}%" if cpu else "0%")\n        self.footer_labels["RAM"].setText(f"{sum(ram)} MB" if ram else "0 MB")\n'


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def backup_files(names: tuple[str, ...]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f".reference_ui_v4_backup_{stamp}"
    for name in names:
        src = APP / name
        if src.exists():
            dst = backup / "sp_farms" / "app" / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return backup


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"[OK] {label}: already applied")
        return text
    if old not in text:
        print(f"[SKIP] {label}: source block not found")
        return text
    print(f"[PATCH] {label}")
    return text.replace(old, new, 1)


def ensure_import(text: str, anchor: str, import_line: str, label: str) -> str:
    if import_line in text:
        return text
    if anchor not in text:
        print(f"[SKIP] {label}: import anchor not found")
        return text
    print(f"[PATCH] {label}")
    return text.replace(anchor, anchor + import_line, 1)


def patch_main_window() -> None:
    path = APP / "main_window.py"
    text = path.read_text(encoding="utf-8")

    text = ensure_import(
        text,
        "from sp_farms.app.qa_profile_lab import QAProfileLab\n",
        "from sp_farms.app.quick_automation_workspace import QuickAutomationWorkspace\n",
        "QuickAutomationWorkspace import",
    )
    text = ensure_import(
        text,
        "from sp_farms.app.workspaces import WorkspaceLayout\n",
        "from sp_farms.app.widgets import ClockWidget\n",
        "ClockWidget import",
    )

    if "NAV_ICONS =" not in text:
        anchor = (
            'NAVIGATION = (\n'
            '    "Home",\n'
            '    "Accounts",\n'
            '    "Pages",\n'
            '    "Groups",\n'
            '    "Content",\n'
            '    "Automation",\n'
            '    "Devices",\n'
            '    "Analytics",\n'
            '    "Settings",\n'
            ')\n'
        )
        addition = anchor + (
            '\nNAV_ICONS = {\n'
            '    "Home": "⌂",\n'
            '    "Accounts": "♙",\n'
            '    "Pages": "▦",\n'
            '    "Groups": "♧",\n'
            '    "Content": "▣",\n'
            '    "Automation": "⚡",\n'
            '    "Devices": "▤",\n'
            '    "Analytics": "⌁",\n'
            '    "Settings": "⚙",\n'
            '}\n'
        )
        if anchor in text:
            text = text.replace(anchor, addition, 1)
            print("[PATCH] navigation icon map")

    create_anchor = "        if self.error_center_workspace:\n"
    quick_block = (
        "        self.quick_automation_workspace: QuickAutomationWorkspace | None = (\n"
        "            QuickAutomationWorkspace(self._context.automation_builder_service)\n"
        "            if self._context.automation_builder_service\n"
        "            else None\n"
        "        )\n"
    )
    if quick_block not in text and create_anchor in text:
        text = text.replace(create_anchor, quick_block + create_anchor, 1)
        print("[PATCH] create Quick Automation workspace")

    for workspace_name in ("home_workspace", "_workspace"):
        marker = (
            f'        self.{workspace_name}.automation_route_requested.connect('
            'lambda: self.navigate("Automation"))\n'
        )
        extra = marker + (
            f'        self.{workspace_name}.settings_route_requested.connect('
            'lambda: self.navigate("Settings"))\n'
        )
        marker_index = text.find(marker)
        if marker_index != -1:
            nearby = text[marker_index:marker_index + 260]
            if "settings_route_requested" not in nearby:
                text = text.replace(marker, extra, 1)
                print(f"[PATCH] {workspace_name} settings route")

    text = replace_once(
        text,
        "            btn.setText(translated)\n",
        '            icon = NAV_ICONS.get(section, "")\n'
        '            btn.setText(f"{icon}  {translated}".strip())\n',
        "locale-aware nav icons",
    )

    text = replace_once(
        text,
        "            button = QPushButton(section)\n",
        '            button = QPushButton(f"{NAV_ICONS.get(section, \'\')}  {section}".strip())\n',
        "navigation icons",
    )

    text = text.replace('        mark = QLabel("♣")\n', '        mark = QLabel("❧")\n', 1)

    if "self.clock_widget = ClockWidget()" not in text:
        old = "        navigation_layout.addStretch()\n        shell_layout.addWidget(navigation)\n"
        new = (
            "        navigation_layout.addStretch()\n"
            "        self.clock_widget = ClockWidget()\n"
            "        navigation_layout.addWidget(self.clock_widget)\n"
            "        shell_layout.addWidget(navigation)\n"
        )
        if old in text:
            text = text.replace(old, new, 1)
            print("[PATCH] top date/time widget")

    if 'automation_tabs.addTab(self.quick_automation_workspace, "Quick Mode")' not in text:
        old = "                automation_tabs = QTabWidget()\n"
        new = (
            "                self.automation_tabs = QTabWidget()\n"
            "                automation_tabs = self.automation_tabs\n"
            "                if self.quick_automation_workspace is not None:\n"
            '                    automation_tabs.addTab(self.quick_automation_workspace, "Quick Mode")\n'
        )
        if old in text:
            text = text.replace(old, new, 1)
            print("[PATCH] Automation Quick Mode")
        elif "                self.automation_tabs = QTabWidget()\n" in text:
            anchor = "                automation_tabs = self.automation_tabs\n"
            if anchor in text:
                text = text.replace(
                    anchor,
                    anchor
                    + "                if self.quick_automation_workspace is not None:\n"
                    + '                    automation_tabs.addTab(self.quick_automation_workspace, "Quick Mode")\n',
                    1,
                )
                print("[PATCH] Automation Quick Mode")

    text = text.replace(
        'automation_tabs.addTab(self.automation_builder_workspace, "Automation Builder")',
        'automation_tabs.addTab(self.automation_builder_workspace, "Advanced Builder")',
    )

    if "quick_automation_workspace.advanced_requested.connect" not in text:
        target = "                self._pages.addWidget(automation_tabs)\n"
        hook = (
            "                if self.quick_automation_workspace is not None:\n"
            "                    self.quick_automation_workspace.advanced_requested.connect(\n"
            "                        lambda: automation_tabs.setCurrentWidget(\n"
            "                            self.automation_builder_workspace\n"
            "                        )\n"
            "                        if self.automation_builder_workspace is not None\n"
            "                        else None\n"
            "                    )\n"
        )
        if target in text:
            text = text.replace(target, hook + target, 1)
            print("[PATCH] Quick → Advanced Builder")

    automation_index = text.find('        elif section == "Automation":\n')
    if automation_index != -1:
        nearby = text[automation_index:automation_index + 350]
        if "quick_automation_workspace.refresh_presets()" not in nearby:
            old = (
                '        elif section == "Automation":\n'
                "            self.job_queue_view.refresh()\n"
            )
            new = (
                '        elif section == "Automation":\n'
                "            self.job_queue_view.refresh()\n"
                "            if self.quick_automation_workspace is not None:\n"
                "                self.quick_automation_workspace.refresh_presets()\n"
            )
            text = replace_once(text, old, new, "Automation Quick refresh")

    path.write_text(text, encoding="utf-8")


def patch_account_workspace() -> None:
    path = APP / "account_workspace.py"
    text = path.read_text(encoding="utf-8")

    if "ACCOUNT FLOW" not in text:
        anchor = "        listing_layout.addWidget(self.metrics)\n"
        block = (
            "        listing_layout.addWidget(self.metrics)\n\n"
            "        account_flow = Panel()\n"
            '        account_flow.setProperty("flowPanel", True)\n'
            "        account_flow_layout = QHBoxLayout(account_flow)\n"
            "        account_flow_layout.setContentsMargins(8, 6, 8, 6)\n"
            "        account_flow_layout.setSpacing(5)\n\n"
            '        flow_caption = QLabel("ACCOUNT FLOW")\n'
            '        flow_caption.setProperty("sectionTitle", True)\n'
            "        account_flow_layout.addWidget(flow_caption)\n\n"
            '        self.account_flow_select = QPushButton("1  Select\\n    Account")\n'
            '        self.account_flow_select.setProperty("flowStep", True)\n'
            '        self.account_flow_select.setProperty("flowState", "next")\n'
            "        self.account_flow_select.setEnabled(False)\n\n"
            '        self.account_flow_resolve = QPushButton("2  Resolve\\n    Device + Network")\n'
            '        self.account_flow_resolve.setProperty("flowStep", True)\n'
            "        self.account_flow_resolve.clicked.connect(self.open_context_actions)\n\n"
            '        self.account_flow_restore = QPushButton("3  Restore\\n    Workspace")\n'
            '        self.account_flow_restore.setProperty("flowStep", True)\n'
            "        self.account_flow_restore.clicked.connect(self.restore_selected_workspace)\n\n"
            '        self.account_flow_actions = QPushButton("4  Actions\\n    Content / Maintenance")\n'
            '        self.account_flow_actions.setProperty("flowStep", True)\n'
            "        self.account_flow_actions.clicked.connect(self.open_context_actions)\n\n"
            '        self.account_flow_monitor = QPushButton("5  Monitor\\n    Job Queue")\n'
            '        self.account_flow_monitor.setProperty("flowStep", True)\n'
            "        self.account_flow_monitor.clicked.connect(\n"
            '            lambda: self.local_navigation_requested.emit("Automation")\n'
            "        )\n\n"
            "        self.account_flow_buttons = (\n"
            "            self.account_flow_select,\n"
            "            self.account_flow_resolve,\n"
            "            self.account_flow_restore,\n"
            "            self.account_flow_actions,\n"
            "            self.account_flow_monitor,\n"
            "        )\n"
            "        for index, button in enumerate(self.account_flow_buttons):\n"
            "            account_flow_layout.addWidget(button, stretch=1)\n"
            "            if index < len(self.account_flow_buttons) - 1:\n"
            '                arrow = QLabel("→")\n'
            '                arrow.setProperty("flowArrow", True)\n'
            "                account_flow_layout.addWidget(arrow)\n\n"
            "        listing_layout.addWidget(account_flow)\n"
        )
        if anchor in text:
            text = text.replace(anchor, block, 1)
            print("[PATCH] Account flow strip")

    selection_anchor = (
        "        self.release_btn.setEnabled(bool(count >= 1 and self._pool_service is not None))\n"
    )
    if "self.account_flow_resolve.setEnabled" not in text and selection_anchor in text:
        flow_update = selection_anchor + (
            "\n"
            '        if hasattr(self, "account_flow_buttons"):\n'
            "            states = (\n"
            '                "done" if count else "next",\n'
            '                "next" if count else "",\n'
            '                "",\n'
            '                "",\n'
            '                "",\n'
            "            )\n"
            "            for button, state in zip(self.account_flow_buttons, states, strict=True):\n"
            '                button.setProperty("flowState", state)\n'
            "                button.style().unpolish(button)\n"
            "                button.style().polish(button)\n"
            "            self.account_flow_resolve.setEnabled(bool(count))\n"
            "            self.account_flow_restore.setEnabled(\n"
            "                bool(count == 1 and self._restore_service is not None)\n"
            "            )\n"
            "            self.account_flow_actions.setEnabled(bool(count))\n"
            "            self.account_flow_monitor.setEnabled(True)\n"
        )
        text = text.replace(selection_anchor, flow_update, 1)
        print("[PATCH] Account flow state")

    text = text.replace(
        "        self.inspector.setMinimumWidth(390)\n",
        "        self.inspector.setMinimumWidth(345)\n",
    )
    text = text.replace(
        "        self.inspector.setMaximumWidth(520)\n",
        "        self.inspector.setMaximumWidth(470)\n",
    )

    path.write_text(text, encoding="utf-8")


def patch_content_workspace() -> None:
    path = APP / "content_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        '        title.setStyleSheet("font-size: 18px; font-weight: 700;")\n',
        '        title.setProperty("heading", True)\n',
    )
    text = text.replace(
        '        subtitle.setStyleSheet("color: #64748b; font-size: 12px;")\n',
        '        subtitle.setProperty("muted", True)\n',
    )

    marker = "        self.tabs = QTabWidget()\n        self.tabs.setStyleSheet(\n"
    if marker in text:
        start = text.index(marker)
        after = text.find("\n\n        # Tab 1: Media Library", start)
        if after != -1:
            text = text[:start] + "        self.tabs = QTabWidget()\n" + text[after:]
            print("[PATCH] Content global tab theme")

    text = text.replace(
        'self.tabs.addTab(self.media_tab, "Media Library")',
        'self.tabs.addTab(self.media_tab, "Media")',
    )
    text = text.replace(
        'self.tabs.addTab(self.items_tab, "Composed Items")',
        'self.tabs.addTab(self.items_tab, "Drafts / Composed")',
    )

    if "CONTENT FLOW" not in text:
        anchor = "        layout.addLayout(top_bar)\n\n        # Tab Widget\n"
        block = (
            "        layout.addLayout(top_bar)\n\n"
            "        content_flow = Panel()\n"
            '        content_flow.setProperty("flowPanel", True)\n'
            "        content_flow_layout = QHBoxLayout(content_flow)\n"
            "        content_flow_layout.setContentsMargins(8, 6, 8, 6)\n"
            "        content_flow_layout.setSpacing(5)\n\n"
            '        content_flow_title = QLabel("CONTENT FLOW")\n'
            '        content_flow_title.setProperty("sectionTitle", True)\n'
            "        content_flow_layout.addWidget(content_flow_title)\n\n"
            "        for index, (name, detail) in enumerate(\n"
            "            (\n"
            '                ("Media", "Import / choose"),\n'
            '                ("Compose", "Caption + preview"),\n'
            '                ("Destination", "Authorized asset"),\n'
            '                ("Dry Run", "Validate"),\n'
            '                ("Publish", "Now / schedule"),\n'
            "            ),\n"
            "            start=1,\n"
            "        ):\n"
            '            step = SecondaryButton(f"{index}  {name}\\n    {detail}")\n'
            '            step.setProperty("flowStep", True)\n'
            "            if index == 1:\n"
            '                step.setProperty("flowState", "next")\n'
            "                step.clicked.connect(self._on_import_dialog)\n"
            "            else:\n"
            "                step.clicked.connect(self._on_open_composer)\n"
            "            content_flow_layout.addWidget(step, stretch=1)\n"
            "            if index < 5:\n"
            '                arrow = QLabel("→")\n'
            '                arrow.setProperty("flowArrow", True)\n'
            "                content_flow_layout.addWidget(arrow)\n\n"
            "        layout.addWidget(content_flow)\n\n"
            "        # Tab Widget\n"
        )
        if anchor in text:
            text = text.replace(anchor, block, 1)
            print("[PATCH] Content flow strip")

    text = text.replace(
        '        header.setStyleSheet("font-size: 15px; font-weight: 600;")\n',
        '        header.setProperty("sectionTitle", True)\n',
    )
    text = text.replace(
        '        self.name_label.setStyleSheet("font-weight: 600;")\n',
        '        self.name_label.setProperty("sectionTitle", True)\n',
    )
    text = text.replace(
        '        self.delete_btn.setStyleSheet("color: #ef4444;")\n',
        '        self.delete_btn.setProperty("danger", True)\n',
    )

    path.write_text(text, encoding="utf-8")


def patch_context_actions() -> None:
    path = APP / "context_action_dialog.py"
    text = path.read_text(encoding="utf-8")

    tabs_anchor = (
        '        self.tabs = QTabWidget()\n'
        '        self.tabs.setObjectName("contextTabs")\n'
    )
    tabs_new = (
        '        self.tabs = QTabWidget()\n'
        '        self.tabs.setObjectName("contextTabs")\n'
        '        self.tabs.setTabPosition(QTabWidget.TabPosition.West)\n'
        '        self.tabs.setMovable(False)\n'
        '        self.tabs.setUsesScrollButtons(True)\n'
    )
    if "TabPosition.West" not in text:
        text = replace_once(text, tabs_anchor, tabs_new, "Context Actions left rail")

    text = text.replace("        self.resize(960, 680)\n", "        self.resize(1140, 760)\n")
    text = text.replace(
        "        root.setContentsMargins(16, 16, 16, 16)\n        root.setSpacing(12)\n",
        "        root.setContentsMargins(12, 12, 12, 12)\n        root.setSpacing(9)\n",
    )
    text = text.replace(
        '        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")\n',
        '        self.title_label.setProperty("heading", True)\n',
    )
    text = text.replace(
        '        self.status_stream_label.setStyleSheet("font-size: 12px; color: #3b82f6;")\n',
        '        self.status_stream_label.setProperty("muted", True)\n',
    )
    text = text.replace(
        '        self.using_summary_label.setStyleSheet(\n'
        '            "color: #71717a; font-size: 12px; font-family: monospace;"\n'
        "        )\n",
        '        self.using_summary_label.setProperty("muted", True)\n',
    )

    start_marker = "    def _create_post_tab(self) -> QWidget:\n"
    end_marker = "    def _create_video_tab(self) -> QWidget:\n"
    if start_marker in text and end_marker in text:
        start = text.index(start_marker)
        end = text.index(end_marker, start)
        current = text[start:end]
        if "Post Preview" not in current:
            new_method = (
                "    def _create_post_tab(self) -> QWidget:\n"
                "        panel = QWidget()\n"
                "        root = QHBoxLayout(panel)\n"
                "        root.setContentsMargins(10, 10, 10, 10)\n"
                "        root.setSpacing(10)\n\n"
                "        editor = Panel()\n"
                "        editor_layout = QVBoxLayout(editor)\n"
                "        editor_layout.setContentsMargins(10, 9, 10, 9)\n"
                "        editor_layout.setSpacing(8)\n\n"
                '        editor_title = QLabel("Post Content")\n'
                '        editor_title.setProperty("sectionTitle", True)\n'
                "        editor_layout.addWidget(editor_title)\n\n"
                "        form = QFormLayout()\n"
                "        self.post_type_combo = QComboBox()\n"
                "        self.post_type_combo.addItems(\n"
                '            ["Text Only", "Single Image", "Multi-Image", "Video Post", "Link Share"]\n'
                "        )\n"
                '        form.addRow("Post Type:", self.post_type_combo)\n\n'
                "        self.post_caption_edit = QTextEdit()\n"
                '        self.post_caption_edit.setPlaceholderText("Write your post caption here...")\n'
                "        self.post_caption_edit.setMinimumHeight(130)\n"
                '        form.addRow("Caption:", self.post_caption_edit)\n\n'
                "        self.post_media_path = QLineEdit()\n"
                '        self.post_media_path.setPlaceholderText("Local media path (optional)")\n'
                '        form.addRow("Media Path:", self.post_media_path)\n\n'
                '        self.post_schedule_check = QCheckBox("Publish immediately")\n'
                "        self.post_schedule_check.setChecked(True)\n"
                '        form.addRow("Timing:", self.post_schedule_check)\n\n'
                "        editor_layout.addLayout(form)\n"
                "        editor_layout.addStretch()\n"
                "        root.addWidget(editor, stretch=3)\n\n"
                "        preview = Panel()\n"
                "        preview_layout = QVBoxLayout(preview)\n"
                "        preview_layout.setContentsMargins(10, 9, 10, 9)\n"
                "        preview_layout.setSpacing(8)\n\n"
                '        preview_title = QLabel("Post Preview")\n'
                '        preview_title.setProperty("sectionTitle", True)\n'
                "        preview_layout.addWidget(preview_title)\n\n"
                "        target = self.context.primary_target\n"
                '        target_name = target.display_name if target else "Selected destination"\n'
                "        self.post_preview_account = QLabel(target_name)\n"
                '        self.post_preview_account.setProperty("previewTitle", True)\n'
                "        preview_layout.addWidget(self.post_preview_account)\n\n"
                "        self.post_preview_text = QTextEdit()\n"
                "        self.post_preview_text.setReadOnly(True)\n"
                '        self.post_preview_text.setPlaceholderText("Your caption preview appears here.")\n'
                "        self.post_preview_text.setMinimumWidth(280)\n"
                "        preview_layout.addWidget(self.post_preview_text, stretch=1)\n\n"
                '        preview_note = QLabel("Preview only · final rendering depends on the destination platform.")\n'
                '        preview_note.setProperty("muted", True)\n'
                "        preview_note.setWordWrap(True)\n"
                "        preview_layout.addWidget(preview_note)\n\n"
                "        self.post_caption_edit.textChanged.connect(\n"
                "            lambda: self.post_preview_text.setPlainText(\n"
                "                self.post_caption_edit.toPlainText()\n"
                "            )\n"
                "        )\n\n"
                "        root.addWidget(preview, stretch=2)\n"
                "        return self._create_scrollable(panel)\n\n"
            )
            text = text[:start] + new_method + text[end:]
            print("[PATCH] Post tab live preview")

    path.write_text(text, encoding="utf-8")


def patch_advanced_builder() -> None:
    path = APP / "automation_builder_workspace.py"
    text = path.read_text(encoding="utf-8")
    replacements = (
        (
            '        top_bar.setStyleSheet("background-color: #1e293b; border-radius: 8px; padding: 6px;")\n',
            '        top_bar.setProperty("panel", True)\n',
        ),
        (
            '        btn_dry_run.setStyleSheet("background-color: #0369a1; color: white; font-weight: bold;")\n',
            '        btn_dry_run.setProperty("infoAction", True)\n',
        ),
        (
            '        btn_run.setStyleSheet("background-color: #15803d; color: white; font-weight: bold;")\n',
            '        btn_run.setProperty("successAction", True)\n',
        ),
        (
            '        bottom_bar.setStyleSheet("background-color: #0f172a; border-radius: 6px; padding: 4px;")\n',
            '        bottom_bar.setProperty("softPanel", True)\n',
        ),
        (
            '        self._lbl_status.setStyleSheet("color: #94a3b8;")\n',
            '        self._lbl_status.setProperty("muted", True)\n',
        ),
        (
            '        header.setStyleSheet("font-weight: bold; color: #f1f5f9;")\n',
            '        header.setProperty("sectionTitle", True)\n',
        ),
        (
            '        self._setup_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")\n',
            '        self._setup_title.setProperty("sectionTitle", True)\n',
        ),
    )
    for old, new in replacements:
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("[PATCH] Advanced Builder visual cleanup")


def main() -> None:
    if not (APP / "main_window.py").exists():
        fail("Run this script from the SP-Farms repository root.")

    touched = (
        "theme.py",
        "widgets.py",
        "home_dashboard.py",
        "workspaces.py",
        "main_window.py",
        "account_workspace.py",
        "content_workspace.py",
        "context_action_dialog.py",
        "automation_builder_workspace.py",
        "quick_automation_workspace.py",
    )
    backup = backup_files(touched)
    print(f"[OK] Backup created: {backup}")

    (APP / "theme.py").write_text(PAYLOAD_THEME, encoding="utf-8")
    (APP / "widgets.py").write_text(PAYLOAD_WIDGETS, encoding="utf-8")
    (APP / "home_dashboard.py").write_text(PAYLOAD_HOME, encoding="utf-8")
    (APP / "quick_automation_workspace.py").write_text(PAYLOAD_QUICK, encoding="utf-8")
    (APP / "workspaces.py").write_text(PAYLOAD_WORKSPACES, encoding="utf-8")
    print("[COPY] reference theme/widgets/home/quick-mode/device-rail")

    patch_main_window()
    patch_account_workspace()
    patch_content_workspace()
    patch_context_actions()
    patch_advanced_builder()

    print()
    print("SP-Farms Reference UI V4 applied.")
    print("Recommended validation:")
    print(r'  .\.venv\Scripts\python.exe -m pytest tests/test_design_system.py tests/test_main_window.py -q')
    print(r'  .\.venv\Scripts\python.exe -m ruff check sp_farms')
    print(r'  .\.venv\Scripts\python.exe -m sp_farms.app.main')
    print()
    print(f"Rollback backup: {backup}")


if __name__ == "__main__":
    main()
