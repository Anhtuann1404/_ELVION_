# Desktop AX targeting v1 — chỉ đọc

## API và ranh giới

`elvion.desktop_targeting.locate_control(snapshot, *, label, role='AXButton',
now_ns=None, max_age_ms=2000) -> DesktopTargetResult` chỉ duyệt
`DesktopSnapshot` đã có. Locator không gọi Accessibility, observer, subprocess,
file, mạng, model hoặc thao tác. Kết quả bất biến có status, reason mã cố định,
snapshot ID, node ID/role/enabled/bbox chỉ khi `found`, số exact candidates và
tuổi snapshot. Node ID chỉ có nghĩa trong một snapshot; kết quả không phải
authority token, không cấp quyền click hay chứng minh control còn hiện/focus.

MVP chỉ hỗ trợ `com.apple.calculator`, schema 1, `AXButton`. Input/snapshot
được kiểm tra lại: kiểu exact (bool không là int), PID/timestamps, ID duy nhất,
root/parent/depth ≤12, ≤300 elements, bbox native AX screen points hữu hạn
với width/height dương. X/y âm hợp lệ trên màn hình phụ. Không clamp hoặc đổi
tọa độ thành CSS/click coordinates. Không suy visibility từ bbox.

Nhãn dùng NFC, gộp whitespace, casefold; giữ dấu tiếng Việt, dấu câu, chữ số
và ký hiệu. Không fuzzy, bỏ dấu, dịch, substring hay đổi `plus` thành `+`.
Nhãn trống, >256 ký tự hoặc có control characters bị từ chối. Một exact
`AXButton` enabled=True có bbox mới `found`. Hai button cùng nhãn là
`ambiguous`, **kể cả một nút disabled**. Exact label ở role khác đã biết
không được chọn. Node role unknown có cùng nhãn, hoặc button/unknown-role
thiếu nhãn, làm bằng chứng không đủ: `unavailable`, kể cả khi đã thấy một
button phù hợp; nhờ vậy không chọn nhầm một trong hai nút có thể trùng.
Một candidate disabled/unknown enabled/thiếu bbox cũng `unavailable`.
`not_found` chỉ có nghĩa không thấy exact AXButton **trong cây đủ bằng chứng**,
không khẳng định target vắng khỏi app hay ngoài snapshot.

Freshness dựa trên monotonic clock cùng host. Timestamp tương lai trả
`stale/CLOCK_IN_FUTURE`; `age_ms > max_age_ms` trả
`stale/SNAPSHOT_EXPIRED`. `max_age_ms` integer 1–10000, mặc định 2000;
biên đúng 2000 ms còn hợp lệ. Snapshot truncated luôn `unavailable` sau khi
loại clock tương lai, kể cả có candidate; không tự re-observe. Timestamp của
observer hiện ghi **cuối lượt thu thập**, nên tuổi theo snapshot có thể nhỏ
hơn tuổi của node đầu tiên. Đây chưa phải freshness đủ cho thực thi.

## Benchmark synthetic

`benchmarks/desktop_targeting/cases.py` định nghĩa **30 ca** với oracle thủ
công trước khi gọi locator: positive, absent, duplicate, wrong role, disabled,
unknown enabled/label/role, thiếu bbox, stale/future, truncated, parent/ID/
schema/bbox sai, Unicode và punctuation. Runner:

```sh
PYTHONPATH=src:. python3 -m benchmarks.desktop_targeting.runner
```

Runner không mở Calculator, không cần AX, model hoặc quyền desktop. Mỗi lần
xuất JSON và Markdown tên mới, quyền 0600 dưới
`artifacts/benchmarks/desktop-targeting/`. Report ghi `synthetic_only=true`,
`actions=0`, mọi ca/exception trong mẫu số, accuracy theo expected status,
positive hit, wrong target (đúng text nhưng sai node vẫn trượt), false
acceptance trên negative, false rejection, correct refusal và lỗi bất ngờ.
`correct` tổng là độ khớp oracle synthetic, **không** có nghĩa mọi ca từ chối
là tác vụ thành công. Lần đầu 31/10/2026: 30/30 khớp oracle, 0 false
acceptances, 0 actions. Đây là unit/synthetic evidence, không phải kết quả
trên mọi app hay kết quả học máy. Test scorer với locator cố ý trả node sai
đã chứng minh wrong-target và false-acceptance được tính trượt.

## Demo Calculator thật

Người dùng tự mở Calculator trước. Không có cờ `--include-labels`, script
**không gọi observer** và chỉ nhắc opt-in. Khi bật, nó gọi observer đúng một
lần với `include_labels=True`, rồi định vị ngay nếu upstream trả `observed`:

```sh
PYTHONPATH=src python3 scripts/check_desktop_targeting.py --label '7' --include-labels
PYTHONPATH=src python3 scripts/check_desktop_targeting.py --label '+' --include-labels
```

Stdout chỉ gồm summary status/reason/snapshot ID, node ID/role/bbox **nếu
found**, tuổi và candidate count; không dump cây/label khác, không lưu
snapshot. Nếu permission/app không chạy/lỗi, script in upstream status rồi
dừng, không gọi locator trên cây rỗng, không mở app, xin quyền, thử lại,
click/gõ/AX action hay đổi focus. Title/description có thể riêng tư; đề xuất
liệt kê nhãn chỉ qua công cụ opt-in riêng sau review và cần giới hạn dữ liệu,
không tự thêm dump vào demo này. Nhãn `7`, `+`, `=` có thể khác theo ngôn ngữ
và mode Calculator; không tự đổi nhãn để tạo kết quả pass.

