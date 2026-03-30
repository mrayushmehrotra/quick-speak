#!/bin/bash
# ── QuickSpeak — Build Script ────────────────────────────────────────────────
# This script bundles the application into a standalone Linux executable.
# ─────────────────────────────────────────────────────────────────────────────

# Stop on errors
set -e

# Enter project root
cd "$(dirname "$0")/.."

echo "📦 Creating QuickSpeak distribution..."

# Install dependencies if not already in virtualenv
source .venv/bin/activate
pip install pyinstaller numpy pyaudio SpeechRecognition

# Clean up previous builds
rm -rf build dist

# Run PyInstaller
# --onefile: bundle into a single binary
# --windowed: don't open a terminal (GUI mode)
# --add-data: include the models folder if it exists
echo "🔨 Running PyInstaller..."
ADD_DATA_ARGS=""
if [ -d "models" ]; then
    ADD_DATA_ARGS="--add-data models:models"
fi

pyinstaller --noconfirm --onefile --windowed \
    --name quick-speak \
    $ADD_DATA_ARGS \
    --hidden-import speech_recognition \
    --hidden-import numpy \
    main.py

# Create a desktop launcher as well
echo "📝 Creating desktop launcher..."
cat <<EOF > dist/quick-speak.desktop
[Desktop Entry]
Name=QuickSpeak
Comment=Voice-to-Clipboard App
Exec=./quick-speak
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;AudioVideo;
EOF

chmod +x dist/quick-speak.desktop

echo "✅ Build complete! You can find the executable and launcher in the 'dist' folder."
echo "   Just zip up the 'dist' folder and send it to your friends!"
