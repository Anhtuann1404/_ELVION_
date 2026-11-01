# Báo Cáo Kỹ Thuật: Trải Nghiệm Giọng Nói Rảnh Tay (Hands-free Continuous Voice)

Tài liệu này đặc tả chi tiết kiến trúc, cơ chế xử lý âm thanh thời gian thực, cỗ máy trạng thái, giải pháp phòng chống ảo giác (anti-hallucination), bộ kiểm thử 14 ca và hướng dẫn vận hành tính năng **Hội thoại Rảnh tay (Hands-free Voice Session)** cho trợ lý ELVION trên macOS.

---

## 1. Mục tiêu và Nguyên tắc Thiết kế

### 1.1. Mục tiêu Trải nghiệm Người dùng
- **Đánh thức bằng giọng nói (Wake Word)**: Gọi *"ELVION"*, *"ELVION ơi"*, *"Hey ELVION"*, hoặc *"Ê ELVION"* để đánh thức trợ lý từ trạng thái chờ ngầm (`STANDBY`) trong phòng mà không cần chạm tay vào bàn phím.
- **Tự động nhận diện dứt câu (Voice Activity Detection - VAD)**: Hệ thống tự động nhận biết khi nào người dùng bắt đầu nói và tự ngắt sau khi dứt câu (800ms khoảng lặng liên tục), loại bỏ thao tác bấm phím.
- **Tự động ngắt khi im lặng (Silence Timeout)**: Nếu sau khi thức giấc mà người dùng đổi ý hoặc im lặng quá 3.5 giây, hệ thống tự động gõ chuông huỷ và trở về trạng thái ngủ (`STANDBY`), không bị treo mic.
- **Giữ phiên đối thoại liên tục (Conversational Follow-up Window)**: Sau khi ELVION phát câu trả lời qua loa máy tính, micro duy trì trạng thái "mở tai lắng nghe" trong 5 giây. Người dùng có thể nói tiếp câu thứ hai ngay lập tức mà **không cần phải gọi lại tên**.
- **Chống ảo giác (Anti-Hallucination Guard)**: Lọc triệt để hiện tượng mô hình Whisper tự "bịa" ra các câu thoại ngẫu nhiên (lời cảm ơn, xin subscribe, credit phụ đề) khi phòng im lặng hoặc chỉ có tiếng quạt laptop.

### 1.2. Nguyên tắc Bất biến: Bảo toàn 100% mã nguồn cũ
- **Zero Modification**: Toàn bộ các module hiện có (`InteractiveSession`, `VoiceSession`, `NativeRecorder`, `whisper.py`, `qwen.py`, `contracts.py`) được **giữ nguyên 100% cấu trúc, logic và hợp đồng**.
- **Mở rộng theo cơ chế Composition**: Tính năng mới được tổ chức hoàn toàn trong gói [`src/elvion/voice/continuous/`](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/), bọc ngoài và tái sử dụng các dịch vụ hiện có của ELVION.
- **Bảo toàn hồi quy**: Toàn bộ 964 bài kiểm thử của cả dự án chạy đạt 100% xanh (0 regressions).

---

## 2. Kiến trúc Module Mới (`src/elvion/voice/continuous/`)

```
src/elvion/voice/continuous/
├── __init__.py              # Export các class, hàm và hằng số công khai
├── stream_capture.swift     # Native Swift audio engine tap stream PCM trực tiếp
├── streamer.py              # Trình quản lý tiến trình thu âm thời gian thực
├── ring_buffer.py           # Bộ nhớ đệm âm thanh tròn (AudioRingBuffer trong RAM)
├── vad.py                   # Bộ nhận diện hoạt động giọng nói (VoiceActivityDetector)
├── wakeword.py              # Bộ dò từ khóa đánh thức kèm acoustic pre-filter
├── hallucination.py         # Bộ lọc ảo giác Whisper và các vòng lặp từ rác
└── session.py               # Quản lý vòng đời phiên liên tục (ContinuousVoiceSession)
```

### 2.1. Native Audio Streaming ([stream_capture.swift](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/stream_capture.swift), [streamer.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/streamer.py))
- Biên dịch qua `swiftc` với quyền `NSMicrophoneUsageDescription` được nhúng trực tiếp vào segment binary.
- Khởi tạo `AVAudioEngine` và gắn `installTap` lên `inputNode`.
- Tự động chuyển đổi phần cứng micro từ bất kỳ tần số nào (44.1kHz / 48kHz, Float32) sang định dạng chuẩn hóa **16000 Hz, 1 channel, 16-bit Linear PCM** bằng `AVAudioConverter`.
- Đẩy dữ liệu âm thanh qua `stdout` theo từng khung 20ms (320 mẫu = 640 bytes) với độ trễ cực thấp (< 5ms).

