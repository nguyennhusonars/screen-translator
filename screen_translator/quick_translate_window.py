"""Quick Translate window - type text and get instant translations."""

import logging
import threading
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from screen_translator.speech import speak
from screen_translator.translator import translate, get_definitions
from screen_translator import config

log = logging.getLogger(__name__)

CSS = b"""
#quick-translate-window {
    background-color: #1e1e2e;
}

#qt-header {
    background-color: #313244;
    padding: 8px 14px;
    border-bottom: 1px solid #45475a;
}

#qt-title {
    color: #cdd6f4;
    font-size: 14px;
    font-weight: bold;
}

#qt-input-area {
    background-color: #1e1e2e;
    padding: 12px 14px 8px 14px;
}

#qt-entry {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    caret-color: #cba6f7;
}

#qt-entry:focus {
    border-color: #cba6f7;
}

#qt-lang-bar {
    background-color: #181825;
    padding: 6px 14px;
    border-bottom: 1px solid #313244;
}

#qt-lang-label {
    color: #6c7086;
    font-size: 11px;
}

#qt-result-box {
    background-color: #1e1e2e;
    padding: 10px 14px;
}

#qt-original-label {
    color: #a6adc8;
    font-size: 12px;
    font-style: italic;
}

#qt-translated-label {
    color: #a6e3a1;
    font-size: 16px;
    font-weight: bold;
}

#qt-detected-label {
    color: #6c7086;
    font-size: 10px;
}

#qt-loading-label {
    color: #6c7086;
    font-size: 13px;
    font-style: italic;
}

.qt-btn {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    min-width: 0;
    min-height: 0;
}

.qt-btn:hover {
    background-color: #45475a;
}

#qt-translate-btn {
    background-color: #cba6f7;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
}

#qt-translate-btn:hover {
    background-color: #b4befe;
}

#qt-save-btn {
    background-color: #45475a;
    color: #a6e3a1;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    min-width: 0;
    min-height: 0;
}

#qt-save-btn:hover {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

#qt-footer {
    padding: 8px 14px 12px 14px;
    border-top: 1px solid #313244;
}

#qt-defs-separator {
    color: #45475a;
    font-size: 10px;
    padding: 4px 0 2px 0;
}

.qt-pos-label {
    color: #cba6f7;
    font-size: 10px;
    font-weight: bold;
}

.qt-term-label {
    color: #89dceb;
    font-size: 12px;
}
"""

