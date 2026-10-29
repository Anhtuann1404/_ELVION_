# Tạo và tìm ghi chú thật trong Apple Notes

## Trạng thái ngày 29/10/2026

Đã triển khai NotesScope, planner riêng, NotesPolicy, hai native adapter create/find,
backend JXA và verifier đọc lại note ID. Tổng 101 unit tests thành công (28 ca Notes mới).
Unit tests dùng backend/runner được kiểm soát; không truy cập tài khoản Notes thật.
JXA smoke check xác nhận script parse được, đọc stdin và từ chối operation sai trước truy cập Notes.
Thử tìm một tiêu đề kiểm tra trong môi trường agent trả failed/TRANSIENT_FAILURE,
reason AUTOMATION_FAILED, native_error=-2700. Sau đó người dùng cung cấp JSON desktop cho note.create: awaiting_confirmation → executing → verifying → succeeded, simulated=false và postcondition_verified=true. Đã xác nhận cả create và find qua JSON desktop: find succeeded, simulated=false, postcondition_verified=true và trả cùng ID với lần tạo. Tác vụ find mất khoảng 0,39 giây theo hai timestamp queued/succeeded của lần chạy này; đây là một quan sát đơn lẻ, chưa phải benchmark. Không lưu note ID cá nhân trong tài liệu.
Không tự tạo ghi chú hoặc tự trả lời y thay người dùng trong thử nghiệm này.

## Phạm vi

Chọn Apple Notes cho spike native đầu tiên. CLI bắt buộc chỉ rõ tên tài khoản;
không tự chọn default account hoặc chuyển từ tài khoản local sang iCloud khi thiếu.
Chỉ dùng thư mục tên ELVION trong tài khoản đã chọn. Tạo ghi chú có thể tạo thư mục này
nếu chưa tồn tại; tác dụng này được ghi trong preview để người dùng duyệt.

Bản đầu chỉ tạo ghi chú với tiêu đề, tìm đúng tiêu đề và trả ID sau kiểm chứng;
chưa nhập nội dung dài, đọc body, sửa/xóa hoặc tự hiển thị note trong UI.
Tài khoản/thư mục trùng tên hoặc nhiều ghi chú cùng tiêu đề được trả AMBIGUOUS_TARGET;
không chọn mục đầu tiên. Không xử lý ghi chú khóa hoặc thư mục/ghi chú được chia sẻ.

## Chuẩn bị và chạy

Nếu muốn lưu local, dùng tài khoản On My Mac trong Notes. Theo Apple, có thể bật tại
Notes > Settings > Enable the On My Mac account. Tên hiển thị phụ thuộc ngôn ngữ;
truyền đúng tên tài khoản mà máy sử dụng, không truyền tên thư mục vào --account.
Tên tài khoản chỉ định rõ nơi đến; adapter không tự suy luận local/cloud từ tên tài khoản.
Nếu chọn tài khoản đồng bộ, hành vi đồng bộ do Notes và tài khoản đó quản lý.

Từ thư mục dự án:

```sh
PYTHONPATH=src python3 -m elvion notes "Tạo ghi chú Ôn AI" --account "On My Mac" --grant note.create
```

Luôn có preview và prompt dù không thêm --confirm. Nhập y sau khi kiểm tra đúng title,
account và folder. n/Enter/EOF hủy; không có cờ tự động đồng ý. --grant không thay thế approval.
Không tự bật tài khoản, đổi default account hoặc thay đổi quyền hệ điều hành.

Tìm ghi chú đã tạo:

```sh
PYTHONPATH=src python3 -m elvion notes "Tìm ghi chú Ôn AI" --account "On My Mac" --grant note.find
```

Tìm chính xác trong ELVION, chỉ đọc metadata (ID/title/account/folder/locked/shared), không đọc body.
Có thể thêm --confirm cho tìm kiếm nếu muốn. Thiếu grant thì dừng trước gọi native API.
Kết quả thành công có simulated=false, evidence.note_id và postcondition_verified=true.
Không tồn tại note/account/folder: TARGET_NOT_FOUND và reason cụ thể, không tự tạo khi tìm.

