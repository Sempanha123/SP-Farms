import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QTableView

from sp_farms.app.design_preview import DesignPreview
from sp_farms.app.theme import DARK_PALETTE, LIGHT_PALETTE, ThemeMode, style_sheet
from sp_farms.app.widgets import CompactTable, EmptyState, PrimaryButton, StatusChip


def application() -> QApplication:
    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        return instance
    return QApplication([])


def test_theme_contains_semantic_tokens_and_focus_states() -> None:
    sheet = style_sheet(ThemeMode.DARK)

    assert DARK_PALETTE.accent in sheet
    assert DARK_PALETTE.danger in sheet
    assert "QPushButton:focus" in sheet
    assert "selection-background-color" in sheet
    assert style_sheet(ThemeMode.LIGHT) != sheet
    assert LIGHT_PALETTE.window in style_sheet(ThemeMode.LIGHT)


def test_reusable_components_have_compact_semantics() -> None:
    application()
    primary = PrimaryButton("Run")
    chip = StatusChip("Online", "success", ThemeMode.DARK)
    table = CompactTable()
    empty = EmptyState("Nothing here", "Choose a source", "Browse")

    assert primary.property("primary") is True
    assert DARK_PALETTE.success in chip.styleSheet()
    assert isinstance(table, QTableView)
    assert table.verticalHeader().defaultSectionSize() == 34
    assert empty.property("panel") is True


def test_preview_renders_both_themes_offscreen() -> None:
    application()
    for mode in ThemeMode:
        preview = DesignPreview(mode)
        preview.show()
        QApplication.processEvents()
        assert preview.isVisible()
        assert preview.findChild(QLineEdit) is not None
        assert preview.findChildren(PrimaryButton)
        image = preview.grab().toImage()
        assert not image.isNull()
        preview.close()