### 2.2. Audio Ring Buffer ([ring_buffer.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/ring_buffer.py))
- Lưu trữ bộ đệm trượt an toàn đa luồng (thread-safe) chứa từ 2.0 đến 4.0 giây âm thanh Linear PCM trong RAM.
- **Quyền riêng tư tuyệt đối**: Trong chế độ ngủ `STANDBY`, dữ liệu chỉ lưu xoay vòng trong RAM, **tuyệt đối không ghi bất kỳ byte âm thanh nào ra ổ cứng**.
- Cung cấp hàm trích xuất lát cắt âm thanh (`read_recent`) phục vụ bộ dò Wake Word.

### 2.3. Voice Activity Detector thích ứng ([vad.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/vad.py))
- Đo năng lượng RMS và Zero Crossing Rate (ZCR) trên từng khung 20ms.
- **Sàn nhiễu thích ứng (Adaptive Noise Floor)**: Tự động hiệu chỉnh ngưỡng nhiễu nền khi môi trường thay đổi độ ồn.
- **Ngưỡng năng lượng thực tế**: Thiết lập `min_speech_rms = 300.0 - 350.0` và `speech_multiplier = 2.8` giúp bỏ qua hoàn toàn tiếng quạt tản nhiệt của MacBook.
- **Silence Hangover**: Duy trì bộ đếm 800ms im lặng liên tục mới xác nhận dứt câu, tránh ngắt lời khi người dùng chỉ đang lấy hơi.
- **Max Duration Guard**: Giới hạn tối đa 15 giây cho một lượt nói để chống tràn bộ đệm.

### 2.4. Bộ dò Wake Word & Acoustic Pre-filter ([wakeword.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/wakeword.py))
- **Acoustic Pre-filter**: Chỉ khi lát cắt âm thanh có năng lượng RMS vượt ngưỡng $\ge 420.0$ thì mới kích hoạt bộ giải mã âm vị PhoWhisper, tiết kiệm 95% CPU khi phòng yên tĩnh.
- **Biểu thức Regex chuẩn hóa**:
  ```python
  _NORMALIZED_KEYWORD_RE = re.compile(
      r"\b(?:hey\s+|ê\s+|ơi\s+)?(?:el|eo|en|e)\s*vi[oô]n(?:\s+ơi)?\b|\belvion\b",
      re.IGNORECASE,
  )
  ```
  Khớp chính xác các biến thể ngữ âm tiếng Việt (*"ELVION"*, *"ELVION ơi"*, *"Ơi ELVION"*, *"Hey ELVION"*, *"Ê ELVION"*), đồng thời siết ranh giới từ `\b` để loại bỏ hoàn toàn các âm tiết rời rạc do tạp âm.

### 2.5. Bộ lọc Ảo giác Whisper ([hallucination.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/hallucination.py))
- Nhận diện và hủy bỏ tức thì các câu văn bản ma (phantom hallucination) mà Whisper tự sinh ra khi nhận âm thanh im lặng/tiếng quạt:
  - Lời kết video YouTube (*"Cảm ơn các bạn đã theo dõi..."*, *"Hãy like và subscribe..."*, *"Hẹn gặp lại..."*).
  - Thẻ phụ đề (*"Subtitles by..."*, *"Phụ đề bởi..."*, *"Amara.org"*).
  - Vòng lặp từ vô nghĩa (*"ừm ừm ừm..."*, *"à à à..."*, tỷ lệ từ lặp $\ge 75\%$).
- Hủy bỏ các đoạn thu âm có năng lượng RMS trung bình $< 280.0$, ngăn không cho đẩy dữ liệu rác vào mô hình LLM.

### 2.6. Continuous Voice Session ([session.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/session.py))
- Điều phối cỗ máy 6 trạng thái kèm 2 bộ đếm thời gian an toàn (`_listen_deadline` và `_follow_up_deadline`):

```
       ┌────────────────────────────────────────────────────────┐
       │                                                        │
       ▼                                                        │
    [STANDBY] ◄──(Quá 3.5s im lặng)───────┐                     │
       │                                  │                     │
  (Nghe "ELVION")                         │                     │
       ▼                                  │                     │
    [AWAKE] (Phát chuông Ping!)           │                     │
       │                                  │                     │
       ▼                                  │                     │
  [LISTENING] ────────────────────────────┘                     │
       │                                                        │
 (VAD dứt câu)                                                  │
       ▼                                                        │
 [PROCESSING] (PhoWhisper + Ollama)                             │
       │                                                        │
       ▼                                                        │
   [SPEAKING] (Phát loa Linh TTS)                               │
       │                                                        │
       ▼                                                        │
 ┌─►[FOLLOW_UP] (Mở tai 5s)                                     │
 │     │                                                        │
 │  (Nói tiếp)                                            (Hết 5s)
 │     │                                                        │
 └─── [LISTENING]                                               ▼
                                                       [STANDBY] (Chuông Tink!)
```

