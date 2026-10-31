# Desktop visibility v1 — bằng chứng AX chỉ đọc

## Thiết kế và giới hạn kết luận

MVP chỉ cho Calculator. `evaluate_visibility(evidence, *, now_ns=None,
max_age_ms=1000)` là hàm thuần: không gọi OS, file, subprocess, model hay tự
quan sát lại. Collector riêng có thể đọc trạng thái process/window và AX
hit-test. Kết quả `visible` chỉ có nghĩa **năm điểm mẫu cố định** của control
được system-wide AX hit-test trả đúng target hoặc child có native ancestry về
target, trong cùng lượt probe, sau khi binding PID/window/role/label/bbox/state
đạt. `sampled_visibility_verified=true` khi ấy;
`whole_target_visibility_verified=false` và `freshness_for_execution=false`
trong mọi kết quả. Không dùng kết quả này làm authority token hay lệnh click.

Năm điểm: tâm và bốn điểm tại 25%/75% chiều rộng, chiều cao của bbox AX; đều
nằm trong control, không làm tròn tọa độ trước hit-test. Bbox là native AX
screen points với gốc góc trên trái màn hình menu bar, y tăng xuống; giữ
x/y âm cho màn hình phụ. Không chuyển thành pixels/CSS. Bbox target phải nằm
trọn trong AXWindow và đúng một display từ bước geometry. Layout/target state
đổi, candidate trùng, window cùng PID nhưng không bind duy nhất hoặc hit-test
không hỗ trợ đều `unknown`, không tự thử điểm khác.

`blocked` chỉ khi app `isHidden`, AXWindow `AXMinimized=true`, hoặc ít nhất
một điểm trả một AX object của PID khác/window khác sau binding. Trường hợp
cuối là **điểm mẫu bị chặn theo AX z-order**, không khẳng định mọi pixel bị
che. `frontmost=false` ghi predicate riêng; một mình nó không là blocked.
Hit chỉ vào AXWindow/ancestor, sibling, thiếu PID/window identity hoặc lỗi
hit-test là `unknown`; không tính là positive. Cửa sổ trong suốt/alpha/shape,
Spaces, sheet/popup, animation, scroll clipping và race có thể làm AX hit-test
khác pixel rendering. Không dùng `CGWindowList` ở v1: rectangle/alpha metadata
không đủ chứng minh pixel nhìn thấy, và window ID linkage với AX target chưa
được thiết lập. Không xin Screen Recording vì v1 không chụp màn hình.

Backend nhận descriptor từ snapshot/target/geometry đã kiểm tra, qua stdin
JSON, không truyền label trên argv. Snapshot node ID không là native handle:
helper duyệt cây Calculator hiện tại (≤300 node, depth≤12, ≤4 giây), tìm duy
nhất AXButton có cùng **raw AXTitle/AXDescription**, enabled, bbox, subrole
và AXWindow ancestor có bbox khớp. PID và scope phải khớp. Bất kỳ thay đổi
hoặc nhiều candidate/window cùng geometry đều `unknown`. Native target
reference được giữ trong cùng process/lượt probe để so với hit-test. Helper
không gửi label/title/window list ra stdout. Python kiểm tra duplicate JSON
keys, schema/type/bool không là int, size≤64 KiB, finite bbox, ID, timestamps
và mã reason cố định; subprocess argv, `shell=False`, timeout 5 giây. Build
source-hash dưới `artifacts/native/`; không ghi đè binary hệ thống.
`same_host_clock` chỉ được caller đánh dấu true khi snapshot vừa lấy trực
tiếp trong cùng session/probe; backend mặc định false nếu nhận snapshot không
rõ provenance. Contract observer cũ chưa có host/session ID, nên snapshot
nhập từ file hoặc host khác phải giữ unknown.

