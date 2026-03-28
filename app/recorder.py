"""
app/recorder.py
───────────────
Captures microphone audio into a thread-safe queue.

Public API
----------
Recorder.start()             — open mic stream and begin capture thread
Recorder.stop()              — signal stop, join thread, close stream
Recorder.get_audio_queue()   — returns queue.Queue of raw PCM bytes chunks
Recorder.get_latest_chunk()  — returns the most recently captured chunk (for meter)
"""

import threading
import queue
import pyaudio
import config


class Recorder:
    def __init__(self):
        self._pa            = pyaudio.PyAudio()
        self._queue: queue.Queue = queue.Queue()
        self._stop_evt      = threading.Event()
        self._thread        = None
        self._stream        = None
        self._latest_chunk  = b""   # updated by capture thread; read by meter

    # ── Public methods ────────────────────────────────────────────────────────

    def start(self):
        """Open microphone stream and start background capture thread."""
        # Drain any leftover frames from the previous recording session
        self._drain_queue()
        self._latest_chunk = b""
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
        """
        Signal the capture thread to stop, wait for it to finish,
        then close the audio stream.
        Does NOT call pyaudio.terminate() so the instance can be reused.
        """
        self._stop_evt.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

    def get_audio_queue(self) -> queue.Queue:
        """Return the queue that receives raw PCM bytes chunks."""
        return self._queue

    def get_latest_chunk(self) -> bytes:
        """Return the most recently captured PCM chunk (used for the level meter)."""
        return self._latest_chunk

    # ── Private ───────────────────────────────────────────────────────────────

    def _capture(self):
        """Background thread: reads from mic and enqueues PCM chunks."""
        while not self._stop_evt.is_set():
            try:
                data = self._stream.read(
                    config.CHUNK_SIZE,
                    exception_on_overflow=False,  # avoids crash on buffer overrun
                )
                self._queue.put(data)
                self._latest_chunk = data
            except OSError:
                # Stream was closed externally — exit gracefully
                break

    def _drain_queue(self):
        """Discard any lingering items in the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def __del__(self):
        """Cleanup PyAudio on GC."""
        try:
            self._pa.terminate()
        except Exception:
            pass
