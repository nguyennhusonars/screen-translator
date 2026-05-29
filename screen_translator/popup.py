"""Translation popup window that appears near the mouse cursor."""

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

#copy-button {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    margin: 0 6px 0 0;
    font-size: 11px;
    min-width: 0;
    min-height: 0;
}

#copy-button:hover {
    background-color: #585b70;
}

#save-button {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    margin: 0;
    font-size: 11px;
    min-width: 0;
    min-height: 0;
}

#save-button:hover {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

#speech-button {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    margin: 0 0 10px 5px;
    font-size: 11px;
    min-width: 0;
    min-height: 0;
}

#speech-button:hover {
    background-color: #fab387;
    color: #1e1e2e;
}
"""


class TranslationPopup(Gtk.Window):
    """Borderless popup showing translated text near mouse cursor."""

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_name("translator-popup")
        self.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(350, -1)
        self.set_size_request(200, -1)

        self._timeout_id = None
        self._translated_text = ""
        self._monitor_id = None

        # Apply CSS
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Main container
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self._box)

        # Header bar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_name("popup-header")
        self._header_label = Gtk.Label(label="Translating...")
        self._header_label.set_name("header-label")
        self._header_label.set_halign(Gtk.Align.START)
        header.pack_start(self._header_label, True, True, 0)

        close_btn = Gtk.Button(label="✕")
        close_btn.set_name("close-button")
        close_btn.connect("clicked", lambda _: self.dismiss())
        header.pack_end(close_btn, False, False, 0)
        self._box.pack_start(header, False, False, 0)

        # Content area
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._box.pack_start(self._content, True, True, 0)

        # Click outside to dismiss (when clicking the popup itself)
        self.connect("button-press-event", lambda w, e: self.dismiss())

    def show_loading(self):
        """Show loading state at mouse position."""
        self._clear_content()
        lbl = Gtk.Label(label="Translating...")
        lbl.set_name("loading-text")
        lbl.set_halign(Gtk.Align.START)
        self._content.pack_start(lbl, False, False, 0)
        self._header_label.set_text("Screen Translator")
        self._position_and_show()

    def show_result(self, result):
        """Show translation result. Called from any thread via GLib.idle_add."""
        self._clear_content()

        if result is None:
            self.dismiss()
            return

        if result.get("error"):
            lbl = Gtk.Label(label=f"Error: {result['error']}")
            lbl.set_name("error-text")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_line_wrap(True)
            lbl.set_max_width_chars(45)
            self._content.pack_start(lbl, False, False, 0)
            self._header_label.set_text("Translation Error")
        else:
            src = result.get("source", "auto")
            tgt = result.get("target", "?")
            self._header_label.set_text(f"{src} → {tgt}")

            # Original text section
            orig_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            orig_hbox.set_margin_start(14)
            orig_hbox.set_margin_end(14)
            orig_hbox.set_margin_top(8)
            orig_hbox.set_margin_bottom(4)
            self._content.pack_start(orig_hbox, False, False, 0)

            orig = result["original"]
            self._original_text = orig
            self._source_lang = result.get("source", "auto")
            self._target_lang = result.get("target", "en")

            if len(orig) > 150:
                orig = orig[:147] + "..."
            orig_lbl = Gtk.Label(label=orig)
            orig_lbl.set_name("original-text")
            orig_lbl.set_halign(Gtk.Align.START)
            orig_lbl.set_line_wrap(True)
            orig_lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            orig_lbl.set_max_width_chars(40)
            orig_lbl.set_selectable(True)
            orig_hbox.pack_start(orig_lbl, True, True, 0)

            src_speech_btn = Gtk.Button(label="🔊")
            src_speech_btn.set_name("speech-button")
            src_speech_btn.set_tooltip_text("Listen to original")
            src_speech_btn.set_valign(Gtk.Align.START)
            src_speech_btn.connect("clicked", lambda _: speak(result["original"], result.get("source", "en")))
            orig_hbox.pack_start(src_speech_btn, False, False, 0)

            # Translated text section
            trans_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            trans_hbox.set_margin_start(14)
            trans_hbox.set_margin_end(14)
            trans_hbox.set_margin_top(4)
            trans_hbox.set_margin_bottom(10)
            self._content.pack_start(trans_hbox, False, False, 0)

            self._translated_text = result.get("translated", "")
            trans_lbl = Gtk.Label(label=self._translated_text)
            trans_lbl.set_name("translated-text")
            trans_lbl.set_halign(Gtk.Align.START)
            trans_lbl.set_line_wrap(True)
            trans_lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            trans_lbl.set_max_width_chars(40)
            trans_lbl.set_selectable(True)
            trans_hbox.pack_start(trans_lbl, True, True, 0)

            tgt_speech_btn = Gtk.Button(label="🔊")
            tgt_speech_btn.set_name("speech-button")
            tgt_speech_btn.set_tooltip_text("Listen to translation")
            tgt_speech_btn.set_valign(Gtk.Align.START)
            tgt_speech_btn.connect("clicked", lambda _: speak(self._translated_text, result.get("target", "en")))
            trans_hbox.pack_start(tgt_speech_btn, False, False, 0)

            # Footer Action buttons
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            actions.set_margin_start(14)
            actions.set_margin_bottom(10)
            self._content.pack_start(actions, False, False, 0)

            copy_btn = Gtk.Button(label="📋 Copy Translation")
            copy_btn.set_name("copy-button")
            copy_btn.connect("clicked", self._on_copy)
            actions.pack_start(copy_btn, False, False, 0)

            save_btn = Gtk.Button(label="💾 Save to Study")
            save_btn.set_name("save-button")
            save_btn.connect("clicked", self._on_save)
            actions.pack_start(save_btn, False, False, 0)

        self._position_and_show()

    def show_result_threadsafe(self, result):
        """Thread-safe wrapper to show result from background thread."""
        GLib.idle_add(self.show_result, result)

    def dismiss(self):
        """Hide the popup."""
        self._stop_monitor()
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        self.hide()

    def set_auto_dismiss(self, seconds):
        """Auto-dismiss after N seconds. 0 = never."""
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        if seconds > 0:
            self._timeout_id = GLib.timeout_add_seconds(seconds, self._auto_dismiss)

    def _auto_dismiss(self):
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
            self._target_lang
        )
        if success:
            button.set_label("✓ Saved")
            button.set_sensitive(False)

    def _clear_content(self):
        for child in self._content.get_children():
            self._content.remove(child)
            child.destroy()

    def _position_and_show(self):
        """Position popup near mouse cursor, keeping on screen."""
        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        pointer = seat.get_pointer()
        screen, mx, my = pointer.get_position()
        
        # Ensure window is on the correct screen
        self.set_screen(screen)

        monitor = display.get_monitor_at_point(mx, my)
        geom = monitor.get_geometry()

        # Realize to calculate size without showing it yet
        self.realize()
        _, natural = self.get_preferred_size()
        pw, ph = natural.width, natural.height

        # Position: below and right of cursor, shifted if off-screen
        x = mx + 15
        y = my + 20

        if x + pw > geom.x + geom.width:
            x = mx - pw - 10
        if y + ph > geom.y + geom.height:
            y = my - ph - 10

        x = max(geom.x, x)
        y = max(geom.y, y)

        self.move(x, y)
        
        # Force keep above for some compositors
        self.set_keep_above(True)
        self.present()
        self.show_all()

        self._start_monitor()

    def _start_monitor(self):
        if self._monitor_id is None:
            self._monitor_id = GLib.timeout_add(100, self._monitor_mouse)

    def _stop_monitor(self):
        if self._monitor_id is not None:
            GLib.source_remove(self._monitor_id)
            self._monitor_id = None

    def _monitor_mouse(self):
        """Check if mouse button is pressed outside the popup."""
        if not self.get_visible():
            self._monitor_id = None
            return False

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        pointer = seat.get_pointer()
        root = Gdk.get_default_root_window()

        # Check button state globally using the root window
        _, _, _, mask = root.get_device_position(pointer)
        
        if mask & Gdk.ModifierType.BUTTON1_MASK:
            # Check if pointer is outside our window
            x, y = self.get_position()
            w, h = self.get_size()
            _, mx, my = pointer.get_position()

            if not (x <= mx <= x + w and y <= my <= y + h):
                log.debug("Global click detected outside popup at %d, %d. Dismissing.", mx, my)
                self.dismiss()
                return False

        return True
