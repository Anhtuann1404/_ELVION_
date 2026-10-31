# Desktop observation v1 — macOS Accessibility, chỉ đọc

## Mục đích và phạm vi

Spike này quan sát **Calculator đã chạy** (`com.apple.calculator`) qua AX.
API `elvion.desktop_observation.observe_app(bundle_id, *, include_labels=False)`
trả `DesktopObservationResult` bất biến, status cố định `observed`,
`permission_required`, `app_not_running`, `unsupported` hoặc `error`. Chỉ
`observed` mới có `DesktopSnapshot`; lỗi đọc không bị coi là cây rỗng. Chưa nối
vào selector AIMS, planner, UI hoặc cơ chế hành động. Không dùng model/Vision.

Snapshot có schema version 1, snapshot ID, bundle ID, PID, UTC timestamp,
monotonic timestamp, tuple `DesktopElement`, cờ và lý do truncated. Element
có ID nội bộ snapshot, parent ID, AX role/subrole, enabled `true/false/unknown`,
bbox tùy chọn và label tùy chọn. Bbox `[x,y,width,height]` theo **native AX
screen points** trong hệ tọa độ AX của macOS, không phải CSS pixel, không được
dùng trực tiếp để click. Nhiều màn hình, display scaling, cửa sổ di chuyển và
thời gian giữa đọc từng node đều có thể làm tọa độ thiếu nhất quán/freshness.
Quan sát này không chứng minh target đang ở foreground hay thao tác được.

Mặc định **không đọc/trả title, description, tên cửa sổ hoặc label**. Chỉ khi
`include_labels=True`, helper đọc `AXTitle` hoặc `AXDescription` tối đa 256
ký tự mỗi node. Trong mọi chế độ không đọc `AXValue`, password, nội dung text
area, clipboard hoặc selected text. Tùy ứng dụng, title/description vẫn có
thể chứa nội dung riêng tư; chỉ bật khi thực sự cần và không đưa raw snapshot
vào trace/BUG_LOG. Script mặc định chỉ in status, reason, số node, truncated.

Helper dùng `AXIsProcessTrusted()` (không hiện prompt), tìm process đang chạy,
đọc AX tree bằng `AXUIElementCopyAttributeValue`; không launch/activate app,
không AppleScript/System Events, AX action/set attribute, CGEvent, click, gõ,
cuộn hoặc mở URL. Giới hạn 300 node, depth 12, budget native 4 giây, timeout
subprocess 5 giây, JSON output tối đa 1 MiB. Node lỗi giữ thuộc tính unknown
hoặc bị bỏ qua; chu kỳ được bỏ qua. Nếu hết budget, snapshot ghi `truncated`
và lý do. Python kiểm tra bundle ID **trước khi spawn**, gọi argv với
`shell=False`, kiểm tra schema/parent/bbox/type/size; timeout và lỗi protocol
trả mã cố định, không in raw stderr.

## Chạy thử

Trên macOS, mở Calculator **bằng tay** trước. Cấp Accessibility cho process
chạy Python/Terminal trong **System Settings → Privacy & Security →
Accessibility** nếu muốn quan sát thật. Script không tự xin quyền hoặc mở
Settings. Từ repo:

```sh
PYTHONPATH=src python3 scripts/check_desktop_observation.py
```

Lệnh chỉ in JSON tóm tắt, ví dụ `{"status":"permission_required",...}`.
Để lưu snapshot theo yêu cầu tường minh của người dùng, chọn file mới và hiểu
rằng file chứa cấu trúc AX, có thể chứa label nếu bật cờ:

```sh
PYTHONPATH=src python3 scripts/check_desktop_observation.py --write-snapshot /path/to/new-snapshot.json
```

`--include-labels` chỉ nên bật khi cần; có thể đi cùng `--write-snapshot`.
File tạo mới với quyền 0600, không ghi đè. Helper Swift được build theo SHA256
source vào `artifacts/native/desktop-observation-<hash>`; không tải code ngoài.

## Kiểm chứng và giới hạn

`tests/test_desktop_observation.py` dùng fake backend cho quyền thiếu, app
không chạy, bundle sai không spawn, cây/parent, unknown, label opt-in, schema,
bbox, JSON, output limit, timeout và lỗi backend. Swift đã compile trong môi
trường hiện tại với module cache riêng. Lệnh demo thực tế trả
`permission_required` / `AX_PERMISSION_REQUIRED` (0 node) ngày 30/10/2026;
đây **không** phải bằng chứng đã đọc Calculator qua AX. Cần chạy demo trên
desktop được cấp quyền, kiểm tra cây
quan sát thực tế, số node/truncation, tọa độ nhiều màn hình và privacy trước
khi tích hợp. `AXIsProcessTrusted()` phản ánh quyền process hiện tại; quyền
của Terminal và GUI có thể khác. Build compiler có thể không khả dụng trong
sandbox; `BUILD_FAILED/BACKEND_ERROR` không phải lỗi chất lượng AX tree.

## Đường tích hợp AIMS sau spike

1. Xác nhận native smoke trên Calculator và rà soát dữ liệu AX được phép giữ.
2. Định nghĩa policy cho app/bundle ID, yêu cầu xác nhận và nguồn authority;
   mở allowlist chỉ qua review, không mở từ input model.
3. Chuyển snapshot thành observation channel riêng trong AIMS, giữ ID/timestamp
   và độ tin cậy; không nhập AX bbox trực tiếp vào Vision/CSS coordinates.
4. Thiết kế freshness/re-observe, verifier độc lập và quyền riêng tư của trace
   trước khi cân nhắc bất kỳ action adapter nào. Module này vẫn chỉ đọc.

### Đề xuất cho nhánh chính ghi BUG_LOG

`LIMIT — Desktop AX spike: helper đã compile và fake tests đạt; demo trả
permission_required/AX_PERMISSION_REQUIRED (0 node) khi chạy trong môi trường
hiện tại. Chưa có smoke Calculator với quyền Accessibility. Chưa xác minh tree,
tọa độ nhiều màn hình, truncation và privacy thực tế. Trạng thái: đã triển khai
spike, chờ kiểm chứng native; bước tiếp theo: chạy script chỉ tóm tắt với
Calculator đã mở và quyền AX được cấp, sau đó đánh giá contract trước tích hợp.`

## Review nhánh chính — 30/10/2026

Chạy lại8tests ban đầu và demo native: permission_required,0node. Phát hiện
decoder nhận boolean version/lặp khóa; đã dùng strict_json và kiểm tra kiểu
integer tường minh, thêm test cả UTF8 lỗi. 9/9testsAX đạt, diff-checkqua.
Chưa xác minh cây Calculator thật; không tự cấp quyền hoặc thêm action.

## Smoke desktop do người dùng xác nhận

Ngày30/10/2026, sau cấp Accessibility, người dùng chạy demo và gửi
status observed,reason null,nodes243,truncated false. Đây là smoke native
thành công trên host đó; chưa đối chiếu snapshot chi tiết hoặc tọa độ.
Không suy từ truncated=false rằng AX cung cấp mọi control. Chưa tích hợp
AIMS hay cấp quyền cho bất kỳ thao tác AX nào.
