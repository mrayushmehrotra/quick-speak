# ──────────────────────────────────────────────────────────────────────────────
# QuickSpeak — Configuration
# Edit these values to customise the app behaviour.
# ──────────────────────────────────────────────────────────────────────────────

# ── Speech Engine ─────────────────────────────────────────────────────────────
# "google" — uses Google Speech Recognition API (needs internet)
# "vosk"   — offline recognition (run scripts/download_model.py first)
ENGINE = "google"

# BCP-47 language code (used by Google engine)
LANGUAGE = "en-US"

# ── Vosk (offline) ────────────────────────────────────────────────────────────
# Path to the Vosk model directory (relative to project root)
VOSK_MODEL_PATH = "models/vosk-model"

# ── Audio Capture ─────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000   # Hz  — Vosk requires 16000; Google works fine with it too
CHANNELS    = 1       # Mono
CHUNK_SIZE  = 1024    # PCM frames per read

# ── GUI ───────────────────────────────────────────────────────────────────────
WINDOW_TITLE   = "QuickSpeak"
WINDOW_WIDTH   = 280
WINDOW_HEIGHT  = 120
WINDOW_OPACITY = 0.93   # 0.0 = fully transparent · 1.0 = fully opaque
ALWAYS_ON_TOP  = True   # Float above all other windows

# ── Typing ────────────────────────────────────────────────────────────────────
TYPE_DELAY_MS = 12     # Milliseconds between xdotool keystrokes
APPEND_SPACE  = True   # Append a trailing space after the typed text
