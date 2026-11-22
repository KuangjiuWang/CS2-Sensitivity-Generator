"""Desktop entry point. Configure native display handling before initializing Qt."""
import sys

from core.platform_input import enable_high_dpi


def main() -> int:
    enable_high_dpi()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow, STYLESHEET

    app = QApplication([sys.argv[0]])
    app.setApplicationName("CS2 Sensitivity Generator")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    if "--smoke-test" in sys.argv:
        if sys.platform == "darwin":
            from core.platform_input import RawMouseInput
            RawMouseInput(lambda dx, dy: None)
        QTimer.singleShot(300, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
