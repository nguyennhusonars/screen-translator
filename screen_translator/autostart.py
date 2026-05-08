"""Manage autostart desktop file in ~/.config/autostart/."""

import os
import logging

log = logging.getLogger(__name__)

AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "screen-translator.desktop")

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Exec=screen-translator
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Screen Translator
Comment=Auto-translate highlighted text
Icon=preferences-desktop-locale
Categories=Utility;
"""


def is_enabled():
    """Check if autostart is enabled for the current user."""
    return os.path.exists(AUTOSTART_FILE)


def set_enabled(enabled):
    """Enable or disable autostart."""
    try:
        if enabled:
            if not os.path.exists(AUTOSTART_DIR):
                os.makedirs(AUTOSTART_DIR, exist_ok=True)
            with open(AUTOSTART_FILE, "w") as f:
                f.write(DESKTOP_ENTRY)
            log.info("Autostart enabled: %s", AUTOSTART_FILE)
        else:
            if os.path.exists(AUTOSTART_FILE):
                os.remove(AUTOSTART_FILE)
            log.info("Autostart disabled")
    except Exception as e:
        log.error("Failed to set autostart: %s", e)