`VisibilityEvidence` gắn `reference_id`, snapshot ID, bundle, PID, target
node/scope, bbox target/window, thời gian monotonic của snapshot và probe,
`same_host_clock`, flags binding/layout/state/display, hidden/minimized/
frontmost và năm hit statuses. `VisibilityResult` chỉ đưa status/reason,
structural IDs, age, số điểm, predicates; không chứa label, ảnh, title hoặc
raw tree. Timestamp snapshot của observer ghi cuối lượt đọc; `age_ms` không
đảm bảo từng node còn mới. Clock khác host/session hoặc timestamp tương lai
trả `unknown`, không clamp về 0. Upstream lỗi protocol trả `error` mã cố định.

Nguồn Apple đã đối chiếu ngày 31/10/2026:

- [AXUIElementCopyElementAtPosition](https://developer.apple.com/documentation/applicationservices/1462077-axuielementcopyelementatposition): tọa độ top-left, hit-test theo window z-order; system-wide object không giới hạn một app.
- [AXUIElementCreateSystemWide](https://developer.apple.com/documentation/applicationservices/1462095-axuielementcreatesystemwide) và [AXUIElement.h](https://developer.apple.com/documentation/applicationservices/axuielement_h): public read APIs, PID và attributes.
- [kAXMinimizedAttribute](https://developer.apple.com/documentation/applicationservices/kaxminimizedattribute): trạng thái cửa sổ minimize.
- [NSRunningApplication](https://developer.apple.com/documentation/appkit/nsrunningapplication): `isHidden`/`isActive`; Apple lưu ý thuộc tính thay đổi theo run loop và race.
- [CGWindowListCopyWindowInfo](https://developer.apple.com/documentation/coregraphics/cgwindowlistcopywindowinfo%28_%3A_%3A%29): có metadata window nhưng v1 không dùng để suy pixel visibility.

## Cách chạy và đọc kết quả

```sh
PYTHONPATH=src:. python3 -m benchmarks.desktop_visibility.runner
PYTHONPATH=src python3 scripts/check_desktop_visibility.py --label '7' --include-labels
```

Calculator phải được người dùng mở sẵn. Thiếu `--include-labels` thì demo
không gọi observer. Demo prewarm helper trước khi capture; nếu observer,
targeting hoặc geometry không đủ bằng chứng thì in reason và dừng. Không
click/gõ/activate/đổi focus, không screenshot/OCR/model, không lưu snapshot
thô. `visible` chỉ là sampled AX evidence, không là action verifier.

Benchmark synthetic và native được báo riêng. Report mới dưới
`artifacts/benchmarks/desktop-visibility/`, `synthetic_only=true`, `actions=0`;
mọi case/exception nằm trong mẫu số. Tests cố ý làm evaluator luôn visible và
sai binding để chắc chắn scorer bắt false visible. Kết quả fake không chứng
minh desktop thật. Nhánh chính cần review policy, execution freshness và
action verifier trước khi tích hợp AIMS.

Ngày 31/10/2026: 28/28 ca synthetic khớp oracle (4 sampled positive,
4 blocked, 17 unknown, 3 lỗi protocol; 0 false visible, 0 false blocked,
0 actions). Helper Swift biên dịch được. Demo native của process agent trả
`VISIBILITY_BACKEND_UNAVAILABLE`; kiểm tra riêng xác định
`DisplayGeometryBackend.read()` trả `DISPLAY_LAYOUT_UNAVAILABLE` trong môi
trường này, trước khi observer/visibility probe chạy. Không kết luận về quyền
Terminal hoặc visibility Calculator của người dùng từ lỗi môi trường đó.

### Đề xuất BUG_LOG cho nhánh chính

`LIMIT — Desktop visibility v1: AX geometry/targeting đã có smoke, nhưng chưa
có bằng chứng pixel hay execution freshness. Public system-wide AX hit-test
chỉ xác minh các điểm mẫu trong một lượt probe; overlay trong suốt, clipping,
Spaces, animation và race vẫn có thể làm kết luận khác thực tế. Trạng thái:
spike chỉ đọc, 28/28 synthetic, helper compile; process agent bị
DISPLAY_LAYOUT_UNAVAILABLE trước visibility probe, chờ native demo/review;
bước tiếp theo: kiểm tra summary
Calculator với quyền AX, sau đó thiết kế verifier riêng trước mọi action.`
