"""Continuous hands-free voice interaction: wake word, VAD, and conversational session retention."""
from elvion.voice.continuous.ring_buffer import AudioRingBuffer
from elvion.voice.continuous.session import ContinuousSessionState, ContinuousVoiceSession
from elvion.voice.continuous.streamer import build_stream_helper, is_stream_helper_ready, open_live_audio_stream
from elvion.voice.continuous.vad import VADState, VoiceActivityDetector
from elvion.voice.continuous.wakeword import (
    KeywordWakeWordDetector, WakeWordDetector, WakeWordResult, calculate_pcm_rms,
)

__all__ = [
    "AudioRingBuffer",
    "ContinuousSessionState",
    "ContinuousVoiceSession",
    "KeywordWakeWordDetector",
    "VADState",
    "VoiceActivityDetector",
    "WakeWordDetector",
    "WakeWordResult",
    "build_stream_helper",
    "calculate_pcm_rms",
    "is_stream_helper_ready",
    "open_live_audio_stream",
]
