"""Monitor clipboard/selection changes and fire callback on new text.

On Wayland: polls `wl-paste` (PRIMARY and CLIPBOARD) every 500 ms in background threads.
On X11:     uses GTK Clipboard owner-change signals + 1 s polling fallback.

Requires: wl-clipboard  (sudo apt install wl-clipboard)  on Wayland sessions.
"""

import os
import logging
import subprocess
import threading
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

log = logging.getLogger(__name__)


def _is_wayland():
    return bool(os.environ.get("WAYLAND_DISPLAY"))


class ClipboardMonitor:
    """Watches PRIMARY selection and CLIPBOARD for changes, fires callback."""

    def __init__(self, on_selection, delay_ms=600, min_length=2, max_length=5000):
        self._on_selection = on_selection
        self._settle_seconds = delay_ms / 1000.0
        self._min_length = min_length
        self._max_length = max_length
        self._enabled = True
        self._last_primary = ""
        self._last_clipboard = ""
        self._last_dispatched = ""   # dedup: don't fire same text twice
        self._stop_event = threading.Event()
        self._threads = []

        if _is_wayland():
            self._start_wayland()
        else:
            self._start_x11()

    def set_enabled(self, enabled):
        self._enabled = enabled

    def stop(self):
        """Signal background threads to exit. Safe to call at app shutdown."""
        self._stop_event.set()

    # ─── Wayland backend ───────────────────────────────────────────────────────

    def _start_wayland(self):
        """Spawn two watch threads: one for PRIMARY, one for CLIPBOARD."""
        log.info("Wayland detected — using wl-paste --watch.")

        # Verify wl-paste exists
        try:
            subprocess.run(
                ["wl-paste", "--version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            log.error(
                "wl-paste not found. Install it: sudo apt install wl-clipboard. "
                "Falling back to GTK (may not work on Wayland)."
            )
            GLib.idle_add(self._start_x11)
            return

        for source, extra_args in [("primary", ["--primary"]), ("clipboard", [])]:
            t = threading.Thread(
                target=self._wl_watch_loop,
                args=(source, extra_args),
                daemon=True,
            )
            t.start()
            self._threads.append(t)

    def _wl_paste(self, extra_args):
        """Run wl-paste and return text, or empty string on failure."""
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"] + extra_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace")
        except Exception:
            pass
        return ""

    def _wl_watch_loop(self, source, extra_args):
        """Background thread: wait for wl-paste --watch events."""
        log.info("wl-paste watch thread started for %s", source)
        
        # wl-paste --watch runs the given command every time the clipboard changes.
        # We just echo "CHANGED" and read stdout to detect when to poll.
        cmd = ["wl-paste", "--watch", "echo", "CHANGED"] + extra_args
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1, # Line buffered
            )
        except Exception as e:
            log.error("Failed to start wl-paste --watch: %s", e)
            return

        while not self._stop_event.is_set():
            line = proc.stdout.readline()
            if not line:
                break  # Process died
                
            if not self._enabled:
                continue
                
            # A change occurred! Wait a moment for selection to settle.
            if self._stop_event.wait(self._settle_seconds):
                break
                
            text = self._wl_paste(extra_args).strip()
            last = self._last_primary if source == "primary" else self._last_clipboard
            
            if text and text != last:
                if source == "primary":
                    self._last_primary = text
                else:
                    self._last_clipboard = text
                GLib.idle_add(self._dispatch, text)

        proc.terminate()

    # ─── X11 / GTK backend ────────────────────────────────────────────────────

    def _start_x11(self):
        log.info("X11 mode — using GTK clipboard polling.")
        self._gtk_primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self._gtk_clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self._pending_id = None

        self._gtk_primary.connect("owner-change", self._on_owner_change)
        self._gtk_clipboard.connect("owner-change", self._on_owner_change)
        log.info("Clipboard: owner-change signals connected")

        GLib.timeout_add(1000, self._poll_gtk)
        log.info("Clipboard: GTK polling started (1000 ms)")
        return False  # Don't repeat if called via idle_add

    def _on_owner_change(self, clipboard, event):
        if not self._enabled:
            return
        if self._pending_id is not None:
            GLib.source_remove(self._pending_id)
        self._pending_id = GLib.timeout_add(int(self._delay_ms * 1000), self._poll_gtk_once)

    def _poll_gtk(self):
        if self._enabled:
            self._poll_gtk_once()
        return True  # keep running

    def _poll_gtk_once(self):
        self._pending_id = None
        primary_text = (self._gtk_primary.wait_for_text() or "").strip()
        clipboard_text = (self._gtk_clipboard.wait_for_text() or "").strip()

        if primary_text and primary_text != self._last_primary:
            self._last_primary = primary_text
            self._dispatch(primary_text)
        elif clipboard_text and clipboard_text != self._last_clipboard:
            self._last_clipboard = clipboard_text
            self._dispatch(clipboard_text)

        return False

    # ─── Shared dispatch ──────────────────────────────────────────────────────

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
        return False  # for GLib.idle_add
