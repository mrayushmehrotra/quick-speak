"""
main.py
───────
QuickSpeak entry point.

Wires together Recorder → Recognizer → Typer → GUI and starts the Tk event loop.

Flow
----
  User clicks Start
      → recorder.start()
      → meter update loop begins (every 100 ms via root.after)

  User clicks Stop
      → recorder.stop()      (blocks ≤ 2 s for thread join)
      → meter loop cancelled
      → recognizer.recognize(queue, on_result)   [non-blocking daemon thread]

  STT finishes (on_result callback)
      → typer.type_text(text)
      → GUI status shows snippet
      → After 2 000 ms → gui.set_idle()
"""

import tkinter as tk

import config
from app.recorder    import Recorder
from app.recognizer  import Recognizer
from app.typer       import Typer
from app.gui         import GUI

# ──────────────────────────────────────────────────────────────────────────────
# Module-level state
# ──────────────────────────────────────────────────────────────────────────────
recorder    = Recorder()
recognizer  = Recognizer()
typer_      = Typer()

root        = tk.Tk()
gui         = None          # assigned after GUI is constructed
_meter_job  = None          # root.after job id


# ──────────────────────────────────────────────────────────────────────────────
# Meter loop
# ──────────────────────────────────────────────────────────────────────────────

def _meter_tick():
    """Called every 100 ms while recording to animate the level meter."""
    global _meter_job
    chunk = recorder.get_latest_chunk()
    gui.update_meter(chunk)
    _meter_job = root.after(100, _meter_tick)


def _start_meter_loop():
    global _meter_job
    _meter_job = root.after(100, _meter_tick)


def _stop_meter_loop():
    global _meter_job
    if _meter_job is not None:
        root.after_cancel(_meter_job)
        _meter_job = None


# ──────────────────────────────────────────────────────────────────────────────
# Recording callbacks
# ──────────────────────────────────────────────────────────────────────────────

def on_start():
    """Called when the user clicks 🎙 Start."""
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
    Uses root.after() for all GUI/Typer interactions to stay thread-safe.
    """
    def _finish():
        if text:
            typer_.type_text(text)
            snippet = text[:35] + ("…" if len(text) > 35 else "")
            gui.update_status(f"✅ Typed: {snippet}")
        else:
            gui.update_status("⚠️ Couldn't understand audio")

        # Return to idle after 2 s
        root.after(2000, gui.set_idle)

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
    x  = (sw - config.WINDOW_WIDTH)  // 2
    y  = (sh - config.WINDOW_HEIGHT) // 2
    root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}+{x}+{y}")

    print(f"[Main] QuickSpeak ready (engine={config.ENGINE!r})")
    root.mainloop()


if __name__ == "__main__":
    main()
