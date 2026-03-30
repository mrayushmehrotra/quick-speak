"""
app/gui.py
──────────
Sleek floating overlay matching the sketch design with rounded corners:
  ┌─────────────────────────────────────────────────────┐
  │  ( ~~~ rounded waveform ~~~ )  ( ◼ stop button )    │
  └─────────────────────────────────────────────────────┘

Implements rounded window corners via transparency and a drawn pill shape.
Waveform bars are also rounded for a premium feel.
"""

import tkinter as tk
import math
import numpy as np
import config

# ── Colour palette ────────────────────────────────────────────────────────────
BG          = "#000000"          # black background
CARD_BG     = "#111111"          # subtle grey-black for the pill
BORDER      = "#333333"          # subtle border
WAVE_IDLE   = "#333333"          # grey when idle
WAVE_COLOR  = "#ffffff"          # always white
WAVE_GLOW   = "#ffffff"          # soft white glow
STOP_RING   = "#ef4444"          # red ring
STOP_FILL   = "#ffffff"          # white square
STOP_HOVER  = "#dc2626"          # darker red hover
TEXT_FG     = "#e2e8f0"
SUBTEXT_FG  = "#64748b"
SUCCESS_FG  = "#4ade80"

# Window dimensions
W = 460
H = 100
RADIUS = 25  # for rounded corners

