"""
app/gui.py
──────────
Sleek floating overlay matching the sketch design:
  ┌─────────────────────────────────────────────────────┐
  │  [~~~waveform animation~~~]  [ ◼ stop button ]      │
  └─────────────────────────────────────────────────────┘

States
------
  IDLE       → mic icon pulses gently, click anywhere to begin
  RECORDING  → waveform animates, red stop button active
  PROCESSING → spinner text, buttons locked
  DONE       → "Copied!" flash, auto-return to IDLE

Thread-safety rule
------------------
NEVER update Tk widgets from a non-main thread.
All cross-thread updates must go through `root.after(0, lambda: ...)`
"""

import tkinter as tk
import math
import random
import numpy as np
import config

# ── Colour palette ────────────────────────────────────────────────────────────
BG          = "#000000"          # black background
CARD_BG     = "#000000"          # pill card
BORDER      = "#222222"          # subtle border
WAVE_IDLE   = "#333333"          # grey when idle
WAVE_COLOR  = "#ffffff"          # always white
WAVE_GLOW   = "#ffffff"          # soft white glow
STOP_RING   = "#ef4444"          # red ring
STOP_FILL   = "#ffffff"          # white square
STOP_HOVER  = "#dc2626"          # darker red hover
MIC_COLOR   = "#ffffff"
TEXT_FG     = "#e2e8f0"
SUBTEXT_FG  = "#64748b"
SUCCESS_FG  = "#4ade80"

# Window dimensions
W = 460
H = 100

