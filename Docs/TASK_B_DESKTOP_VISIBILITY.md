# Task B — Thiết kế và spike kiểm tra visibility desktop, chỉ đọc

Thực hiện trong `/Users/yingjunn_/Study_/ELVION`. Đọc AGENTS.md trước, rồi
hoàn tất thiết kế, implementation thử nghiệm, tests, benchmark và tài liệu
bàn giao. Không commit/push/reset/stash. Nhánh chính đang đo Vision9B; không
chạy model, benchmark Vision hoặc tác vụ của nhánh chính.

## 1. Mốc hiện tại

- Calculator AX observation: native observed243nodes, không truncated.
- Targeting label7: found,AXButton,enabled,candidate1 trong calculator_content.
- Ba window controls được loại bằng subroleSDK và parentAXWindow, không
  suy từ thiếu nhãn/tọa độ/ID. Defaultall_buttons vẫn giữ.
- Geometry đã nativegeometry_consistent: targetbbox[1103,-519,48,48],
  window[1093,-706,230,408],display[62,-900,1600,900],scale1.
- Chưa có visibility verification hoặc executionfreshness. Chưa click.

Đọc để dùng đúng API:

- src/elvion/desktop_observation/{contracts.py,observer.py,__init__.py}
- src/elvion/desktop_targeting/{contracts.py,locator.py,geometry.py}
- scripts/check_desktop_geometry.py
- Docs/DESKTOP_OBSERVATION.md,DESKTOP_TARGETING.md,DESKTOP_GEOMETRY.md

Mục tiêu: phân biệt visible/blocked/unknown/error bằng bằng chứng chỉ đọc
trên desktop, không biến geometry_consistent thành visible hoặc quyền click.

## 2. File độc lập được phép tạo

- src/elvion/desktop_visibility/__init__.py
- src/elvion/desktop_visibility/contracts.py
- src/elvion/desktop_visibility/evaluator.py
- src/elvion/desktop_visibility/backend.py
- native/macos/DesktopVisibility.swift
- scripts/check_desktop_visibility.py
- benchmarks/desktop_visibility/__init__.py
- benchmarks/desktop_visibility/cases.py
- benchmarks/desktop_visibility/runner.py
- tests/test_desktop_visibility.py
- tests/test_desktop_visibility_benchmark.py
- Docs/DESKTOP_VISIBILITY.md

Không sửa file hiện hữu, đặc biệt observer/helper/targeting/geometry,
core/AIMS/executor/policy/planner/UI/voice/browser/Vision hoặc artifact cũ.
Nếu cần thay contract hiện hữu, nêu đề xuất; không tự sửa. Nhánh chính tích
hợp BUG_LOG/CURRENT_TASKS. Gửi mọi bug/giới hạn/bằng chứng và giải pháp để
nhánh chính ghi nhật ký. Không coi giới hạn môi trường là lỗi model.

## 3. Thiết kế trước implementation

Ghi trong DESKTOP_VISIBILITY.md:

1. Bằng chứng nào chứng minh thuộc tính nào; điều kiện visible/blocked/unknown.
2. Nguồn public API macOS và hệ tọa độ; đối chiếu SDK/tài liệu Apple, không
   dùng private API hay đoán từ tên thuộc tính.
3. Cách gắn evidence với bundle/PID/window/target/scope/snapshot và thời gian.
4. Ranh giới: sampled-point evidence khác chứng minh toàn bộ pixel nhìn thấy;
   foreground khác visibility; visibility khác enabled/clickable/authority.
5. Quyền, dữ liệu tối thiểu, giới hạn về overlays, Spaces, nhiều màn hình,
   cửa sổ trong suốt, animation, clipping/scroll, race và stale data.

Sau đó implement spike theo thiết kế. Không cần hỏi chủ dự án để làm code
chỉ đọc/tests; nếu thiếu bằng chứng hoặc public API không đủ thì trả unknown
có lý do, không tạo positive giả để có demo.

## 4. Hợp đồng đề xuất

Tạo immutable dataclasses VisibilityEvidence và VisibilityResult cùng hàm
pure evaluate_visibility(evidence, *, now_ns=None, max_age_ms=1000).
Collector/backend riêng lấy bằng chứng chỉ đọc; evaluator không gọi OS,
file,subprocess,model hoặc tự re-observe. Đặt giới hạn hợp lý, nêu rõ trong docs.

Result tối thiểu: status visible/blocked/unknown/error,reason mã cố định,
snapshot/reference ID,bundle/PID,target_scope,thời gian/age,số điểm đã kiểm,
những predicate đã/chưa được kiểm chứng,actions=0. Không chứa authority token.

Nếu chỉ kiểm tra điểm, field phải nêu sampled_visibility_verified và
whole_target_visibility_verified=false. freshness_for_execution=false luôn
trong spike này. Không gộp mọi thứ vào một boolean visible_verified mơ hồ.

MVP chỉ Calculator. Bbox giữ nativeAXscreenpoints và gốc màn hình menu;
không scale thành pixels,CSS hoặc tọa độ click. Kiểu dữ liệu/giới hạn node/
output/thời gian và ID/binding phải được validate; bool không là int.
Tuổi tương lai, timestamps khác host/session không kiểm chứng được hoặc
layout/window/target đổi thì unknown/error phù hợp, không clamp thời gian.

## 5. Bằng chứng native có thể dùng và cách xử lý

Chỉ dùng public API đọc: process state,AX hidden/minimized/window state,
frontmost app,metadata window/layout và accessibility hit-test ở tọa độ.
Ví dụ AXUIElementCopyElementAtPosition là phép đọc, không di chuyển chuột;
chỉ dùng sau xác minh tài liệu/coordinate/binding. Không screenshot/OCR/model.

