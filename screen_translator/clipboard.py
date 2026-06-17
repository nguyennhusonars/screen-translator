"""Monitor clipboard/selection changes and fire callback on new text.

Uses purely passive GTK clipboard owner-change signals.
Since Screen Translator runs via GDK_BACKEND=x11 (XWayland), 
XWayland handles syncing the Wayland clipboard to GTK transparently!
No polling, no wl-paste, no performance penalties.
"""

import logging
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

log = logging.getLogger(__name__)

class ClipboardMonitor:
    """Watches PRIMARY selection and CLIPBOARD for changes, fires callback."""

    def __init__(self, on_selection, delay_ms=600, min_length=2, max_length=5000):
        self._on_selection = on_selection
        self._delay_ms = delay_ms
        self._min_length = min_length
        self._max_length = max_length
        self._enabled = True
        
        self._last_primary = ""
        self._last_clipboard = ""
        self._last_dispatched = ""

        self._pending_id = None

        log.info("Starting native GTK clipboard monitor via XWayland.")
        self._gtk_primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self._gtk_clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self._gtk_primary.connect("owner-change", self._on_owner_change)
        self._gtk_clipboard.connect("owner-change", self._on_owner_change)

    def set_enabled(self, enabled):
        self._enabled = enabled

    def stop(self):
        """Clean shutdown."""
        if self._pending_id is not None:
            GLib.source_remove(self._pending_id)
            self._pending_id = None

    def _on_owner_change(self, clipboard, event):
        """Fired by GTK when the clipboard contents change."""
        if not self._enabled:
            return
            
        if self._pending_id is not None:
            GLib.source_remove(self._pending_id)
            
        # Wait delay_ms to debounce active drag-selecting
        self._pending_id = GLib.timeout_add(self._delay_ms, self._read_selection)

    def _read_selection(self):
        self._pending_id = None
        
        primary_text = (self._gtk_primary.wait_for_text() or "").strip()
        clipboard_text = (self._gtk_clipboard.wait_for_text() or "").strip()

        if primary_text and primary_text != self._last_primary:
            self._last_primary = primary_text
            self._dispatch(primary_text)
            
        elif clipboard_text and clipboard_text != self._last_clipboard:
            self._last_clipboard = clipboard_text
            self._dispatch(clipboard_text)

        return False  # Don't repeat

    def _dispatch(self, text):
        if not self._enabled:
            return False
            
        if text == self._last_dispatched:
            log.debug("Duplicate selection ignored: %.40s...", text)
            return False
            
        self._last_dispatched = text
        
        if self._min_length <= len(text) <= self._max_length:
            log.info("New selection (%d chars): %.50s...", len(text), text)
            self._on_selection(text)
        else:
            log.debug("Selection ignored: length %d out of [%d, %d]",
                      len(text), self._min_length, self._max_length)
        return False
