#!/usr/bin/env python3
"""Interactive demonstration runner for continuous hands-free voice interaction.

Usage:
    PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py [--simulate] [--audio] [--interactive]
"""
import argparse
import os
import subprocess
import sys
import threading
import time

from elvion.voice.continuous import (
    AudioRingBuffer, ContinuousSessionState, ContinuousVoiceSession,
    KeywordWakeWordDetector, VoiceActivityDetector,
)


def play_sound(name: str) -> None:
    """Play macOS system audio chime."""
    path = f"/System/Library/Sounds/{name}.aiff"
    if sys.platform == "darwin" and os.path.exists(path):
        subprocess.run(["/usr/bin/afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def speak(text: str) -> None:
    """Speak text using macOS native Linh voice."""
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/say", "-v", "Linh", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def on_state_change(new_state: ContinuousSessionState) -> None:
    symbols = {
        ContinuousSessionState.STANDBY: "💤 [STANDBY] Đang ngủ, chờ gọi 'ELVION'...",
        ContinuousSessionState.AWAKE: "✨ [AWAKE] Đã thức giấc! 'ELVION' được nhận diện.",
        ContinuousSessionState.LISTENING: "🎙️  [LISTENING] Đang lắng nghe câu nói của bạn (VAD)...",
        ContinuousSessionState.PROCESSING: "⚙️  [PROCESSING] Đang xử lý câu hỏi qua mô hình...",
        ContinuousSessionState.SPEAKING: "🔊 [SPEAKING] Đang phát câu trả lời bằng giọng nói...",
        ContinuousSessionState.FOLLOW_UP: "👂 [FOLLOW_UP] Đang mở tai chờ nói tiếp (5s không cần gọi tên)...",
    }
    print(symbols.get(new_state, f"State: {new_state}"))


def on_wake(detection, audio: bool = True) -> None:
    print(f"\n🔔 >>> Ting! Đã phát hiện từ khóa '{detection.keyword}' (Độ tin cậy: {detection.confidence:.2f})")
    if audio:
        play_sound("Ping")


def on_transcript(text: str) -> None:
    print(f"📝 >>> Văn bản nhận dạng: \"{text}\"")


def on_reply(text: str, audio: bool = True) -> None:
    print(f"💬 >>> ELVION trả lời: \"{text}\"")
    if audio:
        speak(text)


def run_simulated_demo(audio: bool = True) -> None:
    print("================================================================")
    print("=== CHẠY DEMO MÔ PHỎNG HANDS-FREE VOICE SESSION (KÈM ÂM THANH) ===")
    print("================================================================")
    session = ContinuousVoiceSession(
        follow_up_seconds=4.0,
        on_state_change=on_state_change,
        on_wake=lambda d: on_wake(d, audio=audio),
        on_transcript=on_transcript,
        on_reply=lambda r: on_reply(r, audio=audio),
    )
    session.start()

    print("\n--- 1. Ở trạng thái STANDBY (Im lặng ambient) ---")
    session.tick()
    time.sleep(1.0)

    print("\n--- 2. Người dùng gọi: 'ELVION ơi!' ---")
    session.wake_detector.set_simulated_detection("elvion")
    # Feed frame triggering wake
    session.feed_audio(b"\x00\x00" * 320)
    time.sleep(1.0)

    print("\n--- 3. Người dùng nói: 'Mở Apple Music' (VAD phát hiện tiếng nói) ---")
    speech_frame = b"\x20\x20" * 320  # High amplitude frame
    for _ in range(6):
        session.feed_audio(speech_frame)

    print("\n--- 4. Người dùng im lặng kết thúc câu (VAD phát hiện silence hangover) ---")
    silence_frame = b"\x00\x00" * 320
    for _ in range(45):
        session.feed_audio(silence_frame)

    # Simulate model reply
    print("\n--- Mô hình Ollama phản hồi qua giọng nói Linh (macOS TTS) ---")
    on_reply("Dạ, ELVION đang mở Apple Music cho bạn.", audio=audio)

    print(f"\n--- 5. Trạng thái hiện tại: {session.state.value.upper()} ---")
    print("ELVION đang ở chế độ FOLLOW_UP (5s)! Bạn có thể nói câu tiếp theo ngay mà không cần gọi lại tên.")
    time.sleep(3.0)

    print("\n--- 6. Sau khi hết thời gian chờ im lặng, ELVION tự động ngủ (STANDBY) ---")
    session._follow_up_deadline = time.monotonic() - 1.0  # Force expire
    session.tick()
    if audio:
        play_sound("Tink")

    session.stop()
    print("\n======================= HOÀN TẤT DEMO ===========================")


def run_interactive_demo(audio: bool = True) -> None:
    print("================================================================")
    print("=== CHẾ ĐỘ TƯƠNG TÁC TEST TRỰC TIẾP HANDS-FREE VOICE SESSION ===")
    print("================================================================")
    print("Hướng dẫn:")
    print("  1. Gõ 'elvion' hoặc 'elvion ơi' để đánh thức (nghe chuông Ting!).")
    print("  2. Gõ lệnh/câu hỏi bất kỳ (ELVION sẽ cất tiếng trả lời qua loa!).")
    print("  3. Sau khi trả lời, tai ELVION vẫn MỞ trong 5 giây (FOLLOW_UP).")
    print("     -> Bạn có thể gõ câu tiếp theo NGAY mà KHÔNG CẦN gọi 'elvion'.")
    print("  4. Nếu để quá 5 giây không nói, ELVION sẽ gõ chuông Tink và về ngủ (STANDBY).")
    print("  5. Gõ 'exit' hoặc 'quit' để thoát.")
    print("================================================================\n")

    session = ContinuousVoiceSession(
        follow_up_seconds=5.0,
        on_state_change=on_state_change,
        on_wake=lambda d: on_wake(d, audio=audio),
        on_transcript=on_transcript,
        on_reply=lambda r: on_reply(r, audio=audio),
    )
    session.start()

    running = True

    def clock_tick_loop():
        last_state = session.state
        while running:
            time.sleep(0.5)
            session.tick()
            if last_state == ContinuousSessionState.FOLLOW_UP and session.state == ContinuousSessionState.STANDBY:
                if audio:
                    play_sound("Tink")
            last_state = session.state

    ticker = threading.Thread(target=clock_tick_loop, daemon=True)
    ticker.start()

    try:
        while True:
            prompt_str = f"[{session.state.value.upper()}] Nhập câu của bạn: "
            user_input = input(prompt_str).strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            lower = user_input.lower()
            if session.state == ContinuousSessionState.STANDBY:
                if "elvion" in lower:
                    session.wake_detector.set_simulated_detection("elvion")
                    session.feed_audio(b"\x00\x00" * 320)
                    time.sleep(0.3)
                    # Check if there is extra utterance after wake word
                    remaining = lower.replace("elvion", "").replace("ơi", "").strip()
                    if remaining:
                        on_transcript(remaining)
                        on_reply(f"ELVION đã nghe: {remaining}", audio=audio)
                        session._set_state(ContinuousSessionState.FOLLOW_UP)
                        session._follow_up_deadline = time.monotonic() + session.follow_up_seconds
                else:
                    print("⚠️ ELVION đang ngủ! Hãy gọi 'elvion' hoặc 'elvion ơi' trước.")
            elif session.state in (ContinuousSessionState.FOLLOW_UP, ContinuousSessionState.AWAKE, ContinuousSessionState.LISTENING):
                on_transcript(user_input)
                on_reply(f"Đã thực hiện: {user_input}", audio=audio)
                session._set_state(ContinuousSessionState.FOLLOW_UP)
                session._follow_up_deadline = time.monotonic() + session.follow_up_seconds
    except (KeyboardInterrupt, EOFError):
        print("\nĐang dừng phiên...")
    finally:
        running = False
        session.stop()
        print("Đã thoát session.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy thử nghiệm chế độ rảnh tay liên tục ELVION")
    parser.add_argument("--interactive", "-i", action="store_true", help="Chạy chế độ tương tác phím thử nghiệm giữ phiên")
    parser.add_argument("--no-audio", action="store_true", help="Tắt âm thanh chuông và TTS")
    args = parser.parse_args()

    audio = not args.no_audio
    if args.interactive:
        run_interactive_demo(audio=audio)
    else:
        run_simulated_demo(audio=audio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
