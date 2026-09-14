from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ColumnPickerDialog(QDialog):
    columns_changed = Signal(tuple)

    def __init__(
        self,
        columns: Sequence[tuple[str, str, bool]],
        visible_indices: set[int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Customize Table Columns")
        self.resize(380, 520)
        self.setObjectName("columnPickerDialog")
        self._columns = tuple(columns)
        self._checkboxes: list[QCheckBox] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter columns...")
        self.search_input.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_input)

        button_bar = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.reset_default_btn = QPushButton("Reset Defaults")
        self.reset_default_btn.clicked.connect(self.reset_defaults)
        button_bar.addWidget(self.select_all_btn)
        button_bar.addWidget(self.deselect_all_btn)
        button_bar.addWidget(self.reset_default_btn)
        layout.addLayout(button_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.checkbox_layout = QVBoxLayout(container)
        self.checkbox_layout.setSpacing(6)
        self.checkbox_layout.setContentsMargins(6, 6, 6, 6)

        for index, (_key, label, _default_vis) in enumerate(self._columns):
            cb = QCheckBox(label)
            cb.setProperty("col_index", index)
            cb.setChecked(index in visible_indices)
            self._checkboxes.append(cb)
            self.checkbox_layout.addWidget(cb)

        self.checkbox_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _filter_list(self, query: str) -> None:
        q = query.strip().casefold()
        for cb in self._checkboxes:
            cb.setVisible(not q or q in cb.text().casefold())

    def select_all(self) -> None:
        for cb in self._checkboxes:
            cb.setChecked(True)

    def deselect_all(self) -> None:
        for index, cb in enumerate(self._checkboxes):
            if index == 0:
                cb.setChecked(True)  # Always keep Account/Name visible
            else:
                cb.setChecked(False)

    def reset_defaults(self) -> None:
        for index, (_key, _label, default_vis) in enumerate(self._columns):
            self._checkboxes[index].setChecked(default_vis)

    @property
    def selected_column_indices(self) -> set[int]:
        res: set[int] = set()
        for index, cb in enumerate(self._checkboxes):
            if cb.isChecked() or index == 0:
                res.add(index)
        return res


class BulkCategoryDialog(QDialog):
    def __init__(
        self,
        categories: Sequence[tuple[str, str]],
        selected_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Category")
        self.resize(360, 180)
        self.setObjectName("bulkCategoryDialog")

        from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        count_label = QLabel(f"{selected_count} accounts selected")
        count_label.setStyleSheet("font-weight: bold;")
        form.addRow("Target:", count_label)

        self.category_combo = QComboBox()
        self.category_combo.addItem("— None (Clear Category) —", None)
        for cat_id, name in categories:
            self.category_combo.addItem(name, cat_id)
        form.addRow("Category:", self.category_combo)
        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def selected_category_id(self) -> str | None:
        data = self.category_combo.currentData()
        return str(data) if data is not None else None


class BulkTagDialog(QDialog):
    def __init__(
        self,
        tags: Sequence[tuple[str, str]],
        selected_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Tags")
        self.resize(360, 320)
        self.setObjectName("bulkTagDialog")

        from PySide6.QtWidgets import QLabel

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(f"Set tags for {selected_count} selected accounts:")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        cb_layout = QVBoxLayout(container)
        cb_layout.setSpacing(6)

        self._tag_checkboxes: list[QCheckBox] = []
        for tag_id, tag_name in tags:
            cb = QCheckBox(tag_name)
            cb.setProperty("tag_id", tag_id)
            self._tag_checkboxes.append(cb)
            cb_layout.addWidget(cb)

        cb_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def selected_tag_ids(self) -> tuple[str, ...]:
        return tuple(
            str(cb.property("tag_id"))
            for cb in self._tag_checkboxes
            if cb.isChecked() and cb.property("tag_id") is not None
        )
