from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "sp_farms" / "app"

THEME_PAYLOAD = 'from dataclasses import dataclass\nfrom enum import StrEnum\n\n\nclass ThemeMode(StrEnum):\n    LIGHT = "light"\n    DARK = "dark"\n\n\n@dataclass(frozen=True, slots=True)\nclass ThemePalette:\n    window: str\n    surface: str\n    surface_alt: str\n    border: str\n    text: str\n    muted_text: str\n    accent: str\n    accent_hover: str\n    accent_text: str\n    warning: str\n    danger: str\n    success: str\n    info: str\n    selection: str\n\n\nLIGHT_PALETTE = ThemePalette(\n    window="#F3F5F3",\n    surface="#FFFFFF",\n    surface_alt="#EEF1EF",\n    border="#C9D0CC",\n    text="#151A17",\n    muted_text="#667069",\n    accent="#EFC51B",\n    accent_hover="#F8D444",\n    accent_text="#14150E",\n    warning="#C98916",\n    danger="#D84D53",\n    success="#1FAE61",\n    info="#3976D8",\n    selection="#FFF4BC",\n)\n\nDARK_PALETTE = ThemePalette(\n    window="#0B0F11",\n    surface="#111619",\n    surface_alt="#171D20",\n    border="#2C3539",\n    text="#F3F5F5",\n    muted_text="#929DA2",\n    accent="#F4C915",\n    accent_hover="#FFD83D",\n    accent_text="#15150D",\n    warning="#E0A329",\n    danger="#EF5C62",\n    success="#28C96F",\n    info="#4B87EA",\n    selection="#34331E",\n)\n\n\ndef palette(mode: ThemeMode) -> ThemePalette:\n    return LIGHT_PALETTE if mode is ThemeMode.LIGHT else DARK_PALETTE\n\n\ndef style_sheet(mode: ThemeMode) -> str:\n    c = palette(mode)\n    dark = mode is ThemeMode.DARK\n\n    top = "#0E1315" if dark else "#FAFBFA"\n    raised = "#141A1D" if dark else "#FFFFFF"\n    soft = "#151B1E" if dark else "#F5F7F5"\n    hover = "#20272A" if dark else "#E7ECE8"\n    row_hover = "#1A2124" if dark else "#F1F4F1"\n    row_line = "#222A2E" if dark else "#DEE3DF"\n    header = "#161D20" if dark else "#E8EDE9"\n    disabled = "#111517" if dark else "#ECEFEC"\n    success_bg = "#153622" if dark else "#E8F7ED"\n    warning_bg = "#352A16" if dark else "#FFF4D8"\n    error_bg = "#381B20" if dark else "#FDECEE"\n    info_bg = "#172A45" if dark else "#EAF1FF"\n\n    return f"""\nQWidget {{\n    background: {c.window};\n    color: {c.text};\n    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;\n    font-size: 12px;\n}}\n\nQMainWindow {{\n    background: {c.window};\n}}\n\nQFrame[panel="true"], QDialog {{\n    background: {c.surface};\n    border: 1px solid {c.border};\n    border-radius: 7px;\n}}\n\nQFrame[softPanel="true"] {{\n    background: {soft};\n    border: 1px solid {c.border};\n    border-radius: 7px;\n}}\n\nQFrame[metric="true"] {{\n    min-height: 54px;\n    background: {raised};\n    border: 1px solid {c.border};\n    border-radius: 7px;\n}}\n\nQLabel {{\n    background: transparent;\n    border: 0;\n}}\n\nQLabel[muted="true"] {{\n    color: {c.muted_text};\n}}\n\nQLabel[heading="true"] {{\n    font-size: 16px;\n    font-weight: 700;\n}}\n\nQLabel[sectionTitle="true"] {{\n    font-size: 13px;\n    font-weight: 700;\n}}\n\nQLabel[metricValue="true"] {{\n    font-size: 18px;\n    font-weight: 750;\n}}\n\nQLabel#brand {{\n    font-size: 20px;\n    font-weight: 800;\n}}\n\nQLabel#brandVersion,\nQLabel#brandSubtitle,\nQLabel#clockDate {{\n    color: {c.muted_text};\n}}\n\nQLabel#brandSubtitle,\nQLabel#clockDate {{\n    font-size: 10px;\n}}\n\nQLabel#clockTime {{\n    font-size: 14px;\n    font-weight: 750;\n}}\n\nQWidget#topNavigation {{\n    background: {top};\n    border-bottom: 1px solid {c.border};\n}}\n\nQLabel#brandMark {{\n    color: #06110A;\n    background: #34C86A;\n    border: 1px solid #4ADB7F;\n    border-radius: 10px;\n    font-size: 20px;\n    font-weight: 900;\n}}\n\nQPushButton {{\n    min-height: 29px;\n    padding: 0 10px;\n    border: 1px solid {c.border};\n    border-radius: 6px;\n    background: {c.surface_alt};\n}}\n\nQPushButton:hover {{\n    background: {hover};\n    border-color: #59656A;\n}}\n\nQPushButton:pressed {{\n    background: {c.surface};\n}}\n\nQPushButton:disabled {{\n    color: #626A6E;\n    background: {disabled};\n    border-color: #262E31;\n}}\n\nQPushButton:focus {{\n    border: 1px solid {c.accent};\n}}\n\nQPushButton[primary="true"] {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[primary="true"]:hover {{\n    background: {c.accent_hover};\n    border-color: {c.accent_hover};\n}}\n\nQPushButton[successAction="true"] {{\n    color: #06140B;\n    background: {c.success};\n    border-color: {c.success};\n    font-weight: 700;\n}}\n\nQPushButton[infoAction="true"] {{\n    color: white;\n    background: {c.info};\n    border-color: {c.info};\n    font-weight: 700;\n}}\n\nQPushButton[danger="true"] {{\n    color: {c.danger};\n    background: {error_bg};\n    border-color: #71363C;\n}}\n\nQPushButton[nav="true"] {{\n    min-height: 34px;\n    padding: 0 12px;\n    background: transparent;\n    border-color: transparent;\n    font-weight: 600;\n}}\n\nQPushButton[nav="true"]:hover {{\n    background: {hover};\n    border-color: {c.border};\n}}\n\nQPushButton[nav="true"]:checked {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[localNav="true"] {{\n    min-height: 28px;\n    padding: 0 10px;\n    background: transparent;\n    border-color: transparent;\n}}\n\nQPushButton[localNav="true"]:hover {{\n    background: {hover};\n}}\n\nQPushButton[localNav="true"]:checked {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQPushButton[actionNav="true"] {{\n    min-height: 28px;\n    text-align: left;\n    background: transparent;\n    border-color: transparent;\n}}\n\nQPushButton[actionNav="true"]:hover {{\n    background: {hover};\n}}\n\nQPushButton[actionNav="true"]:checked {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQLineEdit,\nQComboBox,\nQSpinBox,\nQDateTimeEdit,\nQTextEdit {{\n    min-height: 29px;\n    padding: 0 8px;\n    background: {c.surface};\n    border: 1px solid {c.border};\n    border-radius: 6px;\n    selection-background-color: {c.info};\n}}\n\nQTextEdit {{\n    padding: 6px;\n}}\n\nQLineEdit:hover,\nQComboBox:hover,\nQSpinBox:hover,\nQDateTimeEdit:hover,\nQTextEdit:hover {{\n    border-color: #505C61;\n}}\n\nQLineEdit:focus,\nQComboBox:focus,\nQSpinBox:focus,\nQDateTimeEdit:focus,\nQTextEdit:focus {{\n    border-color: {c.accent};\n}}\n\nQCheckBox {{\n    spacing: 5px;\n}}\n\nQCheckBox::indicator {{\n    width: 14px;\n    height: 14px;\n    border: 1px solid #677177;\n    border-radius: 3px;\n}}\n\nQCheckBox::indicator:hover {{\n    border-color: {c.accent};\n}}\n\nQCheckBox::indicator:checked {{\n    background: {c.accent};\n    border-color: {c.accent};\n}}\n\nQGroupBox {{\n    margin-top: 10px;\n    padding: 10px 8px 8px 8px;\n    background: {soft};\n    border: 1px solid {c.border};\n    border-radius: 7px;\n    font-weight: 650;\n}}\n\nQGroupBox::title {{\n    subcontrol-origin: margin;\n    left: 9px;\n    padding: 0 5px;\n    background: {c.window};\n}}\n\nQTableView,\nQListView,\nQListWidget,\nQTreeView,\nQTreeWidget {{\n    background: {c.surface};\n    alternate-background-color: {soft};\n    border: 1px solid {c.border};\n    border-radius: 6px;\n    gridline-color: {c.border};\n    selection-background-color: {c.selection};\n    selection-color: {c.text};\n    outline: 0;\n}}\n\nQTableView::item {{\n    padding: 2px 5px;\n    border-bottom: 1px solid {row_line};\n}}\n\nQTableView::item:hover,\nQListView::item:hover,\nQListWidget::item:hover,\nQTreeView::item:hover {{\n    background: {row_hover};\n}}\n\nQTableView::item:selected,\nQListView::item:selected,\nQListWidget::item:selected,\nQTreeView::item:selected {{\n    background: {c.selection};\n    border-left: 2px solid {c.accent};\n}}\n\nQListView::item,\nQListWidget::item,\nQTreeView::item {{\n    padding: 5px 6px;\n}}\n\nQHeaderView::section {{\n    min-height: 28px;\n    padding: 0 6px;\n    background: {header};\n    border: 0;\n    border-right: 1px solid {c.border};\n    border-bottom: 1px solid {c.border};\n    font-weight: 650;\n}}\n\nQLabel[chip="true"] {{\n    padding: 2px 7px;\n    border: 1px solid {c.border};\n    border-radius: 8px;\n    font-weight: 600;\n}}\n\nQLabel[state="success"] {{\n    color: {c.success};\n    background: {success_bg};\n    border-color: #28633F;\n}}\n\nQLabel[state="warning"] {{\n    color: {c.warning};\n    background: {warning_bg};\n    border-color: #6A5424;\n}}\n\nQLabel[state="error"] {{\n    color: {c.danger};\n    background: {error_bg};\n    border-color: #71363C;\n}}\n\nQLabel[state="active"] {{\n    color: #78A8FF;\n    background: {info_bg};\n    border-color: #335E96;\n}}\n\nQLabel[state="neutral"] {{\n    color: {c.muted_text};\n}}\n\nQTabWidget::pane {{\n    border: 1px solid {c.border};\n    border-radius: 6px;\n    top: -1px;\n}}\n\nQTabBar::tab {{\n    min-height: 29px;\n    padding: 0 12px;\n    margin-right: 2px;\n    background: {c.surface_alt};\n    border: 1px solid {c.border};\n    border-radius: 5px;\n}}\n\nQTabBar::tab:hover {{\n    background: {hover};\n}}\n\nQTabBar::tab:selected {{\n    color: {c.accent_text};\n    background: {c.accent};\n    border-color: {c.accent};\n    font-weight: 700;\n}}\n\nQTabWidget#contextTabs QTabBar::tab {{\n    min-width: 148px;\n    min-height: 30px;\n    margin: 1px 4px 1px 0;\n    text-align: left;\n}}\n\nQProgressBar {{\n    min-height: 11px;\n    background: {soft};\n    border: 1px solid {c.border};\n    border-radius: 5px;\n    text-align: center;\n}}\n\nQProgressBar::chunk {{\n    background: {c.success};\n    border-radius: 4px;\n}}\n\nQSplitter::handle {{\n    background: {c.window};\n    width: 4px;\n    height: 4px;\n}}\n\nQSplitter::handle:hover {{\n    background: {c.accent};\n}}\n\nQMenu,\nQToolTip {{\n    background: {c.surface};\n    color: {c.text};\n    border: 1px solid {c.border};\n}}\n\nQMenu::item {{\n    padding: 6px 22px 6px 10px;\n}}\n\nQMenu::item:selected {{\n    background: {c.selection};\n}}\n\nQScrollArea {{\n    border: 0;\n    background: transparent;\n}}\n\nQScrollBar:vertical {{\n    width: 9px;\n    background: transparent;\n}}\n\nQScrollBar::handle:vertical {{\n    background: #465156;\n    border-radius: 4px;\n    min-height: 22px;\n}}\n\nQScrollBar:horizontal {{\n    height: 9px;\n    background: transparent;\n}}\n\nQScrollBar::handle:horizontal {{\n    background: #465156;\n    border-radius: 4px;\n    min-width: 22px;\n}}\n"""\n'
WIDGETS_PAYLOAD = 'from collections.abc import Sequence\n\nfrom PySide6.QtCore import QDateTime, Qt, QTimer\nfrom PySide6.QtGui import QColor\nfrom PySide6.QtWidgets import (\n    QFrame,\n    QHBoxLayout,\n    QLabel,\n    QPushButton,\n    QTableView,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.theme import ThemeMode, palette\n\n\nclass Panel(QFrame):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setProperty("panel", True)\n\n\nclass SoftPanel(QFrame):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setProperty("softPanel", True)\n\n\nclass PrimaryButton(QPushButton):\n    def __init__(self, text: str, parent: QWidget | None = None) -> None:\n        super().__init__(text, parent)\n        self.setProperty("primary", True)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass DestructiveButton(QPushButton):\n    def __init__(self, text: str, parent: QWidget | None = None) -> None:\n        super().__init__(text, parent)\n        self.setProperty("danger", True)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass SecondaryButton(QPushButton):\n    def __init__(self, text: str, parent: QWidget | None = None) -> None:\n        super().__init__(text, parent)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass QuickActionButton(QPushButton):\n    """Compatibility widget. V7 does not use Quick Action card layouts."""\n\n    def __init__(\n        self,\n        title: str,\n        subtitle: str = "",\n        icon: str = "›",\n        parent: QWidget | None = None,\n    ) -> None:\n        text = f"{icon}  {title}"\n        if subtitle:\n            text += f"\\n    {subtitle}"\n        super().__init__(text, parent)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n\nclass FlowStepButton(QPushButton):\n    """Compatibility widget. V7 does not show step-flow strips."""\n\n    def __init__(\n        self,\n        number: int,\n        title: str,\n        detail: str = "",\n        parent: QWidget | None = None,\n    ) -> None:\n        text = f"{number}  {title}"\n        if detail:\n            text += f"\\n    {detail}"\n        super().__init__(text, parent)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n\n    def set_flow_state(self, state: str) -> None:\n        self.setProperty("flowState", state)\n        self.style().unpolish(self)\n        self.style().polish(self)\n\n\nclass StatusChip(QLabel):\n    _STATE_ICONS = {\n        "success": "●",\n        "warning": "▲",\n        "error": "●",\n        "danger": "●",\n        "active": "●",\n        "info": "●",\n        "neutral": "○",\n        "paused": "⏸",\n        "running": "▶",\n    }\n\n    def __init__(\n        self,\n        text: str,\n        state: str = "neutral",\n        mode: ThemeMode | None = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(text, parent)\n        self.setProperty("chip", True)\n        self.update_state(state=state, text=text, mode=mode)\n\n    def update_state(\n        self,\n        state: str,\n        text: str | None = None,\n        mode: ThemeMode | None = None,\n    ) -> None:\n        raw = text if text is not None else self.text()\n        icon = self._STATE_ICONS.get(state.lower(), "")\n        display = raw\n        if icon and not raw.startswith(tuple(self._STATE_ICONS.values())):\n            display = f"{icon} {raw}"\n\n        self.setText(display)\n        self.setProperty("state", state)\n        self.setAccessibleName(f"Status: {raw}")\n        self.setAccessibleDescription(f"Current status is {state} ({raw})")\n\n        if mode is not None:\n            c = palette(mode)\n            color_name = {\n                "success": "success",\n                "warning": "warning",\n                "error": "danger",\n                "danger": "danger",\n                "active": "info",\n                "info": "info",\n                "neutral": "muted_text",\n            }.get(state, "muted_text")\n            color = getattr(c, color_name)\n            self.setStyleSheet(f"color: {color}; border-color: {color};")\n\n        self.style().unpolish(self)\n        self.style().polish(self)\n\n\nclass ClockWidget(QWidget):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setObjectName("topClock")\n\n        layout = QHBoxLayout(self)\n        layout.setContentsMargins(8, 0, 0, 0)\n        layout.setSpacing(8)\n\n        dot = QLabel("●")\n        dot.setStyleSheet("font-size: 12px; color: #F4C915;")\n        layout.addWidget(dot)\n\n        stack = QVBoxLayout()\n        stack.setContentsMargins(0, 0, 0, 0)\n        stack.setSpacing(0)\n\n        self.date_label = QLabel()\n        self.date_label.setObjectName("clockDate")\n        self.time_label = QLabel()\n        self.time_label.setObjectName("clockTime")\n\n        stack.addWidget(self.date_label)\n        stack.addWidget(self.time_label)\n        layout.addLayout(stack)\n\n        self._timer = QTimer(self)\n        self._timer.timeout.connect(self._refresh)\n        self._timer.start(1000)\n        self._refresh()\n\n    def _refresh(self) -> None:\n        now = QDateTime.currentDateTime()\n        self.date_label.setText(now.toString("ddd, MMM d, yyyy"))\n        self.time_label.setText(now.toString("hh:mm AP"))\n\n\nclass SectionHeader(QWidget):\n    def __init__(\n        self,\n        title: str,\n        subtitle: str = "",\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n\n        layout = QHBoxLayout(self)\n        layout.setContentsMargins(0, 0, 0, 0)\n\n        stack = QVBoxLayout()\n        stack.setSpacing(0)\n\n        heading = QLabel(title)\n        heading.setProperty("heading", True)\n        stack.addWidget(heading)\n\n        if subtitle:\n            detail = QLabel(subtitle)\n            detail.setProperty("muted", True)\n            detail.setWordWrap(True)\n            stack.addWidget(detail)\n\n        layout.addLayout(stack)\n        layout.addStretch()\n\n\nclass EmptyState(Panel):\n    def __init__(\n        self,\n        title: str,\n        message: str,\n        action_text: str | None = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(16, 14, 16, 14)\n        layout.setSpacing(6)\n\n        heading = QLabel(title)\n        heading.setProperty("sectionTitle", True)\n        layout.addWidget(heading)\n\n        detail = QLabel(message)\n        detail.setProperty("muted", True)\n        detail.setWordWrap(True)\n        layout.addWidget(detail)\n\n        if action_text:\n            action = PrimaryButton(action_text)\n            layout.addWidget(action, alignment=Qt.AlignmentFlag.AlignLeft)\n\n\nclass CompactTable(QTableView):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setAlternatingRowColors(True)\n        self.setShowGrid(False)\n        self.verticalHeader().setDefaultSectionSize(32)\n        self.verticalHeader().hide()\n        self.horizontalHeader().setStretchLastSection(True)\n\n\nclass MetricRow(QWidget):\n    def __init__(\n        self,\n        metrics: Sequence[tuple[str, str]] = (),\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n\n        self._layout = QHBoxLayout(self)\n        self._layout.setContentsMargins(0, 0, 0, 0)\n        self._layout.setSpacing(6)\n\n        self.value_labels: list[QLabel] = []\n        self.name_labels: list[QLabel] = []\n\n        if metrics:\n            self.set_metrics(metrics)\n\n    def set_metrics(\n        self,\n        metrics: Sequence[tuple[str, str]],\n    ) -> None:\n        if not self.value_labels or len(self.value_labels) != len(metrics):\n            while self._layout.count():\n                item = self._layout.takeAt(0)\n                widget = item.widget() if item else None\n                if widget is not None:\n                    widget.deleteLater()\n\n            self.value_labels.clear()\n            self.name_labels.clear()\n\n            for label, value in metrics:\n                panel = Panel()\n                panel.setProperty("metric", True)\n\n                panel_layout = QVBoxLayout(panel)\n                panel_layout.setContentsMargins(10, 6, 10, 6)\n                panel_layout.setSpacing(1)\n\n                value_label = QLabel(value)\n                value_label.setProperty("metricValue", True)\n                self.value_labels.append(value_label)\n\n                name_label = QLabel(label)\n                name_label.setProperty("muted", True)\n                self.name_labels.append(name_label)\n\n                panel_layout.addWidget(value_label)\n                panel_layout.addWidget(name_label)\n                self._layout.addWidget(panel)\n        else:\n            for index, (label, value) in enumerate(metrics):\n                self.value_labels[index].setText(value)\n                self.name_labels[index].setText(label)\n\n\ndef apply_icon_tint(widget: QWidget, mode: ThemeMode) -> None:\n    widget.setProperty(\n        "iconTint",\n        QColor(palette(mode).muted_text),\n    )\n'
HOME_PAYLOAD = 'from __future__ import annotations\n\nfrom PySide6.QtCore import Signal\nfrom PySide6.QtWidgets import (\n    QGridLayout,\n    QHBoxLayout,\n    QLabel,\n    QListWidget,\n    QListWidgetItem,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.widgets import MetricRow, Panel, PrimaryButton, StatusChip\nfrom sp_farms.application.context import ApplicationContext\nfrom sp_farms.domain.device_management import ManagedDevice\nfrom sp_farms.domain.jobs import JobState\n\n\nclass HomeDashboard(QWidget):\n    """Direct monitoring dashboard: no quick-action cards or step-flow strip."""\n\n    route_requested = Signal(str)\n\n    def __init__(\n        self,\n        context: ApplicationContext,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("homeDashboard")\n        self._context = context\n        self._devices: tuple[ManagedDevice, ...] = ()\n        self._build_ui()\n        self.refresh()\n\n    def _build_ui(self) -> None:\n        root = QVBoxLayout(self)\n        root.setContentsMargins(10, 9, 10, 8)\n        root.setSpacing(8)\n\n        header = QHBoxLayout()\n\n        title_stack = QVBoxLayout()\n        title_stack.setSpacing(0)\n\n        title = QLabel("Dashboard")\n        title.setProperty("heading", True)\n        title_stack.addWidget(title)\n\n        subtitle = QLabel(\n            "Current accounts, devices, queue state, failures, and recent activity."\n        )\n        subtitle.setProperty("muted", True)\n        title_stack.addWidget(subtitle)\n\n        header.addLayout(title_stack)\n        header.addStretch()\n\n        refresh = PrimaryButton("Refresh")\n        refresh.clicked.connect(self.refresh)\n        header.addWidget(refresh)\n\n        root.addLayout(header)\n\n        self.metrics = MetricRow(\n            (\n                ("Accounts", "0"),\n                ("Online Devices", "0"),\n                ("Running", "0"),\n                ("Queued", "0"),\n                ("Success", "0"),\n                ("Failed", "0"),\n            )\n        )\n        root.addWidget(self.metrics)\n\n        body = QGridLayout()\n        body.setSpacing(8)\n\n        activity = Panel()\n        activity_layout = QVBoxLayout(activity)\n        activity_layout.setContentsMargins(10, 9, 10, 9)\n        activity_layout.setSpacing(6)\n\n        activity_title = QLabel("Recent Activity")\n        activity_title.setProperty("sectionTitle", True)\n        activity_layout.addWidget(activity_title)\n\n        self.recent_jobs = QListWidget()\n        self.recent_jobs.setObjectName("homeRecentJobs")\n        self.recent_jobs.setUniformItemSizes(True)\n        activity_layout.addWidget(self.recent_jobs, stretch=1)\n\n        body.addWidget(activity, 0, 0, 2, 1)\n\n        health = Panel()\n        health_layout = QVBoxLayout(health)\n        health_layout.setContentsMargins(10, 9, 10, 9)\n        health_layout.setSpacing(6)\n\n        health_title = QLabel("System Status")\n        health_title.setProperty("sectionTitle", True)\n        health_layout.addWidget(health_title)\n\n        self.device_health = StatusChip("No devices", "neutral")\n        self.job_health = StatusChip("No jobs", "neutral")\n        self.account_health = StatusChip("No accounts", "neutral")\n        self.queue_health = StatusChip("Queue clear", "success")\n\n        health_layout.addWidget(self.device_health)\n        health_layout.addWidget(self.job_health)\n        health_layout.addWidget(self.account_health)\n        health_layout.addWidget(self.queue_health)\n        health_layout.addStretch()\n\n        body.addWidget(health, 0, 1)\n\n        devices = Panel()\n        device_layout = QVBoxLayout(devices)\n        device_layout.setContentsMargins(10, 9, 10, 9)\n        device_layout.setSpacing(6)\n\n        device_title = QLabel("Device Status")\n        device_title.setProperty("sectionTitle", True)\n        device_layout.addWidget(device_title)\n\n        self.device_list = QListWidget()\n        self.device_list.setObjectName("homeDeviceSnapshot")\n        self.device_list.setUniformItemSizes(True)\n        device_layout.addWidget(self.device_list, stretch=1)\n\n        body.addWidget(devices, 1, 1)\n\n        body.setColumnStretch(0, 3)\n        body.setColumnStretch(1, 2)\n        body.setRowStretch(0, 1)\n        body.setRowStretch(1, 2)\n\n        root.addLayout(body, stretch=1)\n\n    def set_devices(\n        self,\n        devices: tuple[ManagedDevice, ...],\n    ) -> None:\n        self._devices = devices\n        self.refresh()\n\n    @staticmethod\n    def _state_text(state: object) -> str:\n        value = getattr(state, "value", None)\n        return str(\n            value if value is not None else state\n        ).replace("_", " ").title()\n\n    def refresh(self) -> None:\n        accounts = (\n            tuple(self._context.account_service.list_accounts())\n            if self._context.account_service is not None\n            else ()\n        )\n        jobs = (\n            tuple(self._context.job_service.list_jobs())\n            if self._context.job_service is not None\n            else ()\n        )\n\n        online = sum(\n            bool(device.is_online)\n            for device in self._devices\n        )\n        running = sum(\n            job.state is JobState.RUNNING\n            for job in jobs\n        )\n        queued = sum(\n            job.state in (JobState.PENDING, JobState.QUEUED)\n            for job in jobs\n        )\n        succeeded = sum(\n            job.state is JobState.SUCCEEDED\n            for job in jobs\n        )\n        failed = sum(\n            job.state is JobState.FAILED\n            for job in jobs\n        )\n\n        values = (\n            len(accounts),\n            online,\n            running,\n            queued,\n            succeeded,\n            failed,\n        )\n        for label, value in zip(\n            self.metrics.value_labels,\n            values,\n            strict=True,\n        ):\n            label.setText(str(value))\n\n        self.device_health.update_state(\n            "success" if online else "neutral",\n            f"Devices: {online}/{len(self._devices)} online",\n        )\n        self.job_health.update_state(\n            "error" if failed else "active" if running else "success",\n            f"Jobs: {running} running · {failed} failed",\n        )\n        self.account_health.update_state(\n            "success" if accounts else "neutral",\n            f"Accounts: {len(accounts)} connected",\n        )\n        self.queue_health.update_state(\n            "warning" if queued else "success",\n            f"Queue: {queued} waiting"\n            if queued\n            else "Queue is clear",\n        )\n\n        self.recent_jobs.clear()\n        recent = list(jobs[-12:])\n\n        if not recent:\n            self.recent_jobs.addItem("No recent jobs.")\n        else:\n            for job in reversed(recent):\n                state = self._state_text(\n                    getattr(job, "state", "unknown")\n                )\n                job_type = str(\n                    getattr(job, "job_type", None)\n                    or getattr(job, "type", None)\n                    or "Job"\n                ).replace("_", " ")\n                short_id = str(\n                    getattr(job, "id", "")\n                )[:8]\n\n                self.recent_jobs.addItem(\n                    QListWidgetItem(\n                        f"{state:12}  {job_type}  {short_id}"\n                    )\n                )\n\n        self.device_list.clear()\n\n        if not self._devices:\n            self.device_list.addItem("No devices discovered.")\n            return\n\n        for device in self._devices[:14]:\n            provider = getattr(\n                getattr(device, "provider", None),\n                "value",\n                "device",\n            )\n            account = device.assigned_account or "Unassigned"\n            network = device.network_state or "System"\n\n            self.device_list.addItem(\n                f"{\'●\' if device.is_online else \'○\'} "\n                f"{device.display_name} · {provider} · "\n                f"{account} · {network}"\n            )\n'
WORKSPACES_PAYLOAD = 'from collections.abc import Sequence\nfrom typing import TYPE_CHECKING\n\nfrom PySide6.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal\nfrom PySide6.QtGui import QStandardItemModel\nfrom PySide6.QtWidgets import (\n    QCheckBox,\n    QComboBox,\n    QFormLayout,\n    QHBoxLayout,\n    QHeaderView,\n    QLabel,\n    QLineEdit,\n    QListView,\n    QPushButton,\n    QSplitter,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.widgets import (\n    CompactTable,\n    MetricRow,\n    Panel,\n    PrimaryButton,\n    SecondaryButton,\n    StatusChip,\n)\nfrom sp_farms.domain.device_management import ManagedDevice\nfrom sp_farms.domain.jobs import Job, JobState\n\nif TYPE_CHECKING:\n    from sp_farms.app.device_manager import DeviceManagerView\n    from sp_farms.application.job_service import JobService\n\n\nclass RailFilterProxy(QSortFilterProxyModel):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self._search = ""\n        self._mode = "all"\n\n    def set_search(self, value: str) -> None:\n        self._search = value.strip().lower()\n        self.invalidateFilter()\n\n    def set_mode(self, value: str) -> None:\n        self._mode = value.strip().lower()\n        self.invalidateFilter()\n\n    def filterAcceptsRow(\n        self,\n        source_row: int,\n        source_parent,\n    ) -> bool:\n        source = self.sourceModel()\n        if source is None:\n            return True\n\n        index = source.index(\n            source_row,\n            0,\n            source_parent,\n        )\n        device = source.data(\n            index,\n            Qt.ItemDataRole.UserRole,\n        )\n\n        if not isinstance(device, ManagedDevice):\n            return True\n\n        mode = self._mode\n\n        if mode == "online" and not device.is_online:\n            return False\n\n        if mode == "offline" and device.is_online:\n            return False\n\n        if (\n            mode in {"ldplayer", "mumu", "physical"}\n            and device.provider.value != mode\n        ):\n            return False\n\n        haystack = " ".join(\n            (\n                device.display_name,\n                device.provider.value,\n                device.adb_serial,\n                device.assigned_account or "",\n                device.network_state or "",\n            )\n        ).lower()\n\n        return not self._search or self._search in haystack\n\n\nclass DeviceRail(Panel):\n    devices_route_requested = Signal()\n    automation_route_requested = Signal()\n    settings_route_requested = Signal()\n\n    def __init__(\n        self,\n        model: QAbstractItemModel | None = None,\n        controller: "DeviceManagerView | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("deviceRail")\n        self.setMinimumWidth(245)\n        self.setMaximumWidth(300)\n\n        self._controller = controller\n        self._model = model\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(8, 8, 8, 8)\n        layout.setSpacing(6)\n\n        header = QHBoxLayout()\n\n        title = QLabel("Device Manager")\n        title.setProperty("heading", True)\n        header.addWidget(title)\n        header.addStretch()\n\n        self.online_chip = StatusChip(\n            "0 Online",\n            "neutral",\n        )\n        header.addWidget(self.online_chip)\n\n        layout.addLayout(header)\n\n        control_row = QHBoxLayout()\n\n        self.refresh_btn = SecondaryButton("Refresh")\n        self.add_btn = PrimaryButton("+ Device")\n\n        control_row.addWidget(self.refresh_btn)\n        control_row.addWidget(self.add_btn)\n\n        layout.addLayout(control_row)\n\n        self.search = QLineEdit()\n        self.search.setPlaceholderText(\n            "Search device, serial, account..."\n        )\n        layout.addWidget(self.search)\n\n        filter_row = QHBoxLayout()\n\n        self.mode_filter = QComboBox()\n        self.mode_filter.addItems(\n            (\n                "All Devices",\n                "Online",\n                "Offline",\n                "LDPlayer",\n                "MuMu",\n                "Physical",\n            )\n        )\n\n        self.show_ip = QCheckBox("Show IP")\n\n        filter_row.addWidget(\n            self.mode_filter,\n            stretch=1,\n        )\n        filter_row.addWidget(self.show_ip)\n\n        layout.addLayout(filter_row)\n\n        self.proxy = RailFilterProxy(self)\n        if model is not None:\n            self.proxy.setSourceModel(model)\n\n        self.list_view = QListView()\n        self.list_view.setObjectName("deviceRailList")\n        self.list_view.setUniformItemSizes(True)\n        self.list_view.setModel(self.proxy)\n\n        layout.addWidget(\n            self.list_view,\n            stretch=1,\n        )\n\n        detail_title = QLabel("Selected Device")\n        detail_title.setProperty("sectionTitle", True)\n        layout.addWidget(detail_title)\n\n        detail_panel = Panel()\n        detail_layout = QVBoxLayout(detail_panel)\n        detail_layout.setContentsMargins(\n            8,\n            7,\n            8,\n            7,\n        )\n        detail_layout.setSpacing(5)\n\n        detail_header = QHBoxLayout()\n\n        self.preview_name = QLabel(\n            "No device selected"\n        )\n        self.preview_name.setProperty(\n            "sectionTitle",\n            True,\n        )\n        detail_header.addWidget(self.preview_name)\n        detail_header.addStretch()\n\n        self.preview_state = StatusChip(\n            "Offline",\n            "neutral",\n        )\n        detail_header.addWidget(\n            self.preview_state\n        )\n\n        detail_layout.addLayout(detail_header)\n\n        form = QFormLayout()\n        form.setContentsMargins(\n            0,\n            0,\n            0,\n            0,\n        )\n        form.setHorizontalSpacing(7)\n        form.setVerticalSpacing(3)\n\n        self.preview_provider = QLabel("—")\n        self.preview_account = QLabel("—")\n        self.preview_network = QLabel("—")\n        self.preview_usage = QLabel("—")\n        self.preview_adb = QLabel("—")\n\n        for label in (\n            self.preview_provider,\n            self.preview_account,\n            self.preview_network,\n            self.preview_usage,\n            self.preview_adb,\n        ):\n            label.setProperty("muted", True)\n\n        form.addRow(\n            "Device:",\n            self.preview_provider,\n        )\n        form.addRow(\n            "Account:",\n            self.preview_account,\n        )\n        form.addRow(\n            "Network:",\n            self.preview_network,\n        )\n        form.addRow(\n            "CPU / RAM:",\n            self.preview_usage,\n        )\n        form.addRow(\n            "ADB:",\n            self.preview_adb,\n        )\n\n        detail_layout.addLayout(form)\n\n        state_row = QHBoxLayout()\n\n        self.start_btn = PrimaryButton("Start")\n        self.stop_btn = SecondaryButton("Stop")\n        self.restart_btn = SecondaryButton("Restart")\n\n        state_row.addWidget(self.start_btn)\n        state_row.addWidget(self.stop_btn)\n        state_row.addWidget(self.restart_btn)\n\n        detail_layout.addLayout(state_row)\n\n        app_row = QHBoxLayout()\n\n        self.package_input = QLineEdit()\n        self.package_input.setPlaceholderText(\n            "App package"\n        )\n        self.launch_btn = SecondaryButton("Launch")\n\n        app_row.addWidget(\n            self.package_input,\n            stretch=1,\n        )\n        app_row.addWidget(self.launch_btn)\n\n        detail_layout.addLayout(app_row)\n\n        tool_row = QHBoxLayout()\n\n        self.screenshot_btn = SecondaryButton(\n            "Screenshot"\n        )\n        self.open_device_btn = PrimaryButton(\n            "Open Device"\n        )\n\n        tool_row.addWidget(self.screenshot_btn)\n        tool_row.addWidget(self.open_device_btn)\n\n        detail_layout.addLayout(tool_row)\n\n        layout.addWidget(detail_panel)\n\n        self.search.textChanged.connect(\n            self.proxy.set_search\n        )\n        self.mode_filter.currentTextChanged.connect(\n            lambda text: self.proxy.set_mode(\n                {\n                    "All Devices": "all",\n                    "Online": "online",\n                    "Offline": "offline",\n                    "LDPlayer": "ldplayer",\n                    "MuMu": "mumu",\n                    "Physical": "physical",\n                }.get(text, "all")\n            )\n        )\n\n        self.refresh_btn.clicked.connect(\n            self._refresh\n        )\n        self.add_btn.clicked.connect(\n            self.devices_route_requested.emit\n        )\n        self.open_device_btn.clicked.connect(\n            self.devices_route_requested.emit\n        )\n\n        self.list_view.selectionModel().selectionChanged.connect(\n            self._selection_changed\n        )\n        self.show_ip.toggled.connect(\n            self._selection_changed\n        )\n        self.package_input.textChanged.connect(\n            self._selection_changed\n        )\n\n        self.start_btn.clicked.connect(\n            lambda: self._run("start")\n        )\n        self.stop_btn.clicked.connect(\n            lambda: self._run("stop")\n        )\n        self.restart_btn.clicked.connect(\n            lambda: self._run("restart")\n        )\n        self.launch_btn.clicked.connect(\n            lambda: self._run("launch_app")\n        )\n        self.screenshot_btn.clicked.connect(\n            lambda: self._artifact(\n                "screenshot"\n            )\n        )\n\n        if model is not None:\n            model.modelReset.connect(\n                self._model_reset\n            )\n            model.rowsInserted.connect(\n                self._model_reset\n            )\n            model.rowsRemoved.connect(\n                self._model_reset\n            )\n\n        self._model_reset()\n        self._selection_changed()\n\n    def _selected_device(\n        self,\n    ) -> ManagedDevice | None:\n        index = self.list_view.currentIndex()\n\n        if not index.isValid():\n            return None\n\n        device = self.proxy.data(\n            index,\n            Qt.ItemDataRole.UserRole,\n        )\n\n        return (\n            device\n            if isinstance(\n                device,\n                ManagedDevice,\n            )\n            else None\n        )\n\n    def _all_devices(\n        self,\n    ) -> tuple[ManagedDevice, ...]:\n        if self._model is None:\n            return ()\n\n        devices: list[ManagedDevice] = []\n\n        for row in range(\n            self._model.rowCount()\n        ):\n            device = self._model.data(\n                self._model.index(\n                    row,\n                    0,\n                ),\n                Qt.ItemDataRole.UserRole,\n            )\n\n            if isinstance(\n                device,\n                ManagedDevice,\n            ):\n                devices.append(device)\n\n        return tuple(devices)\n\n    def _refresh(self) -> None:\n        if self._controller is not None:\n            self._controller.refresh()\n\n    def _model_reset(self) -> None:\n        devices = self._all_devices()\n\n        online = sum(\n            device.is_online\n            for device in devices\n        )\n\n        self.online_chip.update_state(\n            "success"\n            if online\n            else "neutral",\n            f"{online} Online",\n        )\n\n        self._selection_changed()\n\n    def _selection_changed(self) -> None:\n        device = self._selected_device()\n\n        if device is None:\n            self.preview_name.setText(\n                "No device selected"\n            )\n            self.preview_state.update_state(\n                "neutral",\n                "Offline",\n            )\n            self.preview_provider.setText("—")\n            self.preview_account.setText("—")\n            self.preview_network.setText("—")\n            self.preview_usage.setText("—")\n            self.preview_adb.setText("—")\n\n            for button in (\n                self.start_btn,\n                self.stop_btn,\n                self.restart_btn,\n                self.launch_btn,\n                self.screenshot_btn,\n            ):\n                button.setEnabled(False)\n\n            return\n\n        self.preview_name.setText(\n            device.display_name\n        )\n        self.preview_state.update_state(\n            "success"\n            if device.is_online\n            else "error",\n            "Running"\n            if device.is_online\n            else "Offline",\n        )\n\n        self.preview_provider.setText(\n            f"{device.provider.value} · "\n            f"Android "\n            f"{device.android_version or \'—\'}"\n        )\n        self.preview_account.setText(\n            device.assigned_account\n            or "Unassigned"\n        )\n\n        network = (\n            device.network_state\n            or "System"\n        )\n\n        if (\n            not self.show_ip.isChecked()\n            and "ip" in network.lower()\n        ):\n            network = "Connected"\n\n        self.preview_network.setText(\n            network\n        )\n\n        cpu = (\n            f"{device.cpu_usage:.0f}%"\n            if device.cpu_usage is not None\n            else "—"\n        )\n        ram = (\n            f"{device.ram_usage_mb} MB"\n            if device.ram_usage_mb\n            is not None\n            else "—"\n        )\n\n        self.preview_usage.setText(\n            f"{cpu} / {ram}"\n        )\n        self.preview_adb.setText(\n            device.adb_serial\n            or "No ADB serial"\n        )\n\n        capabilities = device.capabilities\n\n        self.start_btn.setEnabled(\n            capabilities.can_start_stop\n            and not device.is_online\n        )\n        self.stop_btn.setEnabled(\n            capabilities.can_start_stop\n            and device.is_online\n        )\n        self.restart_btn.setEnabled(\n            capabilities.can_restart\n            and device.is_online\n        )\n        self.launch_btn.setEnabled(\n            capabilities.can_launch_apps\n            and device.is_online\n            and bool(\n                self.package_input.text().strip()\n            )\n        )\n        self.screenshot_btn.setEnabled(\n            capabilities.can_take_screenshot\n            and device.is_online\n        )\n\n    def _run(\n        self,\n        action: str,\n    ) -> None:\n        device = self._selected_device()\n\n        if (\n            device is None\n            or self._controller is None\n        ):\n            return\n\n        package = (\n            self.package_input.text().strip()\n            if action == "launch_app"\n            else None\n        )\n\n        self._controller.run_devices(\n            action,\n            (device,),\n            package,\n        )\n\n    def _artifact(\n        self,\n        action: str,\n    ) -> None:\n        device = self._selected_device()\n\n        if (\n            device is not None\n            and self._controller is not None\n        ):\n            self._controller.collect_device_artifacts(\n                action,\n                (device,),\n            )\n\n\nclass ManagementWorkspace(QWidget):\n    def __init__(\n        self,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName(\n            "managementWorkspace"\n        )\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(\n            0,\n            0,\n            0,\n            0,\n        )\n        layout.setSpacing(8)\n\n        layout.addWidget(\n            MetricRow(\n                (\n                    ("Accounts", "0"),\n                    ("Active", "0"),\n                    (\n                        "Needs attention",\n                        "0",\n                    ),\n                )\n            )\n        )\n\n        toolbar = Panel()\n        toolbar_layout = QHBoxLayout(\n            toolbar\n        )\n        toolbar_layout.setContentsMargins(\n            10,\n            7,\n            10,\n            7,\n        )\n\n        search = QLineEdit()\n        search.setPlaceholderText(\n            "Search accounts, pages, or groups"\n        )\n\n        toolbar_layout.addWidget(\n            search,\n            stretch=1,\n        )\n        toolbar_layout.addWidget(\n            QPushButton("Filter")\n        )\n        toolbar_layout.addWidget(\n            PrimaryButton("Add account")\n        )\n\n        layout.addWidget(toolbar)\n\n        table = CompactTable()\n        table.setObjectName(\n            "managementTable"\n        )\n\n        model = QStandardItemModel(\n            0,\n            6,\n            table,\n        )\n        model.setHorizontalHeaderLabels(\n            (\n                "Account",\n                "Status",\n                "Device",\n                "Network",\n                "Last active",\n                "Actions",\n            )\n        )\n\n        table.setModel(model)\n\n        header = table.horizontalHeader()\n        header.setSectionResizeMode(\n            0,\n            QHeaderView.ResizeMode.Stretch,\n        )\n\n        for column in range(1, 6):\n            header.setSectionResizeMode(\n                column,\n                QHeaderView.ResizeMode.ResizeToContents,\n            )\n\n        layout.addWidget(\n            table,\n            stretch=1,\n        )\n\n\nclass JobQueueDrawer(Panel):\n    automation_route_requested = Signal()\n\n    def __init__(\n        self,\n        service: "JobService | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName(\n            "jobQueueDrawer"\n        )\n        self.setMinimumWidth(240)\n        self.setMaximumWidth(310)\n\n        self._service = service\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(\n            9,\n            9,\n            9,\n            9,\n        )\n        layout.setSpacing(6)\n\n        heading = QLabel("Job Queue")\n        heading.setProperty(\n            "sectionTitle",\n            True,\n        )\n        layout.addWidget(heading)\n\n        self.status = StatusChip(\n            "0 running",\n            "neutral",\n        )\n        layout.addWidget(self.status)\n\n        self.summary = QLabel(\n            "Queue is clear"\n        )\n        self.summary.setProperty(\n            "muted",\n            True,\n        )\n        self.summary.setWordWrap(True)\n        layout.addWidget(self.summary)\n\n        open_queue = PrimaryButton(\n            "Open Queue"\n        )\n        open_queue.clicked.connect(\n            self.automation_route_requested.emit\n        )\n        layout.addWidget(open_queue)\n\n        layout.addStretch()\n\n        self.refresh()\n\n    def refresh(\n        self,\n    ) -> tuple[Job, ...]:\n        jobs = (\n            tuple(\n                self._service.list_jobs()\n            )\n            if self._service is not None\n            else ()\n        )\n\n        running = sum(\n            job.state is JobState.RUNNING\n            for job in jobs\n        )\n        queued = sum(\n            job.state\n            in (\n                JobState.PENDING,\n                JobState.QUEUED,\n            )\n            for job in jobs\n        )\n        failed = sum(\n            job.state is JobState.FAILED\n            for job in jobs\n        )\n\n        self.status.update_state(\n            "error"\n            if failed\n            else (\n                "active"\n                if running\n                else "neutral"\n            ),\n            f"{running} running",\n        )\n\n        self.summary.setText(\n            f"{queued} queued · "\n            f"{failed} failed"\n            if jobs\n            else "Queue is clear"\n        )\n\n        return jobs\n\n\nclass WorkspaceLayout(QWidget):\n    devices_route_requested = Signal()\n    automation_route_requested = Signal()\n    settings_route_requested = Signal()\n\n    def __init__(\n        self,\n        device_model: QAbstractItemModel | None = None,\n        content: QWidget | None = None,\n        device_controller: "DeviceManagerView | None" = None,\n        job_service: "JobService | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n\n        root = QVBoxLayout(self)\n        root.setContentsMargins(\n            6,\n            6,\n            6,\n            0,\n        )\n        root.setSpacing(5)\n\n        splitter = QSplitter(\n            Qt.Orientation.Horizontal\n        )\n        splitter.setObjectName(\n            "workspaceSplitter"\n        )\n        splitter.setChildrenCollapsible(\n            False\n        )\n\n        self.device_rail = DeviceRail(\n            device_model,\n            device_controller,\n        )\n        self.device_rail.devices_route_requested.connect(\n            self.devices_route_requested.emit\n        )\n\n        splitter.addWidget(\n            self.device_rail\n        )\n        splitter.addWidget(\n            content\n            or ManagementWorkspace()\n        )\n\n        self.job_queue = JobQueueDrawer(\n            job_service\n        )\n        self.job_queue.automation_route_requested.connect(\n            self.automation_route_requested.emit\n        )\n\n        splitter.addWidget(\n            self.job_queue\n        )\n\n        splitter.setStretchFactor(\n            0,\n            0,\n        )\n        splitter.setStretchFactor(\n            1,\n            1,\n        )\n        splitter.setStretchFactor(\n            2,\n            0,\n        )\n        splitter.setSizes(\n            [270, 1160, 270]\n        )\n\n        root.addWidget(\n            splitter,\n            stretch=1,\n        )\n\n        status = QWidget()\n        status.setObjectName(\n            "statusBarContent"\n        )\n\n        status_layout = QHBoxLayout(\n            status\n        )\n        status_layout.setContentsMargins(\n            10,\n            4,\n            10,\n            4,\n        )\n        status_layout.setSpacing(10)\n\n        brand = QLabel("SP-FARMS")\n        brand.setStyleSheet(\n            "font-weight: 800;"\n        )\n        status_layout.addWidget(brand)\n        status_layout.addWidget(\n            QLabel("|")\n        )\n\n        self.footer_labels: dict[\n            str,\n            QLabel,\n        ] = {}\n\n        for key, value in (\n            ("Total", "0"),\n            ("Online", "0"),\n            ("Running", "0"),\n            ("Success", "0"),\n            ("Failed", "0"),\n            ("Queue", "0"),\n            ("CPU", "0%"),\n            ("RAM", "0 MB"),\n        ):\n            block = QHBoxLayout()\n            block.setSpacing(3)\n\n            name = QLabel(key)\n            name.setProperty(\n                "muted",\n                True,\n            )\n\n            number = QLabel(value)\n            self.footer_labels[\n                key\n            ] = number\n\n            block.addWidget(name)\n            block.addWidget(number)\n\n            status_layout.addLayout(\n                block\n            )\n\n        status_layout.addStretch()\n        status_layout.addWidget(\n            QLabel(\n                "Automate Smarter • "\n                "Manage Bigger"\n            )\n        )\n\n        root.addWidget(status)\n\n        if device_controller is not None:\n            device_controller.devices_changed.connect(\n                self._update_device_status\n            )\n\n    def refresh_jobs(self) -> None:\n        jobs = self.job_queue.refresh()\n        self._update_job_status(jobs)\n\n    def _update_job_status(\n        self,\n        jobs: Sequence[Job],\n    ) -> None:\n        self.footer_labels[\n            "Success"\n        ].setText(\n            str(\n                sum(\n                    job.state\n                    is JobState.SUCCEEDED\n                    for job in jobs\n                )\n            )\n        )\n        self.footer_labels[\n            "Failed"\n        ].setText(\n            str(\n                sum(\n                    job.state\n                    is JobState.FAILED\n                    for job in jobs\n                )\n            )\n        )\n        self.footer_labels[\n            "Queue"\n        ].setText(\n            str(\n                sum(\n                    job.state\n                    in (\n                        JobState.PENDING,\n                        JobState.QUEUED,\n                    )\n                    for job in jobs\n                )\n            )\n        )\n\n    def _update_device_status(\n        self,\n        devices: object,\n    ) -> None:\n        if not isinstance(\n            devices,\n            tuple,\n        ):\n            return\n\n        managed = tuple(\n            device\n            for device in devices\n            if isinstance(\n                device,\n                ManagedDevice,\n            )\n        )\n        online = tuple(\n            device\n            for device in managed\n            if device.is_online\n        )\n\n        self.footer_labels[\n            "Total"\n        ].setText(\n            str(len(managed))\n        )\n        self.footer_labels[\n            "Online"\n        ].setText(\n            str(len(online))\n        )\n        self.footer_labels[\n            "Running"\n        ].setText(\n            str(len(online))\n        )\n\n        cpu = [\n            device.cpu_usage\n            for device in managed\n            if device.cpu_usage\n            is not None\n        ]\n        ram = [\n            device.ram_usage_mb\n            for device in managed\n            if device.ram_usage_mb\n            is not None\n        ]\n\n        self.footer_labels[\n            "CPU"\n        ].setText(\n            f"{sum(cpu) / len(cpu):.0f}%"\n            if cpu\n            else "0%"\n        )\n        self.footer_labels[\n            "RAM"\n        ].setText(\n            f"{sum(ram)} MB"\n            if ram\n            else "0 MB"\n        )\n'


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def backup_files(names: tuple[str, ...]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f".full_redesign_v7_backup_{stamp}"

    for name in names:
        source = APP / name
        if not source.exists():
            continue

        target = backup / "sp_farms" / "app" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    return backup


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
    *,
    required: bool = False,
) -> str:
    if new in text:
        print(f"[OK] {label}: already applied")
        return text

    if old not in text:
        message = f"{label}: source block not found"
        if required:
            fail(message)
        print(f"[SKIP] {message}")
        return text

    print(f"[PATCH] {label}")
    return text.replace(old, new, 1)


