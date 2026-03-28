# 🤖 QuickSpeak — AI Agent Build Guide

This document is a **precise technical specification** for building the QuickSpeak application. Follow **every section in order** to avoid bugs.

---

## 1. Architecture Overview

```
User speaks
     │
     ▼
[recorder.py] — PyAudio stream → raw PCM frames → queue
     │
     ▼
[recognizer.py] — consumes queue → sends to STT engine → returns text string
     │
     ▼
[typer.py] — receives text → calls xdotool to type into focused window
     │
     ▼
[gui.py] — Tkinter floating window → controls recorder start/stop, shows status + level meter
     │
     ▼
[main.py] — creates GUI, wires modules together, starts Tk mainloop
```

### Module Responsibilities (strict separation)

| Module | Responsibility | Does NOT do |
|--------|---------------|------------|
| `recorder.py` | Open mic, buffer PCM frames | Any STT, any GUI |
| `recognizer.py` | Convert audio bytes → text string | Any GUI, any file I/O |
| `typer.py` | Type text via xdotool | Any audio, any GUI |
| `gui.py` | Tk window, buttons, meter | Any audio logic |
| `main.py` | Wire everything, start loop | Heavy logic |

---

## 2. Detailed File Specifications

---

### 2.1 `config.py`

```python
# ── Speech Engine ─────────────────────────────────────────────────
ENGINE = "google"          # "google" | "vosk"
LANGUAGE = "en-US"         # BCP-47 language tag

# ── Vosk (offline) settings ───────────────────────────────────────
VOSK_MODEL_PATH = "models/vosk-model"   # relative path

# ── Audio capture ─────────────────────────────────────────────────
SAMPLE_RATE = 16000        # Hz — Vosk requires 16000; Google works with 16000 too
CHANNELS = 1               # Mono
CHUNK_SIZE = 1024          # Frames per buffer read

# ── GUI ───────────────────────────────────────────────────────────
WINDOW_TITLE   = "QuickSpeak"
WINDOW_WIDTH   = 280
WINDOW_HEIGHT  = 110
WINDOW_OPACITY = 0.93      # 0.0 transparent → 1.0 opaque
ALWAYS_ON_TOP  = True

# ── Typing ────────────────────────────────────────────────────────
TYPE_DELAY_MS = 12         # ms between xdotool keystrokes
APPEND_SPACE  = True       # add trailing space after typed text
```

---

### 2.2 `app/recorder.py`

**Purpose:** Opens a PyAudio stream and puts raw PCM chunks into a thread-safe queue.

```python
"""
Key rules:
1. Use a threading.Event (stop_event) to gracefully end recording — never kill threads.
2. PyAudio stream must be opened with:
   - format=pyaudio.paInt16
   - channels=config.CHANNELS
   - rate=config.SAMPLE_RATE
   - input=True
   - frames_per_buffer=config.CHUNK_SIZE
3. The recording loop runs in a daemon thread.
4. expose: start(), stop(), get_audio_queue()
5. get_audio_queue() returns a queue.Queue of bytes objects (raw PCM chunks).
6. After stop(), drain the queue to get all buffered audio before processing.
"""

import pyaudio
import queue
import threading
import config

class Recorder:
    def __init__(self):
        self._pa       = pyaudio.PyAudio()
        self._queue    = queue.Queue()
        self._stop_evt = threading.Event()
        self._thread   = None
        self._stream   = None

    def start(self):
        """Open mic stream and start background capture thread."""
        self._stop_evt.clear()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=config.CHANNELS,
            rate=config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.CHUNK_SIZE,
        )
        self._thread = threading.Thread(target=self._capture, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the capture thread to finish and close the stream."""
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

    def get_audio_queue(self):
        return self._queue

    def _capture(self):
        while not self._stop_evt.is_set():
            try:
                data = self._stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                self._queue.put(data)
            except Exception:
                break
```

**Common bugs to avoid:**
- Do NOT call `self._pa.terminate()` in `stop()` — the same PyAudio instance should be reusable between recordings.
- Always pass `exception_on_overflow=False` to `stream.read()` to prevent crash on buffer overrun.

---

### 2.3 `app/recognizer.py`

**Purpose:** Collect all PCM chunks from the queue and run STT.

