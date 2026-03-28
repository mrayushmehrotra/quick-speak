# QuickSpeak 🎙️

> A lightweight Linux voice-to-text overlay that types what you say into any active input field.

## What It Does

QuickSpeak sits as a tiny floating dialog on your screen. When you click **Start**, it listens to your microphone and uses speech recognition to transcribe your speech — then it **types the text directly into whatever input field is currently focused** on your system (browser, terminal, IDE, form field — anywhere).

Think of it as pressing a **"dictate"** button: focus your cursor in any text field, launch QuickSpeak, speak, and the words appear in that field automatically.

---

## Features

- 🪟 Tiny, always-on-top floating overlay (no taskbar clutter)
- 🎙️ One-click **Start** / **Stop** recording
- ⌨️ Types text directly into any focused input via `xdotool`
- 🔇 Visual audio level meter while recording
- 🌐 Offline-capable (Vosk) **or** cloud (Google Speech API)
- 🐧 Linux-only (X11 / Wayland with XWayland)

---

## Quick Start

```bash
# 1. Install system dependencies
sudo apt install python3-pip python3-tk portaudio19-dev xdotool

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. (Optional) Download Vosk offline model — skip for Google API
python scripts/download_model.py

# 4. Run the app
python main.py
```

---

## Directory Structure

```
quick-speak/
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── config.py                # User-editable settings
├── app/
│   ├── gui.py               # Tkinter floating dialog
│   ├── recorder.py          # Microphone audio capture
│   ├── recognizer.py        # Speech-to-text engine wrapper
│   └── typer.py             # xdotool text injector
├── scripts/
│   └── download_model.py    # Downloads Vosk model
├── assets/
│   └── icon.png             # App icon
└── docs/
    └── AGENT_GUIDE.md       # Detailed guide for AI agents building this
```

---

## Usage

1. Place your cursor inside **any** text input on your screen (browser URL bar, text editor, form field, terminal, etc.)
2. Launch QuickSpeak (or use the shortcut if configured)
3. Click **🎙️ Start**
4. Speak clearly
5. Click **⏹ Stop** — the text is typed into your focused field instantly

---

## Configuration (`config.py`)

| Key | Default | Description |
|-----|---------|-------------|
| `ENGINE` | `"google"` | `"google"` or `"vosk"` |
| `LANGUAGE` | `"en-US"` | BCP-47 language code |
| `VOSK_MODEL_PATH` | `"models/vosk-model"` | Path to Vosk model dir |
| `WINDOW_OPACITY` | `0.92` | Float 0.0–1.0 |
| `ALWAYS_ON_TOP` | `True` | Keep dialog above all windows |
| `TYPE_DELAY_MS` | `12` | Delay between keystrokes (ms) |

---

## System Requirements

| Requirement | Version |
|-------------|---------|
| OS | Linux (Ubuntu 20.04+ recommended) |
| Python | 3.8+ |
| Display | X11 or XWayland |
| `xdotool` | Any recent version |
| `portaudio` | 19+ |

---

## License

MIT
