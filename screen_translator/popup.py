"""Translation popup window that appears near the mouse cursor.

Designed to avoid perturbing the focus stack of other apps:
  - WindowTypeHint.NOTIFICATION (Mutter/GNOME treats it as system overlay)
  - accept_focus=False, focus_on_map=False, skip_taskbar, skip_pager
  - No present()/keep_above per show — widget tree is built once and reused
  - Outside-click handled via passive Gdk.Seat grab (no polling)
"""

import logging
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from screen_translator.speech import speak

log = logging.getLogger(__name__)

CSS = b"""
#translator-popup {
    background-color: #1e1e2e;
    border-radius: 12px;
    border: 1px solid #45475a;
    padding: 0;
}

#popup-header {
    background-color: #313244;
    border-radius: 12px 12px 0 0;
    padding: 6px 12px;
}

#header-label {
    color: #a6adc8;
    font-size: 11px;
    font-weight: bold;
}

#close-button {
    background: none;
    border: none;
    color: #6c7086;
    padding: 2px 6px;
    border-radius: 6px;
    min-width: 0;
    min-height: 0;
}

#close-button:hover {
    background-color: #45475a;
    color: #f38ba8;
}

#original-text {
    color: #bac2de;
    font-size: 12px;
    padding: 8px 14px 4px 14px;
}

#translated-text {
    color: #cdd6f4;
    font-size: 14px;
    font-weight: bold;
    padding: 4px 14px 10px 14px;
}

#error-text {
    color: #f38ba8;
    font-size: 12px;
    padding: 8px 14px;
}

#loading-text {
    color: #a6adc8;
    font-size: 12px;
    font-style: italic;
    padding: 12px 14px;
}

#copy-button, #save-button, #speech-button {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    min-width: 0;
    min-height: 0;
}

#copy-button { margin: 0 6px 0 0; }
#save-button { margin: 0; }
#speech-button { margin: 0 0 10px 5px; }

#copy-button:hover { background-color: #585b70; }
#save-button:hover { background-color: #a6e3a1; color: #1e1e2e; }
#speech-button:hover { background-color: #fab387; color: #1e1e2e; }
"""

_css_loaded = False


def _ensure_css():
    global _css_loaded
    if _css_loaded:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _css_loaded = True


