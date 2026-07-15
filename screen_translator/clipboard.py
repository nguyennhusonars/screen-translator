"""Monitor clipboard/selection changes and fire callback on new text.

Hybrid approach:
- CLIPBOARD: Uses native GTK owner-change (XWayland syncs this perfectly).
- PRIMARY: Uses native GTK owner-change as a trigger, then runs wl-paste --primary
  once to read the text. No polling, no background threads, no lag!
"""

import os
import logging
import subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

log = logging.getLogger(__name__)

class ClipboardMonitor:
    def __init__(self, on_selection, delay_ms=600, min_length=2, max_length=5000):
        self._on_selection = on_selection
        self._settle_seconds = delay_ms / 1000.0
        self._min_length = min_length
        self._max_length = max_length
        self._enabled = True
        
        self._last_primary = ""
        self._last_clipboard = ""
        self._last_dispatched = ""

        self._pending_clipboard_id = None
        self._pending_primary_id = None

        log.info("Starting passive hybrid clipboard monitor (GTK owner-change triggers).")
        
        # 1. Native GTK for CLIPBOARD
        self._gtk_clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self._gtk_clipboard.connect("owner-change", self._on_clipboard_change)

        # 2. Native GTK for PRIMARY owner-change trigger
        self._gtk_primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self._gtk_primary.connect("owner-change", self._on_primary_change)

    def set_enabled(self, enabled):
        self._enabled = enabled

    def stop(self):
        if self._pending_clipboard_id is not None:
            GLib.source_remove(self._pending_clipboard_id)
            self._pending_clipboard_id = None
        if self._pending_primary_id is not None:
            GLib.source_remove(self._pending_primary_id)
            self._pending_primary_id = None

    # --- GTK CLIPBOARD ---
    def _on_clipboard_change(self, clipboard, event):
        if not self._enabled:
            return
        if self._pending_clipboard_id is not None:
            GLib.source_remove(self._pending_clipboard_id)
        self._pending_clipboard_id = GLib.timeout_add(
            int(self._settle_seconds * 1000), 
            self._read_gtk_clipboard
        )

    def _read_gtk_clipboard(self):
        self._pending_clipboard_id = None
        text = (self._gtk_clipboard.wait_for_text() or "").strip()
        if text and text != self._last_clipboard:
            self._last_clipboard = text
            self._dispatch(text)
        return False

    # --- PRIMARY owner-change trigger ---
    def _on_primary_change(self, clipboard, event):
        if not self._enabled:
            return
        if self._pending_primary_id is not None:
            GLib.source_remove(self._pending_primary_id)
        self._pending_primary_id = GLib.timeout_add(
            int(self._settle_seconds * 1000), 
            self._read_wl_primary
        )

    def _wl_paste_primary(self):
        try:
            result = subprocess.run(
                ["wl-paste", "--primary", "--no-newline"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace").strip()
        except Exception:
            pass
        return ""

    def _read_wl_primary(self):
        self._pending_primary_id = None
        text = self._wl_paste_primary()
        if text and text != self._last_primary:
            self._last_primary = text
            self._dispatch(text)
        return False

    # --- DISPATCH ---
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
        return False
