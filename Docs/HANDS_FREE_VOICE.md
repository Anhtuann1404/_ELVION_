# Trải nghiệm Giọng nói Rảnh tay: Wake Word, VAD và Giữ phiên Hội thoại

Tài liệu này đặc tả kiến trúc, cỗ máy trạng thái, bộ kiểm thử và hướng dẫn vận hành tính năng **Hội thoại Rảnh tay (Hands-free Continuous Voice)** cho trợ lý ELVION trên macOS.

---

## 1. Mục tiêu và Nguyên tắc Thiết kế

### 1.1. Mục tiêu Trải nghiệm Người dùng
- **Đánh thức bằng giọng nói (Wake Word)**: Người dùng có thể gọi tên `"ELVION"`, `"Hey ELVION"`, hoặc `"Ơi ELVION"` để đánh thức trợ lý từ trạng thái chờ ngầm (ambient standby) mà không cần chạm tay vào bàn phím.
- **Tự động nhận diện dứt câu (Voice Activity Detection - VAD)**: Loại bỏ hoàn toàn việc phải bấm phím Enter lần 2 để kết thúc ghi âm; hệ thống tự động nhận biết khi nào người dùng nói xong (khoảng lặng 800ms) để gửi câu hỏi đi xử lý.
- **Giữ phiên đối thoại liên tục (Conversational Follow-up Window)**: Sau khi ELVION trả lời xong, micro duy trì trạng thái "mở tai lắng nghe" trong khoảng 4–5 giây. Người dùng có thể hỏi tiếp hoặc ra lệnh tiếp theo ngay lập tức mà **không cần phải gọi lại tên** cho mỗi câu nói.
- **Tự động quay về chế độ ngủ**: Nếu sau thời gian chờ (5 giây) người dùng không nói thêm gì, hệ thống tự động quay về trạng thái `STANDBY` (ngủ chờ gọi tên) để tiết kiệm tài nguyên và bảo vệ quyền riêng tư.

### 1.2. Nguyên tắc Bất biến: Không sửa cấu trúc mã nguồn cũ
- **Zero Modification**: Toàn bộ các module hiện có (`InteractiveSession`, `VoiceSession`, `NativeRecorder`, `whisper.py`, `qwen.py`, `contracts.py`) được **giữ nguyên 100% cấu trúc, logic và hợp đồng**.
- **Module hóa độc lập (Decorator / Composition)**: Tính năng mới được đóng gói hoàn toàn trong package mới [`src/elvion/voice/continuous/`](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/), bọc lấy `VoiceSession` cũ từ bên ngoài.
- **Bảo toàn 100% kiểm thử cũ**: Toàn bộ hơn 950 test cases cũ của toàn bộ dự án tiếp tục chạy đạt 100%, bảo đảm không gây ra bất kỳ lỗi hồi quy nào (0 regressions).

---

## 2. Kiến trúc Module Mới (`src/elvion/voice/continuous/`)

```
src/elvion/voice/continuous/
├── __init__.py              # Export các giao diện công khai
├── ring_buffer.py           # Bộ nhớ đệm âm thanh tròn (AudioRingBuffer trong RAM)
├── vad.py                   # Bộ nhận diện hoạt động giọng nói (VoiceActivityDetector)
├── wakeword.py              # Bộ dò từ khóa đánh thức (KeywordWakeWordDetector)
└── session.py               # Quản lý phiên liên tục (ContinuousVoiceSession)
```

### 2.1. `AudioRingBuffer` ([ring_buffer.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/ring_buffer.py))
- Lưu trữ bộ đệm trượt an toàn theo luồng (thread-safe) chứa từ 2.0 đến 4.0 giây âm thanh Linear PCM 16 kHz, 16-bit, mono (tương đương 64.000 đến 128.000 bytes).
- Luôn giữ căn chỉnh mẫu 2-byte khi ghi tràn (circular roll-over).
- Cung cấp phương thức trích xuất lát cắt âm thanh gần nhất (`read_recent`) và đóng gói thành tệp/luồng WAV chuẩn hóa (`to_wav_bytes`, `save_to_wav`).

