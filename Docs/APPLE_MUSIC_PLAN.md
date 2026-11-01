# Kế hoạch phát triển khả năng điều khiển Apple Music trên macOS (ELVION)

## Thử catalog qua UI với agent-desktop — 02/11/2026

Đã tìm Beethoven trên Apple Music catalog thật sau khi người dùng cho phép
physical input. Headed click mục Tìm kiếm mở ô nhập; AX set-value nhập
query đúng. Bước submit bằng icon/AXConfirm chưa chuyển trang kết quả;
phải click dòng gợi ý truy vấn theo ảnh và bounds cửa sổ. Sau đó ảnh và
AX xác nhận kết quả catalog. Player vẫn paused; không chọn/phát bài.
Report: `artifacts/benchmarks/agent-desktop/music-search-c914fe1122fc4766b78a7d24f267b9b1.json`.

Giới hạn JXA search library vẫn đúng, nhưng đã có bằng chứng đường UI có
thể tìm catalog. Ca này gồm thao tác theo ảnh do agent giám sát, chưa có
adapter catalog tự động tái lập hay benchmark Vision local. Cần xử lý
popover/submit và verifier trước khi tuyên bố tích hợp sản phẩm hoàn tất.

## Ghi chú review tích hợp — 01/11/2026

- Nhánh chính chạy lại 29 test gốc: đạt; các ca này dùng fake backend.
  Test AM-26/27 xử lý chuỗi qua fake, chưa chứng minh native JXA bằng
  tên bài đặc biệt; không dùng kết quả đó để kết luận loại mọi injection.
- Sửa hai lỗi ở parser native: MusicBackendError bị bắt lại làm mất mã/
  uncertainty; state không hợp lệ bị đổi thành stopped. Thêm
  `tests/test_apple_music_native_errors.py`, tổng 32 test Music đạt.
- Native proof đã báo cáo chỉ là read-only, chưa xác nhận play/pause/
  resume thật hoặc luồng CLI search→chọn→play. CLI/session hiện chưa đăng
  ký capability Music và chưa cập nhật MusicSelectionState từ kết quả
  search. Tích hợp này còn việc, không gọi toàn luồng đã hoàn tất.
- Tại lúc review, các file Music vẫn untracked trong checkout chung;
  tên nhánh `codex/apple-music` chưa tương đương một commit bàn giao.

## 1. Mục tiêu và phạm vi

### Kiểm lại native 02/11/2026

6/6 ca read-only đạt với JXA/Swift: AppKit, player state, search chuỗi
test Unicode, search ngoặc kép/backslash, tra ID không tồn tại, Swift
observation. Report không có dữ liệu track:
`artifacts/benchmarks/apple-music/readonly-b71bbbe9b54e4191a263c8a93f5e0523.json`.
Player default3s đạt0,193s; Swift đạt1,082s. Lần đọc player trước đó
timeout3s chưa rõ nguyên nhân, ghi AM-NATIVE-003 trong BUG_LOG. Không
dispatch playback. 32 test Music rerun đạt; full suite sau sửa922, OK
(1 skipped). Đây chưa phải chứng nhận play/pause/resume native.

Phát triển vertical slice độc lập cho Apple Music trên macOS theo kiến trúc của ELVION:
- Mở / kiểm tra ứng dụng: `app.open` (bundle `com.apple.Music`).
- Đọc trạng thái player: `music.read_state` (playing / paused / stopped / volume).
- Đọc track hiện tại: `music.current_track` (tên, nghệ sĩ, album, persistent ID).
- Tìm kiếm bài hát: `music.search` (trong thư viện cục bộ / đám mây của người dùng).
- Chọn và phát bài: `music.play` (chỉ định track qua `persistent_id`).
- Tạm dừng / Tiếp tục: `music.pause`, `music.resume`.
- Kiểm chứng độc lập: `verify_music_action` qua fresh observation (không tin tưởng response của bước execute).

### Phân biệt 4 trạng thái cốt lõi (Bằng chứng cụ thể)
1. **Ứng dụng đã mở** (`app_running`): AppKit trả về PID > 0 của bundle `com.apple.Music`.
2. **Đã tìm thấy kết quả** (`candidates_found`): Danh sách track có `persistent_id`, `name`, `artist`, `duration`.
3. **Đã chọn đúng track** (`track_selected`): Người dùng hoặc planner xác nhận `persistent_id` cụ thể, không đoán mò hay tự thay thế.
4. **Track đã bắt đầu phát** (`track_playing`): Observation độc lập xác nhận `player_state == "playing"` VÀ `current_track.persistent_id == target_persistent_id`.

---

## 2. Khảo sát hệ thống và phân tích phương án

