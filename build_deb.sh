#!/bin/bash
#
# Build .deb package for Screen Translator
# Usage: ./build_deb.sh
#
# Prerequisites:
#   sudo apt install debhelper dpkg-dev
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Screen Translator .deb package ==="

# Ensure debian/rules is executable
chmod +x debian/rules
chmod +x debian/postinst
chmod +x debian/postrm
chmod +x data/screen-translator.sh

# Clean previous builds
rm -f ../screen-translator_*.deb
rm -f ../screen-translator_*.changes
rm -f ../screen-translator_*.buildinfo
rm -f ../screen-translator_*.tar.*
rm -f ../screen-translator_*.dsc

# Build the package
dpkg-buildpackage -us -uc -b --no-check-builddeps

echo ""
echo "=== Build complete ==="
echo "Package: $(ls ../screen-translator_*.deb 2>/dev/null)"
echo ""
echo "Install with:"
echo "  sudo dpkg -i ../screen-translator_*.deb"
echo "  sudo apt-get install -f  # fix any missing dependencies"
