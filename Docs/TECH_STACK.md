# Công nghệ đề xuất v0.1

Ngày 29/10/2026, người dùng đã đồng ý Python core, Swift helper nhỏ, SQLite + Keychain và nhập/xuất CLI trước. Các lựa chọn còn lại trong bảng là đề xuất; package, chi tiết bridge và khả năng tích hợp từng ứng dụng cần kiểm chứng trên MacBook Pro M5 16 GB. Đã chốt tự xây lõi và AIMS baseline, ưu tiên nghiên cứu AIMS; dùng model pretrained giai đoạn đầu. Local mặc định, model cloud chỉ được bật theo từng tác vụ đã cho phép; chưa chọn nhà cung cấp hay model cụ thể.

| Lớp | Khởi đầu | Lý do / điểm kiểm chứng |
| --- | --- | --- |
| Lõi agent | Python 3, type hints, asyncio khi cần I/O | Thuận tiện thử nghiệm ML, hợp đồng adapter rõ; không ép mọi module bất đồng bộ. |
| macOS bridge | Spike app.open dùng open + AppKit qua JXA; Swift helper khi cần API/IPC sâu hơn | Đã thử native launch/quan sát; chưa triển khai Swift. Giữ ranh giới adapter để thay backend mà không đổi core. |
| Điều khiển UI | macOS Accessibility; browser DOM qua adapter riêng; ảnh màn hình khi được cấp quyền | Tách quyền và bằng chứng theo từng phương thức. |
| Lưu trữ | JSONL trace đã lọc đang dùng; SQLite metadata và Keychain secret triển khai sau | Dễ triển khai trên một máy, dễ quản lý vòng đời dữ liệu. |
| Interface | CLI trước, sau đó menu bar / desktop UI | Đảm bảo luồng lõi kiểm thử được trước khi làm UI lớn. |
| Voice | Giai đoạn sau CLI: push-to-talk; STT/TTS pretrained ưu tiên local, chọn theo benchmark trên máy | Đo tiếng Việt, latency, RAM trước khi chốt engine/model; chưa bật nghe liên tục. |
| Reasoning | Planner quy tắc tự xây + adapter model pretrained khi cần, ưu tiên local | So model nhỏ tại máy với chất lượng tác vụ; model cloud chỉ chạy trong phạm vi tác vụ được người dùng cho phép. |
| Đánh giá | Unittest thư viện chuẩn cho contracts/policy/native/trace; JSONL projection allowlist đã triển khai, chưa cần pytest | So baseline AIMS, tái lập lỗi và hồi quy. |
| Đóng gói | CLI nội bộ trước; app macOS khi quyền/bridge ổn | Kiểm thử permission trong bản đóng gói thực tế. |

Không khóa nhà cung cấp model, framework UI hay STT/TTS vào hợp đồng lõi. Mọi lựa chọn thay thế phải đo trên máy đích: RAM đỉnh, thời gian đáp ứng, độ chính xác tiếng Việt và tác vụ, mức tiêu thụ điện, quyền hệ thống và chi phí.
