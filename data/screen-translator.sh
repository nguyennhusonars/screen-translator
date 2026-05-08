#!/bin/bash
# Launcher script for Screen Translator
# Must use system Python for PyGObject (gi) access
export PYTHONPATH="/opt/screen-translator/lib:/opt/screen-translator:${PYTHONPATH}"
exec /usr/bin/python3 -m screen_translator.main "$@"