def patch_main_window() -> None:
    path = APP / "main_window.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "        self.setMinimumSize(1024, 680)\n",
        "        self.setMinimumSize(1180, 720)\n",
        1,
    )
    text = text.replace(
        "        self.resize(1440, 900)\n",
        "        self.resize(1520, 930)\n",
        1,
    )
    text = text.replace(
        "        navigation_layout.setContentsMargins(10, 7, 12, 7)\n",
        "        navigation_layout.setContentsMargins(12, 6, 12, 6)\n",
        1,
    )
    text = text.replace(
        "        navigation_layout.setSpacing(4)\n",
        "        navigation_layout.setSpacing(3)\n",
        1,
    )

    text = text.replace(
        'automation_tabs.addTab(self.scheduler_workspace, "Scheduler & Calendar")',
        'automation_tabs.addTab(self.scheduler_workspace, "Schedule")',
    )
    text = text.replace(
        'automation_tabs.addTab(self.approval_workspace, "Approval Queue")',
        'automation_tabs.addTab(self.approval_workspace, "Approvals")',
    )
    text = text.replace(
        'automation_tabs.addTab(self.job_queue_view, "Job Execution Queue")',
        'automation_tabs.addTab(self.job_queue_view, "Queue")',
    )

    quick_tab = (
        "                if self.quick_automation_workspace is not None:\n"
        '                    automation_tabs.addTab(self.quick_automation_workspace, "Quick Mode")\n'
    )
    text = text.replace(quick_tab, "", 1)

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Main shell / navigation")


