# Kế hoạch thử nghiệm YouTube bằng DOM và Vision

Ngày 01/11/2026. Trạng thái: kế hoạch; chưa triển khai hoặc đo native. Nền browser/vision hiện chỉ có trong working tree nhánh chính, chưa có ở `origin/main`; xem `YOUTUBE_VISION_ISSUES.md`.

## Vertical slice

1. Dùng Chromium context riêng của `BrowserSession`; tìm bằng URL `https://www.youtube.com/results?search_query=...` qua `navigate` sau grant và xác nhận cho truy vấn. Không mở rộng allowlist host. Đọc tối đa một danh sách ngắn các `ytd-video-renderer` đang hiển thị, lấy tiêu đề, kênh, URL và `v` video ID. Bỏ ads/Shorts/playlist; nếu DOM thiếu hoặc không nhất quán thì dừng, không đoán.
2. Trả handle gắn với đúng phiên và video ID, hiển thị danh sách để người dùng chọn. Hai tiêu đề trùng nhau vẫn phân biệt bằng kênh và video ID. Trước điều hướng, kiểm tra handle còn hợp lệ và xác nhận đúng URL/video ID đã chọn.
3. Điều hướng đúng URL video đã duyệt bằng browser hiện có. Verifier đọc URL cuối và `v` độc lập với kết quả `navigate`; sai ID, consent/login/captcha hoặc trạng thái không rõ thì không báo thành công và không tự thử lại. Thành công chỉ là **đã mở trang video**, không suy ra video đang phát.
4. Tích hợp bằng capability và policy riêng cho YouTube; nhánh chính nối CLI/session sau bàn giao vì `src/elvion/interface/session.py` ngoài phạm vi sửa. Không thêm framework browser tổng quát.

## Ranh giới DOM và Vision

- DOM đủ rõ cho đọc danh sách, nhận video ID, chọn handle và kiểm tra URL sau điều hướng. Vision không cần thiết để làm các bước này.
- Vision chỉ là phép đánh giá riêng cho ô tìm kiếm và thẻ video khi DOM không có locator đáng tin. Dùng `VisionFrame`/grounder/controller hiện có; proposal trên ảnh không được tự cấp quyền hoặc click.
- Harness capture ảnh viewport thật, metadata frame/source/model, oracle do người chấm khóa trước inference, và bảng kết quả riêng cho DOM/Vision/click. Chỉ cho phép click thử nghiệm sau ngưỡng chất lượng định trước trên tập held-out; các ảnh dev đã xem không tính là kiểm độc lập.

## Kiểm chứng và giới hạn

- Fixture kiểm các ca YT-01..15 và YT-V01..10 khi YouTube thật không ổn định; báo fixture và native riêng, kể cả failure/timeout trong mẫu số.
- Native thử không đăng nhập và không thao tác tài khoản. Browser policy có thể chặn host phụ hoặc consent, vì vậy không nới chính sách chỉ để qua ca test.
- Lệnh chạy và báo cáo số liệu sẽ bổ sung sau khi có mốc browser/vision ổn định để rebase worktree này. Chưa có bằng chứng native hay benchmark YouTube mới.
