"""Translation engine using Google Translate (free, no API key)."""

import logging
import threading
from deep_translator import GoogleTranslator
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES

log = logging.getLogger(__name__)


# Cache recent translations to avoid repeated API calls
_cache = {}
_CACHE_MAX = 500


def get_supported_languages():
    """Return dict of {language_name: language_code}."""
    return dict(GOOGLE_LANGUAGES_TO_CODES)


def translate(text, target_lang="vi", source_lang="auto"):
    """
    Translate text. Returns dict with keys:
      - source: detected source language code
      - target: target language code
      - original: original text
      - translated: translated text
      - error: error message if failed, else None
    """
    text = text.strip()
    if not text:
        return None

    cache_key = (text, target_lang, source_lang)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)

        # Detect language if source was 'auto'
        actual_source = source_lang
        if source_lang == "auto":
            try:
                # Get detected language (usually returns code like 'en')
                detected = translator.detect_language(text)
                # Ensure it's a code gTTS understands (e.g., 'en' not 'english')
                # GoogleTranslator.detect_language usually returns the code already.
                actual_source = detected
            except Exception as e:
                log.warning("Language detection failed: %s", e)
                actual_source = "en"

        result = {
            "source": actual_source,
            "target": target_lang,
            "original": text,
            "translated": translated or "",
            "error": None,
        }

        # Manage cache size
        if len(_cache) >= _CACHE_MAX:
            # Remove oldest quarter
            keys = list(_cache.keys())
            for k in keys[: _CACHE_MAX // 4]:
                del _cache[k]
        _cache[cache_key] = result
        return result

    except Exception as e:
        return {
            "source": source_lang,
            "target": target_lang,
            "original": text,
            "translated": "",
            "error": str(e),
        }


def translate_async(text, target_lang, callback, source_lang="auto"):
    """Translate in background thread, call callback(result) in the thread."""
    def _work():
        result = translate(text, target_lang, source_lang)
        callback(result)
    t = threading.Thread(target=_work, daemon=True)
    t.start()
