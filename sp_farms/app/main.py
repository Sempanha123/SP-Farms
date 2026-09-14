import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from sp_farms.app.main_window import MainWindow
from sp_farms.bootstrap import create_application


def main(argv: Sequence[str] | None = None) -> int:
    application = QApplication(list(argv) if argv is not None else sys.argv)
    context = create_application()
    window = MainWindow(context)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
