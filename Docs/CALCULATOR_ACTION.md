# Calculator AXPress — Task A, 31/10/2026

## Phạm vi

Một capability nghiên cứu `desktop.calculator.press7`, chỉ cho Calculator
đang chạy, một AXButton có nhãn chính xác `7`, scope calculator_content,
subrole nil. Không mở ứng dụng, Clear, gõ phím, click tọa độ, kích hoạt cửa
sổ hoặc dùng Vision. Chưa đăng ký vào CLI/voice/GUI chung.

Luồng dùng TaskOrchestrator/AdapterRegistry/AIMS và ConfirmationManager
hiện có. Policy mới bắt buộc hai grant của phiên: press7 và read_entry,
cùng xác nhận một lần, gắn digest với PID/process marker, bbox target/window,
display layout, action và hậu điều kiện. Thay target hoặc digest phải dừng.

## Trình tự

1. Opt-in quyền thao tác/đọc kết quả và cung cấp profile ô nhập số hiện tại đã review.
2. Build helper trước khoảng quan sát; khám phá target/geometry chỉ đọc.
3. Preview nút 7, PID, ảnh hưởng và thời hạn; chờ y/N.
4. Sau xác nhận, đọc ô nhập số hiện tại mới bằng collector độc lập Task B. Phải
   đúng process/profile/session, duy nhất và bằng 0. Thiếu bằng chứng dừng.
5. Helper reacquire target, giữ AX reference và kiểm tra geometry/process,
   enabled/minimized/hidden, hỗ trợ AXPress, layout và năm điểm AX hit-test.
6. Helper báo prepared qua private pipe. Python kiểm tra lại token, grants,
   digest và tuổi quan sát ban đầu trước commit.
7. Ghi reservation idempotency bền vững trước khi gửi bất kỳ byte commit nào;
   kiểm tra authority lần nữa, rồi gửi nonce/digest của phiên helper.
8. Trong cùng process helper, tìm lại và so CFEqual với reference đang giữ,
   kiểm tra lại target/window/layout/năm điểm mẫu và expiry. Chỉ có một
   vị trí gọi AXUIElementPerformAction(target, AXPress).
9. AX return success chỉ tạo action receipt; verifier đọc kết quả mới và gọi
   pure verifier Task B để xác nhận 0 → 7. Sau-read phải có timestamp sau mốc
   reservation. Không suy observed value từ request hoặc AX exit code.

Từ chối hoặc lỗi trước commit không được gửi action. Timeout, partial write,
native error hoặc protocol sai sau mốc có thể đã commit đều uncertain.
Không tự retry/fallback. Native helper từ chối rõ trước mutation có thể trả
blocked, nhưng reservation đã ghi vẫn không được tái sử dụng.

## Native và giới hạn

Public SDK `AXUIElement.h` mô tả cannotComplete có thể xuất hiện dù ứng dụng
đã có tác dụng. Không thử lại theo error code đó. ActionNames, AXPress,
system-wide hit testing, AppKit process metadata và CoreGraphics display
bounds đều dùng public APIs. Không gọi AXSetAttributeValue/CGEventPost.

Helper dùng JSON line qua pipe riêng, không nhận executable/action/label tùy
ý, không đọc AXValue. Process marker là launchDate cùng định dạng collector.
Giới hạn: 300 node, depth 12, mỗi pha probe 1.8s, chờ commit 1s, AX call
timeout 0.75s. Python chờ tối đa 3s prepared và 4s final.

Quan sát số 0 phải mới trong vòng 2s tại kiểm tra Python trước commit.
Final probe native vẫn có khoảng thời gian tiếp theo; helper không giữ native
reference ô nhập số hiện tại và không đọc lại số 0 ngay sát AXPress. Người dùng
hoặc ứng dụng vẫn có thể đổi nội dung giữa các lần đọc. Các guard là mẫu
quan sát có giới hạn, không loại bỏ TOCTOU, không chứng minh whole pixels,
không bảo đảm kết quả thuộc duy nhất tác động ELVION. Verifier độc lập sau
đó có thể từ chối. Thu hồi grant sau khi commit đã gửi không hủy được action
đang bay; expiry vẫn được helper kiểm tra trước dispatch.

Journal SQLite lưu key/digest, không lưu số hiển thị hoặc AX tree, file 0600.
Một key đã reserve không được gửi lại kể cả sau restart/uncertain. Mỗi yêu
cầu mới có key mới và cần xác nhận mới; không tuyên bố exactly-once toàn hệ
thống. Xóa journal hoặc hỏng storage làm mất lịch sử; không dùng thao tác đó
để retry tự động. Journal không ghi được thì không commit.

Trace dùng projection allowlist hiện có, chỉ bổ sung capability/adapter/policy
và reason codes. Không ghi raw result, bbox, profile hoặc process marker.

## Cách thử trên desktop — v2

Diagnostic đã xác định profile entry cố định: AXStaticText ID rỗng dưới
AXScrollArea/StandardInputView. Đầu tiên chạy smoke **chỉ đọc**, tự bấm 7:

```sh
PYTHONPATH=src python3 scripts/check_calculator_verification.py --include-current-entry
```

Sau khi smoke entry đạt, đưa Calculator về 0, để nút 7 không bị Terminal che.
Lệnh action có thể thay đổi trạng thái Calculator và vẫn cần xác nhận:

```sh
PYTHONPATH=src python3 scripts/check_calculator_action.py --grant-press7 --include-current-entry
```

