# Xác nhận và hợp đồng adapter

## Kết quả

Ngày 29/10/2026: demo có xác nhận tương tác trước hành động, kèm Adapter Protocol,
registry và observation chuẩn. Giai đoạn này có 48 kiểm thử; hiện tổng 73 sau khi thêm native app.open. Xem `MACOS_APP_OPEN.md` để biết kết quả chạy thật.

## Chạy thử

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI" --grant note.create --confirm
```

CLI hiện preview gồm app, capability, arguments và risk; request có ID, digest và hạn dùng.
Nhập `y`, `yes` hoặc `có` để đồng ý. Phản hồi khác, Enter hoặc EOF từ chối; Ctrl+C trong
lúc chờ hủy tác vụ. Confirmation hết hạn sau 60 giây: nhập y sau hạn vẫn không chạy.
Mặc định note.create giả low-risk chỉ cần grant; --confirm bật chế độ thử approval.
Không bật gửi tin, sửa/xóa dữ liệu thật hoặc tự động đồng ý cho hành động nhạy cảm.

- `--grant note.create`: cho phép capability cho lần chạy.
- `--confirm`: yêu cầu xem trước và đồng ý đúng hành động trong phạm vi capability đó.
- Thiếu grant thì không có prompt, không thực thi.
- stdout luôn là TaskReport JSON; preview và prompt đi stderr.
- Ghi chú chỉ trong RAM, mất khi process kết thúc.

## Cơ chế confirmation

1. Planner tạo ActionIntent, policy kiểm tra capability và target.
2. Registry/AIMS chọn adapter đủ điều kiện.
3. Policy tạo ConfirmationRequest: ID, step ID, preview, digest SHA-256 và hạn dùng.
4. CLI trình bày request rồi tạo ConfirmationResponse từ phản hồi trực tiếp của người dùng.
5. Policy kiểm tra lại quyền và tiêu thụ confirmation. ID/digest sai, đổi nội dung/người nhận,
   hết hạn, từ chối hoặc dùng lại đều không được cấp token.
6. Nếu hợp lệ, cấp token cho đúng task/step/digest, với thời hạn không vượt approval.
7. Adapter tính lại digest và kiểm tra token trước thực thi. Verifier đọc observation mới.

ConfirmationManager lưu các request trong RAM. Mỗi request chỉ dùng một lần;
tạo preview mới cho cùng step loại preview cũ. Các lỗi không tự retry.
Khi action thay đổi, hệ thống dừng: cần tạo request mới rồi xin xác nhận lại,
chưa có giao diện chỉnh nội dung và tự động hỏi lại trong cùng phiên.

Không có handler xác nhận thì trả awaiting_confirmation kèm preview, không thực thi;
không giữ request để resume. CLI luôn cung cấp handler khi có --confirm.
Token là đối tượng nội bộ trong process tin cậy, chưa là credential cho IPC hoặc plugin không tin cậy.

## Adapter Protocol

`core/adapter.py` chỉ phụ thuộc hợp đồng dữ liệu chung:

| Thành phần | Vai trò |
| --- | --- |
| descriptor | Khai báo ID, app/platform, method, quyền, capabilities, khả năng verify và simulated. |
| probe(intent) | Kiểm tra hỗ trợ/readiness; không tạo tác dụng bên ngoài. |
| execute(intent, token) | Thực thi đúng action đã được policy cho phép. |
| observe(request) | Đọc trạng thái bằng ObservationRequest/Observation. |

`adapters/registry.py` đăng ký/tra cứu theo descriptor.name, chặn ID trùng,
kiểm tra quyền adapter và loại probe lỗi/sai ID/sai method. `can_verify=false` bị loại
ở baseline này. Verifier không còn import FakeNotesAdapter cụ thể.

Observation có trạng thái observed, not_found hoặc unavailable. Với note.create,
verifier yêu cầu đúng note ID và title khớp hậu điều kiện. Observation lỗi không được
biến thành success. Execute lỗi hoặc result sai method trả uncertain, không thử đường khác.

Protocol giúp thống nhất cách gọi; không tự kiểm chứng được tính trung thực của adapter.
Cần test tích hợp cho từng adapter thật. DemoOrchestrator hiện từ chối descriptor simulated=false.

## File nên đọc theo thứ tự

1. `core/contracts.py`: ConfirmationResponse, CapabilityDescriptor, ObservationRequest/Observation.
2. `core/adapter.py`: giao diện adapter chung.
3. `adapters/registry.py`: quản lý adapter và kiểm tra probe.
4. `policy/confirmation.py`: quản lý preview/approval một lần.
5. `policy/rules.py`: quyền và phát hành token.
6. `core/orchestrator.py`: nối luồng, trạng thái chờ/hủy/lỗi.
7. `interface/cli.py`: nhập phản hồi và xuất kết quả.
8. `tests/test_confirmation_and_registry.py`: các ca đúng/sai cụ thể.

## Kiểm thử

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Kiểm tra đủ quyền + approval, thiếu quyền, từ chối, EOF/Ctrl+C, hết hạn, replay,
reissue, đổi nội dung/người nhận, probe lỗi và exception lúc execute/observe.
Preview được trình bày có chủ ý cho người dùng; events không ghi nội dung riêng tư hoặc token.
Chưa có log bền vững, resume task, SQLite/Keychain hoặc Swift helper. Native app.open dùng backend hệ thống sẵn có, xem `MACOS_APP_OPEN.md`.