class TranslationPopup(Gtk.Window):
    """Borderless popup showing translated text near the mouse cursor.

    Built once and reused across translations. Content swaps in place;
    the window is only mapped/unmapped via show()/hide() — never re-presented.
    """

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        _ensure_css()

        self.set_name("translator-popup")
        # NOTIFICATION hint: Mutter/GNOME treats this as a system overlay
        # that should not perturb focus or appear in the dock.
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(350, -1)
        self.set_size_request(200, -1)

        self._timeout_id = None
        self._original_text = ""
        self._translated_text = ""
        self._source_lang = "auto"
        self._target_lang = "en"

        self._build_widgets()

        # Click on the popup itself dismisses it.
        self.connect("button-press-event", lambda *_: self.dismiss())

    # ─── Widget tree (built once) ─────────────────────────────────────────────

    def _build_widgets(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_name("popup-header")
        self._header_label = Gtk.Label(label="Screen Translator")
        self._header_label.set_name("header-label")
        self._header_label.set_halign(Gtk.Align.START)
        header.pack_start(self._header_label, True, True, 0)

        close_btn = Gtk.Button(label="✕")
        close_btn.set_name("close-button")
        close_btn.connect("clicked", lambda _: self.dismiss())
        header.pack_end(close_btn, False, False, 0)
        outer.pack_start(header, False, False, 0)

        # Stack: loading | error | result
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.NONE)
        outer.pack_start(self._stack, True, True, 0)

        # Loading page
        loading = Gtk.Label(label="Translating...")
        loading.set_name("loading-text")
        loading.set_halign(Gtk.Align.START)
        self._stack.add_named(loading, "loading")

        # Error page
        self._error_label = Gtk.Label()
        self._error_label.set_name("error-text")
        self._error_label.set_halign(Gtk.Align.START)
        self._error_label.set_line_wrap(True)
        self._error_label.set_max_width_chars(45)
        self._stack.add_named(self._error_label, "error")

        # Result page
        result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        orig_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        orig_row.set_margin_start(14)
        orig_row.set_margin_end(14)
        orig_row.set_margin_top(8)
        orig_row.set_margin_bottom(4)
        self._orig_label = Gtk.Label()
        self._orig_label.set_name("original-text")
        self._orig_label.set_halign(Gtk.Align.START)
        self._orig_label.set_line_wrap(True)
        self._orig_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._orig_label.set_max_width_chars(40)
        self._orig_label.set_selectable(True)
        orig_row.pack_start(self._orig_label, True, True, 0)
        orig_speech = Gtk.Button(label="🔊")
        orig_speech.set_name("speech-button")
        orig_speech.set_tooltip_text("Listen to original")
        orig_speech.set_valign(Gtk.Align.START)
        orig_speech.connect("clicked", lambda _: speak(self._original_text, self._source_lang))
        orig_row.pack_start(orig_speech, False, False, 0)
        result_box.pack_start(orig_row, False, False, 0)

        trans_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        trans_row.set_margin_start(14)
        trans_row.set_margin_end(14)
        trans_row.set_margin_top(4)
        trans_row.set_margin_bottom(10)
        self._trans_label = Gtk.Label()
        self._trans_label.set_name("translated-text")
        self._trans_label.set_halign(Gtk.Align.START)
        self._trans_label.set_line_wrap(True)
        self._trans_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._trans_label.set_max_width_chars(40)
        self._trans_label.set_selectable(True)
        trans_row.pack_start(self._trans_label, True, True, 0)
        trans_speech = Gtk.Button(label="🔊")
        trans_speech.set_name("speech-button")
        trans_speech.set_tooltip_text("Listen to translation")
        trans_speech.set_valign(Gtk.Align.START)
        trans_speech.connect("clicked", lambda _: speak(self._translated_text, self._target_lang))
        trans_row.pack_start(trans_speech, False, False, 0)
        result_box.pack_start(trans_row, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        actions.set_margin_start(14)
        actions.set_margin_bottom(10)
        self._copy_btn = Gtk.Button(label="📋 Copy Translation")
        self._copy_btn.set_name("copy-button")
        self._copy_btn.connect("clicked", self._on_copy)
        actions.pack_start(self._copy_btn, False, False, 0)
        self._save_btn = Gtk.Button(label="💾 Save to Study")
        self._save_btn.set_name("save-button")
        self._save_btn.connect("clicked", self._on_save)
        actions.pack_start(self._save_btn, False, False, 0)
        result_box.pack_start(actions, False, False, 0)

        self._stack.add_named(result_box, "result")

        outer.show_all()

    # ─── Public API ───────────────────────────────────────────────────────────

    def show_loading(self):
        """Show loading state at the current mouse position."""
        self._header_label.set_text("Translating...")
        self._stack.set_visible_child_name("loading")
        self._copy_btn.set_label("📋 Copy Translation")
        self._save_btn.set_label("💾 Save to Study")
        self._save_btn.set_sensitive(True)
        self._show_at_cursor()

    def show_result(self, result):
        """Render a translation result (or error)."""
        if result is None:
            self.dismiss()
            return

        if result.get("error"):
            self._error_label.set_text(f"Error: {result['error']}")
            self._header_label.set_text("Translation Error")
            self._stack.set_visible_child_name("error")
            return

        self._original_text = result.get("original", "")
        self._translated_text = result.get("translated", "")
        self._source_lang = result.get("source", "auto")
        self._target_lang = result.get("target", "en")

        self._header_label.set_text(f"{self._source_lang} → {self._target_lang}")
        display_orig = self._original_text
        if len(display_orig) > 150:
            display_orig = display_orig[:147] + "..."
        self._orig_label.set_text(display_orig)
        self._trans_label.set_text(self._translated_text)
        self._copy_btn.set_label("📋 Copy Translation")
        self._save_btn.set_label("💾 Save to Study")
        self._save_btn.set_sensitive(True)
        self._stack.set_visible_child_name("result")

    def dismiss(self):
        """Hide the popup."""
        self._cancel_timeout()
        self.hide()

    def set_auto_dismiss(self, seconds):
        """Auto-dismiss after N seconds. 0 = never."""
        self._cancel_timeout()
        if seconds > 0:
            self._timeout_id = GLib.timeout_add_seconds(seconds, self._on_timeout)

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _cancel_timeout(self):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _on_timeout(self):
        self._timeout_id = None
        self.dismiss()
        return False

    def _on_copy(self, button):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self._translated_text, -1)
        button.set_label("✓ Copied")
        GLib.timeout_add(1500, lambda: button.set_label("📋 Copy Translation") or False)

    def _on_save(self, button):
        from screen_translator.history import save_translation
        success = save_translation(
            self._original_text,
            self._translated_text,
            self._source_lang,
            self._target_lang,
        )
        if success:
            button.set_label("✓ Saved")
            button.set_sensitive(False)

    def _show_at_cursor(self):
        """Show or refresh popup near mouse cursor. No present()/raise."""
        if self.get_visible():
            # Already visible — just let the new content take effect.
            self.queue_resize()
            return

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        pointer = seat.get_pointer()
        _screen, mx, my = pointer.get_position()
        
        log.info("Popup placement: GDK display is %s, cursor at (%d, %d)", 
                 display.__class__.__name__, mx, my)

        monitor = display.get_monitor_at_point(mx, my) or display.get_primary_monitor()
        geom = monitor.get_geometry()
        log.info("Monitor geom: x=%d, y=%d, w=%d, h=%d", geom.x, geom.y, geom.width, geom.height)

        # Ensure GdkWindow is created (realized) so move() is processed by X11
        self.realize()

        # Calculate exact natural size of window contents before showing
        min_sz, nat_sz = self.get_preferred_size()
        pw = max(nat_sz.width, 350)
        ph = max(nat_sz.height, 120)
        log.info("Calculated window size: %dx%d", pw, ph)

        x = mx + 15
        y = my + 20
        if x + pw > geom.x + geom.width:
            x = mx - pw - 10
        if y + ph > geom.y + geom.height:
            y = my - ph - 10
        x = max(geom.x, x)
        y = max(geom.y, y)

        log.info("Moving window to: (%d, %d)", x, y)
        self.move(x, y)
        self.show_all()
