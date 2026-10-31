# Task B — Quan sát desktop macOS qua Accessibility, chỉ đọc

## Mục tiêu

Tạo module quan sát ứng dụng macOS đã chạy qua Accessibility (AX), chuẩn bị
cho AIMS mở rộng ra desktop. Module độc lập với Vision đang đánh giá held-out.
Đọc AGENTS.md trước. Không commit/push, không gọi model, không tự tích hợp
vào sản phẩm. Đây là spike quan sát, chưa phải adapter điều khiển máy tính.

## Phạm vi file

Chỉ tạo các file sau:

- `src/elvion/desktop_observation/__init__.py`
- `src/elvion/desktop_observation/contracts.py`
- `src/elvion/desktop_observation/observer.py`
- `native/macos/DesktopObservation.swift`
- `scripts/check_desktop_observation.py`
- `tests/test_desktop_observation.py`
- `Docs/DESKTOP_OBSERVATION.md`

Không sửa Vision, browser, planner, selector AIMS, core, CLI/voice/GUI,
manifest, artifact held-out hay file của người khác. Nếu cần đổi contract
chung, đề xuất khi bàn giao. Nhánh chính tích hợp BUG_LOG/CURRENT_TASKS;
gửi mô tả mọi bug/vướng mắc, bằng chứng, cách xử lý và trạng thái kiểm chứng.

## Hợp đồng module v1

Export `observe_app(bundle_id, *, include_labels=False)` và các dataclass
immutable `DesktopSnapshot`, `DesktopElement`, `DesktopObservationResult`.

- Result phân biệt observed, permission_required, app_not_running,
  unsupported, error bằng mã cố định. Không coi lỗi đọc là cây rỗng hợp lệ.
- Snapshot có schema version, ID, bundle ID, PID, UTC/monotonic timestamp,
  elements, cờ truncated và lý do.
- Element có ID nội bộ snapshot, parent ID, AX role/subrole, enabled
  true/false/unknown và bbox tùy chọn. Thiếu thuộc tính giữ unknown.
- Ghi rõ đơn vị/gốc tọa độ native; không tự coi tọa độ AX là CSS pixel
  hoặc đủ dùng click. Nêu giới hạn màn hình/scaling/freshness.
- Mặc định không trả/log nhãn riêng tư hoặc tiêu đề cửa sổ. include_labels
  chỉ bật tường minh, lấy name/title/description tối thiểu. Không đọc AXValue,
  password, text area content, clipboard hay selected text trong mọi chế độ.

MVP allowlist duy nhất `com.apple.calculator`, bundle ID được kiểm tra trước
subprocess. Chỉ quan sát process đã chạy; không tự launch/activate app,
chuyển cửa sổ hoặc hiện hộp thoại cấp quyền.

## Native helper và giới hạn

Swift dùng AppKit/ApplicationServices, AXUIElement để đọc quyền và cây AX.
Không shell, AppleScript, System Events, AXUIElementPerformAction,
AXUIElementSetAttributeValue, CGEvent, click, gõ, cuộn, openURL hay activate.
Kiểm tra quyền không tự xin quyền. Build helper theo hash vào artifacts/native.

Giới hạn node (ví dụ 300), depth (12), thời gian IPC/tổng subprocess (5 giây),
output (1 MiB); xử lý chu kỳ và node lỗi. Báo truncated khi hết budget.
Python gọi argv shell=False, validate schema/size/type/finite bbox. Timeout,
JSON sai hoặc protocol lỗi trả mã cố định, không in raw stderr/private data.
Backend native/subprocess injectable để fake tests không cần quyền AX thật.

## Kiểm thử, demo và bàn giao

Test có ý nghĩa cho: thiếu quyền không duyệt; app không chạy không launch;
bundle ID sai không spawn; parent/tree hợp lệ; unknown attribute; bbox/schema/
JSON sai; timeout/node/depth/output limits; mặc định không lộ nhãn; bật label
vẫn không đọc giá trị nhạy cảm. Fake backend xác nhận không có hành động.

Script demo chỉ Calculator, mặc định stdout trạng thái và số node. Ghi snapshot
chỉ khi người dùng yêu cầu tường minh và biết phạm vi dữ liệu. Không dump nội
dung app ra trace/BUG_LOG. Tài liệu nêu lệnh chạy, quyền cần thiết và phần chưa
xác minh. Nếu sandbox chặn, hoàn tất fake tests/script và báo chưa desktop
verified; không nhận native thành công. Chủ dự án có thể chạy demo sau.

Chạy test mới, suite phù hợp và git diff --check. Báo file, API export, kết quả
fake/native tách biệt, bug/giới hạn, lệnh demo. Không sửa sản phẩm để tích hợp;
chưa bật bất kỳ thao tác AX nào. Đưa kế hoạch tích hợp AIMS trong tài liệu.
