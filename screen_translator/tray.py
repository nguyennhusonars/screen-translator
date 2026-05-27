"""System tray icon using AppIndicator3."""

import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

from gi.repository import Gtk
from screen_translator import __version__
from screen_translator.translator import get_supported_languages


# Common languages shown at top of menu
COMMON_LANGS = [
    ("Vietnamese", "vi"),
    ("English", "en"),
    ("Chinese (Simplified)", "zh-CN"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("French", "fr"),
    ("German", "de"),
    ("Spanish", "es"),
    ("Russian", "ru"),
    ("Thai", "th"),
]


class TrayIcon:
    """System tray icon with settings menu."""

    def __init__(self, config, on_toggle_auto, on_toggle_autostart, on_change_source, on_change_target, on_quit):
        """
        Args:
            config: current config dict
            on_toggle_auto: callable(enabled: bool)
            on_toggle_autostart: callable(enabled: bool)
            on_change_source: callable(lang_code: str)
            on_change_target: callable(lang_code: str)
            on_quit: callable()
        """
        self._config = config
        self._on_toggle_auto = on_toggle_auto
        self._on_toggle_autostart = on_toggle_autostart
        self._on_change_source = on_change_source
        self._on_change_target = on_change_target
        self._on_quit = on_quit

        self._indicator = AppIndicator3.Indicator.new(
            "screen-translator",
            "preferences-desktop-locale",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_title("Screen Translator")

        self._build_menu()

    def _create_lang_menu(self, current_code, on_change_callback, include_auto=False):
        submenu = Gtk.Menu()
        group = None

        if include_auto:
            item = Gtk.RadioMenuItem.new_with_label([], "Auto Detect (auto)")
            group = item
            if current_code == "auto":
                item.set_active(True)
            item.connect("toggled", lambda w: w.get_active() and on_change_callback("auto"))
            submenu.append(item)

        # Common languages
        for name, code in COMMON_LANGS:
            item = Gtk.RadioMenuItem.new_with_label([], f"{name} ({code})")
            if group:
                item.join_group(group)
            else:
                group = item
            if code == current_code:
                item.set_active(True)
            item.connect("toggled", lambda w, c=code: w.get_active() and on_change_callback(c))
            submenu.append(item)

        submenu.append(Gtk.SeparatorMenuItem())

        # All other languages
        all_langs = get_supported_languages()
        common_codes = {c for _, c in COMMON_LANGS}
        for name, code in sorted(all_langs.items()):
            if code in common_codes:
                continue
            item = Gtk.RadioMenuItem.new_with_label([], f"{name} ({code})")
            item.join_group(group)
            if code == current_code:
                item.set_active(True)
            item.connect("toggled", lambda w, c=code: w.get_active() and on_change_callback(c))
            submenu.append(item)

        return submenu

    def _build_menu(self):
        menu = Gtk.Menu()

        # Title
        title = Gtk.MenuItem(label=f"Screen Translator v{__version__}")
        title.set_sensitive(False)
        menu.append(title)
        menu.append(Gtk.SeparatorMenuItem())

        # Quick Translate window
        qt_item = Gtk.MenuItem(label="⚡ Quick Translate")
        qt_item.connect("activate", lambda _: self._on_quick_translate())
        menu.append(qt_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Auto-translate toggle
        self._auto_item = Gtk.CheckMenuItem(label="Auto-translate selections")
        self._auto_item.set_active(self._config.get("auto_translate", True))
        self._auto_item.connect("toggled", self._on_auto_toggled)
        menu.append(self._auto_item)

        # Autostart toggle
        from screen_translator import autostart
        self._autostart_item = Gtk.CheckMenuItem(label="Start at Login")
        self._autostart_item.set_active(autostart.is_enabled())
        self._autostart_item.connect("toggled", self._on_autostart_toggled)
        menu.append(self._autostart_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Source language submenu
        src_item = Gtk.MenuItem(label="Source Language")
        src_submenu = self._create_lang_menu(
            current_code=self._config.get("source_language", "auto"),
            on_change_callback=self._on_change_source,
            include_auto=True
        )
        src_item.set_submenu(src_submenu)
        menu.append(src_item)

        # Target language submenu
        tgt_item = Gtk.MenuItem(label="Target Language")
        tgt_submenu = self._create_lang_menu(
            current_code=self._config.get("target_language", "vi"),
            on_change_callback=self._on_change_target,
            include_auto=False
        )
        tgt_item.set_submenu(tgt_submenu)
        menu.append(tgt_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Study History
        history_item = Gtk.MenuItem(label="📖 View Study History")
        history_item.connect("activate", lambda _: self._on_view_history())
        menu.append(history_item)

        clear_history_item = Gtk.MenuItem(label="🗑️ Clear Study History")
        clear_history_item.connect("activate", lambda _: self._on_clear_history())
        menu.append(clear_history_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _: self._on_quit())
        menu.append(quit_item)

        menu.show_all()
        self._indicator.set_menu(menu)

    def _on_auto_toggled(self, item):
        self._on_toggle_auto(item.get_active())

    def _on_autostart_toggled(self, item):
        self._on_toggle_autostart(item.get_active())

    def _on_quick_translate(self):
        from screen_translator.quick_translate_window import QuickTranslateWindow
        if not hasattr(self, "_qt_win") or self._qt_win is None:
            self._qt_win = QuickTranslateWindow(self._config)
            self._qt_win.connect("destroy", lambda w: setattr(self, "_qt_win", None))
            self._qt_win.show_all()
        else:
            self._qt_win.present()

    def _on_view_history(self):
        from screen_translator.history_window import HistoryWindow
        if not hasattr(self, "_history_win") or self._history_win is None:
            self._history_win = HistoryWindow()
            self._history_win.connect("destroy", lambda w: setattr(self, "_history_win", None))
            # show_all() is already called inside HistoryWindow._build_ui()
        else:
            self._history_win.load_items()
            self._history_win.present()

    def _on_clear_history(self):
        from screen_translator.history import clear_history
        clear_history()
        if hasattr(self, "_history_win") and self._history_win is not None:
            self._history_win.load_items()