Smoke observer do người dùng báo ngày 30/10/2026 là `observed`, 243 nodes,
`truncated=false`; chưa có đối chiếu label, role/bbox từng node. Benchmark
30/30 không chứng minh demo native sẽ `found`. Lần thử demo `--label '7'
--include-labels` trong môi trường agent ngày 31/10/2026 trả
`permission_required/AX_PERMISSION_REQUIRED`, không có snapshot; quyền của
process này khác smoke người dùng. Chưa nối AIMS/executor;
nhánh chính cần review policy, freshness verifier và action adapter riêng.

### Nội dung đề xuất để nhánh chính ghi BUG_LOG

`LIMIT — AX targeting v1: synthetic 30/30, 0 false acceptances; chưa xác minh
label/role/bbox Calculator thật. Observer smoke 243 nodes không chứng minh
target 7/+ hay các node khác có AXTitle/AXDescription. Freshness timestamp
ghi cuối thu thập nên chưa đủ cho execution. Trạng thái: locator đã kiểm thử
synthetic, chờ native review; bước tiếp theo: demo opt-in một nhãn trên
Calculator đã mở, review summary/snapshot an toàn, rồi thiết kế verifier và
policy trước tích hợp AIMS. Không có nguyên nhân lỗi model/AX được xác minh.`

## Review nhánh chính — 31/10/2026

Đã chạy lại14tests targeting/benchmark và9tests observer:23đạt. Benchmark
synthetic30/30,0falseacceptances,0actions tại
artifacts/benchmarks/desktop-targeting/desktop-targeting-20261030T175351-d7c3eeaf.json.
Chờ summary targeting native từTerminal đã có quyền; không yêu cầu cấp
quyền lại chỉ vì process agent củaTaskB báopermission_required. Chưa sửa
code sản phẩm trong lượt review, chưa tích hợp AIMS hayaction.

## Diagnostic incomplete evidence — 31/10/2026

Native summary cho label7 có1exactcandidate nhưng unavailable do unknowns.
Để biết nhóm node gây chặn mà không dump nhãn/tọa độ, chạy:

```bash
PYTHONPATH=src python3 scripts/check_desktop_targeting.py --label '7' --include-labels --diagnose-evidence
```

Script vẫn chỉ observe một lần rồi tìm; chỉ khi reason incomplete mới xuất
counts, tối đa8blocker IDs/roles và ancestor chains, cùng count trạng thái
candidate enabled/bbox. Không có label dump hay click coordinates. API pure
evidence_summary không cấp quyền hay nới guard; snapshotID/nodeID chỉ là
tham chiếu trong snapshot.25AXtestsđạt,synthetic30/30giữ nguyên.

## Phạm vi calculator_content — 31/10/2026

Diagnostic desktop xác nhận1button7 enabled có bbox và3AXButton thiếu nhãn
là con trực tiếp AXWindow. Chưa có subrole trong diagnostic cũ nên chưa
khẳng định ba nút là close/minimize/zoom. Không đoán từ số lượng3hay vị trí.

API thêm scope='all_buttons' mặc định (giữ policy cũ), hoặc
scope='calculator_content'. Phạm vi content chỉ loại AXButton có subrole
AXCloseButton/AXMinimizeButton/AXZoomButton/AXFullScreenButton **và parent
trực tiếp AXWindow**. Subrole thiếu/khác, parent khác hoặc role unknown
không được loại. Đây là scope có chủ đích loại window-management controls,
không là chứng minh visibility của mọi node còn lại. Bbox/label/enabled và
duplicate/stale/truncated guards vẫn giữ. Không dùng scope này để tìm nút
quản lý cửa sổ; kết quả found luôn mang trường scope để caller biết phạm vi.

Tên subrole đã đối chiếu SDK macOS tại
ApplicationServices.framework/Frameworks/HIServices.framework/Headers/AXRoleConstants.h.

```bash
PYTHONPATH=src python3 scripts/check_desktop_targeting.py --label '7' --include-labels --scope calculator-content --diagnose-evidence
```

Diagnostic nay có subrole của blocker và số excluded_window_controls/
excluded_subroles, kể cả khi found, không nhãn hoặc tọa độ blocker. Vẫn
chỉ một observation.28AXtests đạt; benchmark cũ30/30 là scopeall_buttons,
không mạo nhận30ca benchmark riêng cho content. Content có unit tests về
subrole/parent thật, unknowns, duplicates/freshness và binding scope demo.
Chờ người dùng chạy để xác minh subroles và nút7thật; chưa click.

## Native content scope do người dùng xác nhận —31/10/2026

Demo label7 trả found/EXACT_BUTTON,AXButton enabled,candidate1,243nodes,
blockers0. Ba exclusions xác nhận subrolesAXCloseButton/AXZoomButton/
AXMinimizeButton mỗi loại1. Đây là native summary do người dùng gửi; chưa
review fullsnapshot hoặc đối chiếu tọa độ. Bbox cóyâm, phù hợp khả năng
negative origin trong nativeAXcoordinates nhưng chưa xác minh layout màn
hình. Không có click. Chỉ chốt mốc tìm label7trong Calculatorcontent, không
suy ra mọi nhãn/app hoặc freshness đủ cho actionadapter.