```python
"""
Key rules:
1. Collect ALL chunks from the queue into a single `bytes` object after stop().
2. For Google: use the `speech_recognition` library (SpeechRecognition package).
   - Create sr.AudioData from raw PCM bytes with sample_rate and sample_width=2.
   - Call recognizer.recognize_google(audio_data, language=config.LANGUAGE).
3. For Vosk: load model once at init, create KaldiRecognizer, feed chunks in loop.
4. Return plain string (empty string "" on failure, NOT None).
5. Run recognition in a background thread so GUI stays responsive.
6. Accept a callback: on_result(text: str) called when recognition finishes.
"""

import queue
import threading
import config

class Recognizer:
    def __init__(self):
        if config.ENGINE == "vosk":
            self._init_vosk()
        # Google needs no init

    def _init_vosk(self):
        from vosk import Model, KaldiRecognizer
        self._vosk_model = Model(config.VOSK_MODEL_PATH)
        # KaldiRecognizer is created fresh each recognition run

    def recognize(self, audio_queue: queue.Queue, on_result):
        """
        Drain audio_queue, run STT, call on_result(text).
        Runs in a daemon thread so GUI is not blocked.
        """
        t = threading.Thread(
            target=self._run,
            args=(audio_queue, on_result),
            daemon=True,
        )
        t.start()

    def _run(self, audio_queue: queue.Queue, on_result):
        # Drain all frames
        frames = []
        while not audio_queue.empty():
            frames.append(audio_queue.get_nowait())
        raw_audio = b"".join(frames)

        if not raw_audio:
            on_result("")
            return

        try:
            if config.ENGINE == "vosk":
                text = self._recognize_vosk(raw_audio)
            else:
                text = self._recognize_google(raw_audio)
        except Exception as e:
            print(f"[Recognizer] Error: {e}")
            text = ""

        on_result(text)

    def _recognize_google(self, raw: bytes) -> str:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        audio_data = sr.AudioData(raw, config.SAMPLE_RATE, sample_width=2)
        return recognizer.recognize_google(audio_data, language=config.LANGUAGE)

    def _recognize_vosk(self, raw: bytes) -> str:
        import json
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self._vosk_model, config.SAMPLE_RATE)
        # Feed in 4096-byte chunks
        chunk_size = 4096
        for i in range(0, len(raw), chunk_size):
            rec.AcceptWaveform(raw[i:i+chunk_size])
        result = json.loads(rec.FinalResult())
        return result.get("text", "")
```

**Common bugs to avoid:**
- Google's `sr.AudioData` requires `sample_width=2` for 16-bit (paInt16) audio.
- Vosk model path must point to the **directory** (e.g. `models/vosk-model-en-us-0.22`), not a file.
- Always call `rec.FinalResult()` (not `rec.Result()`) to get the complete transcription.

---

### 2.4 `app/typer.py`

**Purpose:** Use `xdotool type` to inject text into the currently focused window.

```python
"""
Key rules:
1. Use subprocess to call: xdotool type --clearmodifiers --delay <ms> -- "<text>"
2. The `--` separator prevents text starting with `-` from being treated as a flag.
3. Use `--clearmodifiers` to avoid Shift/Ctrl being held from the app's own UI.
4. Add a trailing space if config.APPEND_SPACE is True.
5. Strip leading/trailing whitespace from the text before typing (speech engines pad it).
6. If text is empty string, do nothing (no subprocess call).
7. Log what was typed for debugging.
"""

import subprocess
import config

class Typer:
    def type_text(self, text: str):
        text = text.strip()
        if not text:
            return
        if config.APPEND_SPACE:
            text = text + " "
        cmd = [
            "xdotool", "type",
            "--clearmodifiers",
            f"--delay={config.TYPE_DELAY_MS}",
            "--",
            text,
        ]
        print(f"[Typer] Typing: {text!r}")
        subprocess.run(cmd, check=False)
```

**Common bugs to avoid:**
- Do NOT use `shell=True` with subprocess — it breaks argument escaping for special chars.
- xdotool can have issues with Unicode beyond BMP — warn users in README if needed.
- The `--clearmodifiers` flag is **critical** — without it, Shift held in the GUI will capitalise everything.

---

### 2.5 `app/gui.py`

**Purpose:** Tiny always-on-top Tkinter window with Start/Stop buttons and a status label.

