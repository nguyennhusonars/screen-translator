# Screen Translator

Auto-translate highlighted text on Ubuntu. Select any text and see the translation in a popup near your cursor.

## Features

- **Auto-detect language** of selected text
- **Instant popup** with translation near your cursor
- **Text-to-Speech (TTS)**: Listen to the translated text aloud
- **System tray** icon with settings menu
- **Target language selector** (100+ languages, Vietnamese default)
- **Translation cache** to avoid repeated API calls
- **Autostart** on login

## Install

### From .deb package

```bash
# Build
sudo apt install debhelper dpkg-dev python3-langdetect  # build dependencies (one-time)
./build_deb.sh

# Install
sudo dpkg -i ../screen-translator_1.0.0-1_all.deb
sudo apt-get install -f   # install any missing dependencies
```

### Run without installing

```bash
pip3 install deep-translator
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
python3 -m screen_translator.main
```

## Usage

1. Launch **Screen Translator** from Applications menu or run `screen-translator`
2. Highlight any text on screen
3. Translation popup appears near your cursor
4. Right-click tray icon to change target language or toggle auto-translate

## Uninstall

```bash
sudo apt remove screen-translator
```

## Requirements

- Ubuntu 22.04 / 24.04
- X11 display server (Wayland: partial support)
- Internet connection (uses Google Translate)

## Config

Settings saved to `~/.config/screen-translator/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `target_language` | `vi` | Target language code |
| `auto_translate` | `true` | Translate on text selection |
| `popup_timeout` | `8` | Seconds before popup hides (0=never) |
| `selection_delay_ms` | `600` | Debounce delay after selecting text |
| `min_text_length` | `2` | Minimum characters to trigger |
| `max_text_length` | `5000` | Maximum characters to translate |
