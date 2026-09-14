import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from sp_farms.app.main_window import MainWindow
from sp_farms.bootstrap import create_application


def _resolve_app_icon() -> QIcon | None:
    # Check bundled PyInstaller sys._MEIPASS or repository assets
    base_dir = getattr(sys, "_MEIPASS", None)
    candidates: list[Path] = []
    if base_dir:
        candidates.extend([
            Path(base_dir) / "assets" / "icons" / "sp_farms.ico",
            Path(base_dir) / "assets" / "icons" / "sp_farms.png",
        ])
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates.extend([
        repo_root / "assets" / "icons" / "sp_farms.ico",
        repo_root / "assets" / "icons" / "sp_farms.png",
    ])
    for candidate in candidates:
        if candidate.exists():
            return QIcon(str(candidate))
    return None


def main(argv: Sequence[str] | None = None) -> int:
    application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setApplicationName("SP-Farms")
    application.setOrganizationName("SP-Farms")
    icon = _resolve_app_icon()
    if icon is not None:
        application.setWindowIcon(icon)
    context = create_application()
    window = MainWindow(context)
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