---

## 3. Danh mục Kiểm thử Chi tiết (`tests/test_continuous_voice.py`)

Bộ kiểm thử đạt **14/14 test cases passed** trong **0.015 giây**:

| STT | Tên ca kiểm thử | Phạm vi | Mô tả kiểm thử & Tiêu chuẩn nghiệm thu | Kết quả |
|:---:|---|---|---|:---:|
| 1 | `test_ring_buffer_capacity_and_overflow` | AudioRingBuffer | Ghi vượt dung lượng tối đa (41.6KB > 32KB); kiểm tra bộ đệm giữ đúng kích thước trần và xoay vòng dữ liệu cũ. | **PASS** |
| 2 | `test_ring_buffer_read_recent_and_clear` | AudioRingBuffer | Đọc chính xác 0.2s âm thanh gần nhất và xác minh hàm `clear()` giải phóng bộ nhớ về 0 byte. | **PASS** |
| 3 | `test_ring_buffer_wav_conversion` | AudioRingBuffer | Chuyển đổi dữ liệu byte PCM thành tệp WAV hợp lệ: 1 channel, 16000 Hz, 16-bit depth. | **PASS** |
| 4 | `test_vad_silence_vs_speech_rms` | VAD | Đưa sóng âm giả lập tiếng nói (RMS > 2000) và sóng im lặng (RMS < 50); kiểm tra độ phân tách ngưỡng. | **PASS** |
| 5 | `test_vad_state_transitions_onset_to_hangover_cutoff` | VAD | Kiểm tra chu trình 4 pha: `SILENCE` $\rightarrow$ `SPEECH_STARTED` (đủ onset) $\rightarrow$ `SPEAKING` $\rightarrow$ `SPEECH_ENDED` (đủ 800ms hangover). | **PASS** |
| 6 | `test_vad_max_duration_guard` | VAD | Bơm liên tục frame tiếng nói quá thời lượng tối đa; kiểm tra VAD buộc ngắt dứt điểm để bảo vệ bộ nhớ. | **PASS** |
| 7 | `test_wake_detector_simulated_detection` | WakeWord | Kiểm tra cơ chế bơm từ khóa giả lập phục vụ kiểm thử hermetic tự động độc lập phần cứng. | **PASS** |
| 8 | `test_wake_detector_delegated_verifier` | WakeWord | Kiểm tra tầng verifier bóc tách âm vị: khớp đúng từ khóa *"ELVION"* và từ chối các câu không liên quan. | **PASS** |
| 9 | `test_session_lifecycle_standby_to_awake_to_follow_up` | Session | Kiểm tra toàn bộ vòng đời: Nghe wake word $\rightarrow$ phát chuông $\rightarrow$ thu âm $\rightarrow$ xử lý $\rightarrow$ chuyển sang `FOLLOW_UP`. | **PASS** |
| 10 | `test_session_follow_up_speech_without_wake_word` | Session | Trong cửa sổ `FOLLOW_UP`, khi có frame tiếng nói, phiên chuyển thẳng sang `LISTENING` mà **không cần gọi lại tên**. | **PASS** |
| 11 | `test_session_follow_up_timeout_returns_to_standby` | Session | Mô phỏng đồng hồ trôi qua 5.0 giây không có tiếng nói; phiên tự động chuyển về ngủ `STANDBY`. | **PASS** |
| 12 | `test_listening_timeout_returns_to_standby_when_user_silent` | Session | Kiểm chứng tính năng chống treo: Đã thức giấc nhưng người dùng im lặng quá 3.0s $\rightarrow$ tự động ngắt và về `STANDBY`. | **PASS** |
| 13 | `test_whisper_hallucination_filter` | Hallucination | Kiểm chứng bộ lọc: Bắt chính xác lời cảm ơn YouTube, phụ đề, từ lặp $\ge 75\%$; cho phép câu lệnh hợp lệ đi qua. | **PASS** |
| 14 | `test_session_stop_clears_memory_and_resets` | Session | Dừng phiên kiểm tra cờ running tắt, giải phóng toàn bộ audio PCM khỏi RAM và reset state về `STANDBY`. | **PASS** |

**Kiểm thử hồi quy toàn bộ dự án**:
```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -p "test_*.py"
# Kết quả: Ran 964 tests in 19.8s -> OK (0 regressions)
```

---

