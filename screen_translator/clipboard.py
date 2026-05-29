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
        self._last_primary = ""
        self._last_clipboard = ""
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
        """Read current selection text from primary and clipboard."""
        self._pending_id = None
        
        # Read both buffers
        primary_text = self._primary.wait_for_text() or ""
        clipboard_text = self._clipboard.wait_for_text() or ""
        
        primary_text = primary_text.strip()
        clipboard_text = clipboard_text.strip()

        # Check which one actually changed compared to its own last state
        new_text = None
        
        if primary_text and primary_text != self._last_primary:
            new_text = primary_text
            self._last_primary = primary_text
        elif clipboard_text and clipboard_text != self._last_clipboard:
            new_text = clipboard_text
            self._last_clipboard = clipboard_text
            
        if not new_text:
            # If both are empty and we had something before
            if not primary_text and not clipboard_text and (self._last_primary or self._last_clipboard):
                log.debug("Selection cleared")
                self._last_primary = ""
                self._last_clipboard = ""
                self._on_selection(None)
            return False

        if self._min_length <= len(new_text) <= self._max_length:
            log.info("New selection (%d chars): %.50s...", len(new_text), new_text)
            self._on_selection(new_text)
        else:
            self._on_selection(None)

        return False  # Don't repeat (for debounced calls)
