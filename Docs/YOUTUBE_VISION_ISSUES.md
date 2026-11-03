# Vướng mắc YouTube Vision

## YT-BLOCK-001 — Browser baseline chưa có trong commit nền

- Triệu chứng: worktree tạo từ `origin/main` không có `src/elvion/browser/`, `src/elvion/vision/` hoặc phiên CLI có `:web-read`/`:web-summary`, dù các file này có trong working tree nhánh chính.
- Bằng chứng: `origin/main` tại `defd32d9`; các thư mục trên chỉ là thay đổi chưa commit ở `/Users/yingjunn_/Study_/ELVION`.
- Tác động: Không thể xây và kiểm thử vertical slice tích hợp trên nhánh độc lập mà không sao chép nền web đang được nhánh chính sửa, dễ tạo diff trùng và xung đột khi tích hợp.
- Trạng thái: Đã giải quyết phần thiếu nền: `feat/browser-vision-base` tại `b8766e6` đã được push; nhánh YouTube đã rebase lên commit này. Chưa có phép đo Vision; không kết luận chất lượng mới.
- Nguyên nhân xác minh: Chênh lệch giữa working tree và `origin/main`. Chưa có bằng chứng lỗi của browser runtime.
- Bước tiếp theo: Tiếp tục triển khai và đo trên worktree YouTube. Tích hợp CLI ở nhánh chính vì `interface/session.py` vẫn ngoài phạm vi sửa.

## YT-NATIVE-001 — Phép chờ tiêu đề YouTube lỗi do Trusted Types

- Triệu chứng: `YouTubeSession.navigate` báo `YT_PAGE_NOT_READY` dù có lượt trang đã hiện tiêu đề và 16 `ytd-video-renderer`.
- Nguyên nhân đã xác minh ngày 04/11/2026: `page.wait_for_function("document.title.length > 0")` trả ngay `EvalError: Evaluating a string as JavaScript violates this document's Trusted Type assignment requirements.` Lỗi bị bắt rộng và đổi thành `YT_PAGE_NOT_READY`, khiến chẩn đoán ban đầu sai.
- Sửa: đọc `page.title()` qua Playwright trong tối đa 10 giây; không thực thi chuỗi JavaScript trong trang, không thay policy/allowlist và không retry điều hướng.
- Kiểm: 3/3 lượt Chromium headless đọc được tiêu đề, 12–16 renderer; một lượt `YouTubeWorkflow.search` trả 5 video; một lượt tìm rồi mở đúng URL/video ID đã chọn. Đây là mẫu nhỏ, chưa chứng minh ổn định dài hạn hoặc phát video.
- Trạng thái: Đã sửa lỗi chờ; giữ kiểm native trên các trang và trạng thái YouTube khác trong phạm vi đánh giá tiếp theo. Capture dev cũ tại `artifacts/benchmarks/web-observation/capture-73805142f5d6/` vẫn chưa có annotation độc lập hoặc điểm Vision.

## YT-VISION-001 — Pilot bỏ sót ô tìm kiếm trên ảnh YouTube

- Ngày 04/11/2026, người dùng đo ô tìm kiếm trên ảnh công khai `capture-f3a8575c460a` tại `[315.8,5.3,542.3,41.5]` trước inference. Ảnh và annotation đã khóa hash; actions=0. Một người tự chấm và tự kiểm, chưa có reviewer thứ hai.
- Pipeline OCR/Vision cấu hình `qwen3.5:4b` trả `not_found`/`TARGET_NOT_FOUND` trong 2762.5 ms. Scorer ghi `false_abstention`; không click. Proposal tại `artifacts/benchmarks/youtube-vision/capture-f3a8575c460a/proposal-f89b39f629d3.json` (artifact cục bộ, không commit).
- Ca thứ hai `capture-8658300f622e` là trang chủ với ô trống, người dùng đo `[317.6,8.6,539.9,36.1]` trước inference. Pipeline cùng cấu hình vẫn trả `not_found`, `false_abstention` sau 465.0 ms; proposal `proposal-61b35779853f.json` trong capture đó.
- Kiểm ảnh sau inference: ca đầu chứa truy vấn trong ô; ca thứ hai hiển thị placeholder tiếng Việt “Tìm kiếm” trong khi target đầu vào là “Search”. OCR native-v1 và upscale2x-v2 đều có 0 khớp chính xác với “Search” trên cả hai ảnh; ảnh thứ hai cũng không đọc được placeholder mờ. Grounder yêu cầu ứng viên nhãn trước khi xác minh vai trò, nên chưa có cơ sở quy lỗi riêng cho model 4B. Đây là chẩn đoán đường OCR/nhãn, không là phép đo khả năng nhận diện ngữ nghĩa độc lập của model.
- Trạng thái: Mở. Cần thêm scene và reviewer độc lập, khóa nhãn trước inference. Không dùng hai ca pilot này để bật Vision live hoặc báo tỷ lệ tổng quát.
