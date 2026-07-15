"""Main entry point for Screen Translator."""

import os
import signal
import logging
# Force XWayland for window positioning (wl-paste handles clipboard natively)
os.environ["GDK_BACKEND"] = "x11"
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

        self._popup = None
        self._request_seq = 0   # increments per selection; stale callbacks dropped
        self._tray = TrayIcon(
            self._config,
            on_toggle_auto=self._on_toggle_auto,
            on_toggle_autostart=self._on_toggle_autostart,
            on_change_source=self._on_change_source,
            on_change_target=self._on_change_target,
            on_quit=self._quit,
        )
        self._clipboard = ClipboardMonitor(
            self._on_text_selected,
            delay_ms=self._config.get("selection_delay_ms", 600),
            min_length=self._config.get("min_text_length", 2),
            max_length=self._config.get("max_text_length", 5000),
        )
        log.info("Screen Translator started. Waiting for text selections...")

    def _ensure_popup(self):
        if self._popup is None:
            self._popup = TranslationPopup()
        return self._popup

    def _on_text_selected(self, text):
        """Called when user highlights text."""
        if text is None:
            if self._popup:
                GLib.idle_add(self._popup.dismiss)
            return

        if not self._config.get("auto_translate", True):
            return

        self._request_seq += 1
        seq = self._request_seq

        log.info("Translating [#%d]: %.60s...", seq, text)
        popup = self._ensure_popup()
        GLib.idle_add(popup.show_loading)

        source = self._config.get("source_language", "auto")
        target = self._config.get("target_language", "vi")
        translate_async(
            text,
            target_lang=target,
            callback=lambda result: self._on_translation_done(seq, result),
            source_lang=source,
        )

    def _on_translation_done(self, seq, result):
        """Called from background thread when translation completes."""
        if seq != self._request_seq:
            log.debug("Dropping stale translation [#%d] (current: #%d)", seq, self._request_seq)
            return

        if result and result.get("error"):
            log.error("Translation error: %s", result["error"])
        elif result:
            log.info("Translated [#%d]: %.60s...", seq, result.get("translated", ""))

        def _show():
            if seq != self._request_seq or self._popup is None:
                return False
            self._popup.show_result(result)
            timeout = self._config.get("popup_timeout", 8)
            self._popup.set_auto_dismiss(timeout)
            return False
        GLib.idle_add(_show)

    def _on_toggle_autostart(self, enabled):
        """Called when user toggles 'Start at Login' in tray."""
        autostart.set_enabled(enabled)

    def _on_toggle_auto(self, enabled):
        self._config["auto_translate"] = enabled
        self._clipboard.set_enabled(enabled)
        config.save(self._config)
        log.info("Auto-translate: %s", enabled)
        if not enabled and self._popup:
            self._popup.dismiss()

    def _on_change_source(self, lang_code):
        self._config["source_language"] = lang_code
        config.save(self._config)
        log.info("Source language: %s", lang_code)

    def _on_change_target(self, lang_code):
        self._config["target_language"] = lang_code
        config.save(self._config)
        log.info("Target language: %s", lang_code)

    def _quit(self):
        log.info("Quitting")
        if self._clipboard is not None:
            self._clipboard.stop()
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