Lần đầu điều khiển Notes, macOS có thể yêu cầu quyền Automation cho ứng dụng chạy lệnh.
Nếu bị từ chối, hệ thống dừng; không chuyển sang UI automation để vượt quyền.
Ứng dụng packaged tương lai cần cấu hình quyền riêng theo cơ chế macOS, chưa triển khai ở đây.

## Cách hoạt động

| File | Trách nhiệm |
| --- | --- |
| core/notes.py | Scope tài khoản rõ ràng, app ID và folder ELVION cố định. |
| planning/notes.py | Tạo/Tìm ghi chú <tiêu đề>; intent gắn scope và hậu điều kiện. |
| policy/notes.py | Grant theo capability, chặn thay scope, bắt buộc approval khi tạo. |
| adapters/apple_notes.py | Probe filesystem, JSON stdin, JXA create/find/get, xử lý lỗi và replay. |
| verification/apple_notes.py | Đọc lại ID và kiểm tra title/account/folder, trạng thái khóa/chia sẻ. |
| core/runtime.py | NotesOrchestrator lắp planner/policy/adapters/verifier riêng trong pipeline chung. |
| tests/test_apple_notes.py | 28 ca logic đúng/lỗi với backend được kiểm soát. |

Script JXA cố định, dữ liệu tài khoản/tiêu đề truyền qua stdin, không nằm trong argv/code.
Tiêu đề được escape HTML trước khi làm body; không chạy shell, không nội suy input thành mã.
Probe không khởi chạy Notes hay xin Automation; truy cập tài khoản bắt đầu trong execute,
sau khi policy cấp quyền và người dùng xác nhận nếu là create.

Tạo note/folder kiểm tra lại hạn token ngay trong JXA trước mutation để tránh thực thi
sau khi hết hạn trong lúc chờ macOS. Mỗi command timeout 15 giây. Timeout hoặc lỗi sau
khi bắt đầu mutation trả uncertain và không retry; có thể đã tạo folder hoặc note.
Cache theo idempotency key ngăn tạo lại cùng step trong một process, kể cả kết quả uncertain.
Chưa có dedup bền vững qua lần chạy mới; không tự chạy lại khi kết quả uncertain.

Verifier không tin ID trả về đơn thuần: yêu cầu quan sát mới từ đúng tài khoản/ELVION,
ID/title khớp và không shared/locked. Kiểm chứng lỗi sau create trả uncertain.
Trace events không chứa title/account/body/token; preview có thông tin đích để người dùng duyệt.
Không log raw stderr; chỉ giữ reason thuộc allowlist và native_error dạng số.

## Kiểm tra mốc app.open còn lại

Giữ Calculator đang mở rồi chạy trong Terminal desktop:

```sh
PYTHONPATH=src python3 scripts/check_app_open.py
```

Script kiểm tra thiếu grant, từ chối confirmation và already_running; không đóng ứng dụng.
Output JSON: result=pass nếu cả ba qua, incomplete nếu có ca skip, fail nếu có ca sai.
Exit code tương ứng 0/2/1. Nếu không quan sát thấy Calculator chạy, ca already_running bị skip.
Trong agent hiện: missing_grant=pass, declined_confirmation=pass, already_running=skip.
Không ghi nhận ca desktop chưa chạy là thành công; không giả lập kết quả chạy thật.

## Nguồn đối chiếu

- Scripting dictionary trên máy: /System/Applications/Notes.app/Contents/Resources/Notes.sdef.
- CocoaStandard.sdef: định nghĩa make/new/at/with properties.
- [Apple: Notes settings và On My Mac](https://support.apple.com/en-gb/guide/notes/apd97da26aed/mac)
- [Apple: How Mac Scripting Works](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/HowMacScriptingWorks.html)
