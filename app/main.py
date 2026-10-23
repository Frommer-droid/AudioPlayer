"""Инициализация Qt, локализации и журналирования."""
import ctypes
import logging
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.settings import ROOT
from app.services.open_requests import launch_paths
from app.services.single_instance import SingleInstance


def main():
    if getattr(sys, "frozen", False):
        from app.services.windows_associations import repair_registered_verbs
        repair_registered_verbs()
    locale = QLocale(QLocale.Language.Russian, QLocale.Country.Russia)
    QLocale.setDefault(locale)
    app = QApplication(sys.argv)
    app.setApplicationName("AudioPlayer")
    instance = SingleInstance()
    try:
        try:
            paths = launch_paths(sys.argv[1:])
        except (OSError, ValueError) as error:
            raise RuntimeError(f"Не удалось прочитать выбранные файлы: {error}") from error
        if not instance.start_or_forward(paths):
            return 0
        return _run_primary(app, instance, locale)
    except RuntimeError as error:
        QMessageBox.critical(None, "AudioPlayer", str(error))
        return 1
    finally:
        instance.close()


def _run_primary(app, instance, locale):
    # Secondary launches only need Qt IPC, not audio services or another window.
    from app.ui.application_icon import application_icon
    from app.ui.main_window import PlayerWindow
    from app.ui.theme import apply_theme

    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(filename=log_dir / "app.log", filemode="w", encoding="utf-8", level=logging.INFO)
    logging.info("Интерпретатор: %s", sys.executable)
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("frommer.audioplayer.desktop.1")
    app.setWindowIcon(application_icon())
    translator = QTranslator(app)
    if translator.load(locale, "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    apply_theme(app)

    def on_exception(kind, value, traceback):
        logging.error("Ошибка приложения", exc_info=(kind, value, traceback))
        QMessageBox.critical(None, "AudioPlayer", f"Ошибка: {value}\nПодробности записаны в logs/app.log.")

    sys.excepthook = on_exception
    window = PlayerWindow()
    def receive(paths):
        logging.info("Запрос открытия: %d файлов", len(paths))
        if paths:
            window.open_paths(paths)
            logging.info("В активной очереди: %d файлов", len(window.playlist.paths))
        window._restore_from_tray()

    instance.set_handler(receive)
    app.aboutToQuit.connect(instance.close)
    window.show()
    return app.exec()
