# Kế hoạch ELVION

## Tầm nhìn và ranh giới

Trợ lý cá nhân local-first cho MacBook Pro M5 16 GB: nhận yêu cầu bằng giọng hoặc chữ, hiểu mục tiêu, lên kế hoạch, chọn công cụ, thực thi trên macOS và báo kết quả kèm bằng chứng. Kiến trúc module cho phép chuyển sang hệ điều hành khác và loa thông minh sau này.

V1 hướng đến sáu nhóm khả năng: (1) giọng nói; (2) lịch, báo thức, nhắc việc; (3) tìm kiếm và tóm tắt web; (4) thao tác ứng dụng; (5) soạn và gửi tin nhắn sau xác nhận; (6) quản lý cuộc gọi khi có tích hợp phù hợp. Mỗi nhóm được bật riêng khi adapter, quyền và phép thử đáp ứng tiêu chí; đây là đích sản phẩm, không phải tính năng đã có.

## Nguyên tắc sản phẩm

- Ưu tiên dữ liệu và suy luận trên máy. Model cloud chỉ được dùng khi người dùng chủ động cho phép theo tác vụ, với mục đích và dữ liệu rõ; phát sinh ngoài phạm vi phải hỏi lại. Quyền này tách khỏi quyền dùng dịch vụ theo tác vụ và quyền gửi/sửa/xóa dữ liệu.
- Chính sách quyền được kiểm tra trước và ngay trước hành động có tác dụng bên ngoài. Hiển thị nội dung, người nhận và ứng dụng trước khi gửi tin nhắn hoặc thực hiện hành động nhạy cảm.
- AIMS chọn đường thao tác theo khả năng, độ tin cậy, thời gian và rủi ro: API/native, DOM/Accessibility, rồi thị giác khi thực sự phù hợp. Thị giác không vượt quyền ứng dụng/hệ điều hành.
- Mô hình và bộ chọn có thể thay thế. Tự xây lõi điều phối, policy, adapters, verifier và AIMS; bắt đầu bằng quy tắc đo được, sau đó mới học từ dữ liệu đánh giá. Ưu tiên nghiên cứu AIMS; planner bắt đầu đơn giản, dùng model ngôn ngữ và STT/TTS pretrained khi cần, chưa huấn luyện mô hình nền từ đầu.
- Ghi vết quyết định, bằng chứng thực thi và lỗi; tránh lưu nội dung riêng tư không cần thiết.

## Các mốc, theo thứ tự phụ thuộc

| Mốc | Đầu ra kiểm chứng được |
| --- | --- |
| 0. Foundation | CLI nhận lệnh chữ, cấu hình, event log, registry công cụ, policy và một tác vụ giả lập chạy xuyên suốt. |
| 1. Computer control + AIMS | Adapter macOS/native và Accessibility tối thiểu; selector quy tắc; demo mở ứng dụng và tạo/tìm ghi chú với kiểm chứng và xác nhận khi cần. Browser DOM bổ sung khi có use case web cụ thể. |
| 2. Agent core + evaluation | Planner theo bước có giới hạn, thực thi lại sau lỗi an toàn, bộ kịch bản và số đo thành công/thời gian/chọn đường. |
| 3. Voice + skills | Push-to-talk, STT/TTS, quản lý lịch/nhắc việc và tra cứu web; xử lý lỗi nghe nhầm. |
| 4. V1 release | Luồng nhắn tin, cuộc gọi theo năng lực hệ thống/tích hợp, kiểm thử quyền, đóng gói macOS và hướng dẫn sử dụng. |
| 5. ML research | Thu dữ liệu gắn nhãn từ trace đã giảm dữ liệu nhạy cảm; huấn luyện AIMS, so với baseline và kiểm tra lệch phân phối. |
| 6. Deep learning, đa nền tảng, IoT | Mở rộng khi V1 có dữ liệu và nhu cầu rõ; giữ hợp đồng adapter ổn định. |

Không gắn mốc thời gian cố định trước khi đo tốc độ triển khai thực tế. Mỗi mốc cần một demo tái lập và tiêu chí đo trong `CURRENT_TASKS.md`.

## Đánh giá

Tập benchmark gồm tác vụ bình thường, ứng dụng đổi giao diện, thiếu quyền, thao tác nhầm đối tượng, nội dung web không đáng tin và mạng mất kết nối. Đo task success, tỷ lệ hành động sai, tỷ lệ hỏi xác nhận đúng lúc, p50/p95 độ trễ, số lần fallback, chi phí tài nguyên và khả năng khôi phục. So AIMS với các baseline cố định (API-only, Accessibility-only, vision-only khi được phép) trên cùng tập tác vụ, tính cả trường hợp đường cố định không khả thi.
