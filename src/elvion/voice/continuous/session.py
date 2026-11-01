"""Continuous, hands-free conversational voice session with wake-word and session retention."""
from enum import StrEnum
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable

from elvion.voice.continuous.hallucination import is_whisper_hallucination
from elvion.voice.continuous.ring_buffer import AudioRingBuffer
from elvion.voice.continuous.vad import VADState, VoiceActivityDetector
from elvion.voice.continuous.wakeword import (
    KeywordWakeWordDetector, WakeWordDetector, WakeWordResult, calculate_pcm_rms,
)


class ContinuousSessionState(StrEnum):
    STANDBY = "standby"          # Ambient listening for wake word ("ELVION")
    AWAKE = "awake"              # Wake word recognized, brief chime/acknowledgment
    LISTENING = "listening"      # VAD actively streaming user query
    PROCESSING = "processing"    # Transcribing and routing through agent pipeline
    SPEAKING = "speaking"        # Generating voice response via TTS
    FOLLOW_UP = "follow_up"      # Open-ear window (3-5s) waiting for continuous follow-up


class ContinuousVoiceSession:
    """Hands-free session manager composing VoiceSession without modifying existing code."""

    def __init__(
        self,
        *,
        voice_session=None,
        wake_detector: WakeWordDetector | None = None,
        vad: VoiceActivityDetector | None = None,
        ring_buffer: AudioRingBuffer | None = None,
        follow_up_seconds: float = 5.0,
        listen_timeout_seconds: float = 3.5,
        clock: Callable[[], float] = time.monotonic,
        on_state_change: Callable[[ContinuousSessionState], None] | None = None,
        on_wake: Callable[[WakeWordResult], None] | None = None,
        on_transcript: Callable[[str], None] | None = None,
        on_reply: Callable[[str], None] | None = None,
        wake_slice_seconds: float = 1.5,
        min_utterance_bytes: int = 1280,
    ):
        self.voice_session = voice_session
        self.wake_detector = wake_detector if wake_detector is not None else KeywordWakeWordDetector(clock=clock)
        self.vad = vad if vad is not None else VoiceActivityDetector()
        self.ring_buffer = ring_buffer if ring_buffer is not None else AudioRingBuffer(capacity_seconds=4.0)

        self.follow_up_seconds = float(follow_up_seconds)
        self.listen_timeout_seconds = float(listen_timeout_seconds)
        self.clock = clock
        self.wake_slice_seconds = float(wake_slice_seconds)
        self.min_utterance_bytes = int(min_utterance_bytes)

        self.on_state_change = on_state_change
        self.on_wake = on_wake
        self.on_transcript = on_transcript
        self.on_reply = on_reply

        self.state = ContinuousSessionState.STANDBY
        self._lock = threading.Lock()
        self._active_utterance_pcm = bytearray()
        self._follow_up_deadline = 0.0
        self._listen_deadline = 0.0
        self._running = False
        self._last_processed_transcript = ""

    def _set_state(self, new_state: ContinuousSessionState) -> None:
        if self.state != new_state:
            self.state = new_state
            if self.on_state_change is not None:
                try:
                    self.on_state_change(new_state)
                except Exception:
                    pass

    def start(self) -> None:
        """Start the continuous hands-free session loop."""
        with self._lock:
            self._running = True
            self._set_state(ContinuousSessionState.STANDBY)
            self.ring_buffer.clear()
            self.vad.reset()

    def stop(self) -> None:
        """Stop the session and release in-memory audio buffers."""
        with self._lock:
            self._running = False
            self._set_state(ContinuousSessionState.STANDBY)
            self.ring_buffer.clear()
            self._active_utterance_pcm.clear()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def feed_audio(self, chunk: bytes) -> None:
        """Ingest streaming audio frame (16 kHz 16-bit mono Linear PCM)."""
        with self._lock:
            if not self._running:
                return

            # Always maintain rolling ambient window in ring buffer
            self.ring_buffer.write(chunk)
            now = self.clock()

            # -------------------------------------------------------------
            # State 1: STANDBY (Listening for Wake Word)
            # -------------------------------------------------------------
            if self.state == ContinuousSessionState.STANDBY:
                slice_bytes = self.ring_buffer.read_recent(self.wake_slice_seconds)
                detection = self.wake_detector.detect(slice_bytes)
                if detection.detected:
                    if self.on_wake is not None:
                        try:
                            self.on_wake(detection)
                        except Exception:
                            pass
                    self._set_state(ContinuousSessionState.AWAKE)
                    # Prepare for speech capture
                    self.vad.reset()
                    self._active_utterance_pcm.clear()
                    self._listen_deadline = now + self.listen_timeout_seconds
                    self._set_state(ContinuousSessionState.LISTENING)

            # -------------------------------------------------------------
            # State 2: FOLLOW_UP (Waiting for speech without needing wake word)
            # -------------------------------------------------------------
            elif self.state == ContinuousSessionState.FOLLOW_UP:
                if now >= self._follow_up_deadline:
                    # Follow-up timeout expired -> return to standby
                    self._set_state(ContinuousSessionState.STANDBY)
                    self.vad.reset()
                else:
                    vad_state = self.vad.process_frame(chunk)
                    if vad_state == VADState.SPEECH_STARTED:
                        # User spoke again! Transition directly to LISTENING
                        self._set_state(ContinuousSessionState.LISTENING)
                        self._active_utterance_pcm.clear()
                        self._active_utterance_pcm.extend(chunk)
                        self._listen_deadline = now + self.listen_timeout_seconds

            # -------------------------------------------------------------
            # State 3: LISTENING (Capturing speech until silence or limit)
            # -------------------------------------------------------------
            elif self.state == ContinuousSessionState.LISTENING:
                # If user hasn't started speaking and listening timeout expired -> abort to standby
                if self.vad.state == VADState.SILENCE and now >= self._listen_deadline:
                    self._set_state(ContinuousSessionState.STANDBY)
                    self._active_utterance_pcm.clear()
                    self.vad.reset()
                    return

                self._active_utterance_pcm.extend(chunk)
                vad_state = self.vad.process_frame(chunk)
                if vad_state == VADState.SPEECH_ENDED:
                    # User finished speaking! Transition to PROCESSING
                    self._set_state(ContinuousSessionState.PROCESSING)
                    utterance_pcm = bytes(self._active_utterance_pcm)
                    self._active_utterance_pcm.clear()
                    self._dispatch_utterance(utterance_pcm)

    def _dispatch_utterance(self, pcm_data: bytes) -> None:
        """Process captured speech through existing VoiceSession without altering it."""
        if not pcm_data or len(pcm_data) < self.min_utterance_bytes:
            # Too short or noise -> revert to standby
            self._set_state(ContinuousSessionState.STANDBY)
            self.vad.reset()
            return

        # Check utterance energy: reject low-amplitude ambient noise (RMS < 280)
        rms = calculate_pcm_rms(pcm_data)
        if rms < 280.0:
            self._set_state(ContinuousSessionState.STANDBY)
            self.vad.reset()
            return

        with tempfile.TemporaryDirectory(prefix="elvion-handsfree-") as tmp_dir:
            wav_path = Path(tmp_dir) / "input.wav"
            self.ring_buffer.save_to_wav(wav_path, pcm_bytes=pcm_data)

            transcript = ""
            reply_text = ""

            try:
                # 1. Use existing voice_input transcriber if available
                if self.voice_session is not None and hasattr(self.voice_session, "voice_input"):
                    vi = self.voice_session.voice_input
                    if hasattr(vi, "transcribe"):
                        res = vi.transcribe(wav_path)
                        transcript = res.text if hasattr(res, "text") else str(res)
                    elif hasattr(vi, "transcriber") and hasattr(vi.transcriber, "transcribe"):
                        res = vi.transcriber.transcribe(wav_path)
                        transcript = res.text if hasattr(res, "text") else str(res)

                # Filter out empty or Whisper phantom hallucinations
                if transcript and not is_whisper_hallucination(transcript):
                    self._last_processed_transcript = transcript
                    if self.on_transcript is not None:
                        self.on_transcript(transcript)

                    # 2. If voice_session has interactive execution, route query
                    if self.voice_session is not None:
                        if hasattr(self.voice_session, "conversation_bridge") and self.voice_session.conversation_bridge is not None:
                            bridge_res = self.voice_session.conversation_bridge.handle(transcript)
                            reply_text = getattr(bridge_res, "text", "") or ""
                        elif hasattr(self.voice_session, "handle_utterance"):
                            reply_text = self.voice_session.handle_utterance(transcript)

                # 3. Speak reply via TTS if output service available
                if reply_text and self.on_reply is not None:
                    self._set_state(ContinuousSessionState.SPEAKING)
                    self.on_reply(reply_text)

            except Exception:
                pass

        # If no valid transcript or reply was produced, gracefully sleep
        if not reply_text:
            self._set_state(ContinuousSessionState.STANDBY)
            self.vad.reset()
            return

        # Complete turn and transition to FOLLOW_UP
        self._set_state(ContinuousSessionState.FOLLOW_UP)
        self._follow_up_deadline = self.clock() + self.follow_up_seconds
        self.vad.reset()

    def tick(self) -> None:
        """Periodic clock maintenance (checks follow-up and listening timeout expiration)."""
        with self._lock:
            if not self._running:
                return
            now = self.clock()
            if self.state == ContinuousSessionState.FOLLOW_UP:
                if now >= self._follow_up_deadline:
                    self._set_state(ContinuousSessionState.STANDBY)
                    self.vad.reset()
            elif self.state == ContinuousSessionState.LISTENING:
                if self.vad.state == VADState.SILENCE and now >= self._listen_deadline:
                    self._set_state(ContinuousSessionState.STANDBY)
                    self._active_utterance_pcm.clear()
                    self.vad.reset()
                return
            if self.state == ContinuousSessionState.FOLLOW_UP:
                if self.clock() >= self._follow_up_deadline:
                    self._set_state(ContinuousSessionState.STANDBY)
                    self.vad.reset()
