#!/usr/bin/env python3
"""Interactive hands-free continuous voice runner for ELVION.

Live Mode (Default):
    Listens to the real microphone in real time.
    Waits for the user to say "ELVION" or "ELVION ơi".
    Captures live speech using VAD, transcribes with configured STT, thinks with Ollama,
    and replies out loud via macOS TTS (Linh).

Simulation Mode (--simulate):
    Hermetic test scenario injecting artificial PCM frames for CI/unit testing.

Usage:
    PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py [--simulate] [--no-speak]
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

from elvion.conversation.contracts import CapabilityContext
from elvion.conversation.service import ConversationService
from elvion.interface.voice_settings import VoicePreferences, VoicePreferencesStore
from elvion.models.ollama import OllamaProvider
from elvion.voice.continuous import (
    AudioRingBuffer, ContinuousSessionState, ContinuousVoiceSession,
    KeywordWakeWordDetector, VoiceActivityDetector,
    open_live_audio_stream,
)
from elvion.voice.input.types import VoiceInputError
from elvion.voice.input.whisper import WhisperTranscriber


def play_sound(name: str) -> None:
    """Play macOS system audio chime."""
    path = f"/System/Library/Sounds/{name}.aiff"
    if sys.platform == "darwin" and os.path.exists(path):
        subprocess.run(
            ["/usr/bin/afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def speak(text: str) -> None:
    """Speak text using macOS native Linh voice."""
    if sys.platform == "darwin":
        subprocess.run(
            ["/usr/bin/say", "-v", "Linh", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def run_live_mic(speak_enabled: bool = True) -> None:
    # 1. Load saved voice preferences
    try:
        prefs = VoicePreferencesStore().load()
    except Exception:
        prefs = VoicePreferences()

    # 2. Select and preflight configured STT engine
    try:
        if prefs.stt_engine == "qwen":
            from elvion.voice.input.qwen import QwenTranscriber, DEFAULT_MODEL
            # Follow resolve_voice_options rules: do not inherit Whisper file models when Qwen is chosen
            model_path = prefs.stt_model if (prefs.stt_model and Path(prefs.stt_model).is_dir()) else DEFAULT_MODEL
            # Qwen only accepts 'none' or 'tech'; 'elvion' is a Whisper preset
            qwen_ctx = prefs.stt_context if prefs.stt_context in ("none", "tech") else "tech"
            transcriber = QwenTranscriber(
                model_path=model_path,
                context=qwen_ctx,
                language="vi",
            )
            stt_desc = f"Qwen ASR ({Path(model_path).name if model_path else 'default'})"
        else:
            transcriber = WhisperTranscriber(
                model_path=prefs.stt_model,
                context=prefs.stt_context or "none",
            )
            model_name = Path(prefs.stt_model).name if prefs.stt_model else "default"
            stt_desc = f"Whisper.cpp ({model_name})"

        transcriber.check_available()
    except (VoiceInputError, ValueError, Exception) as err:
        err_msg = getattr(err, "code", str(err))
        print(f"❌ Không thể khởi động STT ({err_msg}). Vui lòng kiểm tra lại cấu hình voice.")
        return

    print("=" * 64)
    print("🎙️  ELVION HANDS-FREE VOICE (MICROPHONE THẬT - LIVE MODE)")
    print("=" * 64)
    print("Hệ thống khởi tạo từ cấu hình giọng nói:")
    print(f"  - STT Engine: {stt_desc}")
    print("  - LLM Model:  Local Ollama (qwen3.5:4b)")
    print(f"  - TTS Voice:  macOS Voice Linh ({'BẬT' if speak_enabled else 'TẮT'})")
    print("=" * 64)

    ring_buf_verifier = AudioRingBuffer(capacity_seconds=3.0)

    try:
        provider = OllamaProvider(model="qwen3.5:4b")
        conv_service = ConversationService(provider)
        session_id = f"handsfree-{uuid4().hex[:8]}"
    except Exception as e:
        print(f"⚠️ Không thể kết nối Ollama ({e}). Chuyển sang chế độ echo phản hồi.")
        conv_service = None
        session_id = None

    def verify_wake_slice(pcm_slice: bytes) -> str:
        """Transcribe recent 1.5s slice when acoustic energy rises in STANDBY."""
        try:
            with tempfile.TemporaryDirectory(prefix="elvion-wake-") as tmp_dir:
                wav_path = Path(tmp_dir) / "slice.wav"
                ring_buf_verifier.clear()
                ring_buf_verifier.write(pcm_slice)
                ring_buf_verifier.save_to_wav(wav_path, pcm_bytes=pcm_slice)
                res = transcriber.transcribe(wav_path)
                return getattr(res, "text", "") or ""
        except Exception:
            return ""

    wake_detector = KeywordWakeWordDetector(
        verifier=verify_wake_slice,
        energy_threshold=420.0,
        min_check_interval=0.5,
    )
    vad = VoiceActivityDetector(
        min_speech_rms=350.0,
        speech_multiplier=2.8,
        silence_hangover_ms=800,
    )

    def on_state_change(new_state: ContinuousSessionState) -> None:
        symbols = {
            ContinuousSessionState.STANDBY: "\n💤 [STANDBY] Đang ngủ ngầm trong phòng. Chờ bạn gọi 'ELVION'...",
            ContinuousSessionState.AWAKE: "✨ [AWAKE] Đã nghe thấy gọi 'ELVION'! Đang thức giấc...",
            ContinuousSessionState.LISTENING: "🎙️  [LISTENING] Đang lắng nghe câu nói của bạn...",
            ContinuousSessionState.PROCESSING: "⚙️  [PROCESSING] Đang suy nghĩ câu trả lời...",
            ContinuousSessionState.SPEAKING: "🔊 [SPEAKING] Đang phát câu trả lời qua loa...",
            ContinuousSessionState.FOLLOW_UP: "👂 [FOLLOW_UP] Đang mở tai chờ bạn nói tiếp (5s không cần gọi tên)...",
        }
        print(symbols.get(new_state, f"State: {new_state}"), flush=True)

    def on_wake(detection) -> None:
        print(f"\n🔔 >>> Ting! Đã phát hiện gọi '{detection.keyword.upper()}'!", flush=True)
        play_sound("Ping")

    def on_transcript(text: str) -> None:
        print(f"📝 >>> Bạn nói: \"{text}\"", flush=True)

    def on_reply(text: str) -> None:
        print(f"💬 >>> ELVION: \"{text}\"", flush=True)
        if speak_enabled:
            speak(text)

    # Session adapter wrapping transcriber and conversation
    class LiveVoiceAdapter:
        def __init__(self):
            self.voice_input = transcriber

        def handle_utterance(self, text: str) -> str:
            if conv_service is not None:
                try:
                    res = conv_service.handle(
                        session_id,
                        text,
                        request_id=uuid4(),
                        capabilities=CapabilityContext(granted=()),
                        outcome=None,
                    )
                    if getattr(res, "route", "") == "action_request":
                        return f"Dạ, mình nhận diện yêu cầu tác vụ: {getattr(res, 'handoff_utterance', text)}."
                    if getattr(res, "route", "") == "error":
                        return f"Hội thoại local gặp lỗi ({getattr(res, 'reason', 'MODEL_ERROR')})."
                    return getattr(res, "text", "") or "Dạ, mình chưa nghe rõ."
                except Exception:
                    return f"Dạ, mình ghi nhận: {text}"
            return f"Dạ, mình đã nghe thấy: {text}"

    adapter = LiveVoiceAdapter()
    session = ContinuousVoiceSession(
        voice_session=adapter,
        wake_detector=wake_detector,
        vad=vad,
        follow_up_seconds=5.0,
        listen_timeout_seconds=3.5,
        async_dispatch=True,
        on_state_change=on_state_change,
        on_wake=on_wake,
        on_transcript=on_transcript,
        on_reply=on_reply,
        wake_slice_seconds=1.5,
    )

    running = True

    def clock_tick_loop():
        last_state = session.state
        while running:
            time.sleep(0.2)
            session.tick()
            if last_state in (ContinuousSessionState.FOLLOW_UP, ContinuousSessionState.LISTENING) and session.state == ContinuousSessionState.STANDBY:
                play_sound("Tink")
            last_state = session.state

    ticker = threading.Thread(target=clock_tick_loop, daemon=True)
    ticker.start()

    try:
        with open_live_audio_stream(chunk_size=640) as stream:
            session.start()
            on_state_change(ContinuousSessionState.STANDBY)
            print("\n🟢 MICROPHONE ĐÃ MỞ VÀ ĐANG LẮNG NGHE THỰC TẾ.", flush=True)
            print("👉 Hãy nói: \"ELVION ơi\" hoặc \"ELVION\" để đánh thức.", flush=True)
            print("👉 Nhấn Ctrl+C để dừng chương trình.\n", flush=True)

            for chunk in stream:
                if not running:
                    break
                session.feed_audio(chunk)
    except KeyboardInterrupt:
        print("\n\n🛑 Đã nhận tín hiệu dừng từ người dùng.")
    except RuntimeError as err:
        if "MIC_PERMISSION_DENIED" in str(err):
            print("\n❌ LỖI QUYỀN TRUY CẬP MICROPHONE (MIC_PERMISSION_DENIED):")
            print("   macOS đã từ chối quyền truy cập Microphone cho tiến trình thu âm.")
            print("   👉 Vui lòng vào: Cài đặt hệ thống (System Settings) > Quyền riêng tư & Bảo mật (Privacy & Security) > Micrô (Microphone)")
            print("   👉 Gạt bật quyền cho Terminal / iTerm / IDE mà bạn dùng để chạy lệnh.")
        else:
            print(f"\n❌ Lỗi khởi động luồng thu âm micro: {err}")
    finally:
        running = False
        session.stop()
        session.wait_idle(timeout=1.0)
        print("✅ Đã giải phóng microphone và đóng phiên.")


def run_simulated_demo() -> None:
    print("================================================================")
    print("=== CHẾ ĐỘ MÔ PHỎNG KIỂM THỬ TỰ ĐỘNG (CI / UNIT SCENARIO) ======")
    print("================================================================")
    session = ContinuousVoiceSession(
        follow_up_seconds=4.0,
        async_dispatch=False,
        on_state_change=lambda s: print(f"State -> {s.value}"),
        on_wake=lambda d: print(f"Wake detected: {d.keyword}"),
        on_transcript=lambda t: print(f"Transcript: {t}"),
        on_reply=lambda r: print(f"Reply: {r}"),
    )
    session.start()
    session.wake_detector.set_simulated_detection("elvion")
    session.feed_audio(b"\x00\x00" * 320)
    for _ in range(6):
        session.feed_audio(b"\x20\x20" * 320)
    for _ in range(45):
        session.feed_audio(b"\x00\x00" * 320)
    session._follow_up_deadline = time.monotonic() - 1.0
    session.tick()
    session.stop()
    print("=== MÔ PHỎNG HOÀN TẤT ===")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy trải nghiệm rảnh tay liên tục ELVION")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Chạy kịch bản mô phỏng kiểm thử nhanh (không mở microphone thật)",
    )
    parser.add_argument(
        "--no-speak",
        action="store_true",
        help="Tắt đọc phát âm thanh qua loa (chỉ in văn bản)",
    )
    args = parser.parse_args()

    if args.simulate:
        run_simulated_demo()
    else:
        run_live_mic(speak_enabled=not args.no_speak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