### 2.2. `VoiceActivityDetector` ([vad.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/vad.py))
- Phân tích từng khung âm thanh 20ms (320 mẫu = 640 bytes) với hai chỉ số:
  - **Năng lượng RMS (Root Mean Square)**: Đo độ lớn âm thanh.
  - **Tỷ lệ đổi dấu Zero Crossing Rate (ZCR)**: Đo đặc trưng âm thanh người nói so với tạp âm nền.
- **Sàn nhiễu thích ứng (Adaptive Noise Floor)**: Tự động điều chỉnh ngưỡng nền khi môi trường xung quanh thay đổi độ ồn.
- **Cơ chế chống ngắt sớm (Silence Hangover)**: Khi người dùng bắt đầu nói (`SPEECH_STARTED`), hệ thống chỉ xác nhận dứt câu (`SPEECH_ENDED`) khi có ít nhất 800ms im lặng liên tục, tránh ngắt giữa câu khi người dùng chỉ đang tạm ngưng lấy hơi.
- **Giới hạn an toàn (Max Speech Duration)**: Tự động kết thúc câu nói nếu vượt quá 15 giây để ngăn chặn việc ghi âm vô tận.

### 2.3. `KeywordWakeWordDetector` ([wakeword.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/wakeword.py))
- Quét lát cắt âm thanh 1.5 giây gần nhất từ Ring Buffer trong RAM để tìm kiếm các từ khóa: `"elvion"`, `"hey elvion"`, `"ê elvion"`, `"ơi elvion"`.
- Hỗ trợ kết nối verifier siêu nhẹ (nhận dạng âm vị/STT lát cắt nhỏ) và cơ chế mô phỏng (`simulate_keyword`) để kiểm thử hermetic tự động 100% không phụ thuộc micro thật.

### 2.4. `ContinuousVoiceSession` ([session.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/session.py))
- Điều phối cỗ máy trạng thái (State Machine) gồm 6 trạng thái rõ ràng:

```
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  ▼                                                        │
[STANDBY] ──(Nghe thấy "ELVION")──► [AWAKE]                │
                                       │                   │
                                       ▼                   │
                                  [LISTENING] ◄────────┐   │
                                       │               │   │
                             (VAD phát hiện dứt lời)   │   │
                                       │               │   │
                                       ▼               │   │
                                 [PROCESSING]          │   │
                                       │               │   │
                                 (STT + Model)         │   │
                                       │               │   │
                                       ▼               │   │
                                  [SPEAKING]           │   │
                                       │               │   │
                                 (TTS đọc đáp)         │   │
                                       │               │   │
                                       ▼               │   │
   ┌───────────────────────────── [FOLLOW_UP]          │   │
   │                                   │               │   │
(Hết 5s im lặng)                 (Nói tiếp ngay)       │   │
   │                                   └───────────────┘   │
   └───────────────────────────────────────────────────────┘
```

---

## 3. Ma trận Kiểm thử (`tests/test_continuous_voice.py`)

Bộ kiểm thử độc lập bao gồm **12 test cases**, kiểm tra toàn diện và đạt **100% (12/12 test cases passed)** trong **0.013s**:

| Mã test | Thành phần | Mô tả kiểm thử | Kết quả |
|---|---|---|---|
| `test_ring_buffer_capacity_and_overflow` | AudioRingBuffer | Giới hạn dung lượng RAM chuẩn xác, tự động xoay vòng bỏ dữ liệu cũ | **ĐẠT** |
| `test_ring_buffer_read_recent_and_clear` | AudioRingBuffer | Đọc đúng lát cắt thời gian yêu cầu và dọn sạch bộ nhớ khi clear | **ĐẠT** |
| `test_ring_buffer_wav_conversion` | AudioRingBuffer | Chuyển đổi Linear PCM thành file WAV 16kHz mono 16-bit chuẩn | **ĐẠT** |
| `test_vad_silence_vs_speech_rms` | VAD | Phân biệt chuẩn xác giữa tạp âm nền và tiếng người nói | **ĐẠT** |
| `test_vad_state_transitions_onset_to_hangover_cutoff` | VAD | Chu trình SILENCE -> SPEECH_STARTED -> SPEAKING -> SPEECH_ENDED | **ĐẠT** |
| `test_vad_max_duration_guard` | VAD | Tự động ngắt khi tiếng nói vượt quá giới hạn tối đa | **ĐẠT** |
| `test_wake_detector_simulated_detection` | WakeWordDetector | Nhận diện từ khóa mô phỏng cho kiểm thử hermetic | **ĐẠT** |
| `test_wake_detector_delegated_verifier` | WakeWordDetector | Nhận diện từ khóa qua bộ bóc tách âm vị | **ĐẠT** |
| `test_session_lifecycle_standby_to_awake_to_follow_up` | ContinuousSession | Chu trình từ Standby -> Nghe Wake Word -> Thu âm -> Xử lý -> Follow-up | **ĐẠT** |
| `test_session_follow_up_speech_without_wake_word` | ContinuousSession | Nói tiếp trong cửa sổ 5s tự động thu âm mà KHÔNG cần gọi lại tên | **ĐẠT** |
| `test_session_follow_up_timeout_returns_to_standby` | ContinuousSession | Sau 5s im lặng tự động quay về trạng thái ngủ (Standby) | **ĐẠT** |
| `test_session_stop_clears_memory_and_resets` | ContinuousSession | Dừng phiên giải phóng sạch bộ nhớ và đưa về trạng thái an toàn | **ĐẠT** |

