"""
app/gui.py
──────────
Tiny always-on-top Tkinter floating overlay.

Layout
------
  ┌──────────────────────────────────┐
  │  🎙️ QuickSpeak            [×]    │  ← native title bar
  ├──────────────────────────────────┤
  │  Status: Ready                   │  ← status label
  │  [███████░░░░░░░░░░░░░░░░░░░░░]  │  ← audio level meter
  │   [ 🎙 Start ]   [ ⏹ Stop ]      │  ← buttons
  └──────────────────────────────────┘

Thread-safety rule
------------------
NEVER update Tk widgets from a non-main thread.
All cross-thread updates must go through `root.after(0, lambda: ...)`.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import config


class GUI:
    def __init__(self, root: tk.Tk, on_start, on_stop):
        self.root     = root
        self.on_start = on_start   # callable()
        self.on_stop  = on_stop    # callable()

        self._setup_window()
        self._build_ui()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.resizable(False, False)

        # Always float above other windows
        self.root.attributes("-topmost", config.ALWAYS_ON_TOP)

        # Semi-transparent window (may not work on all compositors)
        try:
            self.root.attributes("-alpha", config.WINDOW_OPACITY)
        except tk.TclError:
            pass  # compositor doesn't support transparency — ignore

        # Hint to WM that this is a dialog (no taskbar entry on most DEs)
        try:
            self.root.attributes("-type", "dialog")
        except tk.TclError:
            pass  # not all WMs support this hint — ignore

        # Dark-ish background
        self.root.configure(bg="#1e1e2e")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        BG        = "#1e1e2e"
        FG        = "#cdd6f4"
        BTN_START = "#a6e3a1"   # green
        BTN_STOP  = "#f38ba8"   # red
        BTN_FG    = "#1e1e2e"   # dark text on coloured buttons
        METER_FG  = "#89b4fa"   # blue

        # ── Status label ──────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        status_lbl = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg=BG,
            fg=FG,
            font=("sans-serif", 10),
            padx=10,
        )
        status_lbl.pack(fill="x", pady=(8, 2))

        # ── Level meter ───────────────────────────────────────────────────────
        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure(
            "Meter.Horizontal.TProgressbar",
            troughcolor="#313244",
            background=METER_FG,
            thickness=8,
        )
        self.meter = ttk.Progressbar(
            self.root,
            orient="horizontal",
            length=config.WINDOW_WIDTH - 20,
            mode="determinate",
            maximum=100,
            style="Meter.Horizontal.TProgressbar",
        )
        self.meter.pack(padx=10, pady=(0, 6))

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=4)

        self.start_btn = tk.Button(
            btn_frame,
            text="🎙 Start",
            command=self._handle_start,
            bg=BTN_START,
            fg=BTN_FG,
            activebackground="#8ec87e",
            relief="flat",
            font=("sans-serif", 10, "bold"),
            width=10,
            cursor="hand2",
        )
        self.start_btn.grid(row=0, column=0, padx=8)

        self.stop_btn = tk.Button(
            btn_frame,
            text="⏹ Stop",
            command=self._handle_stop,
            bg="#45475a",         # greyed-out when disabled
            fg="#6c7086",
            activebackground="#f28ba8",
            relief="flat",
            font=("sans-serif", 10, "bold"),
            width=10,
            cursor="hand2",
            state="disabled",
        )
        self.stop_btn.grid(row=0, column=1, padx=8)

        self._btn_stop_color = BTN_STOP    # remember active colour
        self._btn_start_color = BTN_START

    # ── State transitions (called from main thread only) ─────────────────────

    def set_recording(self):
        """Switch to RECORDING state."""
        self.start_btn.config(state="disabled", bg="#45475a", fg="#6c7086")
        self.stop_btn.config(
            state="normal",
            bg=self._btn_stop_color,
            fg="#1e1e2e",
        )
        self.status_var.set("🔴 Listening…")

    def set_processing(self):
        """Show processing indicator (recognition running)."""
        self.stop_btn.config(state="disabled", bg="#45475a", fg="#6c7086")
        self.status_var.set("⏳ Processing…")

    def set_idle(self):
        """Return to IDLE / Ready state."""
        self.start_btn.config(
            state="normal",
            bg=self._btn_start_color,
            fg="#1e1e2e",
        )
        self.stop_btn.config(state="disabled", bg="#45475a", fg="#6c7086")
        self.meter["value"] = 0

    # ── Thread-safe updates ───────────────────────────────────────────────────

    def update_status(self, msg: str):
        """Update the status label from any thread."""
        self.root.after(0, lambda: self.status_var.set(msg))

    def update_meter(self, chunk_bytes: bytes):
        """
        Calculate RMS of the latest PCM chunk and animate the meter.
        Safe to call from any thread.
        """
        if not chunk_bytes:
            return
        arr = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
        if arr.size == 0:
            return
        rms   = float(np.sqrt(np.mean(arr ** 2)))
        value = min(100, int(rms / 50))   # map ~0–5000 RMS → 0–100
        self.root.after(0, lambda v=value: self.meter.__setitem__("value", v))

    # ── Button handlers ───────────────────────────────────────────────────────

    def _handle_start(self):
        self.set_recording()
        self.on_start()

    def _handle_stop(self):
        self.set_processing()
        self.on_stop()