Snapshot node IDs như n115 KHÔNG là identity native bền vững hoặc AX handle
qua process. Không đọc cây mới rồi coi n115 mới là cùng element. Nếu dùng
hit-test, thiết kế helper giữ native element reference của target trong cùng
lượt probe; tái xác định mục tiêu bằng descriptor đầy đủ và tính duy nhất
(PID,window,scope,role,label,bbox/state), đối chiếu thay đổi với input.
Không tìm lại bằng label hoặc tọa độ đơn lẻ. Không bind được thì unknown.
Không trả found/visible chỉ vì cùng PID hoặc hit trúng AXWindow ancestor.

Có thể chọn center và bốn điểm nằm bên trong control làm policy cố định;
định nghĩa inset/rounding. Tất cả điểm phải được bind đúng target hoặc child
được xác minh bằng native ancestry trong chính lượt probe. Parent-only hit,
node khác cùng role,label trùng,missing identity hoặc hit-test unsupported
không được dùng làm positive. Không random điểm hoặc thử lại đến khi pass.

Windowmetadata cần bind đúng window: cùng PID chưa đủ nếu app có nhiều
window. Không dùng window title để ghép nếu không cần. Nếu không có public
windowID linkage, unique PID+geometry chỉ là đối chiếu có giới hạn; ghi rõ
và giữ unknown nếu thiếu/đổi/trùng, không gọi đó là identity tuyệt đối.

CGWindowList (nếu dùng): xác minh thứ tự front-to-back/layer và các field
cần thiết từ nguồn chính thức. Không suy visibility từ list rỗng hoặc thiếu
field/permission. Rectangle overlap không chứng minh pixel bị che bởi window
có alpha/shape phức tạp; nếu chưa đủ bằng chứng thì unknown. Không bỏ qua
sheet,popup,overlay,cửa sổ cùng app chỉ vì owner PID giống. Một điểm chưa bị
che không chứng minh toàn bộ button nhìn thấy.

AX/process báo minimized/hidden chắc chắn có thể là blocked với lý do tương
ứng. Frontmost=false tự nó không chứng minh target bị che: báo riêng predicate
hoặc unknown nếu MVP yêu cầu foreground. Phân biệt blocked được quan sát với
không có bằng chứng đủ. Thiếu AX/ScreenRecording fields không tự mở prompt
xin quyền; chỉ kiểm tra quyền mà API thực sự cần, không yêu cầu thêm quyền
không liên quan. Không tự activate hoặc làm target hiện lên để đạt visible.

## 6. Giới hạn hành vi và privacy

Không AXPerformAction,AXSetAttribute,CGEvent,click,gõ,cuộn,đổi focus,activate,
launch,AppleScript/SystemEvents hoặc mởSettings. Không private AX APIs.
Không AXValue,password,text content,clipboard,selected text.

Helper bounded thời gian/số node/depth/output, subprocess argv shell=False.
Build sourcehash vào artifacts/native, không ghi đè system binary. Lỗi JSON,
duplicate keys,bad size/bbox/timestamps => mã cố định, không rawstderr.

Demo Calculator cần --include-labels tường minh như targeting hiện có.
Không dump label/title/appname của cửa sổ khác, hoặc raw windowlist. Summary
chỉ status/reason/count/predicates và structural IDs cần thiết. Không lưu
snapshot thô/screenshot mặc định. Không log content người dùng vào BUG_LOG.
Chỉ một lượt probe; không tự retry/fallback khi không rõ.

## 7. Benchmark và tests

Ít nhất24 synthetic situations với oracle trước evaluator, covering:
unobstructed sampled target,minimized,hidden,off-display,partial clipping,
opaque/transparent/unknown overlays,same-app popup,wrong window same PID,
duplicate label,ancestor-only hit,wrong child,layout/geometry/state change,
stale/future clock,missing permission/field,unsupported hit-test and malformed
protocol. Negative origins/mixed scale giữ đúng units. Test partial điểm
đúng không đủ positive theo policy. Unknown không được tính như đã visible.

Scorer tách positive hits,false visible (nguy hiểm),false blocked,unknown,
errors; mọi observation/exception có trong mẫu số. Inject evaluator cố ý luôn
visible hoặc trả sai binding để chứng minh scorer báo trượt. Clock cố định,
không sleep; fake backend cho tests không cần desktop permission.

Runner: PYTHONPATH=src:. python3 -m benchmarks.desktop_visibility.runner.
Report JSON/Markdown tên mới dưới artifacts/benchmarks/desktop-visibility/,
synthetic_only=true,actions=0. Fake success không phải native verified.

## 8. Demo và bàn giao

Script mới dùng label7 và Calculator đã mở bằng tay; --include-labels bắt
buộc trước đọc nhãn. Prewarm helper trước thu dữ liệu để tránh stale do build.
Nếu upstream không có target/geometry/evidence thì giữ reason và dừng.
Không cần người dùng chạy nhiều lần nếu thiếu bằng chứng cùng một nguyên nhân.

Viết lệnh demo chính xác sau implementation. Native test có thể nhờ chủ dự
án chạy khi bàn giao; nếu sandbox thiếu quyền/WindowServer thì vẫn hoàn tất
thiết kế/pure tests/runner và ghi native chưa verified. Không nhận permission
required của process agent là quyền Terminal của người dùng bị mất.

Chạy test mới,benchmark,checks phù hợp và git diff --check. Bàn giao file/API,
design decisions,nguồn Apple/SDK đã xác minh,metrics fake/native tách biệt,
giới hạn và đề xuất tích hợp. Dừng ở evidence/checker chỉ đọc; chưa sửa
executor,AIMS,liveVision hoặc tự bấm nút7. Freshness cho execution và action
verifier là task riêng sau review.
