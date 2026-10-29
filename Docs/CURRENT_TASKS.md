# Công việc hiện tại

Trạng thái tại 29/10/2026: đã có 7 file thiết kế trong `Docs/`; chưa có bằng chứng code chạy. Thư mục hiện tại chưa là Git working tree; chưa xác minh kết nối tới repo remote. Không đánh dấu các mốc là hoàn thành cho đến khi chạy thử.

Đã chốt: Python core, Swift helper nhỏ, SQLite + Keychain; nhập/xuất CLI trước. Hai tác vụ demo thực tế đầu tiên là mở ứng dụng và tạo/tìm ghi chú. Tự xây lõi và AIMS baseline, ưu tiên nghiên cứu AIMS sau khi có dữ liệu; dùng model pretrained giai đoạn đầu. Local mặc định, cloud chỉ bật cho từng tác vụ được cho phép. Chưa chọn model/nhà cung cấp; chưa tích hợp cloud trong Sprint 0.

## Sprint 0 — bộ xương chạy được

| Ưu tiên | Việc | Hoàn thành khi |
| --- | --- | --- |
| P0 | Đưa tài liệu vào repo, tạo `src/elvion/{core,policy,aims,adapters,storage,interface}` và `tests/`. | Có cấu trúc import được, README hướng dẫn chạy. |
| P0 | Định nghĩa Python types cho `TaskRequest`, `ActionIntent`, `ProbeResult`, `ActionResult`, `ConfirmationRequest`, `TaskStatus`. | Serialize/validate được và lỗi schema rõ. |
| P0 | CLI nhận lệnh chữ + adapter giả `note.create`. | Chạy xuyên suốt, trả status và trace ID. |
| P0 | Policy mặc định từ chối capability chưa cấp; confirmation ràng buộc digest. | Thiếu quyền bị chặn; sửa người nhận/nội dung thì xác nhận cũ vô hiệu. |
| P0 | AIMS quy tắc và probe ba adapter giả. | Chọn đúng đường khả thi; ghi lý do loại và fallback; policy phủ quyết được. |
| P1 | Event log cục bộ có lọc secret và verifier hậu điều kiện. | Không log token; success chỉ sau khi verify. |
| P1 | Spike macOS: mở ứng dụng, đọc trạng thái qua bridge/Accessibility. | Demo trên máy thật và ghi rõ permission cần cấp. |
| P1 | Benchmark 10–20 ca đại diện. | Có báo cáo success, latency, fallback, kết quả không chắc chắn. |

## Tiếp theo

1. Spike hai tác vụ đã chọn: mở ứng dụng và tạo/tìm ghi chú; xác định ứng dụng ghi chú, adapter khả thi và quyền, rồi kiểm chứng native và Accessibility trên máy thật.
2. Đưa browser DOM vào adapter khi có use case tìm kiếm/web cụ thể.
3. Tích hợp push-to-talk và thử STT/TTS tiếng Việt trên máy 16 GB.
4. Chỉ sau khi baseline có số đo, thử selector học máy và so trên cùng tập đánh giá.

## Definition of done cho mỗi tác vụ

Có demo lặp lại được; quyền và trường hợp từ chối rõ; hành động rủi ro có preview/xác nhận; verifier kiểm tra hậu điều kiện; log giải thích đường AIMS đã chọn; có ca lỗi và kết quả `uncertain` khi thích hợp.
