# Công việc hiện tại

Trạng thái tại 29/10/2026: đã chạy luồng CLI tạo ghi chú giả lập xuyên suốt và 131 kiểm thử unittest thành công. Có hợp đồng dữ liệu, planner quy tắc, policy cấp quyền theo tác vụ, xác nhận CLI dùng một lần, Protocol/registry adapter, AIMS chọn giữa ba adapter giả và verifier dùng observation chuẩn. Đã có native `app.open` cho Calculator. Người dùng xác nhận ngày 29/10/2026 đã chạy thành công và thấy Calculator mở trên desktop. Đây là kết quả người dùng báo, chưa có JSON/trace desktop để đối chiếu verifier. Lần thử riêng trong môi trường agent trước đó trả -10827/uncertain. Đã thêm spike Apple Notes tạo/tìm đúng tiêu đề trong tài khoản chỉ định / ELVION, luôn xác nhận khi tạo; thử đọc trong agent trả -2700. Sau đó người dùng cung cấp JSON desktop xác nhận note.create succeeded, simulated=false, postcondition_verified=true; note.find cũng succeeded, postcondition_verified=true và trả cùng ID với lần tạo. Thiếu grant/từ chối app.open đã qua subprocess check; already-running vẫn skip trong agent. Đã có trace JSONL local theo task, allowlist privacy v1 và CLI list/show; 30 kiểm thử trace/storage qua. Chưa có model hoặc SQLite; trace home mặc định chưa được desktop acceptance trong agent. `origin` trỏ tới `https://github.com/Anhtuann1404/_ELVION_.git`; chưa kiểm tra lại kết nối mạng hoặc commit/push trong lần triển khai này.

Đã chốt: Python core, Swift helper nhỏ, SQLite + Keychain; nhập/xuất CLI trước. Hai tác vụ demo thực tế đầu tiên là mở ứng dụng và tạo/tìm ghi chú. Tự xây lõi và AIMS baseline, ưu tiên nghiên cứu AIMS sau khi có dữ liệu; dùng model pretrained giai đoạn đầu. Local mặc định, cloud chỉ bật cho từng tác vụ được cho phép. Chưa chọn model/nhà cung cấp; chưa tích hợp cloud trong Sprint 0.

## Sprint 0 — bộ xương chạy được

| Ưu tiên | Việc | Hoàn thành khi |
| --- | --- | --- |
| P0 | Đã tạo khung `src/elvion/`, `native/macos/`, `configs/`, `tests/`, `benchmarks/`, `scripts/`; cập nhật docs và README. | Kiểm tra import và CLI; commit/push là bước riêng, chưa thực hiện. |
| P0 — Đã làm | Định nghĩa sáu hợp đồng chính, enum phương thức/lỗi và token nội bộ. | Validate khi khởi tạo, serialize JSON; chưa có parser JSON đầu vào tổng quát. |
| P0 — Đã làm | CLI `demo "Tạo ghi chú <tiêu đề>"` + fake `note.create`. | Chạy xuyên suốt, trả JSON status/task ID/trace ID; dữ liệu chỉ trong bộ nhớ. |
| P0 — Đã làm trong demo | Policy từ chối mặc định, grant theo lần chạy; `--confirm` hiển thị preview và nhận approval, token gắn action/task/step/thời hạn. | Kiểm tra đồng ý, từ chối, EOF, Ctrl+C, hết hạn, action thay đổi, digest/ID sai, replay. Tác vụ nhạy cảm thật vẫn chưa được hỗ trợ. |
| P0 — Đã làm | Adapter Protocol, registry ID duy nhất, descriptor và observation chuẩn. | Fake adapters cùng giao diện; verifier không import fake cụ thể; probe sai/lỗi hoặc thiếu quyền bị loại. |
| P0 — Đã làm baseline giả | Probe native/API, Accessibility, Vision giả; ưu tiên cố định sau lọc policy. | Ghi candidates/lý do; native không khả dụng thì chọn Accessibility trước thực thi. Chưa thử đường dự phòng sau thực thi lỗi. |
| P1 — Đã triển khai | Trace JSONL từng task, projection allowlist, fsync từng event, CLI list/show và tình trạng log độc lập. | 30 kiểm thử trace/privacy qua; đã ghi/đọc file tạm thật. Không lưu utterance/title/account/note ID/token. Cần desktop acceptance đường home mặc định. |
| P1 — Một phần | Native `app.open`: CLI run, allowlist Calculator, policy/AIMS và AppKit quan sát tiến trình. | 25 kiểm thử mới thành công; người dùng xác nhận Calculator mở trên desktop. Còn kiểm tra riêng app đã chạy/chưa chạy, JSON verifier và quyền trên desktop; Accessibility chưa triển khai. |
| P1 — Happy path đã xác minh | Apple Notes create/find, scope theo tài khoản / ELVION, approval bắt buộc khi tạo, đọc lại ID để verify. | 28 kiểm thử Notes qua; JXA parse/stdin smoke check qua. Create đã được xác minh qua JSON desktop: có approval, verify và succeeded, simulated=false. Find desktop cũng succeeded và trả cùng ID với lần tạo; lần đọc riêng trong agent trả -2700. |
| P1 | Benchmark 10–20 ca đại diện. | Có báo cáo success, latency, fallback, kết quả không chắc chắn. |

## Tiếp theo

0. Đã có xác nhận, Protocol/registry và native app.open. Đọc `MACOS_APP_OPEN.md`; đã nhận xác nhận từ người dùng rằng Calculator mở thành công. Cần đối chiếu JSON verifier và các ca còn lại trước khi hoàn tất toàn bộ spike. Trace bền vững và privacy allowlist đã triển khai; xem TRACE_STORAGE.md. Retention và dataset labeling còn để sau.
1. Chạy `scripts/check_app_open.py` trong Terminal desktop khi Calculator mở. Happy path create/find Notes đã được xác minh bằng JSON desktop; tiếp theo kiểm tra các ca lỗi Notes và trace home mặc định trên desktop; bổ sung Accessibility sau khi có tác vụ cụ thể.
2. Đưa browser DOM vào adapter khi có use case tìm kiếm/web cụ thể.
3. Tích hợp push-to-talk và thử STT/TTS tiếng Việt trên máy 16 GB.
4. Chỉ sau khi baseline có số đo, thử selector học máy và so trên cùng tập đánh giá.

## Definition of done cho mỗi tác vụ

Có demo lặp lại được; quyền và trường hợp từ chối rõ; hành động rủi ro có preview/xác nhận; verifier kiểm tra hậu điều kiện; log giải thích đường AIMS đã chọn; có ca lỗi và kết quả `uncertain` khi thích hợp.
