"""Lightweight, adaptive Voice Activity Detector (VAD) using Energy and ZCR."""
from array import array
from enum import StrEnum
import math
import sys


class VADState(StrEnum):
    SILENCE = "silence"
    SPEECH_STARTED = "speech_started"
    SPEAKING = "speaking"
    SPEECH_ENDED = "speech_ended"


class VoiceActivityDetector:
    """Frame-by-frame Voice Activity Detector with adaptive noise floor and silence hangover."""

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
        min_speech_rms: float = 300.0,
        speech_multiplier: float = 2.8,
        speech_onset_frames: int = 3,
        silence_hangover_ms: int = 800,
        max_speech_duration_ms: int = 15000,
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.samples_per_frame = int(sample_rate * (frame_duration_ms / 1000.0))
        self.bytes_per_frame = self.samples_per_frame * 2  # 16-bit = 2 bytes

        self.min_speech_rms = float(min_speech_rms)
        self.speech_multiplier = float(speech_multiplier)
        self.speech_onset_frames = max(1, speech_onset_frames)
        self.silence_hangover_frames = max(1, int(silence_hangover_ms / frame_duration_ms))
        self.max_speech_frames = max(1, int(max_speech_duration_ms / frame_duration_ms))

        self.noise_floor = float(min_speech_rms * 0.4)
        self.state = VADState.SILENCE

        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._total_speech_frames = 0

    def compute_rms(self, frame_bytes: bytes) -> float:
        """Calculate Root Mean Square (RMS) amplitude of audio frame."""
        if len(frame_bytes) < 2:
            return 0.0
        samples = array("h", frame_bytes)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return 0.0
        total_sq = sum(int(s) * int(s) for s in samples)
        return math.sqrt(total_sq / len(samples))

    def compute_zcr(self, frame_bytes: bytes) -> float:
        """Calculate Zero Crossing Rate (ZCR) of audio frame."""
        if len(frame_bytes) < 4:
            return 0.0
        samples = array("h", frame_bytes)
        if sys.byteorder != "little":
            samples.byteswap()
        crossings = 0
        for i in range(1, len(samples)):
            if (samples[i] >= 0 and samples[i - 1] < 0) or (samples[i] < 0 and samples[i - 1] >= 0):
                crossings += 1
        return crossings / len(samples)

    def process_frame(self, frame_bytes: bytes) -> VADState:
        """Process one audio frame and return the updated VAD state."""
        rms = self.compute_rms(frame_bytes)
        threshold = max(self.min_speech_rms, self.noise_floor * self.speech_multiplier)
        is_frame_speech = rms >= threshold

        if self.state == VADState.SILENCE:
            if is_frame_speech:
                self._consecutive_speech_frames += 1
                if self._consecutive_speech_frames >= self.speech_onset_frames:
                    self.state = VADState.SPEECH_STARTED
                    self._consecutive_silence_frames = 0
                    self._total_speech_frames = self._consecutive_speech_frames
            else:
                self._consecutive_speech_frames = 0
                # Adapt noise floor slowly during silence (bounded below speech threshold)
                self.noise_floor = min(self.min_speech_rms * 0.85, 0.95 * self.noise_floor + 0.05 * rms)

        elif self.state in (VADState.SPEECH_STARTED, VADState.SPEAKING):
            self.state = VADState.SPEAKING
            self._total_speech_frames += 1

            if is_frame_speech:
                self._consecutive_silence_frames = 0
            else:
                self._consecutive_silence_frames += 1

            # Check for end of speech (silence hangover met or max speech exceeded)
            if (
                self._consecutive_silence_frames >= self.silence_hangover_frames
                or self._total_speech_frames >= self.max_speech_frames
            ):
                self.state = VADState.SPEECH_ENDED

        elif self.state == VADState.SPEECH_ENDED:
            # Remains ended until reset
            pass

        return self.state

    def reset(self) -> None:
        """Reset state tracking back to silence while preserving estimated noise floor."""
        self.state = VADState.SILENCE
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._total_speech_frames = 0

    @property
    def is_speech_active(self) -> bool:
        return self.state in (VADState.SPEECH_STARTED, VADState.SPEAKING)
