"""
app/recognizer.py
─────────────────
Converts a queue of raw PCM bytes into a transcribed text string.

Supported engines
-----------------
"google" — SpeechRecognition + Google Web Speech API  (internet required)
"vosk"   — Vosk offline model (run scripts/download_model.py first)

Public API
----------
Recognizer.recognize(audio_queue, on_result)
    Drains `audio_queue`, runs STT in a daemon thread,
    then calls on_result(text: str) when done.
    `text` is always a str — empty string "" on any failure.
"""

import json
import queue
import threading

import config


class Recognizer:
    def __init__(self):
        self._vosk_model = None
        if config.ENGINE == "vosk":
            self._init_vosk()

    # ── Public ────────────────────────────────────────────────────────────────

    def recognize(self, audio_queue: queue.Queue, on_result):
        """
        Spawn a daemon thread that drains `audio_queue`, runs STT,
        and calls `on_result(text: str)`.
        Non-blocking — returns immediately.
        """
        t = threading.Thread(
            target=self._run,
            args=(audio_queue, on_result),
            daemon=True,
        )
        t.start()

    # ── Private ───────────────────────────────────────────────────────────────

    def _init_vosk(self):
        try:
            from vosk import Model  # type: ignore
            self._vosk_model = Model(config.VOSK_MODEL_PATH)
        except Exception as exc:
            print(f"[Recognizer] Failed to load Vosk model: {exc}")
            print("[Recognizer] Falling back to Google engine.")

    def _run(self, audio_queue: queue.Queue, on_result):
        """Drain queue → assemble audio → transcribe → callback."""
        frames = []
        while not audio_queue.empty():
            try:
                frames.append(audio_queue.get_nowait())
            except queue.Empty:
                break

        raw_audio = b"".join(frames)

        if not raw_audio:
            print("[Recognizer] No audio recorded.")
            on_result("")
            return

        try:
            if config.ENGINE == "vosk" and self._vosk_model is not None:
                text = self._recognize_vosk(raw_audio)
            else:
                text = self._recognize_google(raw_audio)
        except Exception as exc:
            print(f"[Recognizer] Error during recognition: {exc}")
            text = ""

        print(f"[Recognizer] Result: {text!r}")
        on_result(text)

    # ── Google ────────────────────────────────────────────────────────────────

    def _recognize_google(self, raw: bytes) -> str:
        import speech_recognition as sr  # type: ignore

        recognizer = sr.Recognizer()
        # sample_width=2 because paInt16 is 2 bytes per sample
        audio_data = sr.AudioData(raw, config.SAMPLE_RATE, sample_width=2)

        try:
            return recognizer.recognize_google(audio_data, language=config.LANGUAGE)
        except sr.UnknownValueError:
            # Could not understand audio (silence, noise, unclear speech)
            return ""
        except sr.RequestError as exc:
            print(f"[Recognizer] Google API error: {exc}")
            return ""

    # ── Vosk ──────────────────────────────────────────────────────────────────

    def _recognize_vosk(self, raw: bytes) -> str:
        from vosk import KaldiRecognizer  # type: ignore

        rec = KaldiRecognizer(self._vosk_model, config.SAMPLE_RATE)

        # Feed audio in chunks to avoid memory spikes
        chunk_size = 4096
        for i in range(0, len(raw), chunk_size):
            rec.AcceptWaveform(raw[i : i + chunk_size])

        # FinalResult() flushes the remaining partial hypothesis
        result = json.loads(rec.FinalResult())
        return result.get("text", "")
