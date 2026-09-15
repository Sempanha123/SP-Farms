"""Unit tests for Phase 56: Visual Reference Fidelity and Theme Lock."""

from sp_farms.app.theme import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    ThemeMode,
    ThemePalette,
    palette,
    style_sheet,
)


def test_theme_palettes_completeness():
    for mode, pal in [(ThemeMode.LIGHT, LIGHT_PALETTE), (ThemeMode.DARK, DARK_PALETTE)]:
        assert pal.window.startswith("#")
        assert pal.surface.startswith("#")
        assert pal.surface_alt.startswith("#")
        assert pal.border.startswith("#")
        assert pal.text.startswith("#")
        assert pal.accent.startswith("#")
        assert pal.success.startswith("#")
        assert pal.warning.startswith("#")
        assert pal.danger.startswith("#")


def test_dark_palette_reference_fidelity():
    # Lock brand and reference colors
    assert DARK_PALETTE.window == "#0D1113"
    assert DARK_PALETTE.surface == "#121719"
    assert DARK_PALETTE.surface_alt == "#181E21"
    assert DARK_PALETTE.border == "#343C40"
    assert DARK_PALETTE.accent == "#F4C915"
    assert DARK_PALETTE.success == "#25D06F"


def test_style_sheet_generation_and_selectors():
    dark_css = style_sheet(ThemeMode.DARK)
    assert "#0D1113" in dark_css
    assert "#F4C915" in dark_css
    assert "QWidget#topNavigation" in dark_css
    assert "QFrame#deviceRail" in dark_css
    assert "QFrame#accountActions" in dark_css
    assert "QTableView" in dark_css
    assert "QHeaderView::section" in dark_css
    assert "QLabel[chip=\"true\"]" in dark_css


def test_palette_lookup():
    assert palette(ThemeMode.LIGHT) == LIGHT_PALETTE
    assert palette(ThemeMode.DARK) == DARK_PALETTE