class GUI:
    def __init__(self, root: tk.Tk, on_start, on_stop):
        self.root     = root
        self.on_start = on_start
        self.on_stop  = on_stop

        # Internal state
        self._state        = "idle"
        self._wave_samples = [0.0] * 60
        self._wave_phase   = 0.0
        self._anim_job     = None
        self._flash_job    = None
        self._latest_chunk = b""
        self._stop_enabled = False

        self._setup_window()
        self._build_ui()
        self._start_idle_animation()

    def _setup_window(self):
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", config.ALWAYS_ON_TOP)
        
        # Transparent background for rounded corners
        # On Linux, this requires a compositor.
        self.root.wait_visibility(self.root)
        try:
            self.root.wm_attributes("-transparentcolor", "black") # Windows fallback
            self.root.config(bg="black")
            self.root.attributes("-alpha", config.WINDOW_OPACITY)
        except tk.TclError:
            pass

        # Draggable
        self.root.bind("<Button-1>", self._start_move)
        self.root.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def _build_ui(self):
        # Main background canvas for the pill shape
        self._bg_canvas = tk.Canvas(self.root, width=W, height=H, bg="black", highlightthickness=0)
        self._bg_canvas.pack(fill="both", expand=True)

        # Draw the main pill background
        self._draw_rounded_rect(self._bg_canvas, 10, 10, W-10, H-10, 20, fill=CARD_BG, outline=BORDER, width=1)

        # ── Status bar area ──────────────────────────────────────────────────
        self._status_area = tk.Canvas(self._bg_canvas, width=300, height=20, bg=CARD_BG, highlightthickness=0)
        self._bg_canvas.create_window(W//2 - 50, 25, window=self._status_area)
        
        self._status_lbl = tk.Label(self._status_area, text="Click waveform to start", fg=SUBTEXT_FG, bg=CARD_BG, font=("Helvetica", 9))
        self._status_lbl.pack(side="left")

        close_btn = tk.Label(self._bg_canvas, text="×", fg=SUBTEXT_FG, bg=CARD_BG, font=("Helvetica", 14), cursor="hand2")
        self._bg_canvas.create_window(W-30, 28, window=close_btn)
        close_btn.bind("<Button-1>", lambda _: self.root.destroy())

        # ── Waveform Canvas ──────────────────────────────────────────────────
        self._canvas = tk.Canvas(self.root, bg=CARD_BG, highlightthickness=0, width=340, height=52)
        self._bg_canvas.create_window(190, 60, window=self._canvas)
        self._canvas.bind("<Button-1>", self._on_canvas_click)

        # ── Stop Button ──────────────────────────────────────────────────────
        self._stop_canvas = tk.Canvas(self.root, bg=CARD_BG, highlightthickness=0, width=52, height=52)
        self._bg_canvas.create_window(W-55, 60, window=self._stop_canvas)
        self._draw_stop_button(STOP_RING, False)
        self._stop_canvas.bind("<Button-1>", self._on_stop_click)
        self._stop_canvas.bind("<Enter>", lambda _: self._on_stop_hover(True))
        self._stop_canvas.bind("<Leave>", lambda _: self._on_stop_hover(False))

    def _draw_stop_button(self, ring_color, enabled):
        c = self._stop_canvas
        c.delete("all")
        cx, cy, r = 26, 26, 20
        c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=ring_color, width=3, fill=CARD_BG)
        sq_s = 9
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
            self.set_recording()
            self.on_start()

    def _on_stop_click(self, event):
        if self._state == "recording":
            self.set_processing()
            self.on_stop()

    def _start_idle_animation(self):
        if self._anim_job: self.root.after_cancel(self._anim_job)
        self._animate_idle()

    def _animate_idle(self):
        if self._state != "idle": return
        self._wave_phase += 0.08
        samples = [math.sin(self._wave_phase + i * 0.3) * 6 for i in range(60)]
        self._draw_waveform(samples, WAVE_IDLE)
        self._anim_job = self.root.after(40, self._animate_idle)

    def _animate_recording(self):
        if self._state != "recording": return
        chunk = self._latest_chunk
        if chunk:
            arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            n = 60
            step = max(1, len(arr) // n)
            bars = [abs(float(arr[i*step])) / 16384.0 * 24 for i in range(min(n, len(arr)//step))]
            while len(bars) < n: bars.append(0.0)
            bars = bars[:n]
            self._wave_samples = [0.8 * bars[i] + 0.2 * self._wave_samples[i] for i in range(n)]
        else:
            self._wave_samples = [v * 0.85 for v in self._wave_samples]
        self._draw_waveform(self._wave_samples, WAVE_COLOR)
        self._anim_job = self.root.after(40, self._animate_recording)

    def _draw_waveform(self, samples, color):
        c = self._canvas
        c.delete("all")
        cw, ch = 340, 52
        mid = ch // 2
        n = len(samples)
        bar_w = max(3, (cw - n*2) // n) # Slightly thicker bars for better rounding
        spacing = (cw - bar_w * n) / (n + 1)
        
        for i, amp in enumerate(samples):
            x = spacing + i * (bar_w + spacing)
            half = max(2, int(amp))
            y1, y2 = mid - half, mid + half
            
            # Using a line with round caps to simulate a rounded rectangle bar
            c.create_line(x+bar_w/2, y1, x+bar_w/2, y2, fill=color, width=bar_w, capstyle="round")

    def set_recording(self):
        self._state = "recording"
        if self._anim_job: self.root.after_cancel(self._anim_job)
        self._status_lbl.config(text="Listening...", fg="#ef4444")
        self._set_stop_enabled(True)
        self._animate_recording()

    def set_processing(self):
        self._state = "processing"
        if self._anim_job: self.root.after_cancel(self._anim_job)
        self._status_lbl.config(text="Processing...", fg="#f59e0b")
        self._set_stop_enabled(False)
        self._draw_waveform(self._wave_samples, WAVE_IDLE)

    def set_idle(self):
        self._state = "idle"
        self._status_lbl.config(text="Click waveform to start", fg=SUBTEXT_FG)
        self._set_stop_enabled(False)
        self._start_idle_animation()

    def update_status(self, msg: str, color: str = TEXT_FG):
        self.root.after(0, lambda: self._status_lbl.config(text=msg, fg=color))

    def flash_copied(self, text: str):
        def _do_flash():
            snippet = text[:30] + ("..." if len(text) > 30 else "")
            self._status_lbl.config(text=f"✅ Copied: {snippet}", fg=SUCCESS_FG)
            samples = [abs(math.sin(i * 0.4)) * 12 + 3 for i in range(60)]
            self._draw_waveform(samples, SUCCESS_FG)
            self._flash_job = self.root.after(2500, self.set_idle)
        self.root.after(0, _do_flash)

    def update_meter(self, chunk_bytes: bytes):
        self._latest_chunk = chunk_bytes
