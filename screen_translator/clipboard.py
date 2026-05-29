"""Monitor X11 PRIMARY selection (highlighted text) for changes."""

import logging
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

log = logging.getLogger(__name__)


class ClipboardMonitor:
    """Watches PRIMARY selection and fires callback when highlighted text changes."""

    def __init__(self, on_selection, delay_ms=600, min_length=2, max_length=5000):
        self._on_selection = on_selection
        self._delay_ms = delay_ms
        self._min_length = min_length
        self._max_length = max_length
        self._last_text = ""
        self._pending_id = None
        self._enabled = True

        self._primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        # Method 1: owner-change signal
        self._primary.connect("owner-change", self._on_owner_change)
        self._clipboard.connect("owner-change", self._on_owner_change)
        log.info("Clipboard: owner-change signals connected")

        # Method 2: polling fallback
        self._poll_interval_ms = 1000
        GLib.timeout_add(self._poll_interval_ms, self._poll_clipboard)
        log.info("Clipboard: polling fallback started (%dms)", self._poll_interval_ms)

    def set_enabled(self, enabled):
        self._enabled = enabled

    def _on_owner_change(self, clipboard, event):
        """Called when selection owner changes."""
        if not self._enabled:
            return
        log.debug("owner-change signal fired")
        if self._pending_id is not None:
            GLib.source_remove(self._pending_id)
            self._pending_id = None
        self._pending_id = GLib.timeout_add(self._delay_ms, self._read_selection)

    def _poll_clipboard(self):
        """Fallback: poll clipboards periodically."""
        if self._enabled:
            self._read_selection()
        return True  # Keep polling

    def _read_selection(self):
        """Read current selection text from primary or clipboard."""
        self._pending_id = None
        
        # Try primary first (highlighted text), then clipboard (copied text)
        text = self._primary.wait_for_text()
        if not text or not text.strip():
            text = self._clipboard.wait_for_text()

        if not text or not text.strip():
            if self._last_text:
                log.debug("Selection cleared")
                self._last_text = ""
                self._on_selection(None)
            return False

        text = text.strip()
        if text != self._last_text:
            if self._min_length <= len(text) <= self._max_length:
                log.info("New selection (%d chars): %.50s...", len(text), text)
                self._last_text = text
                self._on_selection(text)
            else:
                # Text changed but doesn't meet length requirements
                self._last_text = text
                self._on_selection(None)
                
        return False  # Don't repeat (for debounced calls)
