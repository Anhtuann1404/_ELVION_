# Nhật ký quyết định

| ID | Trạng thái | Quyết định / câu hỏi |
| --- | --- | --- |
| D-001 | Đã thống nhất | ELVION là dự án trợ lý cá nhân dài hạn, local-first cho macOS, máy đích MacBook Pro M5 16 GB. |
| D-002 | Đã thống nhất | Hybrid AIMS chọn API/native, DOM/Accessibility hoặc vision theo khả năng, độ tin cậy, tốc độ và rủi ro; không dùng thị giác để vượt quyền. |
| D-003 | Đã thống nhất | Module và hợp đồng được thiết kế sớm; triển khai baseline đơn giản trước khi huấn luyện bộ chọn. |
| D-004 | Đã thống nhất | Nhắn tin có xác nhận; mở rộng sang lịch/nhắc việc, web, ứng dụng, cuộc gọi và IoT theo giai đoạn. |
| D-005 | Đã thống nhất 29/10/2026 | Python core, Swift helper nhỏ cho macOS, SQLite cho dữ liệu và Keychain cho secret. Thư viện và chi tiết bridge cần kiểm chứng bằng spike. |
| D-006 | Còn mở | Quyền truy cập từng ứng dụng, cách quản lý cuộc gọi khả thi và model tiếng Việt cụ thể. Chính sách cloud được chốt tại D-010. |
| D-007 | Đã thống nhất 29/10/2026 | Nhập và xuất qua CLI trước; giọng nói và giao diện đồ họa triển khai sau. |
| D-008 | Đã thống nhất 29/10/2026 | Hai tác vụ demo đầu tiên: mở ứng dụng và tạo/tìm ghi chú. Ứng dụng ghi chú cụ thể, adapter và quyền cần kiểm chứng. |
| D-009 | Đã thống nhất 29/10/2026 | Tự xây orchestrator, policy, adapters, verifier và AIMS baseline. Tập trung nghiên cứu AIMS trước; chỉ huấn luyện khi có dữ liệu và benchmark. Planner bắt đầu bằng quy tắc, tự quản lý bước/điều kiện/giới hạn/phục hồi; có thể dùng model pretrained đề xuất bước khi cần. Dùng pretrained cho mô hình ngôn ngữ và STT/TTS giai đoạn đầu; chưa huấn luyện mô hình nền từ đầu hay chốt fine-tune. |
| D-010 | Đã thống nhất 29/10/2026 | Local mặc định; CLI giai đoạn đầu chỉ gọi model cloud khi người dùng chủ động cho phép cho từng tác vụ. Quyền ràng buộc mục đích, dữ liệu và thời hạn tác vụ; ngoài phạm vi phải hỏi lại. Quyền dùng model cloud tách khỏi quyền dùng dịch vụ theo tác vụ và quyền thực hiện hành động bên ngoài. Nhà cung cấp, model và hạn mức cụ thể chưa chọn. |

Khi chốt một điểm mở: ghi ngày, bối cảnh, phương án đã thử, số đo và tác động lên hợp đồng API.