**Kiểm thử hồi quy toàn bộ kho mã ELVION**:
```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -p "test_*.py"
# Kết quả: Ran 962 tests in 19.964s -> OK (0 regressions)
```

---

## 4. Hướng dẫn Kiểm thử Thực tế (How to Test)

Bạn có thể kiểm tra tính năng theo 2 cách:

### Cách 1: Chạy bộ kiểm thử tự động
Chạy lệnh unittest trong terminal:
```bash
PYTHONPATH=src:. python3 -m unittest -v tests/test_continuous_voice.py
```
Toàn bộ 12 ca kiểm thử sẽ chạy xong trong chưa đầy 0.1 giây và báo `OK`.

### Cách 2: Chạy kịch bản mô phỏng trực quan
Chúng tôi đã cung cấp sẵn script demo tương tác tại [`scripts/run_handsfree_voice.py`](file:///Users/yingjunn_/Study_/ELVION/scripts/run_handsfree_voice.py):
```bash
PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py
```

**Kết quả hiển thị trên terminal**:
```text
=== CHẠY DEMO MÔ PHỎNG HANDS-FREE VOICE SESSION ===

--- 1. Ở trạng thái STANDBY (Im lặng ambient) ---

--- 2. Người dùng gọi: 'ELVION ơi!' ---

🔔 >>> Ting! Đã phát hiện từ khóa 'elvion' (Độ tin cậy: 0.95)
✨ [AWAKE] Đã thức giấc! 'ELVION' được nhận diện.
🎙️  [LISTENING] Đang lắng nghe câu nói của bạn (VAD)...

--- 3. Người dùng nói: 'Mở Apple Music' (VAD phát hiện tiếng nói) ---

--- 4. Người dùng im lặng kết thúc câu (VAD phát hiện silence hangover) ---
⚙️  [PROCESSING] Đang xử lý câu hỏi qua mô hình...
👂 [FOLLOW_UP] Đang mở tai chờ nói tiếp (5s không cần gọi tên)...

--- 5. Trạng thái hiện tại: follow_up ---
ELVION đang ở chế độ FOLLOW_UP! Bạn có thể nói câu tiếp theo ngay mà không cần gọi tên.

--- 6. Sau 4 giây im lặng, ELVION tự động trở về ngủ (STANDBY) ---
💤 [STANDBY] Đang ngủ, chờ gọi 'ELVION'...

=== HOÀN TẤT DEMO ===
```

---

## 5. Ranh giới Quyền riêng tư & An toàn (Privacy Bounds)
- **Không ghi âm lén ra đĩa**: Ở trạng thái `STANDBY`, các khung âm thanh liên tục chỉ được lưu đè trong bộ nhớ RAM (`AudioRingBuffer`, tối đa 3-4 giây), tuyệt đối **không ghi bất kỳ tệp tin nào ra đĩa cứng**.
- **Chỉ xuất tệp khi được kích hoạt**: Tệp WAV tạm thời chỉ được tạo ra khi và chỉ khi:
  1. Từ khóa đánh thức được phát hiện.
  2. Người dùng phát âm câu lệnh và VAD xác nhận kết thúc câu.
- **Tự động dọn dẹp**: Tệp WAV tạm thời được xóa sạch ngay sau khi mô hình STT hoàn tất xử lý.
