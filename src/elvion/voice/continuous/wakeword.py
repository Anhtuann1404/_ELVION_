"""Lightweight wake-word detection for waking ELVION from ambient standby."""
from dataclasses import dataclass
import math
import re
import struct
import time
from typing import Callable, Protocol, runtime_checkable

WAKE_KEYWORDS = ("elvion", "hey elvion", "ê elvion", "ơi elvion", "elvion ơi")
_NORMALIZED_KEYWORD_RE = re.compile(
    r"\b(?:hey\s+|ê\s+|ơi\s+)?(?:e[ol]|ai|eo|em|en)\s*vi[oôe]?n?\b",
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
        energy_threshold: float = 300.0,
    ):
        self.keywords = keywords
        self.threshold = threshold
        self.verifier = verifier
        self.clock = clock
        self.min_check_interval = float(min_check_interval)
        self.energy_threshold = float(energy_threshold)
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
        if not audio_bytes or len(audio_bytes) < 3200:  # Need at least 100ms
            return WakeWordResult(detected=False, timestamp=now)

        # 2. If a micro-verifier (e.g. PhoWhisper slice) is attached, run fast transcript check
        if self.verifier is not None:
            if now - self._last_check_time < self.min_check_interval:
                return WakeWordResult(detected=False, timestamp=now)
            rms = calculate_pcm_rms(audio_bytes)
            if rms < self.energy_threshold:
                return WakeWordResult(detected=False, timestamp=now)

            self._last_check_time = now
            try:
                transcript = self.verifier(audio_bytes).strip().lower()
                if self._matches_text(transcript):
                    return WakeWordResult(
                        detected=True,
                        keyword="elvion",
                        confidence=0.92,
                        timestamp=now,
                    )
            except Exception:
                pass

        # Default non-detection
        return WakeWordResult(detected=False, timestamp=now)

    def _matches_text(self, text: str) -> bool:
        norm = text.lower().strip()
        cleaned = re.sub(r"[^\w\s]", " ", norm)
        tokens = cleaned.split()
        joined = " ".join(tokens)
        for kw in self.keywords:
            if kw in joined:
                return True
        return bool(_NORMALIZED_KEYWORD_RE.search(joined))

    def reset(self) -> None:
        self._simulated_matches.clear()
        self._last_check_time = 0.0
