"""Comprehensive test suite for continuous hands-free voice interaction.

Hermetic verification of:
1. AudioRingBuffer: memory bounds, alignment, circular roll-over, WAV export.
2. VoiceActivityDetector: RMS, adaptive noise floor, onset, silence hangover, cutoff.
3. KeywordWakeWordDetector: keyword matching, verifier delegation, simulation.
4. ContinuousVoiceSession: ambient standby, wake word triggering, speech capture,
   conversational follow-up retention, timeout back to standby, privacy.
"""
from array import array
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from elvion.voice.continuous.ring_buffer import AudioRingBuffer
from elvion.voice.continuous.session import ContinuousSessionState, ContinuousVoiceSession
from elvion.voice.continuous.vad import VADState, VoiceActivityDetector
from elvion.voice.continuous.wakeword import KeywordWakeWordDetector, WakeWordResult


def make_sine_pcm(freq_hz: float = 440.0, duration_seconds: float = 0.1, amplitude: float = 12000.0) -> bytes:
    """Generate Linear PCM 16 kHz 16-bit mono sine wave samples."""
    sample_rate = 16000
    total_samples = int(sample_rate * duration_seconds)
    samples = array("h")
    for i in range(total_samples):
        val = int(amplitude * math.sin(2 * math.pi * freq_hz * (i / sample_rate)))
        samples.append(max(-32768, min(32767, val)))
    return samples.tobytes()


def make_silence_pcm(duration_seconds: float = 0.1, amplitude: float = 10.0) -> bytes:
    """Generate near-silent ambient PCM audio samples."""
    return make_sine_pcm(freq_hz=60.0, duration_seconds=duration_seconds, amplitude=amplitude)


