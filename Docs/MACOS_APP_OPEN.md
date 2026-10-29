# Native app.open: Calculator

## Trạng thái ngày 29/10/2026

Đã triển khai CLI run, allowlist, AppPolicy, native adapter/backend và verifier tiến trình.
73 unit tests thành công (48 ca cũ + 25 ca mới). Unit tests không mở ứng dụng thật.
Lần chạy tích hợp trong môi trường agent chưa mở thành công: LaunchServices trả -10827.
Người dùng xác nhận ngày 29/10/2026: lệnh chạy thành công và Calculator mở trên desktop.
Đã có xác nhận tác động thật từ người dùng; chưa nhận JSON/trace để đối chiếu verifier,
chưa phân loại lần chạy là cold launch hay app đã chạy. Cần kiểm tra các ca còn lại trước khi hoàn tất toàn bộ spike.

## Chạy từ Terminal tại thư mục dự án

```sh
PYTHONPATH=src python3 -m elvion run "Mở Máy tính" --grant app.open
```

Có thể dùng “Mở Calculator”. Tùy chọn xem trước/xác nhận:

```sh
PYTHONPATH=src python3 -m elvion run "Mở Máy tính" --grant app.open --confirm
```

Đây là lệnh thật. Thiếu `--grant app.open` thì bị chặn trước khi gọi công cụ native.
Grant là quyền nội bộ ELVION, không cấp hoặc vượt quyền macOS.
`demo` cũ vẫn chỉ tạo ghi chú trong RAM, không gọi native adapter.

## Luồng thực hiện

1. Planner chuẩn hóa tiếng Việt và chỉ nhận alias trong app_catalog; không chấp nhận app/path/URL tùy ý.
2. ActionIntent app.open có target bundle ID com.apple.calculator, arguments rỗng, hậu điều kiện app_running.
3. AppPolicy kiểm tra đúng target/action/postcondition, low risk và capability grant.
4. Registry probe native adapter: kiểm tra platform, công cụ hệ thống, metadata và executable app bundle.
5. AIMS chỉ có một native adapter thật ở mode run. Không giả lập fallback Accessibility/Vision.
6. Sau confirmation nếu được bật, policy cấp token gắn đúng intent.
7. Backend đọc trạng thái qua AppKit. Nếu app đã chạy, bỏ qua launch; vẫn kiểm chứng lần nữa.
8. Nếu chưa chạy, gọi open -a với đường dẫn Calculator cố định, shell=false, timeout 3 giây.
9. Verifier đọc mới các tiến trình đúng bundle ID, đợi app xuất hiện trong khoảng poll 5 giây.
10. Chỉ succeeded nếu có running=true và PID hợp lệ. Report simulated=false, postcondition_verified=true.

Hậu điều kiện chỉ là ứng dụng đang chạy; không cam kết cửa sổ visible/frontmost.
Không đóng ứng dụng sau test vì có thể là app người dùng đang sử dụng.

## Code cần đọc

| File | Trách nhiệm |
| --- | --- |
| core/app_catalog.py | Alias và bundle ID allowlist ban đầu. |
| planning/rules.py | Cú pháp mở ứng dụng và tạo intent. |
| policy/apps.py | Chính sách app.open cụ thể. |
| adapters/macos_apps.py | Probe, open qua LaunchServices và observation AppKit. |
| verification/apps.py | Kiểm tra bundle ID/PID bằng quan sát mới, có giới hạn chờ. |
| core/orchestrator.py | Pipeline chung và composition demo. |
| core/runtime.py | Composition native app.open. |
| interface/cli.py | Tách rõ demo và run; preview đúng mode. |
| tests/test_macos_apps.py | Kiểm thử bằng backend/runner được kiểm soát. |

## Vì sao chưa dùng Swift helper?

Spike hiện chỉ cần open và AppKit, có thể gọi bằng công cụ macOS sẵn có.
Script JXA là chuỗi cố định trong package Python, không nội suy câu lệnh người dùng;
bundle ID truyền qua argv. Không dùng System Events hay GUI scripting, không chủ động
xin Accessibility/Screen Recording/Microphone cho bước này. Nếu macOS chặn thao tác,
ELVION dừng và báo lỗi; không chuyển đường để vượt quyền.

Swift vẫn là hướng helper khi cần API native sâu hơn, IPC hoặc Keychain;
việc thay backend không thay đổi Adapter Protocol/core.

## Kiểm chứng thực tế và giới hạn

Trong môi trường agent:

- Info.plist tồn tại, bundle ID đúng, executable có trên đĩa.
- AppKit observation trả danh sách PID Calculator rỗng trước khi mở.
- LaunchServices bundle lookup không tìm được app theo ID trong lần kiểm tra.
- open -a /System/Applications/Calculator.app trả OSStatus -10827, thông điệp hệ thống kLSNoExecutableErr.
- Mặc dù thông điệp nói thiếu executable, file executable tồn tại; chưa xác định nguyên nhân môi trường.
- Luồng CLI thật kết thúc uncertain/TRANSIENT_FAILURE, evidence native_exit_code=1 và os_status=-10827.
- Không đánh dấu mở app thành công, không tự retry hay đổi sang GUI automation.

Sau lần chạy desktop được người dùng xác nhận thành công, cần kiểm tra riêng: cold launch, app đã chạy, thiếu grant,
từ chối confirmation. Không cần thay đổi thiết lập bảo mật để chạy unit tests.

Lỗi trước launch trả failed; lỗi launch nonzero/timeout có thể có tác dụng nên trả uncertain.
Lỗi kiểm chứng sau launch cũng trả uncertain. Mỗi lần gọi công cụ có timeout 3 giây;
khoảng poll 5 giây có thể cộng thêm thời gian của lần quan sát cuối.
Diagnostics chỉ lưu mã số, không lưu raw stderr vào trace.

## Nguồn API

- [Apple: NSRunningApplication.runningApplications(withBundleIdentifier:)](https://developer.apple.com/documentation/appkit/nsrunningapplication/runningapplications(withbundleidentifier:))
- [Apple: NSWorkspace.urlForApplication(withBundleIdentifier:)](https://developer.apple.com/documentation/appkit/nsworkspace/urlforapplication(withbundleidentifier:))
- [Apple: Mac Automation Scripting Guide — How Mac Scripting Works](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/HowMacScriptingWorks.html)


## Kiểm tra bổ sung

`PYTHONPATH=src python3 scripts/check_app_open.py` chạy missing_grant, declined_confirmation,
already_running. Trong agent: hai ca đầu pass, ca already_running skip vì không thấy PID Calculator.
Người dùng chạy script khi Calculator mở trong desktop Terminal để hoàn tất ca còn lại.
Tổng project hiện có 101 tests sau khi thêm Notes; 73 là mốc sau spike app.open.
