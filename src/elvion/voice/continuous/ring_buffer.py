"""Thread-safe circular audio buffer for continuous ambient streaming."""
from array import array
import io
from pathlib import Path
import struct
import threading
import wave


class AudioRingBuffer:
    """Stores a rolling window of 16 kHz 16-bit mono Linear PCM audio samples in RAM."""

    def __init__(self, capacity_seconds: float = 3.0, sample_rate: int = 16000):
        if capacity_seconds <= 0 or capacity_seconds > 30:
            raise ValueError("Capacity must be between 0.1 and 30 seconds")
        self.sample_rate = sample_rate
        self.bytes_per_sample = 2  # 16-bit
        self.channels = 1          # mono
        self.bytes_per_second = self.sample_rate * self.bytes_per_sample * self.channels
        self.max_bytes = int(capacity_seconds * self.bytes_per_second)
        # Ensure even number of bytes for 16-bit samples
        if self.max_bytes % 2 != 0:
            self.max_bytes += 1

        self._buffer = bytearray()
        self._lock = threading.Lock()

    @property
    def capacity_seconds(self) -> float:
        return self.max_bytes / self.bytes_per_second

    @property
    def duration_seconds(self) -> float:
        with self._lock:
            return len(self._buffer) / self.bytes_per_second

    def write(self, chunk: bytes) -> None:
        """Append incoming audio bytes, dropping oldest samples if capacity exceeded."""
        if not chunk:
            return
        with self._lock:
            self._buffer.extend(chunk)
            overflow = len(self._buffer) - self.max_bytes
            if overflow > 0:
                # Keep sample alignment (2 bytes per sample)
                if overflow % 2 != 0:
                    overflow += 1
                del self._buffer[:overflow]

    def read_recent(self, seconds: float) -> bytes:
        """Extract the most recent N seconds of audio without clearing the buffer."""
        if seconds <= 0:
            return b""
        requested_bytes = int(seconds * self.bytes_per_second)
        if requested_bytes % 2 != 0:
            requested_bytes += 1
        with self._lock:
            if requested_bytes >= len(self._buffer):
                return bytes(self._buffer)
            return bytes(self._buffer[-requested_bytes:])

    def read_all(self) -> bytes:
        """Extract all current audio in the buffer without clearing."""
        with self._lock:
            return bytes(self._buffer)

    def clear(self) -> None:
        """Discard all stored audio samples."""
        with self._lock:
            self._buffer.clear()

    def to_wav_bytes(self, pcm_bytes: bytes | None = None) -> bytes:
        """Convert raw Linear PCM bytes to a valid in-memory WAV container."""
        data = pcm_bytes if pcm_bytes is not None else self.read_all()
        stream = io.BytesIO()
        with wave.open(stream, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.bytes_per_sample)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(data)
        return stream.getvalue()

    def save_to_wav(self, destination: Path, pcm_bytes: bytes | None = None) -> None:
        """Write Linear PCM audio directly to a destination WAV file."""
        wav_data = self.to_wav_bytes(pcm_bytes)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(wav_data)