```python
"""
Key rules:
1. Window must be: always on top, no resize, transparent background optional.
2. Set window attributes: -topmost True, -alpha WINDOW_OPACITY.
3. Two states: IDLE and RECORDING.
   - IDLE:      Start button enabled, Stop button disabled, status = "Ready"
   - RECORDING: Start button disabled, Stop button enabled, status = "Listening…"
4. After STT finishes: show "Typed: <first 30 chars>…" in status, return to IDLE after 2s.
5. Audio level meter: a ttk.Progressbar updated every 100ms from current mic chunk.
   - compute RMS of latest chunk: rms = sqrt(mean(array(chunk, int16)**2))
   - map rms (0–5000) to (0–100) for the progressbar value
6. on_start callback: callable passed in from main.py
7. on_stop callback: callable passed in from main.py
8. update_status(msg): thread-safe via self.root.after(0, ...)
9. The window should NOT appear in the taskbar: use root.wm_overrideredirect(False)
   Keep it False so the user can drag/close it, but add wm_attributes('-type', 'dialog').

Layout (top→bottom):
   ┌─────────────────────────────────┐
   │  🎙️ QuickSpeak          [×]     │  ← title bar (OS native)
   ├─────────────────────────────────┤
   │  Status: Ready                  │  ← status Label
   │  [████░░░░░░] Level             │  ← ttk.Progressbar (meter)
   │  [ 🎙 Start ]   [ ⏹ Stop ]      │  ← two Buttons side by side
   └─────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import config

class GUI:
    def __init__(self, root: tk.Tk, on_start, on_stop):
        self.root     = root
        self.on_start = on_start
        self.on_stop  = on_stop
        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", config.ALWAYS_ON_TOP)
        self.root.attributes("-alpha",   config.WINDOW_OPACITY)
        self.root.attributes("-type",    "dialog")  # no taskbar entry

    def _build_ui(self):
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var, anchor="w",
                 font=("Inter", 10)).pack(fill="x", padx=10, pady=(8, 0))

        # Level meter
        self.meter = ttk.Progressbar(self.root, orient="horizontal",
                                     length=260, mode="determinate")
        self.meter.pack(padx=10, pady=4)

        # Buttons frame
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=6)

        self.start_btn = tk.Button(btn_frame, text="🎙 Start",
                                   command=self._handle_start, width=10)
        self.start_btn.grid(row=0, column=0, padx=6)

        self.stop_btn = tk.Button(btn_frame, text="⏹ Stop",
                                  command=self._handle_stop,
                                  width=10, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=6)

    # ── State transitions ──────────────────────────────────────────

    def set_recording(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Listening…")

    def set_idle(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.meter["value"] = 0

    def set_processing(self):
        self.status_var.set("Processing…")

    def update_status(self, msg: str):
        """Thread-safe status update."""
        self.root.after(0, lambda: self.status_var.set(msg))

    def update_meter(self, chunk_bytes: bytes):
        """Call periodically with latest audio chunk to animate the meter."""
        if not chunk_bytes:
            return
        arr = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(arr ** 2))
        value = min(100, int(rms / 50))   # scale 0–5000 → 0–100
        self.root.after(0, lambda: self.meter.__setitem__("value", value))

    # ── Button handlers ───────────────────────────────────────────

    def _handle_start(self):
        self.set_recording()
        self.on_start()

    def _handle_stop(self):
        self.set_processing()
        self.stop_btn.config(state="disabled")
        self.on_stop()
```

**Common bugs to avoid:**
- **Never** update Tk widgets from a non-main thread directly — always use `root.after(0, lambda: ...)`.
- `ttk.Progressbar.__setitem__("value", n)` is the correct way to set value programmatically (or `meter["value"] = n` from the main thread).
- `-type dialog` may not work on all window managers; it's a best-effort hint — don't error if it fails.

---

### 2.6 `main.py`

**Purpose:** Wire all modules together and start the Tkinter main loop.

```python
"""
Wiring logic:
1. Create Recorder, Recognizer, Typer instances.
2. Define on_start():
   a. Clear the recorder's queue (drain leftover frames from last run).
   b. Start the recorder.
   c. Start a repeating meter update loop (root.after every 100ms).
3. Define on_stop():
   a. Stop the recorder (blocks until thread joins, max 2s).
   b. Cancel the meter loop.
   c. Call recognizer.recognize(queue, on_result_callback).
4. Define on_result(text):
   a. Call typer.type_text(text).
   b. Update GUI status to show snippet of typed text.
   c. After 2000ms, call gui.set_idle().
5. Create tk.Tk(), build GUI(root, on_start, on_stop).
6. root.mainloop().
"""
```

**Meter update loop pattern (inside main.py):**
```python
_meter_job = None

def _start_meter_loop():
    global _meter_job
    q = recorder.get_audio_queue()
    # Peek at latest chunk without consuming it permanently... 
    # Actually: use a separate small queue just for meter data OR
    # duplicate chunks to a meter_queue in recorder.
    # SIMPLEST approach: use a shared list `latest_chunk = [b""]`
    # updated by recorder, read by meter loop.
    _meter_job = root.after(100, _meter_tick)

def _meter_tick():
    global _meter_job
    chunk = recorder.get_latest_chunk()   # add get_latest_chunk() to Recorder
    gui.update_meter(chunk)
    _meter_job = root.after(100, _meter_tick)

def _stop_meter_loop():
    global _meter_job
    if _meter_job:
        root.after_cancel(_meter_job)
        _meter_job = None
```

