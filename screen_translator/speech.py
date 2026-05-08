"""Text-to-Speech functionality using gTTS."""

import os
import threading
import subprocess
import tempfile
import logging
from gtts import gTTS

log = logging.getLogger(__name__)


def speak(text, lang="en"):
    """
    Speak text using gTTS and mpv.
    Runs in a background thread to avoid blocking.
    """
    if not text:
        return

    def _work():
        try:
            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_name = f.name

            log.info("Generating speech for: %.50s... (lang=%s)", text, lang)
            try:
                tts = gTTS(text=text, lang=lang)
            except ValueError:
                log.warning("Language '%s' not supported by gTTS, falling back to 'en'", lang)
                tts = gTTS(text=text, lang="en")
            tts.save(temp_name)

            log.info("Playing speech via mpv...")
            # Use mpv to play the audio file (no video, hide output)
            subprocess.run(
                ["mpv", "--no-video", "--really-quiet", temp_name],
                check=False
            )

            # Cleanup
            if os.path.exists(temp_name):
                os.remove(temp_name)

        except Exception as e:
            log.error("Speech error: %s", e)

    thread = threading.Thread(target=_work, daemon=True)
    thread.start()