### 2.1. App Catalog và LaunchServices
- Ứng dụng: `/System/Applications/Music.app`
- Bundle ID: `com.apple.Music`
- Executable: `Music`
- Phương thức khởi chạy: `open -b com.apple.Music` hoặc LaunchServices thông qua URL / path chuẩn hóa. Không dùng shell injection.

### 2.2. Apple Events và JXA (JavaScript for Automation)
- AppleScript Scripting Definition (`com.apple.Music.sdef`) cung cấp đầy đủ các thuộc tính và lệnh:
  - `player state`: `playing`, `paused`, `stopped`
  - `current track`: `name`, `artist`, `album`, `persistent ID`, `duration`
  - `search playlist 1 for <text>`: Tìm kiếm trong thư viện
  - `play`, `pause`, `stop`: Điều khiển playback
- **Cơ chế truyền dữ liệu an toàn**:
  - Tránh hoàn toàn việc nối chuỗi AppleScript hoặc shell argv dễ bị injection (`"`, `'`, `\`, ký tự điều khiển, tiếng Việt có dấu).
  - Sử dụng JXA (`osascript -l JavaScript`) với dữ liệu đầu vào truyền qua `stdin` dạng JSON chuẩn hóa (`NSFileHandle.fileHandleWithStandardInput`), tương tự như kiến trúc của `apple_notes.py` trong ELVION.

### 2.3. Rào cản Accessibility và Catalog Search (Blocker đã xác minh)
- **Accessibility Tree (`System Events`)**: Khi thử nghiệm trên macOS, lệnh `osascript` bị từ chối với mã lỗi `-25211` ("osascript không phải là truy cập hỗ trợ được cho phép").
- **Catalog Search**:
  - Scripting Definition (`sdef`) của Music.app chỉ cho phép lệnh `search` trên đối tượng `playlist` (thư viện người dùng: `playlist 1`).
  - Music.app **không có API scripting** để tìm kiếm trên danh mục trực tuyến toàn cầu (Apple Music streaming catalog) mà chưa thêm vào thư viện.
  - Việc tìm catalog trực tuyến đòi hỏi hoặc MusicKit Web API (yêu cầu Apple Developer Token + Music User Token) hoặc UI scripting tự động hóa khung WebKit (bị chặn bởi quyền Accessibility `-25211`).
  - **Kết luận giải pháp**: Hoàn thành đầy đủ tính năng tìm kiếm thư viện (`music.search`) an toàn; ghi nhận rõ blocker catalog search trong `Docs/APPLE_MUSIC_ISSUES.md`. Không giả lập tìm catalog online rồi báo là đã điều khiển ứng dụng thật.

---

## 3. Kiến trúc module và hợp đồng quyền

```
src/elvion/
├── core/
│   └── music.py               # Contracts, Data models, Capabilities, Constants
├── adapters/
│   └── apple_music.py         # AppleMusicAdapter, NativeAppleMusicBackend, FakeAppleMusicBackend
├── policy/
│   └── music.py               # MusicPolicy (CapabilityPolicy, Confirmation, Argument bounds)
├── verification/
│   └── music.py               # verify_music_action (Fresh observation polling)
└── planning/
    └── music.py               # plan_music_command (NL parser, selection state)
```

### 3.1. Hợp đồng quyền và ranh giới an toàn
- **Capability Grants**:
  - Đọc trạng thái (`music.read_state`, `music.current_track`, `music.search`) là các quyền đọc (read-only), risk: `low`.
  - Phát / Tạm dừng (`music.play`, `music.pause`, `music.resume`) là quyền điều khiển, risk: `medium` (có thể yêu cầu confirmation).
- **Không tự tăng volume**: Tuyệt đối không có lệnh thay đổi âm lượng; policy chặn bất kỳ thao tác volume nào.
- **Không can thiệp tài chính / thư viện**: Không mua nhạc, không đăng ký subscription, không xóa track, không chỉnh sửa playlist.
- **Bảo vệ quyền riêng tư (AM-28)**:
  - Tên bài hát, nghệ sĩ, lịch sử nghe nhạc cá nhân **không bao giờ** được ghi vào trace store hoặc log vĩnh viễn.
  - Traces chỉ lưu thông tin kiểm toán: action digest, capability, status, error code, timestamp.

---

## 4. Ma trận Test Cases bắt buộc (AM-01 đến AM-29)

| Mã | Nhóm | Mô tả test case | Trạng thái / Cách kiểm chứng |
|---|---|---|---|
| AM-01 | App & Quyền | Music chưa chạy → mở app và xác nhận đang chạy | `app.open` → AppKit observation xác nhận `running=True`, pids > 0 |
| AM-02 | App & Quyền | Music đã chạy → dùng lại app | `app.open` khi đã chạy → trả về `already_running=True` |
| AM-03 | App & Quyền | Automation/Accessibility bị từ chối | Error `-1743` hoặc permission error → `ErrorCode.PERMISSION_DENIED` |
| AM-04 | App & Quyền | Helper hoặc API hệ thống không khả dụng | macOS tool thiếu / non-darwin → `ErrorCode.UNSUPPORTED` |
| AM-05 | App & Quyền | Ứng dụng đóng giữa thao tác | Music bị đóng trước/trong lúc execute → `ErrorCode.TARGET_NOT_FOUND` |
| AM-06 | App & Quyền | Thiếu grant hoặc người dùng hủy → không dispatch | Policy chặn hoặc confirmation bị từ chối → không gọi backend |
| AM-07 | Tìm & Chọn | Tên bài và nghệ sĩ khớp duy nhất | Tìm kiếm trả về chính xác 1 track |
| AM-08 | Tìm & Chọn | Hai bài cùng tên, khác nghệ sĩ | Tìm kiếm trả về nhiều kết quả → yêu cầu chọn, không tự đoán |
| AM-09 | Tìm & Chọn | Cùng bài có bản live/remaster/cover | Phân biệt qua album / title phụ, không gộp nhầm |
| AM-10 | Tìm & Chọn | Tên tiếng Việt có dấu | UTF-8 an toàn qua JSON-stdin, không lỗi font hoặc hỏng ký tự |
| AM-11 | Tìm & Chọn | Tên có dấu ngoặc kép, apostrophe, ký tự đặc biệt | Escaping an toàn qua JSON, không lỗi cú pháp |
| AM-12 | Tìm & Chọn | Không có kết quả tìm kiếm | Trả về `candidates=[]`, không báo lỗi crash |
| AM-13 | Tìm & Chọn | Nhiều kết quả → yêu cầu người dùng chọn | Trả về danh sách ứng viên có chỉ số rõ ràng |
| AM-14 | Tìm & Chọn | Lựa chọn không hợp lệ hoặc đã hết hiệu lực | Index ngoài phạm vi hoặc token hết hạn → từ chối |
| AM-15 | Tìm & Chọn | Kết quả thay đổi sau khi người dùng duyệt | Track bị xóa / sửa trước khi phát → `ErrorCode.STALE_OBSERVATION` |
| AM-16 | Tìm & Chọn | Catalog cần login/subscription hoặc mất mạng | Báo blocker rõ ràng, không giả lập kết quả giả |
| AM-17 | Player & Verifier | Phát đúng track đã chọn | Verifier xác nhận `state=playing` VÀ `persistent_id` khớp |
| AM-18 | Player & Verifier | Player đang phát track khác → không báo đúng bài | Verifier phát hiện sai `persistent_id` → trả về `False` |
| AM-19 | Player & Verifier | App mở nhưng player chưa phát → không báo đang phát | Verifier kiểm tra `state != playing` → không xác nhận phát |
| AM-20 | Player & Verifier | Pause và kiểm chứng paused | Verifier kiểm tra `state in ("paused", "stopped")` |
| AM-21 | Player & Verifier | Resume và kiểm chứng playing | Verifier kiểm tra `state == "playing"` |
| AM-22 | Player & Verifier | Không có current track | Khi chưa phát gì → trả về `has_track=False`, không văng exception |
| AM-23 | Player & Verifier | Đọc "đang phát gì" khi đang paused | Báo thông tin track nhưng trạng thái ghi rõ là `paused` |
| AM-24 | Player & Verifier | Timeout sau dispatch → uncertain, không tự phát lại | `ActionStatus.UNCERTAIN`, `external_effect_possible=True`, không retry |
| AM-25 | Player & Verifier | Backend trả lời sai schema hoặc thiếu track identity | Bắt lỗi parse schema → `ErrorCode.VERIFICATION_FAILED` |
| AM-26 | Injection & Ranh giới | Tên bài chứa chuỗi giống lệnh shell/script | Không thực thi lệnh, coi là chuỗi ký tự thuần túy |
| AM-27 | Injection & Ranh giới | Tên bài có ký tự escape AppleScript/shell | Xử lý an toàn qua JSON payload |
| AM-28 | Injection & Ranh giới | Log/trace không chứa thông tin thư viện riêng tư | Traces không lưu tên bài / metadata người dùng |
| AM-29 | Injection & Ranh giới | Model không tự thay nghệ sĩ khi tên gần giống | Bắt buộc khớp chính xác hoặc yêu cầu làm rõ |

---

## 5. Báo cáo kết quả kiểm chứng (Native & Unit Tests)

### 5.1. Kết quả Unit Tests (29/29 Đạt)
Chạy lệnh kiểm thử độc lập:
```bash
PYTHONPATH=src:. python3 -m unittest -v tests/test_apple_music.py
```
- **Tổng số test**: 29/29 test cases đạt (AM-01 đến AM-29).
- **Thời gian chạy**: ~0.24s.
- **Hồi quy toàn bộ kho mã**: 919/919 test cases toàn dự án đạt (0 regressions).

### 5.2. Kết quả kiểm chứng Native trên macOS thật
- **Phiên bản macOS**: macOS 15.x / Darwin 24.x (Apple Silicon).
- **Phiên bản Music.app**: Version 1.6.5 (build `com.apple.Music`).
- **Backend sử dụng**: `NativeAppleMusicBackend` (JXA qua stdin JSON) và `native/macos/AppleMusicProbe.swift`.
- **Quyền hệ thống cần thiết**:
  - Direct Apple Events gửi tới `com.apple.Music` (được cấp tự động theo quyền người dùng cục bộ, không yêu cầu Accessibility -25211).
  - Quyền LaunchServices (`/usr/bin/open`) để mở ứng dụng.
- **Capability đã cấp**: `app.open`, `music.read_state`, `music.current_track`, `music.search`, `music.play`, `music.pause`, `music.resume`.
- **Hành động đã dispatch trong kiểm chứng live**:
  - `check_available()`: Kiểm tra sự tồn tại của `/System/Applications/Music.app` và Info.plist -> Đạt.
  - `app_state()`: Đọc AppKit PIDs -> `{'running': True, 'pids': [63808]}` -> Đạt.
  - `player_state()`: Đọc `state`, `volume`, `position`, `current_track` -> Đạt.
  - `search_library("a", limit=1)`: Tìm kiếm track trong thư viện người dùng -> Trả về kết quả đúng cấu trúc -> Đạt.
  - Swift probe (`swift native/macos/AppleMusicProbe.swift`): Trả về JSON hợp lệ -> Đạt.
- **Cách xác định đúng track**: Sử dụng trường `persistentID` (16 ký tự hex cố định từ Music database).
- **Ranh giới an toàn**: Không ghi lại tên bài hát hay thông tin cá nhân vào log trace hay tài liệu.

---

## 6. Hướng dẫn tích hợp cho nhánh chính (Integration Patch & Interface)

Nhánh chính có thể tích hợp Apple Music vào CLI và Session theo các giao diện sau:

### 6.1. Hợp đồng và Capabilities
- Khai báo trong `src/elvion/core/music.py`:
  - `MUSIC_APP_ID = "com.apple.Music"`
  - `MUSIC_CAPABILITIES = {"music.read_state", "music.current_track", "music.search", "music.play", "music.pause", "music.resume", "app.open"}`
- Adapter: `from elvion.adapters.apple_music import create_music_adapters, AppleMusicAdapter`
- Policy: `from elvion.policy.music import MusicPolicy`
- Verifier: `from elvion.verification.music import verify_music_action`
- Planner: `from elvion.planning.music import plan_music, is_music_command, MusicSelectionState`
- Orchestrator: `from elvion.core.music import MusicOrchestrator`

### 6.2. Cập nhật `src/elvion/core/runtime.py` (Đề xuất tích hợp)
Thêm lớp `MusicOrchestrator` vào composition root:
```python
class MusicOrchestrator(TaskOrchestrator):
    def __init__(self, *, backend=None, require_confirmation: bool = False,
                 trace_store: TraceStore | None = None, selection_state=None):
        from functools import partial
        from elvion.adapters.apple_music import create_music_adapters
        from elvion.policy.music import MusicPolicy
        from elvion.verification.music import verify_music_action
        from elvion.planning.music import plan_music

        adapters = create_music_adapters(backend=backend)
        planner = (partial(plan_music, selection_state=selection_state)
                   if selection_state is not None else plan_music)
        super().__init__(
            registry=AdapterRegistry(adapters),
            policy=MusicPolicy(require_confirmation=require_confirmation),
            verifier=verify_music_action,
            simulated=False,
            planner=planner,
            success_message="Thao tác Apple Music đã được kiểm chứng thành công",
            trace_store=trace_store,
        )
```

### 6.3. Cập nhật `src/elvion/interface/cli.py` (Đề xuất CLI subcommand)
Thêm parser lệnh `music`:
```python
    music_parser = commands.add_parser("music", help="Điều khiển Apple Music trên macOS")
    music_parser.add_argument("utterance", help='Ví dụ: "Tìm bài Nơi này có anh", "Tạm dừng nhạc", "Đang phát bài gì?"')
    music_parser.add_argument("--grant", action="append",
                              choices=["app.open", "music.read_state", "music.current_track", "music.search", "music.play", "music.pause", "music.resume"],
                              default=[])
    music_parser.add_argument("--confirm", action="store_true", help="Yêu cầu xác nhận trước khi phát hoặc dừng")
```