Policy v2 dùng grant desktop.calculator.read_entry, precondition
calculator_entry_zero và postcondition calculator_entry_transition. Grant
read_result và intent v1 không được tái dùng để cấp quyền entry. Không diễn
giải entry transition thành kết quả phép tính; không tự nhấn Equals/Clear.

Lệnh vẫn chờ y/N. Enter/n hủy. Grant flags không thay xác nhận. Nếu preview
binding bị thay đổi do di chuyển cửa sổ sau bước khám phá, script dừng; không
tự cập nhật target đã được duyệt. Không bật lại bằng grant rộng hơn.

## Kiểm chứng hiện có

20 unittest dùng fake pipe/backend với policy/orchestrator thật và pure
verifier Task B. Bao phủ deny/cancel/expiry, đổi intent, thu hồi grant trước
commit, precondition sai/cũ, reservation lỗi, timeout/partial write/native
error/protocol sai sau commit, replay key qua journal mới và trace privacy.
Một AX ack không đổi display bị đánh uncertain, không retry.

Native helper đã compile. Đã chạy các request chỉ để từ chối: bool/float
version, bool PID và authorization hết hạn. Không gửi commit, không gọi
AXPress thật trong lượt phát triển này. Native positive và profile kết quả
trên desktop người dùng còn cần kiểm chứng; fake tests không thay thế chúng.


Toàn suite trong lượt này đạt **657 tests**; git diff --check đạt. Preflight
chỉ đọc của agent dừng tại DISPLAY_LAYOUT_UNAVAILABLE. Không dùng lỗi này để
suy ra quyền của Terminal người dùng và không chạy một action thiếu verifier.


### Chốt profile v2 sau diagnostic về 0

Khi về 0 chỉ còn StandardInputView; StandardResultView ở diagnostic cũ
không dùng cho digit7 smoke. Action v2 chỉ dùng current_entry profile cố định.
Lịch sử thiết kế result v1 và các lượt NOT_FOUND được giữ trong BUG_LOG.md.
Native read-only entry 0→7 vẫn chờ người dùng; chưa AXPress thật.


## Native single-action smoke confirmed — 31/10/2026

Người dùng chạy script action v2 và cung cấp summary succeeded,
AXPRESS_RETURNED, postcondition_verified=true, error_code=null, trace saved.
Mốc thực thi AXPress nút7 và quan sát độc lập entry0→7 đã đạt trên desktop.
Trace saved được ghi nhận theo summary, chưa audit lại trace trong lượt này.
Chưa kiểm chứng native mọi negative guard, app khác, causality tuyệt đối hoặc
exactly-once. Capability vẫn chỉ nằm trong script nghiên cứu có xác nhận.


## Kế hoạch negative smoke desktop — 31/10/2026

Các ca dưới đang chờ thực nghiệm, chưa coi là native pass từ unit tests.
Dùng script action v2, không đổi quyền/policy/TTL để ép chạy. Mỗi lần là
request mới có confirmation mới; không tự retry outcome uncertain.

1. Che nút: Calculator ở0, giữ nguyên vị trí cửa sổ, di chuyển Terminal che
   kín nút7. Chạy script và xác nhận y. Mong đợi failed, thường reason
   SAMPLED_VISIBILITY_UNCERTAIN, postcondition_verified=false, entry giữ0.
   Sau khi script kết thúc mới đưa Calculator ra xem. Guard trước đó có thể
   từ chối sớm hơn; khi đó ghi reason thật, không suy ra five-point guard
   đã được kiểm chứng. Nếu entry thành7 hoặc status uncertain, dừng xem trace.
2. Từ chối: Calculator ở0, nút7 không che, trả n. Mong đợi cancelled,
   PERMISSION_DENIED, entry giữ0. Không xác nhận lại cùng task.
3. Sai precondition: Calculator đang5, nút7 không che, giữ5 khi script nhắc
   về0 (đây là ca thử có chủ đích), trả y. Mong đợi failed,
   CALCULATOR_BEFORE_NOT_ZERO_OR_UNKNOWN, entry giữ5, không nối thành57.

Cần summary JSON + giá trị giao diện người dùng quan sát sau từng lượt.
Positive trước đó không chứng minh các ca âm này; read-only visibility
blocked trước đây cũng không thay negative test của action helper.


Negative native occlusion: người dùng nhận failed/STALE_OBSERVATION/
SAMPLED_VISIBILITY_UNCERTAIN, postcondition false, trace saved; UI vẫn0.
Mốc che nút đã đạt theo summary/UI quan sát ngày31/10/2026. Hai ca n và
precondition5 còn chờ, chưa audit lại nội dung trace trong lượt này.


Negative native confirmation n: cancelled/PERMISSION_DENIED,
postcondition false, trace saved; người dùng xác nhận UI vẫn0 ngày31/10/2026.
Ca precondition5 vẫn chờ; không suy rộng từ hai smoke đã đạt.


Negative precondition5: summary người dùng trả failed/VERIFICATION_FAILED/
CALCULATOR_BEFORE_NOT_ZERO_OR_UNKNOWN, postcondition false, trace saved
ngày31/10/2026. Expected refusal đã quan sát; UI sau lượt này chưa được
người dùng xác nhận trong tin nhắn. Không tự ghi nhận UI vẫn5.


Người dùng đã xác nhận UI vẫn5 sau ca precondition refusal. Bộ smoke native
đạt một positive AXPress0→7 và ba negative: occlusion/UI0, decline/UI0,
precondition/UI5. Đây là mốc trong phạm vi Calculator/nút7 đã đo; các giới
hạn TOCTOU/locale/app khác vẫn giữ nguyên. Chưa bật global CLI/voice/GUI.
