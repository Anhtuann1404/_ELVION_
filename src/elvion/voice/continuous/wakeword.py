"""Lightweight wake-word detection for waking ELVION from ambient standby."""
from dataclasses import dataclass
import math
import re
import struct
import time
from typing import Callable, Protocol, runtime_checkable

from elvion.voice.continuous.hallucination import is_whisper_hallucination

WAKE_KEYWORDS = (
    "elvion", "hey elvion", "ê elvion", "ơi elvion", "elvion ơi",
)
_NORMALIZED_KEYWORD_RE = re.compile(
    r"\b(?:hey\s+|hi\s+|ê\s+|ơi\s+|ôi\s+)?"
    r"(?:el|eo|en|e|ê)\s*vi\s*[oô]n(?:\s+ơi)?\b"
    r"|\belvion\b",
    re.IGNORECASE,
)


def calculate_pcm_rms(audio_bytes: bytes) -> float:
    """Calculate Root Mean Square (RMS) energy of 16-bit Linear PCM audio."""
    if not audio_bytes or len(audio_bytes) < 2:
        return 0.0
    count = len(audio_bytes) // 2
    samples = struct.unpack(f"<{count}h", audio_bytes[: count * 2])
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / count)


def calculate_subframe_peak_rms(audio_bytes: bytes, window_samples: int = 1600, hop_samples: int = 800) -> float:
    """Calculate the maximum RMS across sliding sub-windows (100ms window, 50ms hop)."""
    if not audio_bytes or len(audio_bytes) < 4:
        return 0.0
    window_bytes = window_samples * 2
    hop_bytes = hop_samples * 2
    if len(audio_bytes) <= window_bytes:
        return calculate_pcm_rms(audio_bytes)

    max_rms = 0.0
    for i in range(0, len(audio_bytes) - window_bytes + 1, hop_bytes):
        chunk = audio_bytes[i : i + window_bytes]
        r = calculate_pcm_rms(chunk)
        if r > max_rms:
            max_rms = r
    return max_rms


@dataclass(frozen=True, kw_only=True)
class WakeWordResult:
    detected: bool
    keyword: str = ""
    confidence: float = 0.0
    timestamp: float = 0.0


@runtime_checkable
class WakeWordDetector(Protocol):
    def detect(self, audio_bytes: bytes, sample_rate: int = 16000) -> WakeWordResult:
        ...

    def reset(self) -> None:
        ...


