"""Application entry-point for the USM Analyzer desktop app."""

from __future__ import annotations

import signal
import sys
import traceback
from typing import NoReturn

from PyQt6.QtWidgets import QApplication, QMessageBox

from usm_analyzer.config import APP_NAME, APP_ORG, DEFAULT_CONFIG
from usm_analyzer.ui.main_window import MainWindow
from usm_analyzer.utils.logger import get_logger, setup_logging


def _install_global_exception_hook(logger_name: str) -> None:
    """Install exception hook to prevent silent crashes in production."""

    def handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_tb: object) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        get_logger(logger_name).critical("Unhandled exception:\n%s", formatted)

        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None,
                f"{APP_NAME} - Fatal Error",
                "An unexpected error occurred.\n\n"
                "The error has been logged to the application log file.\n"
                "Please restart the application.",
            )

    sys.excepthook = handle_exception


def _configure_application() -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setQuitOnLastWindowClosed(True)

    # Handle Ctrl+C gracefully when running from terminal.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app


def run() -> int:
    """Create and run the UI event loop."""

    logger = setup_logging(DEFAULT_CONFIG.logging)
    _install_global_exception_hook("main")
    app = _configure_application()

    window = MainWindow()
    window.show()

    logger.info("%s started successfully", APP_NAME)

    return app.exec()


def main() -> NoReturn:
    exit_code = run()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