**Add `get_latest_chunk()` to `Recorder`:**
```python
# In __init__:
self._latest_chunk = b""

# In _capture loop:
self._latest_chunk = data

# New method:
def get_latest_chunk(self) -> bytes:
    return self._latest_chunk
```

---

### 2.7 `requirements.txt`

```
SpeechRecognition>=3.10.0
pyaudio>=0.2.13
numpy>=1.24.0
vosk>=0.3.45        # only needed if using vosk engine
```

**Install command:**
```bash
pip install -r requirements.txt
```

---

### 2.8 `scripts/download_model.py`

**Purpose:** Download and extract the Vosk English model automatically.

```python
"""
Steps:
1. Download from: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
2. Save to: models/vosk-model-small-en-us-0.15.zip
3. Extract to: models/
4. Rename extracted folder to: models/vosk-model  (matches VOSK_MODEL_PATH in config.py)
5. Delete the zip file after extraction.
6. Print progress using urllib.request with a progress callback.
"""

import urllib.request
import zipfile
import shutil
from pathlib import Path

MODEL_URL  = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_ZIP  = Path("models/vosk-model-small-en-us-0.15.zip")
MODEL_DIR  = Path("models/vosk-model")
MODELS_DIR = Path("models")

def reporthook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    pct = min(100, downloaded * 100 // total_size) if total_size > 0 else 0
    print(f"\r  Downloading… {pct}%", end="", flush=True)

def main():
    MODELS_DIR.mkdir(exist_ok=True)
    if MODEL_DIR.exists():
        print("Model already exists. Skipping download.")
        return
    print(f"Downloading Vosk model from {MODEL_URL}")
    urllib.request.urlretrieve(MODEL_URL, MODEL_ZIP, reporthook)
    print("\nExtracting…")
    with zipfile.ZipFile(MODEL_ZIP, "r") as zf:
        zf.extractall(MODELS_DIR)
    # Find extracted folder (name varies by version)
    extracted = next(MODELS_DIR.glob("vosk-model-*"))
    extracted.rename(MODEL_DIR)
    MODEL_ZIP.unlink()
    print(f"Model ready at: {MODEL_DIR}")

if __name__ == "__main__":
    main()
```

---

## 3. System Dependency Installation

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-tk \
    portaudio19-dev \
    libportaudio2 \
    xdotool \
    python3-dev

# Fedora / RHEL
sudo dnf install -y python3-pip python3-tkinter portaudio-devel xdotool
```

---

## 4. Known Issues & Workarounds

| Issue | Cause | Fix |
|-------|-------|-----|
| `xdotool type` drops characters on fast typing | Default delay too low | Increase `TYPE_DELAY_MS` to 20–30 |
| App window steals focus from target input | `wm_overrideredirect` or window raise | Do NOT call `root.focus_force()` on start; remove any `root.lift()` calls |
| Google Speech returns `UnknownValueError` | Silence or unclear audio | Catch exception in `_recognize_google`, return `""` |
| `paInt16` mismatch in AudioData | Wrong sample_width | Always `sample_width=2` for paInt16 |
| Meter always shows 0 | Queue drained before meter reads | Use `get_latest_chunk()` pattern (see Section 2.6) |
| Wayland: xdotool doesn't type | Wayland native apps block xdotool | Run app with `DISPLAY=:0` or use `XDG_SESSION_TYPE=x11` at login |

---

## 5. Build & Test Order

1. **Test recorder alone:** `python -c "from app.recorder import Recorder; r=Recorder(); r.start(); import time; time.sleep(3); r.stop(); print('chunks:', r.get_audio_queue().qsize())"`
2. **Test recognizer:** Record 3s, run recognizer, print result.
3. **Test typer:** `python -c "from app.typer import Typer; Typer().type_text('hello world')"` — focus a text editor first.
4. **Test GUI standalone:** `python -c "import tkinter as tk; from app.gui import GUI; r=tk.Tk(); GUI(r, lambda:None, lambda:None); r.mainloop()"`
5. **Full integration:** `python main.py`

---

## 6. File Creation Order for Agent

> Create files **exactly in this order** to avoid import errors:

1. `config.py`
2. `app/__init__.py` (empty)
3. `app/recorder.py`
4. `app/recognizer.py`
5. `app/typer.py`
6. `app/gui.py`
7. `main.py`
8. `scripts/__init__.py` (empty)
9. `scripts/download_model.py`
10. `requirements.txt`