class KeywordWakeWordDetector:
    """Acoustic cadence pre-filter with optional delegated micro-transcriber or mock for testing."""

    def __init__(
        self,
        *,
        keywords: tuple[str, ...] = WAKE_KEYWORDS,
        threshold: float = 0.65,
        verifier: Callable[[bytes], str] | None = None,
        clock: Callable[[], float] = time.monotonic,
        min_check_interval: float = 0.4,
        energy_threshold: float = 140.0,
        ambient_window_seconds: float | None = None,
        on_diagnostic: Callable[[dict], None] | None = None,
    ):
        self.keywords = keywords
        self.threshold = threshold
        self.verifier = verifier
        self.clock = clock
        self.min_check_interval = float(min_check_interval)
        self.energy_threshold = float(energy_threshold)
        self.ambient_window_seconds = ambient_window_seconds
        self.on_diagnostic = on_diagnostic
        self._last_check_time = 0.0
        self._simulated_matches: list[WakeWordResult] = []

    def set_simulated_detection(self, keyword: str = "elvion", confidence: float = 0.95) -> None:
        """Inject a simulated detection for hermetic unit testing."""
        self._simulated_matches.append(
            WakeWordResult(detected=True, keyword=keyword, confidence=confidence, timestamp=self.clock())
        )

    def detect(self, audio_bytes: bytes, sample_rate: int = 16000) -> WakeWordResult:
        """Inspect recent audio buffer slice to determine if wake word was uttered."""
        # 1. Check for simulated/test detections first
        if self._simulated_matches:
            return self._simulated_matches.pop(0)

        now = self.clock()
        if not audio_bytes or len(audio_bytes) < 8000:  # STT requires at least 250ms
            return WakeWordResult(detected=False, timestamp=now)

        if self.ambient_window_seconds is not None:
            window_bytes = int(self.ambient_window_seconds * sample_rate) * 2
            if len(audio_bytes) < window_bytes:
                return WakeWordResult(detected=False, timestamp=now)

        # 2. If a micro-verifier (e.g. PhoWhisper slice) is attached, run fast transcript check
        if self.verifier is not None:
            if now - self._last_check_time < self.min_check_interval:
                return WakeWordResult(detected=False, timestamp=now)

            # Evaluate both peak sub-window and average RMS so speech bursts are not lost in silence
            peak_rms = calculate_subframe_peak_rms(audio_bytes)
            avg_rms = calculate_pcm_rms(audio_bytes)
            effective_rms = max(peak_rms, avg_rms)
            if effective_rms < self.energy_threshold:
                self._diagnostic(reason="below_energy", rms=round(effective_rms))
                return WakeWordResult(detected=False, timestamp=now)

            if self.ambient_window_seconds is not None:
                block_bytes = (sample_rate // 10) * 2
                levels = [calculate_pcm_rms(audio_bytes[offset:offset + block_bytes])
                          for offset in range(0, len(audio_bytes) - block_bytes + 1, block_bytes)]
                floor = sorted(levels)[len(levels) // 4]
                speech_threshold = max(self.energy_threshold, floor * 2)
                if sum(level >= speech_threshold for level in levels) < 2:
                    self._diagnostic(reason="ambient_only", rms=round(effective_rms), floor_rms=round(floor))
                    return WakeWordResult(detected=False, timestamp=now)

            self._last_check_time = now
            started = time.monotonic()
            self._diagnostic(reason="transcribing", rms=round(effective_rms))
            try:
                transcript = self.verifier(audio_bytes).strip().lower()
                matched = bool(transcript and not is_whisper_hallucination(transcript) and self._matches_text(transcript))
                self._diagnostic(reason="matched" if matched else "keyword_mismatch",
                                 rms=round(effective_rms), text=transcript[:2048],
                                 inference_ms=round((time.monotonic() - started) * 1000))
                if matched:
                    return WakeWordResult(
                        detected=True,
                        keyword="elvion",
                        confidence=0.92,
                        timestamp=now,
                    )
            except Exception as exc:
                from elvion.voice.input.types import VoiceInputError
                self._diagnostic(reason="stt_error", code=exc.code if isinstance(exc, VoiceInputError) else "WAKE_VERIFIER_FAILED")

        # Default non-detection
        return WakeWordResult(detected=False, timestamp=now)

    def _diagnostic(self, **event) -> None:
        # Opt-in terminal callback only; no ambient transcript retained or logged.
        if self.on_diagnostic is not None:
            try:
                self.on_diagnostic(event)
            except Exception:
                pass

    def _matches_text(self, text: str) -> bool:
        norm = text.lower().strip()
        cleaned = re.sub(r"[^\w\s]", " ", norm)
        words = cleaned.split()
        # Observed ASR substitution for the complete Vietnamese call.
        if words == ["alvin", "ơi"]:
            return True
        tokens = set(words)

        for kw in self.keywords:
            kw_parts = kw.lower().split()
            if len(kw_parts) == 1:
                if kw_parts[0] in tokens:
                    return True
            else:
                pattern = r"\b" + r"\s+".join(re.escape(p) for p in kw_parts) + r"\b"
                if re.search(pattern, norm):
                    return True

        return bool(_NORMALIZED_KEYWORD_RE.search(norm))

    def reset(self) -> None:
        self._simulated_matches.clear()
        self._last_check_time = 0.0
