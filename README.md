# QuickSpeak 🎙️

> **A premium, floating voice-to-clipboard assistant for Linux.**
> Speak your thoughts, and have them instantly ready for `Ctrl+V` anywhere.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)
![Architecture](https://img.shields.io/badge/display-Wayland%20%2F%20X11-green.svg)

---

## 🎬 Demo

<video src="https://raw.githubusercontent.com/mrayushmehrotra/quick-speak/main/demo/quick-speak.mp4" width="600" controls></video>

---

## ✨ Features

- **💎 Premium Pill UI**: A sleek, borderless, always-on-top floating dialog with rounded corners.
- **🌊 Live Waveforms**: Dynamic, white-on-black audio visualization that reacts to your voice in real-time.
- **📋 Smart Clipboard**: Automatically copies your speech to the system clipboard upon stopping.
- **🌎 Dual-Protocol Support**: Seamlessly works on both **Wayland** (using `wl-copy`) and **X11** (using `xclip`/`xsel`).
- **🔔 Desktop Notifications**: Instant feedback via system notifications when your text is ready.
- **🚀 Single-File Portability**: Can be bundled into a standalone binary for easy distribution.

---

## 🚀 Quick Start

### 1. Install System Dependencies
QuickSpeak relies on these standard Linux tools for audio and clipboard management:

**Ubuntu / Debian / Mint:**
```bash
sudo apt update
sudo apt install python3-tk libportaudio2 wl-clipboard xclip notify-osd
```

**Fedora:**
```bash
sudo dnf install python3-tkinter portaudio wl-clipboard xclip libnotify
```

**Arch:**
```bash
sudo pacman -S tk portaudio wl-clipboard xclip libnotify
```

### 2. Installation (Choose one)

#### Option A: Run from Source (Recommended for focus)
```bash
# Clone and enter the directory
cd quick-speak

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch!
python3 main.py
```

#### Option B: Build a Standalone Binary (For distribution)
```bash
# Bundles everything into a single 'dist/quick-speak' file
bash scripts/distribute.sh
```

---

## 🕹️ How to Use

1. **Launch**: Open QuickSpeak. It will float on top of all your windows.
2. **Start**: Click anywhere on the **Waveform** to begin recording.
3. **Speak**: Talk clearly. The white waves will pulse according to your voice.
4. **Stop**: Click the **Red Circle** button to finish.
5. **Paste**: You'll see a "Copied!" message and receive a notification. Simply hit **`Ctrl+V`** anywhere to paste your transcribed text!

---

## ⚙️ Configuration (`config.py`)

You can customize the app's behavior by editing the `config.py` file:

- `ENGINE`: Choose between `"google"` (Cloud) or `"vosk"` (Offline).
- `LANGUAGE`: Set your BCP-47 language code (e.g., `"en-US"`, `"es-ES"`).
- `WINDOW_OPACITY`: Adjust the transparency of the floating pill.
- `ALWAYS_ON_TOP`: Toggle whether the window stays above others.

---

## 🛠️ Project Structure

- `main.py`: Application entry point and clipboard logic.
- `app/gui.py`: Premium Tkinter-based UI with canvas animations.
- `app/recorder.py`: Multi-threaded audio capture.
- `app/recognizer.py`: Speech-to-text engine aggregator.
- `scripts/distribute.sh`: PyInstaller-based distribution script.

---

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

Developed with ❤️ for the Linux community.