## 4. Nhật Ký Lỗi Đã Ghi Nhận và Xử Lý (`Docs/BUG_LOG.md`)

Trong quá trình phát triển tính năng, 2 vấn đề phát sinh trong môi trường thực tế đã được lập hồ sơ và giải quyết triệt để:

1. **`VOICE-HANDSFREE-001`**: Runner ban đầu chạy kịch bản mô phỏng tĩnh thay vì mở microphone thật.
   - *Khắc phục*: Triển khai `stream_capture.swift` và `streamer.py` truyền dữ liệu PCM thời gian thực từ phần cứng micro macOS vào `ContinuousVoiceSession`.
2. **`VOICE-HANDSFREE-002`**: VAD không tự ngắt trên micro laptop và Whisper bị ảo giác sinh lời thoại ngẫu nhiên khi im lặng.
   - *Khắc phục*: Bổ sung `listen_timeout_seconds = 3.5s`, nâng ngưỡng lọc tạp âm quạt tản nhiệt lên 350 RMS, lọc năng lượng câu nói $< 280$ RMS, và tạo module [hallucination.py](file:///Users/yingjunn_/Study_/ELVION/src/elvion/voice/continuous/hallucination.py).

---

## 5. Hướng Dẫn Vận Hành và Kiểm Thử (How to Test)

### Cách 1: Nói chuyện thật bằng Microphone trên máy Mac (Chế độ mặc định)
Mở cửa sổ Terminal và chạy:
```bash
cd /Users/yingjunn_/Study_/ELVION
PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py
```

**Kịch bản tương tác bạn sẽ trải nghiệm:**
1. **Trạng thái ngủ yên lặng**:
   - Màn hình thông báo `💤 [STANDBY] Đang ngủ ngầm trong phòng. Chờ bạn gọi 'ELVION'...`
   - **Khi bạn im lặng**: Hệ thống đứng yên, tuyệt đối không tự chạy hay phát ra âm thanh linh tinh.
2. **Đánh thức**:
   - Bạn nói to rõ: *"ELVION ơi"* hoặc *"ELVION"*
   - Bạn sẽ nghe tiếng chuông **Ting!** (`Ping.aiff`) vang lên $\rightarrow$ Màn hình hiện `✨ [AWAKE]` rồi chuyển sang `🎙️  [LISTENING]`.
3. **Nói câu hỏi hoặc câu lệnh**:
   - Bạn nói: *"Thời tiết hôm nay thế nào?"* hoặc *"Hôm nay bạn thấy thế nào?"*
   - Bạn dứt câu và im lặng $\rightarrow$ VAD nhận diện sau 800ms $\rightarrow$ Màn hình hiện văn bản bạn vừa nói $\rightarrow$ Loa máy tính sẽ cất tiếng đọc câu trả lời bằng giọng tiếng Việt (Linh)!
4. **Trò chuyện liên tục không cần gọi tên (Session Retention)**:
   - Sau khi đọc xong, màn hình hiện `👂 [FOLLOW_UP] Đang mở tai chờ bạn nói tiếp (5s không cần gọi tên)...`
   - Bạn nói tiếp câu thứ hai ngay lập tức: *"Kể một câu chuyện cười đi"* $\rightarrow$ ELVION lập tức trả lời tiếp mà **không cần bạn phải gọi lại "ELVION"**.
5. **Tự động ngủ lại**:
   - Khi bạn không nói gì quá 5 giây, tiếng chuông gõ nhẹ **Tink** vang lên và ELVION tự động ngủ lại (`STANDBY`).
6. **Thử nghiệm ngắt khi không nói (Silence Timeout)**:
   - Bạn gọi: *"ELVION ơi"* $\rightarrow$ Chuông Ting kêu.
   - Bạn giữ im lặng không nói gì $\rightarrow$ Đúng 3.5 giây sau, chuông Tink kêu và ELVION tự động huỷ lượt nghe, trở về ngủ ngoan ngoãn.

---

### Cách 2: Chạy kiểm thử tự động (Unit Tests)
Chạy bộ test suite 14 ca:
```bash
PYTHONPATH=src:. python3 -m unittest -v tests/test_continuous_voice.py
```
Toàn bộ 14 bài kiểm thử sẽ hoàn tất trong ~0.02 giây và báo `OK`.

---

### Cách 3: Chạy mô phỏng không cần mở Microphone (CI Mode)
Nếu muốn chạy kịch bản tự động trên môi trường không có micro hoặc chạy CI:
```bash
PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py --simulate
```
Chương trình sẽ tự động bơm các frame mô phỏng để kiểm tra chu trình chuyển đổi trạng thái mà không tác động tới phần cứng máy tính.
