# Vướng mắc YouTube Vision

## YT-BLOCK-001 — Browser baseline chưa có trong commit nền

- Triệu chứng: worktree tạo từ `origin/main` không có `src/elvion/browser/`, `src/elvion/vision/` hoặc phiên CLI có `:web-read`/`:web-summary`, dù các file này có trong working tree nhánh chính.
- Bằng chứng: `origin/main` tại `defd32d9`; các thư mục trên chỉ là thay đổi chưa commit ở `/Users/yingjunn_/Study_/ELVION`.
- Tác động: Không thể xây và kiểm thử vertical slice tích hợp trên nhánh độc lập mà không sao chép nền web đang được nhánh chính sửa, dễ tạo diff trùng và xung đột khi tích hợp.
- Trạng thái: Đang chờ mốc commit nền web từ nhánh chính. Chưa có thử nghiệm YouTube hoặc phép đo Vision; không kết luận chất lượng mới.
- Nguyên nhân xác minh: Chênh lệch giữa working tree và `origin/main`. Chưa có bằng chứng lỗi của browser runtime.
- Bước tiếp theo: Nhánh chính commit/push nền browser hoặc cung cấp nhánh tích hợp ổn định; rebase `codex/youtube-vision` lên mốc đó rồi triển khai module, test và phép đo trên worktree riêng.
