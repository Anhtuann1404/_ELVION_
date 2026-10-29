# Demo đầu tiên: từ câu lệnh đến ghi chú giả lập

## Kết quả và phạm vi

Đã chạy luồng CLI tạo ghi chú giả trong bộ nhớ, có kiểm tra quyền, chọn phương thức và
đọc lại trạng thái để kiểm chứng. Không dùng AI model, mạng, microphone hoặc ứng dụng thật.
Python >=3.11, thư viện chuẩn; lệnh `demo` nhận một câu qua đối số, chưa có REPL hội thoại.

## Chạy thử

Tại thư mục gốc ELVION:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI" --grant note.create
```

Kết quả JSON có `status: "succeeded"`, `selected_method: "native_api"`, `simulated: true`,
UUID của task/trace và `evidence.note_id`. Mọi method trong demo đều là fake.
Ghi chú biến mất khi chương trình kết thúc. Chạy lệnh lần nữa là một task mới.

Bỏ quyền:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI"
```

Kết quả `failed`, `PERMISSION_DENIED`, không tạo note, exit code 1.
Quyền `--grant` chỉ dành cho lần chạy demo này, không cấp quyền macOS.

Giả lập native không khả dụng:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI" --grant note.create --disable-native
```

Kết quả `succeeded`, method `accessibility`; candidates ghi native không đủ điều kiện.
Đây là chọn đường trước thực thi, không phải tự động thử lại sau hành động có tác dụng.

## Từng bước trong code

1. `interface/cli.py` dùng argparse đọc câu lệnh và quyền. Tạo `TaskRequest`, gọi orchestrator, xuất JSON và exit code.
2. `core/contracts.py` định nghĩa cấu trúc dữ liệu chung. UUID nhận diện task/step/trace; datetime chuẩn UTC khi serialize; input sai báo ContractError.
3. `planning/rules.py` chỉ hiểu `Tạo ghi chú <tiêu đề>`; giữ nguyên hoa/thường của tiêu đề. Câu khác hoặc thiếu tiêu đề trả UNSUPPORTED.
4. Planner tạo `ActionIntent`: capability `note.create`, app `FakeNotes`, title và hậu điều kiện `note_exists`. Hậu điều kiện mô tả điều cần kiểm chứng.
5. `policy/rules.py` mặc định từ chối. Chỉ cho phép hành động low-risk đúng hình dạng của demo, có grant `note.create` và target FakeNotes.
6. Mỗi fake adapter probe khả năng mà không tạo ghi chú. `aims/selector.py` loại đường không đủ điều kiện, rồi ưu tiên native → Accessibility → DOM → Vision. Demo có ba adapter, chưa có DOM.
7. Nếu policy yêu cầu xác nhận, hiển thị preview và kiểm tra response một lần; policy kiểm tra lại trước thực thi, rồi cấp token gắn task ID, step ID, digest của intent, thời hạn một phút.
8. Adapter kiểm tra token và tính lại digest. Đổi dữ liệu sau cấp quyền làm token mất hiệu lực. Token chỉ là đối tượng trong tiến trình, chưa dùng cho IPC bảo mật.
9. `adapters/fake_notes.py` ghi title vào dictionary. Idempotency key tránh tạo trùng cùng bước trong cùng process; không chống trùng xuyên lần chạy.
10. `verification/notes.py` lấy note ID rồi yêu cầu Observation chuẩn qua Adapter Protocol. Chỉ khi title và hậu điều kiện khớp, orchestrator mới báo succeeded. Báo success nhưng note không tồn tại sẽ thành uncertain.
11. `core/orchestrator.py` trả TaskReport cùng các sự kiện queued, planning, executing, verifying và trạng thái cuối. Trace không ghi title hoặc token; chưa lưu xuống đĩa.

## Các hợp đồng cần hiểu

| Kiểu | Vai trò |
| --- | --- |
| TaskRequest | Câu người dùng nhập, locale, task ID, trace ID và thời điểm. |
| TaskStatus | Tập trạng thái; chưa sử dụng mọi trạng thái trong demo. |
| ActionIntent | Hành động, target, arguments, hậu điều kiện, rủi ro và idempotency key. |
| ProbeResult | Adapter có hỗ trợ, thỏa điều kiện và lý do. |
| ActionResult | Kết quả thực thi và bằng chứng; chưa tự đồng nghĩa task thành công. |
| ConfirmationRequest/Response | Preview và phản hồi xác nhận dùng một lần; bật bằng `--confirm`. |
| AuthorizationToken | Quyền nội bộ có phạm vi và thời hạn cho đúng intent. |

Dùng dataclass để dễ đọc và không thêm dependency. Type hints giúp editor hiểu kiểu;
`__post_init__` mới là phần kiểm tra dữ liệu lúc chạy. `to_dict()` chuyển UUID, enum và
thời gian thành dữ liệu serialize JSON được. Chưa có JSON input parser tổng quát.

## Kiểm chứng

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

48 kiểm thử của demo/confirmation đã qua ngày 29/10/2026 (hiện tổng 73 khi thêm native app.open), gồm cả trường hợp lỗi: thiếu quyền, token hết hạn,
hành động bị sửa, không có adapter, native không khả dụng, success giả và uncertain.
Đây là kết quả trên môi trường phát triển hiện tại, chưa đánh giá ứng dụng thật hay model AI.

## Việc chưa làm

Đã có confirmation tương tác và Protocol/registry adapter; xem `CONFIRMATION_AND_ADAPTERS.md`.
Đã thêm mở Calculator native; xem `MACOS_APP_OPEN.md` cho trạng thái kiểm chứng.
Quyền lưu bền vững/thu hồi, SQLite/Keychain/log bền vững, tạo/tìm ghi chú trên macOS,
cloud, giọng nói và huấn luyện AIMS đều cần các bước tiếp theo.
