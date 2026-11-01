#!/usr/bin/env python3
"""Interactive demonstration runner for continuous hands-free voice interaction.

Usage:
    PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py [--simulate]
"""
import argparse
import sys
import time

from elvion.voice.continuous import (
    AudioRingBuffer, ContinuousSessionState, ContinuousVoiceSession,
    KeywordWakeWordDetector, VoiceActivityDetector,
)


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


def on_wake(detection) -> None:
    print(f"\n🔔 >>> Ting! Đã phát hiện từ khóa '{detection.keyword}' (Độ tin cậy: {detection.confidence:.2f})")


def on_transcript(text: str) -> None:
    print(f"📝 >>> Văn bản nhận dạng: \"{text}\"")


def on_reply(text: str) -> None:
    print(f"💬 >>> ELVION trả lời: \"{text}\"")


def run_simulated_demo() -> None:
    print("=== CHẠY DEMO MÔ PHỎNG HANDS-FREE VOICE SESSION ===")
    session = ContinuousVoiceSession(
        follow_up_seconds=4.0,
        on_state_change=on_state_change,
        on_wake=on_wake,
        on_transcript=on_transcript,
        on_reply=on_reply,
    )
    session.start()

    print("\n--- 1. Ở trạng thái STANDBY (Im lặng ambient) ---")
    session.tick()
    time.sleep(0.5)

    print("\n--- 2. Người dùng gọi: 'ELVION ơi!' ---")
    session.wake_detector.set_simulated_detection("elvion")
    # Feed frame triggering wake
    session.feed_audio(b"\x00\x00" * 320)
    time.sleep(0.5)

    print("\n--- 3. Người dùng nói: 'Mở Apple Music' (VAD phát hiện tiếng nói) ---")
    speech_frame = b"\x20\x20" * 320  # High amplitude frame
    for _ in range(6):
        session.feed_audio(speech_frame)

    print("\n--- 4. Người dùng im lặng kết thúc câu (VAD phát hiện silence hangover) ---")
    silence_frame = b"\x00\x00" * 320
    for _ in range(45):
        session.feed_audio(silence_frame)

    print(f"\n--- 5. Trạng thái hiện tại: {session.state.value} ---")
    print("ELVION đang ở chế độ FOLLOW_UP! Bạn có thể nói câu tiếp theo ngay mà không cần gọi tên.")
    time.sleep(1.0)

    print("\n--- 6. Sau 4 giây im lặng, ELVION tự động trở về ngủ (STANDBY) ---")
    session._follow_up_deadline = time.monotonic() - 1.0  # Force expire
    session.tick()

    session.stop()
    print("\n=== HOÀN TẤT DEMO ===")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy thử nghiệm chế độ rảnh tay liên tục ELVION")
    parser.add_argument("--simulate", action="store_true", default=True, help="Chạy kịch bản mô phỏng kiểm thử nhanh")
    args = parser.parse_args()

    run_simulated_demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
