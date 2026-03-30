"""
main.py
───────
QuickSpeak entry point.

Wires together Recorder → Recognizer → Clipboard → GUI.

Flow
----
  User clicks waveform (idle state)
      → recorder.start()
      → meter update loop begins (every 60 ms via root.after)

  User clicks Stop button
      → recorder.stop()
      → recognizer.recognize(queue, on_result)   [non-blocking daemon thread]

  STT finishes (on_result callback, daemon thread)
      → text is written to the system clipboard  (xclip / xsel / xdotool)
      → system notification fires (notify-send)
      → GUI flashes "Copied!" for 2.5 s
      → GUI returns to idle state
"""

import subprocess
import tkinter as tk

import config
from app.recorder    import Recorder
from app.recognizer  import Recognizer
from app.gui         import GUI

# ──────────────────────────────────────────────────────────────────────────────
# Module-level state
# ──────────────────────────────────────────────────────────────────────────────
recorder   = Recorder()
recognizer = Recognizer()

root       = tk.Tk()
gui        = None          # assigned after GUI is constructed
_meter_job = None          # root.after job id


# ──────────────────────────────────────────────────────────────────────────────
# Clipboard helpers
# ──────────────────────────────────────────────────────────────────────────────

def _copy_to_clipboard(text: str) -> bool:
    """
    Write `text` to the system clipboard using the first available tool.
    Priority: wl-copy (Wayland) -> xclip -> xsel -> xdotool -> tk fallback
    Returns True on success, False if no tool found.
    """
    import os

    # 1. Wayland check (wl-copy)
    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            subprocess.run(["wl-copy"], input=text, text=True, check=True, capture_output=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    # 2. xclip (most common on X11)
    try:
        subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True, capture_output=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # 3. xsel fallback
    try:
        subprocess.run(["xsel", "--clipboard", "--input"], input=text, text=True, check=True, capture_output=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # xdotool last resort
    try:
        subprocess.run(
            ["xdotool", "set_clipboard", text],
            check=True, capture_output=True, text=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fallback: use Tk's own clipboard (works without external tools)
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        return True
    except Exception:
        pass

    return False


def _notify(title: str, body: str):
    """Fire a desktop notification (best-effort; silent on failure)."""
    try:
        subprocess.Popen(
            ["notify-send", "--icon=dialog-information",
             "--expire-time=3000", title, body],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass  # notify-send not installed — ignore


# ──────────────────────────────────────────────────────────────────────────────
# Meter loop
# ──────────────────────────────────────────────────────────────────────────────

def _meter_tick():
    """Called every 60 ms while recording to feed PCM data to the waveform."""
    global _meter_job
    chunk = recorder.get_latest_chunk()
    gui.update_meter(chunk)
    _meter_job = root.after(60, _meter_tick)


def _start_meter_loop():
    global _meter_job
    _meter_job = root.after(60, _meter_tick)


def _stop_meter_loop():
    global _meter_job
    if _meter_job is not None:
        root.after_cancel(_meter_job)
        _meter_job = None


# ──────────────────────────────────────────────────────────────────────────────
# Recording callbacks
# ──────────────────────────────────────────────────────────────────────────────

def on_start():
    """Called when the user clicks the waveform to start recording."""
    print("[Main] Recording started.")
    recorder.start()
    _start_meter_loop()


def on_stop():
    """Called when the user clicks ⏹ Stop."""
    print("[Main] Recording stopped — running recognition.")
    _stop_meter_loop()
    recorder.stop()
    recognizer.recognize(recorder.get_audio_queue(), on_result)


def on_result(text: str):
    """
    Called by Recognizer (from a daemon thread) when transcription is done.
    Copies text to clipboard, fires notification, updates GUI.
    Uses root.after() for all GUI interactions to stay thread-safe.
    """
    def _finish():
        if text:
            ok = _copy_to_clipboard(text)
            snippet = text[:40] + ("…" if len(text) > 40 else "")

            if ok:
                print(f"[Main] Copied to clipboard: {text!r}")
                _notify("QuickSpeak — Copied!", snippet)
                gui.flash_copied(text)
            else:
                print("[Main] Clipboard copy failed — no xclip/xsel/xdotool found.")
                gui.update_status("⚠️ Clipboard tool missing", color="#f59e0b")
                root.after(2500, gui.set_idle)
        else:
            print("[Main] Recognizer returned empty text.")
            gui.update_status("⚠️ Couldn't understand audio", color="#f59e0b")
            root.after(2500, gui.set_idle)

    root.after(0, _finish)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    global gui

    gui = GUI(root, on_start=on_start, on_stop=on_stop)

    # Centre window on screen
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    W  = 460
    H  = 100
    x  = (sw - W) // 2
    y  = (sh - H) // 2
    root.geometry(f"{W}x{H}+{x}+{y}")

    print(f"[Main] QuickSpeak ready (engine={config.ENGINE!r})")
    root.mainloop()


if __name__ == "__main__":
    main()