def patch_account_workspace() -> None:
    path = APP / "account_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        '("Local Accounts", "Security Center", "Error Center", "Pages", "Groups")',
        '("Accounts", "Security", "Errors", "Pages", "Groups")',
        1,
    )
    text = text.replace(
        'if label == "Local Accounts":',
        'if label == "Accounts":',
        1,
    )
    text = text.replace(
        'elif label == "Security Center":',
        'elif label == "Security":',
        1,
    )
    text = text.replace(
        'elif label == "Error Center":',
        'elif label == "Errors":',
        1,
    )

    text = text.replace(
        "        self.inspector.setMinimumWidth(345)\n",
        "        self.inspector.setMinimumWidth(320)\n",
        1,
    )
    text = text.replace(
        "        self.inspector.setMaximumWidth(470)\n",
        "        self.inspector.setMaximumWidth(430)\n",
        1,
    )

    old_layout = '''        toolbar_layout.addWidget(self.search_input, stretch=1)
        toolbar_layout.addWidget(self.smart_filter)
        toolbar_layout.addWidget(self.category_filter)
        toolbar_layout.addWidget(self.status_filter)
        toolbar_layout.addWidget(self.device_filter)
        toolbar_layout.addWidget(self.network_filter)
        toolbar_layout.addWidget(self.columns_btn)
        toolbar_layout.addWidget(self.bulk_btn)
        toolbar_layout.addWidget(self.workflow_btn)
        toolbar_layout.addWidget(self.actions_btn)
        toolbar_layout.addWidget(self.status_chip)
        toolbar_layout.addWidget(self.add_btn)
        listing_layout.addWidget(toolbar)
'''

    new_layout = '''        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_row.addWidget(self.search_input, stretch=1)
        filter_row.addWidget(self.smart_filter)
        filter_row.addWidget(self.category_filter)
        filter_row.addWidget(self.status_filter)
        filter_row.addWidget(self.device_filter)
        filter_row.addWidget(self.network_filter)
        filter_row.addWidget(self.columns_btn)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(self.status_chip)
        action_row.addStretch()
        action_row.addWidget(self.bulk_btn)
        action_row.addWidget(self.workflow_btn)
        action_row.addWidget(self.actions_btn)
        action_row.addWidget(self.add_btn)

        toolbar_layout.addLayout(filter_row)
        toolbar_layout.addLayout(action_row)
        listing_layout.addWidget(toolbar)
'''

    if old_layout in text:
        text = text.replace(
            "        toolbar_layout = QHBoxLayout(toolbar)\n",
            "        toolbar_layout = QVBoxLayout(toolbar)\n"
            "        toolbar_layout.setContentsMargins(8, 7, 8, 7)\n"
            "        toolbar_layout.setSpacing(6)\n",
            1,
        )
        text = text.replace(old_layout, new_layout, 1)
        print("[PATCH] Accounts two-row toolbar")
    elif "filter_row = QHBoxLayout()" in text:
        print("[OK] Accounts two-row toolbar already applied")
    else:
        print("[SKIP] Accounts toolbar structure differs")

    text = text.replace(
        '        detail_heading.setStyleSheet("font-weight: 700;")\n',
        '        detail_heading.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        heading.setStyleSheet("font-weight: 700;")\n',
        '        heading.setProperty("sectionTitle", True)\n',
    )

    path.write_text(text, encoding="utf-8")


