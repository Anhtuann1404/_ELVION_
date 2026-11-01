# Vướng mắc YouTube Vision

## YT-BLOCK-001 — Browser baseline chưa có trong commit nền

- Triệu chứng: worktree tạo từ `origin/main` không có `src/elvion/browser/`, `src/elvion/vision/` hoặc phiên CLI có `:web-read`/`:web-summary`, dù các file này có trong working tree nhánh chính.
- Bằng chứng: `origin/main` tại `defd32d9`; các thư mục trên chỉ là thay đổi chưa commit ở `/Users/yingjunn_/Study_/ELVION`.
- Tác động: Không thể xây và kiểm thử vertical slice tích hợp trên nhánh độc lập mà không sao chép nền web đang được nhánh chính sửa, dễ tạo diff trùng và xung đột khi tích hợp.
- Trạng thái: Đã giải quyết phần thiếu nền: `feat/browser-vision-base` tại `b8766e6` đã được push; nhánh YouTube đã rebase lên commit này. Chưa có phép đo Vision; không kết luận chất lượng mới.
- Nguyên nhân xác minh: Chênh lệch giữa working tree và `origin/main`. Chưa có bằng chứng lỗi của browser runtime.
- Bước tiếp theo: Tiếp tục triển khai và đo trên worktree YouTube. Tích hợp CLI ở nhánh chính vì `interface/session.py` vẫn ngoài phạm vi sửa.

## YT-NATIVE-001 — YouTube public search đôi khi không đạt trạng thái sẵn sàng

- Triệu chứng: cùng truy vấn công khai `python tutorial`, một lượt Chromium headless có tiêu đề và 12 `ytd-video-renderer` sau 1 giây; một lượt khác `YouTubeSession.navigate` chờ `document.title.length > 0` 10 giây rồi trả `YT_PAGE_NOT_READY`.
- Bằng chứng: hai lượt chạy trong worktree YouTube ngày 02/11/2026; trang chỉ đọc, không đăng nhập/click. Một capture dev khác có ảnh viewport và metadata tại `artifacts/benchmarks/web-observation/capture-73805142f5d6/`. Không lưu raw DOM.
- Tác động: Chưa thể coi native search ổn định hoặc xác nhận luồng mở video end-to-end.
- Trạng thái: Đang điều tra; chưa có lỗi code đã xác minh. Giả thuyết gồm tải tài nguyên bị chặn bởi policy cùng host, mạng hoặc trạng thái động của YouTube; chưa phân biệt được.
- Bước tiếp theo: Dùng các lần thử bounded trên cùng policy để ghi mã lỗi, URL cuối, ready/title/result counts; không nới host, không tự retry sau dispatch và không thay đổi kết luận Vision cũ.
