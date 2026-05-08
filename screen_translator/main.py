"""Main entry point for Screen Translator."""

import signal
import logging
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from screen_translator import config, autostart
from screen_translator.clipboard import ClipboardMonitor
from screen_translator.popup import TranslationPopup
from screen_translator.tray import TrayIcon
from screen_translator.translator import translate_async

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


class ScreenTranslator:
    """Main application controller."""

    def __init__(self):
        self._config = config.load()
        log.info("Config loaded: target=%s, auto=%s",
                 self._config["target_language"],
                 self._config["auto_translate"])

        self._popup = TranslationPopup()
        self._tray = TrayIcon(
            self._config,
            on_toggle_auto=self._on_toggle_auto,
            on_toggle_autostart=self._on_toggle_autostart,
            on_change_target=self._on_change_target,
            on_quit=self._quit,
        )
        self._clipboard = ClipboardMonitor(self._on_text_selected)
        self._translator_thread = None
        log.info("Screen Translator started. Waiting for text selections...")

    def _on_text_selected(self, text):
        """Called when user highlights text."""
        if text is None:
            GLib.idle_add(self._popup.dismiss)
            return

        if not self._config.get("auto_translate", True):
            return

        log.info("Translating: %.60s...", text)
        # Show loading popup
        GLib.idle_add(self._popup.show_loading)

        # Translate in background
        target = self._config.get("target_language", "vi")
        translate_async(
            text,
            target_lang=target,
            callback=self._on_translation_done,
        )

    def _on_translation_done(self, result):
        """Called from background thread when translation completes."""
        if result and result.get("error"):
            log.error("Translation error: %s", result["error"])
        elif result:
            log.info("Translated: %.60s...", result.get("translated", ""))

        def _show():
            self._popup.show_result(result)
            timeout = self._config.get("popup_timeout", 8)
            self._popup.set_auto_dismiss(timeout)
        GLib.idle_add(_show)

    def _on_toggle_autostart(self, enabled):
        """Called when user toggles 'Start at Login' in tray."""
        autostart.set_enabled(enabled)

    def _on_toggle_auto(self, enabled):
        self._config["auto_translate"] = enabled
        self._clipboard.set_enabled(enabled)
        config.save(self._config)
        log.info("Auto-translate: %s", enabled)
        if not enabled:
            self._popup.dismiss()

    def _on_change_target(self, lang_code):
        self._config["target_language"] = lang_code
        config.save(self._config)
        log.info("Target language: %s", lang_code)

    def _quit(self):
        log.info("Quitting")
        Gtk.main_quit()

    def run(self):
        Gtk.main()


def main():
    # Allow Ctrl+C to work
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)

    app = ScreenTranslator()
    app.run()


if __name__ == "__main__":
    main()