def patch_asset_workspace() -> None:
    path = APP / "asset_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "        self.setMinimumWidth(280)\n",
        "        self.setMinimumWidth(300)\n",
        1,
    )
    text = text.replace(
        "        self.setMaximumWidth(360)\n",
        "        self.setMaximumWidth(390)\n",
        1,
    )
    text = text.replace(
        '        self.title_label.setStyleSheet("font-weight: 700; font-size: 14px;")\n',
        '        self.title_label.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        shortcuts_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")\n',
        '        shortcuts_heading.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        notes_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")\n',
        '        notes_heading.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        self.actions_btn = PrimaryButton("Actions...")\n',
        '        self.actions_btn = PrimaryButton("Asset Actions")\n',
        1,
    )
    text = text.replace(
        "        root.setContentsMargins(12, 12, 12, 12)\n",
        "        root.setContentsMargins(10, 10, 10, 10)\n",
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Pages / Groups workspace")


def patch_content_workspace() -> None:
    path = APP / "content_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "        layout.setContentsMargins(14, 10, 14, 12)\n",
        "        layout.setContentsMargins(10, 9, 10, 9)\n",
        1,
    )
    text = text.replace(
        '        self.import_btn = SecondaryButton("+ Import Media")\n',
        '        self.import_btn = SecondaryButton("Import Media")\n',
        1,
    )
    text = text.replace(
        '        self.composer_btn = PrimaryButton("✨ Compose Post/Reel")\n',
        '        self.composer_btn = PrimaryButton("Compose Post / Reel")\n',
        1,
    )
    text = text.replace(
        '        self.tabs.addTab(self.templates_tab, "Captions & Hashtags")\n',
        '        self.tabs.addTab(self.templates_tab, "Captions")\n',
        1,
    )
    text = text.replace(
        '        self.tabs.addTab(self.items_tab, "Drafts / Composed")\n',
        '        self.tabs.addTab(self.items_tab, "Drafts")\n',
        1,
    )

    preview_style = '''        self.preview_frame.setStyleSheet(
            "background-color: #1e293b; border-radius: 8px; min-height: 180px; max-height: 220px;"
        )
'''
    preview_new = '''        self.preview_frame.setProperty("softPanel", True)
        self.preview_frame.setMinimumHeight(180)
        self.preview_frame.setMaximumHeight(220)
'''
    text = replace_once(
        text,
        preview_style,
        preview_new,
        "Content preview semantic theme",
    )

    text = text.replace(
        '        lbl1.setStyleSheet("font-weight: 600; font-size: 14px;")\n',
        '        lbl1.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        lbl2.setStyleSheet("font-weight: 600; font-size: 14px;")\n',
        '        lbl2.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        lbl.setStyleSheet("font-weight: 600; font-size: 14px;")\n',
        '        lbl.setProperty("sectionTitle", True)\n',
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Content workspace")


def patch_action_list() -> None:
    path = APP / "farm_reel_action_list.py"

    if not path.exists():
        print("[SKIP] Action List module not installed")
        return

    text = path.read_text(encoding="utf-8")

    if "    QSplitter,\n" not in text:
        text = text.replace(
            "    QSpinBox,\n",
            "    QSpinBox,\n    QSplitter,\n",
            1,
        )

    text = text.replace("    QGridLayout,\n", "", 1)

    class_pos = text.find("class FarmReelActionListWorkspace")
    start = text.find("    def _build_ui(self) -> None:\n", class_pos)
    end = text.find("    @staticmethod\n    def _parse_ids", start)

    if start == -1 or end == -1:
        print("[SKIP] Action List build method markers not found")
        path.write_text(text, encoding="utf-8")
        return

    new_build = '''    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 8, 9, 8)
        root.setSpacing(7)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)

        title = QLabel("Automation Actions")
        title.setProperty("heading", True)
        title_stack.addWidget(title)

        subtitle = QLabel(
            "Select accounts, choose actions, configure, dry-run, then start."
        )
        subtitle.setProperty("muted", True)
        title_stack.addWidget(subtitle)

        header.addLayout(title_stack)
        header.addStretch()

        self.status = StatusChip("0 actions selected", "neutral")
        header.addWidget(self.status)
        root.addLayout(header)

        target_panel = Panel()
        target_layout = QHBoxLayout(target_panel)
        target_layout.setContentsMargins(9, 7, 9, 7)
        target_layout.setSpacing(6)

        target_layout.addWidget(QLabel("Accounts"))
        self.account_ids = QLineEdit()
        self.account_ids.setPlaceholderText("Selected account IDs")
        target_layout.addWidget(self.account_ids, stretch=2)

        target_layout.addWidget(QLabel("Destinations"))
        self.destination_ids = QLineEdit()
        self.destination_ids.setPlaceholderText("Authorized Page / Group IDs")
        target_layout.addWidget(self.destination_ids, stretch=2)

        self.device_policy = QComboBox()
        self.device_policy.addItem("Bound device first", "bound_first")
        self.device_policy.addItem("Any available device", "any_available")
        self.device_policy.addItem("Preferred provider order", "preferred_order")
        target_layout.addWidget(self.device_policy)

        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 32)
        self.concurrency.setValue(4)
        self.concurrency.setPrefix("Devices ")
        target_layout.addWidget(self.concurrency)

        root.addWidget(target_panel)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        available = Panel()
        available_layout = QVBoxLayout(available)
        available_layout.setContentsMargins(8, 8, 8, 8)
        available_layout.setSpacing(5)

        available_header = QHBoxLayout()
        available_title = QLabel("Available Actions")
        available_title.setProperty("sectionTitle", True)
        available_header.addWidget(available_title)
        available_header.addStretch()

        clear = SecondaryButton("Clear")
        clear.clicked.connect(self.clear_actions)
        available_header.addWidget(clear)
        available_layout.addLayout(available_header)

        self.action_search = QLineEdit()
        self.action_search.setPlaceholderText("Search actions...")
        self.action_search.textChanged.connect(self._filter_actions)
        available_layout.addWidget(self.action_search)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemChanged.connect(self._tree_item_changed)
        self.tree.currentItemChanged.connect(self._tree_selection_changed)
        available_layout.addWidget(self.tree, stretch=1)

        self._building_tree = True

        for group_name, step_types in ACTION_GROUPS:
            group_item = QTreeWidgetItem([group_name])
            group_item.setFlags(
                group_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable
            )
            group_item.setExpanded(True)
            self.tree.addTopLevelItem(group_item)

            for step_type in step_types:
                info = CAPABILITY_MATRIX[step_type]
                child = QTreeWidgetItem([info.title])
                child.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    step_type.value,
                )
                child.setFlags(
                    child.flags() | Qt.ItemFlag.ItemIsUserCheckable
                )
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setToolTip(0, info.description)
                group_item.addChild(child)
                self._tree_items[step_type] = child

        self._building_tree = False

        basic = SecondaryButton("Select Basic Setup")
        basic.clicked.connect(self._select_common_flow)
        available_layout.addWidget(basic)
        splitter.addWidget(available)

        selected_panel = Panel()
        selected_layout = QVBoxLayout(selected_panel)
        selected_layout.setContentsMargins(8, 8, 8, 8)
        selected_layout.setSpacing(5)

        selected_title = QLabel("Selected Actions")
        selected_title.setProperty("sectionTitle", True)
        selected_layout.addWidget(selected_title)

        selected_hint = QLabel("Execution order is top to bottom.")
        selected_hint.setProperty("muted", True)
        selected_layout.addWidget(selected_hint)

        self.selected_list = QListWidget()
        self.selected_list.currentRowChanged.connect(
            self._selected_row_changed
        )
        selected_layout.addWidget(self.selected_list, stretch=1)

        order_row = QHBoxLayout()

        up = SecondaryButton("Up")
        down = SecondaryButton("Down")
        remove = SecondaryButton("Remove")

        up.clicked.connect(lambda: self._move_selected(-1))
        down.clicked.connect(lambda: self._move_selected(1))
        remove.clicked.connect(self._remove_selected)

        order_row.addWidget(up)
        order_row.addWidget(down)
        order_row.addWidget(remove)
        selected_layout.addLayout(order_row)

        verification = QLabel(
            "If verification is required, the job waits for operator action "
            "and resumes after verification succeeds."
        )
        verification.setProperty("muted", True)
        verification.setWordWrap(True)
        selected_layout.addWidget(verification)

        splitter.addWidget(selected_panel)

        self.config_editor = ActionConfigEditor()
        self.config_editor.changed.connect(self._refresh_status)
        splitter.addWidget(self.config_editor)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([330, 330, 470])

        root.addWidget(splitter, stretch=1)

        footer_panel = Panel()
        footer = QHBoxLayout(footer_panel)
        footer.setContentsMargins(8, 6, 8, 6)
        footer.setSpacing(6)

        self.preset_name = QLineEdit()
        self.preset_name.setPlaceholderText("Preset name")
        self.preset_name.setText("Custom Action List")
        footer.addWidget(self.preset_name, stretch=1)

        save = SecondaryButton("Save Preset")
        save.clicked.connect(self._save_preset)
        footer.addWidget(save)

        dry = SecondaryButton("Dry Run")
        dry.setProperty("infoAction", True)
        dry.clicked.connect(self._dry_run)
        footer.addWidget(dry)

        queue = SecondaryButton("Queue")
        queue.clicked.connect(self.queue_requested.emit)
        footer.addWidget(queue)

        run = PrimaryButton("Start")
        run.setProperty("successAction", True)
        run.clicked.connect(self._run)
        footer.addWidget(run)

        root.addWidget(footer_panel)

    def _filter_actions(self, text: str) -> None:
        query = text.strip().lower()

        for group_index in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(group_index)
            if group_item is None:
                continue

            group_text = group_item.text(0).lower()
            any_visible = False

            for child_index in range(group_item.childCount()):
                child = group_item.child(child_index)
                if child is None:
                    continue

                visible = (
                    not query
                    or query in group_text
                    or query in child.text(0).lower()
                )
                child.setHidden(not visible)
                any_visible = any_visible or visible

            group_item.setHidden(not any_visible)

'''

    text = text[:start] + new_build + text[end:]
    path.write_text(text, encoding="utf-8")
    print("[PATCH] Action List direct three-column editor")


def patch_automation_builder() -> None:
    path = APP / "automation_builder_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        '        header.setStyleSheet("background-color: #1e293b; border-radius: 8px; padding: 12px;")\n',
        '        header.setProperty("panel", True)\n',
        1,
    )
    text = text.replace(
        '        title.setStyleSheet("font-size: 16px; color: #38bdf8;")\n',
        '        title.setProperty("heading", True)\n',
        1,
    )
    text = text.replace(
        '        safe_chip.setStyleSheet("color: #4ade80; font-weight: bold;")\n',
        '        safe_chip.setProperty("state", "success")\n',
        1,
    )
    text = text.replace(
        '            warn_box.setStyleSheet("background-color: #451a03; border-radius: 6px; padding: 8px;")\n',
        '            warn_box.setProperty("softPanel", True)\n',
        1,
    )
    text = text.replace(
        '            w_title.setStyleSheet("color: #fbbf24; font-weight: bold;")\n',
        '            w_title.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '                w_lbl.setStyleSheet("color: #fef08a;")\n',
        '                w_lbl.setProperty("muted", True)\n',
    )
    text = text.replace(
        '        self._lbl_metrics.setStyleSheet("color: #38bdf8; font-weight: bold;")\n',
        '        self._lbl_metrics.setProperty("sectionTitle", True)\n',
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Task Builder semantic theme")



def patch_analytics_workspace() -> None:
    path = APP / "analytics_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "        main_layout.setContentsMargins(16, 16, 16, 16)\n",
        "        main_layout.setContentsMargins(10, 10, 10, 10)\n",
        1,
    )
    text = text.replace(
        '        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ECEFF4;")\n',
        '        title_lbl.setProperty("sectionTitle", True)\n',
    )
    text = text.replace(
        '        self.lbl_insp_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #88C0D0;")\n',
        '        self.lbl_insp_title.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        self.lbl_insp_details.setStyleSheet("color: #D8DEE9; line-height: 1.4;")\n',
        '        self.lbl_insp_details.setProperty("muted", True)\n',
        1,
    )
    text = text.replace(
        '        self.lbl_device_insp_title.setStyleSheet(\n'
        '            "font-size: 13px; font-weight: bold; color: #A3BE8C;"\n'
        "        )\n",
        '        self.lbl_device_insp_title.setProperty("sectionTitle", True)\n',
        1,
    )
    text = text.replace(
        '        self.lbl_device_insp_details.setStyleSheet("color: #D8DEE9; line-height: 1.4;")\n',
        '        self.lbl_device_insp_details.setProperty("muted", True)\n',
        1,
    )

    text = text.replace(
        'PrimaryButton("🔄 Refresh Insights")',
        'PrimaryButton("Refresh Insights")',
    )
    text = text.replace(
        'SecondaryButton("📥 Export CSV")',
        'SecondaryButton("Export CSV")',
    )
    text = text.replace(
        'SecondaryButton("📄 Export JSON")',
        'SecondaryButton("Export JSON")',
    )
    text = text.replace(
        'PrimaryButton("🔄 Refresh Fleet")',
        'PrimaryButton("Refresh Fleet")',
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Analytics workspace")


def patch_settings_workspace() -> None:
    path = APP / "settings_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "        root.setContentsMargins(16, 16, 16, 16)\n",
        "        root.setContentsMargins(10, 10, 10, 10)\n",
        1,
    )
    text = text.replace(
        "        root.setSpacing(12)\n",
        "        root.setSpacing(8)\n",
        1,
    )
    text = text.replace(
        "        content_split.setSpacing(16)\n",
        "        content_split.setSpacing(10)\n",
        1,
    )
    text = text.replace(
        "        nav_panel.setFixedWidth(200)\n",
        "        nav_panel.setFixedWidth(190)\n",
        1,
    )
    text = text.replace(
        '        self.search.setPlaceholderText("🔍 Search settings by name or keyword...")\n',
        '        self.search.setPlaceholderText("Search settings...")\n',
        1,
    )
    text = text.replace(
        '        sec_title.setStyleSheet("font-size: 16px; font-weight: bold;")\n',
        '        sec_title.setProperty("heading", True)\n',
        1,
    )
    text = text.replace(
        "        panel_layout.setContentsMargins(16, 16, 16, 16)\n",
        "        panel_layout.setContentsMargins(14, 12, 14, 12)\n",
        1,
    )
    text = text.replace(
        "        panel_layout.setSpacing(16)\n",
        "        panel_layout.setSpacing(12)\n",
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Settings workspace")


def patch_operational_workspaces() -> None:
    path = APP / "operational_workspaces.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "        root.setContentsMargins(12, 12, 12, 12)\n",
        "        root.setContentsMargins(10, 10, 10, 10)\n",
    )
    text = text.replace(
        'self.tabs.addTab(self.post_analytics_view, "Social Post Performance")',
        'self.tabs.addTab(self.post_analytics_view, "Social Performance")',
        1,
    )
    text = text.replace(
        'self.tabs.addTab(infra_tab, "Device & Job System Metrics")',
        'self.tabs.addTab(infra_tab, "Device & Jobs")',
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Analytics shell")


def main() -> None:
    if not (APP / "main_window.py").exists():
        fail(
            "Run APPLY_FULL_REDESIGN_V7.py "
            "from the SP-Farms repository root."
        )

    touched = (
        "theme.py",
        "widgets.py",
        "home_dashboard.py",
        "workspaces.py",
        "main_window.py",
        "account_workspace.py",
        "asset_workspace.py",
        "content_workspace.py",
        "farm_reel_action_list.py",
        "automation_builder_workspace.py",
        "analytics_workspace.py",
        "settings_workspace.py",
        "operational_workspaces.py",
    )

    backup = backup_files(touched)
    print(f"[OK] Backup created: {backup}")

    (APP / "theme.py").write_text(THEME_PAYLOAD, encoding="utf-8")
    (APP / "widgets.py").write_text(WIDGETS_PAYLOAD, encoding="utf-8")
    (APP / "home_dashboard.py").write_text(HOME_PAYLOAD, encoding="utf-8")
    (APP / "workspaces.py").write_text(WORKSPACES_PAYLOAD, encoding="utf-8")

    print("[COPY] V7 theme/widgets/home/device rail")

    patch_main_window()
    patch_account_workspace()
    patch_asset_workspace()
    patch_content_workspace()
    patch_action_list()
    patch_automation_builder()
    patch_analytics_workspace()
    patch_settings_workspace()
    patch_operational_workspaces()

    print()
    print("SP-Farms Full Redesign V7 applied.")
    print()
    print("Visible structure:")
    print("  Home       -> monitoring only")
    print("  Accounts   -> table + two-row toolbar + inspector")
    print("  Pages      -> table + asset inspector")
    print("  Groups     -> table + asset inspector")
    print("  Content    -> Media / Captions / Drafts")
    print(
        "  Automation -> Action List / Task Builder / Campaigns / "
        "Schedule / Approvals / Queue"
    )
    print("  Devices    -> Device Manager / QA Profile Lab")
    print("  Analytics  -> existing analytics with V7 theme")
    print("  Settings   -> existing settings with V7 theme")
    print()
    print("Validate:")
    print(r"  .\.venv\Scripts\python.exe -m ruff check sp_farms")
    print(
        r"  .\.venv\Scripts\python.exe -m pytest "
        r"tests/test_design_system.py tests/test_main_window.py "
        r"tests/test_farm_reel_action_list.py -q"
    )
    print(r"  .\.venv\Scripts\python.exe -m sp_farms.app.main")
    print()
    print(f"Rollback backup: {backup}")


if __name__ == "__main__":
    main()
