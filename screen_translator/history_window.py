"""Study history window for viewing, playing back, and managing saved translations."""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Pango
from screen_translator.speech import speak
from screen_translator.history import load_history, delete_entry, clear_history

CSS = b"""
#history-window {
    background-color: #1e1e2e;
}

#history-header-bar {
    background-color: #313244;
    padding: 10px;
    border-bottom: 1px solid #45475a;
}

#history-title {
    color: #cdd6f4;
    font-size: 16px;
    font-weight: bold;
}

#history-scrolled {
    background-color: #1e1e2e;
}

#history-list {
    background-color: #1e1e2e;
}

.history-row {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 12px;
    margin: 6px 12px;
}

.history-row:hover {
    background-color: #24273a;
    border-color: #45475a;
}

.history-meta {
    color: #a6adc8;
    font-size: 10px;
}

.history-original {
    color: #bac2de;
    font-size: 13px;
}

.history-translated {
    color: #a6e3a1;
    font-size: 15px;
    font-weight: bold;
}

.history-action-btn {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    min-width: 0;
    min-height: 0;
}

.history-action-btn:hover {
    background-color: #45475a;
}

.history-delete-btn {
    background-color: #313244;
    color: #f38ba8;
    border: none;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 11px;
    min-width: 0;
    min-height: 0;
}

.history-delete-btn:hover {
    background-color: #f38ba8;
    color: #1e1e2e;
}

#clear-all-btn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
}

#clear-all-btn:hover {
    background-color: #eba0ac;
}

#empty-label {
    color: #6c7086;
    font-size: 14px;
    font-style: italic;
}
"""


class HistoryWindow(Gtk.Window):
    """Study History Management Window."""

    def __init__(self):
        super().__init__(title="Study History")
        self.set_name("history-window")
        self.set_default_size(500, 600)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Style provider
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self._build_ui()
        self.load_items()

    def _build_ui(self):
        # Main layout container
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_vbox)

        # Custom header box
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_name("history-header-bar")
        main_vbox.pack_start(header_box, False, False, 0)

        title_lbl = Gtk.Label(label="📖 Study History List")
        title_lbl.set_name("history-title")
        title_lbl.set_alignment(0.0, 0.5)
        header_box.pack_start(title_lbl, True, True, 10)

        self._clear_btn = Gtk.Button(label="🗑️ Clear All")
        self._clear_btn.set_name("clear-all-btn")
        self._clear_btn.connect("clicked", self._on_clear_all)
        header_box.pack_end(self._clear_btn, False, False, 10)

        # Scrolled container for history list
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_name("history-scrolled")
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_vbox.pack_start(self._scrolled, True, True, 0)

        # List box container
        self._list_box = Gtk.ListBox()
        self._list_box.set_name("history-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._scrolled.add(self._list_box)

        # Empty state label
        self._empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._empty_box.set_center_widget(Gtk.Label(
            label="Your study list is currently empty.\nSave translations to review them here!",
            name="empty-label",
            justify=Gtk.Justification.CENTER
        ))
        main_vbox.pack_start(self._empty_box, False, False, 100)

        self.show_all()

    def load_items(self):
        # Clear existing rows
        for child in self._list_box.get_children():
            self._list_box.remove(child)

        history = load_history()

        if not history:
            self._scrolled.hide()
            self._empty_box.show_all()
            self._clear_btn.set_sensitive(False)
            return

        self._empty_box.hide()
        self._scrolled.show_all()
        self._clear_btn.set_sensitive(True)

        for item in history:
            row_box = self._create_row(item)
            self._list_box.add(row_box)

        self._list_box.show_all()

    def _create_row(self, item):
        row_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        row_outer.get_style_context().add_class("history-row")

        # Top row: Meta and Delete button
        top_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row_outer.pack_start(top_hbox, False, False, 0)

        meta_lbl = Gtk.Label(label=f"[{item['timestamp']}]  {item['source'].upper()} → {item['target'].upper()}")
        meta_lbl.get_style_context().add_class("history-meta")
        top_hbox.pack_start(meta_lbl, False, False, 0)

        del_btn = Gtk.Button(label="🗑️")
        del_btn.get_style_context().add_class("history-delete-btn")
        del_btn.set_tooltip_text("Delete from history")
        del_btn.connect("clicked", self._on_delete, item["id"])
        top_hbox.pack_end(del_btn, False, False, 0)

        # Middle row: Original Text & Speech
        orig_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        orig_hbox.set_margin_top(6)
        row_outer.pack_start(orig_hbox, False, False, 0)

        orig_lbl = Gtk.Label(label=item["original"])
        orig_lbl.get_style_context().add_class("history-original")
        orig_lbl.set_halign(Gtk.Align.START)
        orig_lbl.set_line_wrap(True)
        orig_lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        orig_lbl.set_selectable(True)
        orig_hbox.pack_start(orig_lbl, True, True, 0)

        orig_speech_btn = Gtk.Button(label="🔊 Original")
        orig_speech_btn.get_style_context().add_class("history-action-btn")
        orig_speech_btn.set_valign(Gtk.Align.START)
        orig_speech_btn.connect("clicked", lambda _: speak(item["original"], item["source"]))
        orig_hbox.pack_end(orig_speech_btn, False, False, 5)

        # Bottom row: Translated Text & Speech
        trans_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        trans_hbox.set_margin_top(4)
        row_outer.pack_start(trans_hbox, False, False, 0)

        trans_lbl = Gtk.Label(label=item["translated"])
        trans_lbl.get_style_context().add_class("history-translated")
        trans_lbl.set_halign(Gtk.Align.START)
        trans_lbl.set_line_wrap(True)
        trans_lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        trans_lbl.set_selectable(True)
        trans_hbox.pack_start(trans_lbl, True, True, 0)

        trans_speech_btn = Gtk.Button(label="🔊 Translation")
        trans_speech_btn.get_style_context().add_class("history-action-btn")
        trans_speech_btn.set_valign(Gtk.Align.START)
        trans_speech_btn.connect("clicked", lambda _: speak(item["translated"], item["target"]))
        trans_hbox.pack_end(trans_speech_btn, False, False, 5)

        return row_outer

    def _on_delete(self, button, entry_id):
        if delete_entry(entry_id):
            self.load_items()

    def _on_clear_all(self, button):
        # Standard GTK confirmation dialog
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Clear Study History",
        )
        dialog.format_secondary_text("Are you sure you want to clear your entire study list?")
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            if clear_history():
                self.load_items()


def show_history_window():
    """Create and display the history window."""
    win = HistoryWindow()
    win.show_all()
    # Ensure it stays open even if launched from separate event
    return win