class GUI:
    def __init__(self, root: tk.Tk, on_start, on_stop):
        self.root     = root
        self.on_start = on_start
        self.on_stop  = on_stop

        # Internal state
        self._state        = "idle"        # idle | recording | processing
        self._wave_samples = [0.0] * 60   # circular waveform buffer
        self._wave_phase   = 0.0          # idle sine phase
        self._anim_job     = None
        self._flash_job    = None
        self._latest_chunk = b""
        self._stop_enabled = False

        self._setup_window()
        self._build_ui()
        self._start_idle_animation()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", config.ALWAYS_ON_TOP)
        
        # Make the window look premium: no title bar, rounded-ish if possible
        # For simplicity and cross-platform compatibility, we'll use a styled frame.
        # To make it draggable without a title bar:
        self.root.overrideredirect(True)
        self.root.bind("<Button-1>", self._start_move)
        self.root.bind("<B1-Motion>", self._do_move)

        try:
            self.root.attributes("-alpha", config.WINDOW_OPACITY)
        except tk.TclError:
            pass

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Outer frame acts as card with padding and border
        outer = tk.Frame(self.root, bg=BG, bd=1, relief="flat")
        outer.pack(fill="both", expand=True)

        # ── Top micro-bar: status label & close ──────────────────────────────
        bar = tk.Frame(outer, bg=BG)
        bar.pack(fill="x", padx=12, pady=(6, 0))

        self._mic_dot = tk.Label(bar, text="⬤", fg=WAVE_IDLE, bg=BG, font=("Helvetica", 8))
        self._mic_dot.pack(side="left")

        self._status_lbl = tk.Label(bar, text="Click the waveform to start", fg=SUBTEXT_FG, bg=BG, font=("Helvetica", 9))
        self._status_lbl.pack(side="left", padx=(5, 0))

        close_btn = tk.Label(bar, text="×", fg=SUBTEXT_FG, bg=BG, font=("Helvetica", 13), cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _: self.root.destroy())
        close_btn.bind("<Enter>", lambda _: close_btn.config(fg="#ff5555"))
        close_btn.bind("<Leave>", lambda _: close_btn.config(fg=SUBTEXT_FG))

        # ── Main pill card ───────────────────────────────────────────────────
        card = tk.Frame(outer, bg=CARD_BG, bd=1, relief="solid", highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        # Inner layout: waveform canvas (left) + stop button (right)
        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill="both", expand=True, padx=8, pady=6)

        # Canvas for waveform
        self._canvas = tk.Canvas(inner, bg=CARD_BG, highlightthickness=0, width=340, height=52)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._canvas.bind("<Enter>", lambda _: self._canvas.config(cursor="hand2") if self._state == "idle" else None)
        self._canvas.bind("<Leave>", lambda _: self._canvas.config(cursor=""))

        # Stop button (red circle with square)
        self._stop_frame = tk.Frame(inner, bg=CARD_BG, width=56, height=52)
        self._stop_frame.pack(side="right", padx=(4, 2))
        self._stop_frame.pack_propagate(False)

        self._stop_canvas = tk.Canvas(self._stop_frame, bg=CARD_BG, highlightthickness=0, width=52, height=52)
        self._stop_canvas.pack()
        self._draw_stop_button(STOP_RING, False)
        self._stop_canvas.bind("<Button-1>", self._on_stop_click)
        self._stop_canvas.bind("<Enter>", lambda _: self._on_stop_hover(True))
        self._stop_canvas.bind("<Leave>", lambda _: self._on_stop_hover(False))

        self._set_stop_enabled(False)

    def _draw_stop_button(self, ring_color, enabled):
        c = self._stop_canvas
        c.delete("all")
        cx, cy, r = 26, 26, 20
        c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=ring_color, width=3, fill=CARD_BG)
        sq_s = 9
        # Square inside is white as requested
        sq_color = STOP_FILL if enabled else "#444444"
        c.create_rectangle(cx-sq_s, cy-sq_s, cx+sq_s, cy+sq_s, fill=sq_color, outline="")

    def _set_stop_enabled(self, enabled: bool):
        self._stop_enabled = enabled
        ring = STOP_RING if enabled else BORDER
        self._draw_stop_button(ring, enabled)

    def _on_stop_hover(self, entered: bool):
        if not self._stop_enabled: return
        color = STOP_HOVER if entered else STOP_RING
        self._draw_stop_button(color, True)

    def _on_canvas_click(self, event):
        if self._state == "idle":
            self._handle_start()

    def _on_stop_click(self, event):
        if self._state == "recording":
            self._handle_stop()

    def _handle_start(self):
        self.set_recording()
        self.on_start()

    def _handle_stop(self):
        self.set_processing()
        self.on_stop()

    def _start_idle_animation(self):
        if self._anim_job: self.root.after_cancel(self._anim_job)
        self._animate_idle()

    def _animate_idle(self):
        if self._state != "idle": return
        self._wave_phase += 0.08
        n = 60
        samples = [math.sin(self._wave_phase + i * 0.3) * 6 for i in range(n)]
        self._draw_waveform(samples, WAVE_IDLE, glow=False)
        self._anim_job = self.root.after(40, self._animate_idle)

    def _animate_recording(self):
        if self._state != "recording": return
        chunk = self._latest_chunk
        if chunk:
            arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            n = 60
            step = max(1, len(arr) // n)
            # Refined sensitivity: use a mix of local amplitude for higher dynamics
            bars = [abs(float(arr[i*step])) / 16384.0 * 24 for i in range(min(n, len(arr)//step))]
            while len(bars) < n: bars.append(0.0)
            bars = bars[:n]
            # Fast reaction for pitch-like feel
            self._wave_samples = [0.8 * bars[i] + 0.2 * self._wave_samples[i] for i in range(n)]
        else:
            self._wave_samples = [v * 0.85 for v in self._wave_samples]
        self._draw_waveform(self._wave_samples, WAVE_COLOR, glow=True)
        self._anim_job = self.root.after(40, self._animate_recording)

    def _draw_waveform(self, samples, color, glow=False):
        c = self._canvas
        c.delete("all")
        cw, ch = 340, 52
        mid = ch // 2
        n = len(samples)
        bar_w = max(2, (cw - n) // n)
        spacing = (cw - bar_w * n) / (n + 1)
        for i, amp in enumerate(samples):
            x = spacing + i * (bar_w + spacing)
            half = max(1, int(amp))
            y1, y2 = mid - half, mid + half
            if glow and amp > 4:
                c.create_rectangle(x - 1, y1 - 2, x + bar_w + 1, y2 + 2, fill=WAVE_GLOW, outline="", width=0)
            c.create_rectangle(x, y1, x + bar_w, y2, fill=color, outline="")

    def set_recording(self):
        self._state = "recording"
        if self._anim_job: self.root.after_cancel(self._anim_job)
        self._mic_dot.config(fg="#ef4444")
        self._status_lbl.config(text="Listening...", fg=TEXT_FG)
        self._set_stop_enabled(True)
        self._wave_samples = [0.0] * 60
        self._animate_recording()

    def set_processing(self):
        self._state = "processing"
        if self._anim_job: self.root.after_cancel(self._anim_job)
        self._mic_dot.config(fg="#f59e0b")
        self._status_lbl.config(text="Processing...", fg=SUBTEXT_FG)
        self._set_stop_enabled(False)
        self._draw_waveform(self._wave_samples, WAVE_IDLE, glow=False)

    def set_idle(self):
        self._state = "idle"
        self._mic_dot.config(fg=WAVE_IDLE)
        self._status_lbl.config(text="Click waveform to start", fg=SUBTEXT_FG)
        self._set_stop_enabled(False)
        self._canvas.config(cursor="hand2")
        self._start_idle_animation()

    def update_status(self, msg: str, color: str = TEXT_FG):
        self.root.after(0, lambda: self._status_lbl.config(text=msg, fg=color))

    def flash_copied(self, text: str):
        def _do_flash():
            self._mic_dot.config(fg=SUCCESS_FG)
            snippet = text[:30] + ("..." if len(text) > 30 else "")
            self._status_lbl.config(text=f"✅ Copied: {snippet}", fg=SUCCESS_FG)
            samples = [abs(math.sin(i * 0.4)) * 12 + 3 for i in range(60)]
            self._draw_waveform(samples, SUCCESS_FG, glow=False)
            self._flash_job = self.root.after(2500, self.set_idle)
        self.root.after(0, _do_flash)

    def update_meter(self, chunk_bytes: bytes):
        self._latest_chunk = chunk_bytes