COMMON_LANGS = [
    ("Auto Detect", "auto"),
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


class QuickTranslateWindow(Gtk.Window):
    """A small, always-on-top window to type and instantly translate text."""

    def __init__(self, app_config):
        super().__init__(title="Quick Translate")
        self.set_name("quick-translate-window")
        self.set_default_size(420, 300)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.set_resizable(True)

        self._config = app_config
        self._current_result = None
        self._debounce_id = None

        # Apply CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self._build_ui()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        # ── Header ──────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_name("qt-header")
        root.pack_start(header, False, False, 0)

        title = Gtk.Label(label="⚡ Quick Translate")
        title.set_name("qt-title")
        header.pack_start(title, False, False, 0)

        # ── Language bar ─────────────────────────────────────────────────────
        lang_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lang_bar.set_name("qt-lang-bar")
        root.pack_start(lang_bar, False, False, 0)

        src_lbl = Gtk.Label(label="From:")
        src_lbl.set_name("qt-lang-label")
        lang_bar.pack_start(src_lbl, False, False, 0)

        self._src_combo = Gtk.ComboBoxText()
        for name, code in COMMON_LANGS:
            self._src_combo.append(code, name)
        src_code = self._config.get("source_language", "auto")
        self._src_combo.set_active_id(src_code)
        if self._src_combo.get_active_id() is None:
            self._src_combo.set_active_id("auto")
        lang_bar.pack_start(self._src_combo, False, False, 0)

        arrow = Gtk.Label(label="→")
        arrow.set_name("qt-lang-label")
        lang_bar.pack_start(arrow, False, False, 0)

        tgt_lbl = Gtk.Label(label="To:")
        tgt_lbl.set_name("qt-lang-label")
        lang_bar.pack_start(tgt_lbl, False, False, 0)

        self._tgt_combo = Gtk.ComboBoxText()
        for name, code in COMMON_LANGS:
            if code == "auto":
                continue
            self._tgt_combo.append(code, name)
        tgt_code = self._config.get("target_language", "vi")
        self._tgt_combo.set_active_id(tgt_code)
        if self._tgt_combo.get_active_id() is None:
            self._tgt_combo.set_active_id("vi")
        lang_bar.pack_start(self._tgt_combo, False, False, 0)

        # ── Input area ────────────────────────────────────────────────────────
        input_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_area.set_name("qt-input-area")
        root.pack_start(input_area, False, False, 0)

        self._entry = Gtk.Entry()
        self._entry.set_name("qt-entry")
        self._entry.set_placeholder_text("Type text to translate…")
        self._entry.connect("activate", self._on_translate_clicked)
        self._entry.connect("changed", self._on_entry_changed)
        input_area.pack_start(self._entry, True, True, 0)

        translate_btn = Gtk.Button(label="Translate")
        translate_btn.set_name("qt-translate-btn")
        translate_btn.connect("clicked", self._on_translate_clicked)
        input_area.pack_end(translate_btn, False, False, 0)

        # ── Result area ───────────────────────────────────────────────────────
        self._result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._result_box.set_name("qt-result-box")
        root.pack_start(self._result_box, True, True, 0)

        self._loading_lbl = Gtk.Label(label="")
        self._loading_lbl.set_name("qt-loading-label")
        self._loading_lbl.set_halign(Gtk.Align.START)
        self._result_box.pack_start(self._loading_lbl, False, False, 0)

        self._detected_lbl = Gtk.Label(label="")
        self._detected_lbl.set_name("qt-detected-label")
        self._detected_lbl.set_halign(Gtk.Align.START)
        self._result_box.pack_start(self._detected_lbl, False, False, 0)

        self._original_lbl = Gtk.Label(label="")
        self._original_lbl.set_name("qt-original-label")
        self._original_lbl.set_halign(Gtk.Align.START)
        self._original_lbl.set_line_wrap(True)
        self._original_lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._original_lbl.set_selectable(True)
        self._result_box.pack_start(self._original_lbl, False, False, 0)

        self._translated_lbl = Gtk.Label(label="")
        self._translated_lbl.set_name("qt-translated-label")
        self._translated_lbl.set_halign(Gtk.Align.START)
        self._translated_lbl.set_line_wrap(True)
        self._translated_lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._translated_lbl.set_selectable(True)
        self._result_box.pack_start(self._translated_lbl, False, False, 0)

        # ── Definitions box (shown only for short inputs) ─────────────────────
        self._defs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._result_box.pack_start(self._defs_box, False, False, 4)

        # ── Footer buttons ────────────────────────────────────────────────────
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_name("qt-footer")
        root.pack_end(footer, False, False, 0)

        speak_orig_btn = Gtk.Button(label="🔊 Original")
        speak_orig_btn.get_style_context().add_class("qt-btn")
        speak_orig_btn.connect("clicked", self._on_speak_original)
        footer.pack_start(speak_orig_btn, False, False, 0)

        speak_trans_btn = Gtk.Button(label="🔊 Translation")
        speak_trans_btn.get_style_context().add_class("qt-btn")
        speak_trans_btn.connect("clicked", self._on_speak_translated)
        footer.pack_start(speak_trans_btn, False, False, 0)

        self._save_btn = Gtk.Button(label="💾 Save to Study")
        self._save_btn.set_name("qt-save-btn")
        self._save_btn.connect("clicked", self._on_save)
        self._save_btn.set_sensitive(False)
        footer.pack_end(self._save_btn, False, False, 0)

        self.show_all()
        self._entry.grab_focus()

    def _on_entry_changed(self, entry):
        """Debounce: trigger translate 600ms after user stops typing."""
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
        text = entry.get_text().strip()
        if len(text) >= 2:
            self._debounce_id = GLib.timeout_add(600, self._debounce_translate)
        else:
            self._loading_lbl.set_text("")
            self._detected_lbl.set_text("")
            self._original_lbl.set_text("")
            self._translated_lbl.set_text("")
            self._current_result = None
            self._save_btn.set_sensitive(False)

    def _debounce_translate(self):
        self._debounce_id = None
        self._do_translate()
        return False  # Don't repeat

    def _on_translate_clicked(self, *_):
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = None
        self._do_translate()

    def _do_translate(self):
        text = self._entry.get_text().strip()
        if not text:
            return

        src = self._src_combo.get_active_id() or "auto"
        tgt = self._tgt_combo.get_active_id() or "vi"
        fetch_defs = len(text) <= 40 and " " not in text.strip() or text.strip().count(" ") <= 2

        GLib.idle_add(self._set_loading)

        def _work():
            result = translate(text, target_lang=tgt, source_lang=src)
            defs = get_definitions(text, target_lang=tgt, source_lang=src) if fetch_defs else []
            GLib.idle_add(self._show_result, result)
            GLib.idle_add(self._show_definitions, defs)

        threading.Thread(target=_work, daemon=True).start()

    def _set_loading(self):
        self._loading_lbl.set_text("Translating…")
        self._original_lbl.set_text("")
        self._detected_lbl.set_text("")
        self._translated_lbl.set_text("")
        self._current_result = None
        self._save_btn.set_sensitive(False)
        for c in self._defs_box.get_children():
            self._defs_box.remove(c)

    def _show_result(self, result):
        self._loading_lbl.set_text("")
        if not result or result.get("error"):
            err = result.get("error", "Unknown error") if result else "No result"
            self._translated_lbl.set_text(f"Error: {err}")
            return

        self._current_result = result
        src = result.get("source", "")
        tgt = result.get("target", "")
        self._detected_lbl.set_text(f"Detected: {src.upper()} → {tgt.upper()}")
        self._original_lbl.set_text(result.get("original", ""))
        self._translated_lbl.set_text(result.get("translated", ""))
        self._save_btn.set_sensitive(True)
        self._save_btn.set_label("💾 Save to Study")

    def _show_definitions(self, defs):
        """Render dictionary definitions grouped by part of speech."""
        for c in self._defs_box.get_children():
            self._defs_box.remove(c)

        if not defs:
            return

        sep = Gtk.Label(label="── Other meanings ──")
        sep.set_name("qt-defs-separator")
        sep.set_halign(Gtk.Align.START)
        self._defs_box.pack_start(sep, False, False, 0)

        for group in defs:
            pos = group["pos"]
            terms = group["terms"]

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            pos_lbl = Gtk.Label(label=f"{pos}:")
            pos_lbl.get_style_context().add_class("qt-pos-label")
            pos_lbl.set_halign(Gtk.Align.START)
            pos_lbl.set_width_chars(10)
            row.pack_start(pos_lbl, False, False, 0)

            terms_lbl = Gtk.Label(label=",  ".join(terms))
            terms_lbl.get_style_context().add_class("qt-term-label")
            terms_lbl.set_halign(Gtk.Align.START)
            terms_lbl.set_line_wrap(True)
            terms_lbl.set_selectable(True)
            row.pack_start(terms_lbl, True, True, 0)

            self._defs_box.pack_start(row, False, False, 0)

        self._defs_box.show_all()

    def _on_speak_original(self, *_):
        if self._current_result:
            speak(self._current_result["original"], self._current_result.get("source", "en"))

    def _on_speak_translated(self, *_):
        if self._current_result:
            speak(self._current_result["translated"], self._current_result.get("target", "en"))

    def _on_save(self, button):
        if not self._current_result:
            return
        from screen_translator.history import save_translation
        r = self._current_result
        ok = save_translation(r["original"], r["translated"], r.get("source", ""), r.get("target", ""))
        if ok:
            button.set_label("✓ Saved")
            button.set_sensitive(False)