class ContinuousVoiceTests(unittest.TestCase):

    # =========================================================================
    # Group 1: AudioRingBuffer Tests
    # =========================================================================

    def test_ring_buffer_capacity_and_overflow(self):
        """Ring buffer strictly bounds memory and discards oldest samples upon overflow."""
        # 1.0 second capacity = 32,000 bytes at 16kHz 16-bit mono
        buf = AudioRingBuffer(capacity_seconds=1.0)
        self.assertEqual(buf.capacity_seconds, 1.0)
        self.assertEqual(buf.duration_seconds, 0.0)

        # Write 0.5s of audio (16,000 bytes)
        half_sec = make_sine_pcm(duration_seconds=0.5)
        buf.write(half_sec)
        self.assertAlmostEqual(buf.duration_seconds, 0.5, places=2)

        # Write another 0.8s (25,600 bytes) -> Total 41,600 > 32,000 cap
        point_eight_sec = make_sine_pcm(duration_seconds=0.8)
        buf.write(point_eight_sec)
        # Buffer must be capped at 1.0s
        self.assertAlmostEqual(buf.duration_seconds, 1.0, places=2)
        self.assertEqual(len(buf.read_all()), 32000)

    def test_ring_buffer_read_recent_and_clear(self):
        """read_recent returns requested tail slice; clear discards all."""
        buf = AudioRingBuffer(capacity_seconds=3.0)
        audio = make_sine_pcm(duration_seconds=2.0)
        buf.write(audio)

        recent_1s = buf.read_recent(1.0)
        self.assertEqual(len(recent_1s), 32000)

        # Requesting more than current duration returns all available
        recent_5s = buf.read_recent(5.0)
        self.assertEqual(len(recent_5s), len(audio))

        buf.clear()
        self.assertEqual(buf.duration_seconds, 0.0)
        self.assertEqual(buf.read_all(), b"")

    def test_ring_buffer_wav_conversion(self):
        """to_wav_bytes and save_to_wav produce valid 16kHz mono 16-bit WAV files."""
        buf = AudioRingBuffer(capacity_seconds=2.0)
        audio = make_sine_pcm(duration_seconds=0.5)
        buf.write(audio)

        wav_bytes = buf.to_wav_bytes()
        self.assertTrue(wav_bytes.startswith(b"RIFF"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "output.wav"
            buf.save_to_wav(file_path)
            self.assertTrue(file_path.is_file())

            with wave.open(str(file_path), "rb") as w:
                self.assertEqual(w.getnchannels(), 1)
                self.assertEqual(w.getsampwidth(), 2)
                self.assertEqual(w.getframerate(), 16000)
                self.assertEqual(w.getnframes(), int(16000 * 0.5))

    # =========================================================================
    # Group 2: VoiceActivityDetector (VAD) Tests
    # =========================================================================

    def test_vad_silence_vs_speech_rms(self):
        """VAD accurately distinguishes loud speech from ambient silence."""
        vad = VoiceActivityDetector(min_speech_rms=100.0)
        silence_frame = make_silence_pcm(duration_seconds=0.02, amplitude=20.0)
        speech_frame = make_sine_pcm(duration_seconds=0.02, amplitude=5000.0)

        silence_rms = vad.compute_rms(silence_frame)
        speech_rms = vad.compute_rms(speech_frame)

        self.assertLess(silence_rms, 50.0)
        self.assertGreater(speech_rms, 2000.0)

    def test_vad_state_transitions_onset_to_hangover_cutoff(self):
        """VAD transitions: SILENCE -> SPEECH_STARTED -> SPEAKING -> SPEECH_ENDED."""
        # 20ms frames, onset = 2 frames, silence hangover = 3 frames (60ms)
        vad = VoiceActivityDetector(
            frame_duration_ms=20,
            min_speech_rms=100.0,
            speech_onset_frames=2,
            silence_hangover_ms=60,
        )
        silence_frame = make_silence_pcm(duration_seconds=0.02, amplitude=10.0)
        speech_frame = make_sine_pcm(duration_seconds=0.02, amplitude=4000.0)

        # 1. Ambient silence maintains SILENCE
        state = vad.process_frame(silence_frame)
        self.assertEqual(state, VADState.SILENCE)

        # 2. 1 frame of speech: not yet started (onset needs 2)
        state = vad.process_frame(speech_frame)
        self.assertEqual(state, VADState.SILENCE)

        # 3. 2nd frame of speech: triggers SPEECH_STARTED
        state = vad.process_frame(speech_frame)
        self.assertEqual(state, VADState.SPEECH_STARTED)

        # 4. 3rd frame of speech: transitions to SPEAKING
        state = vad.process_frame(speech_frame)
        self.assertEqual(state, VADState.SPEAKING)

        # 5. User stops speaking: silence frame 1 & 2 (hangover not yet reached)
        vad.process_frame(silence_frame)
        self.assertEqual(vad.state, VADState.SPEAKING)
        vad.process_frame(silence_frame)
        self.assertEqual(vad.state, VADState.SPEAKING)

        # 6. Silence frame 3 (hangover reached 3 frames = 60ms): triggers SPEECH_ENDED
        state = vad.process_frame(silence_frame)
        self.assertEqual(state, VADState.SPEECH_ENDED)

    def test_vad_max_duration_guard(self):
        """VAD forces SPEECH_ENDED if speech exceeds maximum duration limit."""
        # Max speech = 100ms (5 frames of 20ms)
        vad = VoiceActivityDetector(
            frame_duration_ms=20,
            min_speech_rms=50.0,
            speech_onset_frames=1,
            max_speech_duration_ms=100,
        )
        speech_frame = make_sine_pcm(duration_seconds=0.02, amplitude=3000.0)

        for _ in range(6):
            vad.process_frame(speech_frame)

        self.assertEqual(vad.state, VADState.SPEECH_ENDED)

    # =========================================================================
    # Group 3: KeywordWakeWordDetector Tests
    # =========================================================================

    def test_wake_detector_simulated_detection(self):
        """WakeWordDetector supports simulated injection for deterministic testing."""
        detector = KeywordWakeWordDetector()
        detector.set_simulated_detection(keyword="elvion", confidence=0.98)

        sample_audio = make_sine_pcm(duration_seconds=0.2)
        result = detector.detect(sample_audio)

        self.assertTrue(result.detected)
        self.assertEqual(result.keyword, "elvion")
        self.assertAlmostEqual(result.confidence, 0.98)

        # Next call without simulated match returns detected=False
        result2 = detector.detect(sample_audio)
        self.assertFalse(result2.detected)

    def test_wake_detector_delegated_verifier(self):
        """WakeWordDetector triggers when micro-transcriber returns keyword."""
        mock_verifier = Mock(return_value="ơi elvion mở nhạc đi")
        detector = KeywordWakeWordDetector(verifier=mock_verifier)

        audio = make_sine_pcm(duration_seconds=0.5)
        result = detector.detect(audio)

        self.assertTrue(result.detected)
        self.assertEqual(result.keyword, "elvion")

    # =========================================================================
    # Group 4: ContinuousVoiceSession Ambient State & Conversational Retention
    # =========================================================================

    def test_session_lifecycle_standby_to_awake_to_follow_up(self):
        """Session transitions STANDBY -> AWAKE -> LISTENING -> PROCESSING -> FOLLOW_UP."""
        simulated_time = [100.0]
        clock = lambda: simulated_time[0]

        wake_detector = KeywordWakeWordDetector(clock=clock)
        # Fast VAD: 1 frame onset, 2 frames silence hangover
        vad = VoiceActivityDetector(
            frame_duration_ms=20,
            min_speech_rms=100.0,
            speech_onset_frames=1,
            silence_hangover_ms=40,
        )
        states_seen = []
        wake_calls = []
        transcripts_seen = []

        fake_voice_session = Mock()
        fake_voice_session.voice_input.transcribe.return_value = Mock(text="tạm dừng nhạc")
        fake_voice_session.handle_utterance.return_value = "Đã tạm dừng phát nhạc."

        session = ContinuousVoiceSession(
            voice_session=fake_voice_session,
            wake_detector=wake_detector,
            vad=vad,
            follow_up_seconds=4.0,
            clock=clock,
            on_state_change=lambda s: states_seen.append(s),
            on_wake=lambda w: wake_calls.append(w),
            on_transcript=lambda t: transcripts_seen.append(t),
        )

        session.start()
        self.assertEqual(session.state, ContinuousSessionState.STANDBY)

        silence_frame = make_silence_pcm(duration_seconds=0.02, amplitude=10.0)
        speech_frame = make_sine_pcm(duration_seconds=0.02, amplitude=5000.0)

        # 1. Feeding ambient silence in STANDBY keeps it in STANDBY
        session.feed_audio(silence_frame)
        self.assertEqual(session.state, ContinuousSessionState.STANDBY)

        # 2. Inject wake word detection
        wake_detector.set_simulated_detection("elvion")
        session.feed_audio(silence_frame)

        # Should transition to AWAKE, then directly to LISTENING
        self.assertIn(ContinuousSessionState.AWAKE, states_seen)
        self.assertEqual(session.state, ContinuousSessionState.LISTENING)
        self.assertEqual(len(wake_calls), 1)

        # 3. Feed speech frames in LISTENING (5 frames = 100ms)
        for _ in range(5):
            session.feed_audio(speech_frame)
        self.assertEqual(session.state, ContinuousSessionState.LISTENING)

        # 4. User finishes speaking: feed silence frames (hangover = 2 frames)
        session.feed_audio(silence_frame)
        session.feed_audio(silence_frame)

        # Should transition to PROCESSING then automatically to FOLLOW_UP
        self.assertIn(ContinuousSessionState.PROCESSING, states_seen)
        self.assertEqual(session.state, ContinuousSessionState.FOLLOW_UP)
        self.assertEqual(transcripts_seen, ["tạm dừng nhạc"])

    def test_session_follow_up_speech_without_wake_word(self):
        """During FOLLOW_UP window, speaking again triggers LISTENING without saying ELVION."""
        simulated_time = [200.0]
        clock = lambda: simulated_time[0]

        wake_detector = KeywordWakeWordDetector(clock=clock)
        vad = VoiceActivityDetector(
            frame_duration_ms=20,
            min_speech_rms=100.0,
            speech_onset_frames=1,
            silence_hangover_ms=40,
        )

        session = ContinuousVoiceSession(
            wake_detector=wake_detector,
            vad=vad,
            follow_up_seconds=5.0,
            clock=clock,
        )
        session.start()

        # Manually put session into FOLLOW_UP state with 5s deadline
        session._set_state(ContinuousSessionState.FOLLOW_UP)
        session._follow_up_deadline = clock() + 5.0
        vad.reset()

        speech_frame = make_sine_pcm(duration_seconds=0.02, amplitude=4000.0)

        # User speaks in follow-up window (without wake word!)
        session.feed_audio(speech_frame)

        # Must transition directly into LISTENING
        self.assertEqual(session.state, ContinuousSessionState.LISTENING)

    def test_session_follow_up_timeout_returns_to_standby(self):
        """If user stays silent during FOLLOW_UP window, session times out back to STANDBY."""
        simulated_time = [300.0]
        clock = lambda: simulated_time[0]

        session = ContinuousVoiceSession(
            follow_up_seconds=3.0,
            clock=clock,
        )
        session.start()
        session._set_state(ContinuousSessionState.FOLLOW_UP)
        session._follow_up_deadline = clock() + 3.0

        silence_frame = make_silence_pcm(duration_seconds=0.02, amplitude=10.0)

        # Advance clock by 2.0s (still within deadline)
        simulated_time[0] += 2.0
        session.feed_audio(silence_frame)
        self.assertEqual(session.state, ContinuousSessionState.FOLLOW_UP)

        # Advance clock past 3.0s deadline (elapsed 3.5s)
        simulated_time[0] += 1.5
        session.feed_audio(silence_frame)
        # Must return to STANDBY
        self.assertEqual(session.state, ContinuousSessionState.STANDBY)

    def test_session_stop_clears_memory_and_resets(self):
        """Stopping session clears memory buffers and resets state cleanly."""
        session = ContinuousVoiceSession()
        session.start()
        session.ring_buffer.write(make_sine_pcm(duration_seconds=1.0))
        self.assertGreater(session.ring_buffer.duration_seconds, 0.5)

        session.stop()
        self.assertFalse(session.is_running)
        self.assertEqual(session.state, ContinuousSessionState.STANDBY)
        self.assertEqual(session.ring_buffer.duration_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
