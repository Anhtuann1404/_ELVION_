# Kế hoạch thử nghiệm YouTube bằng DOM và Vision

Ngày cập nhật 02/11/2026. Nền browser/Vision đã được đóng gói tại `feat/browser-vision-base` (`b8766e6`) và nhánh YouTube đã rebase lên đó. Đã có thử nghiệm DOM và ảnh dev; chưa có phép đo Vision hoặc xác nhận mở video end-to-end. Xem `YOUTUBE_VISION_ISSUES.md`.

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
- Lệnh chạy DOM có grant và xác nhận riêng cho tìm kiếm/mở video:
  `PYTHONPATH=src:. /Users/yingjunn_/Study_/ELVION/.venv-browser/bin/python scripts/check_youtube.py --query 'python tutorial' --grant web.open`
  khi đứng ở worktree YouTube. Nếu interpreter này không còn, chuẩn bị
  Playwright riêng theo `scripts/prepare_browser.py`.
- `YouTubeWorkflow` dùng `web_runtime` cho hai lần `web.open`; chính sách, grant,
  confirmation và verifier URL không bị thay. Kết quả gắn handle, kênh, video ID
  và revision; chọn handle cũ hoặc browser đã đóng sẽ dừng trước dispatch.
  Verifier thứ hai so video ID từ URL cuối, và chỉ nói “đã mở trang”, không nói “đang phát”.
- `PYTHONPATH=src:. python3 -m unittest discover -s tests -q`: 329 test đạt,
  1 skip CLI integration từ nhánh nền. Test YouTube mới: 9/9.
- Native read-only: YouTube search đã render 10 và 12 video renderer trong hai lượt,
  nhưng một lượt khác không có title sau 10 giây; xem YT-NATIVE-001.
  Chưa chạy thao tác mở video có confirmation thật.
- Harness Vision tái dùng `benchmarks.web_observation.runner`. Capture dev:
  `artifacts/benchmarks/web-observation/capture-73805142f5d6/`, PNG 1280×800,
  actions=0. Ảnh đã xem, còn chờ người đánh giá khóa nhãn; chưa gọi model,
  chưa có điểm Vision. Không dùng ảnh dev này làm held-out.

## Trạng thái test case

“Pass fixture/unit” chỉ xác nhận cơ chế. “Blocked” và “not run” không được
tính là pass native hoặc điểm Vision.

| Case | Trạng thái | Bằng chứng / giới hạn |
| --- | --- | --- |
| YT-01 | Pass unit | Query tiếng Việt được mã hóa URL; chưa đo native. |
| YT-02 | Pass native read-only | Trang kết quả English có 10/12 renderer ở hai lượt; không qua confirmation flow. |
| YT-03 | Pass unit | Dấu ngoặc kép và `&` được mã hóa. |
| YT-04 | Pass unit | Tiêu đề trùng, handle và video ID khác nhau. |
| YT-05 | Pass unit | Href ad không phải watch bị loại; chưa kiểm mọi loại promoted thật. |
| YT-06 | Pass unit | Shorts và playlist bị loại. |
| YT-07 | Pass unit | Không có video hợp lệ trả `YT_NO_CLEAR_RESULTS`. |
| YT-08 | Pass unit; blocked native | Danh sách đổi trong lúc đọc bị từ chối; có lượt title không sẵn sàng sau 10 giây. |
| YT-09 | Pass unit | Handle đúng dẫn tới URL video đúng trong fake runtime; chưa mở video thật. |
| YT-10 | Pass unit | Sai video ID trả verified=false. |
| YT-11 | Pass unit nền | Web runtime xử lý decline; chưa đo YouTube native. |
| YT-12 | Pass smoke | Không cấp `web.open` trả failed trước điều hướng. |
| YT-13 | Pass unit | Browser đã đóng làm handle hết hạn trước dispatch. |
| YT-14 | Pass unit nền | Browser adapter uncertain sau lỗi dispatch, không retry; chưa đo YouTube native. |
| YT-15 | Not run | Consent/login/captcha trên YouTube thật chưa gặp và chưa có fixture riêng. |
| YT-V01 | Captured, chưa chấm | Ô tìm kiếm trong ảnh dev; chưa khóa nhãn hoặc gọi model. |
| YT-V02 | Not run | Chưa có scene ngoài viewport. |
| YT-V03 | Not run | Chưa có scene hai tiêu đề gần giống. |
| YT-V04 | Not run | Chưa có scene popup che mục tiêu. |
| YT-V05 | Not run | Chưa có scene mục tiêu vắng mặt. |
| YT-V06 | Pass unit nền | Controller có frame age guard; chưa đo trên YouTube. |
| YT-V07 | Pass unit nền | Controller có revision guard; chưa đo trên YouTube. |
| YT-V08 | Pass unit nền | Controller/contract từ chối box ngoài viewport; chưa đo trên YouTube. |
| YT-V09 | Pass unit nền | Grounder schema guard; chưa đo trên YouTube. |
| YT-V10 | Pass unit nền | Provider timeout path; chưa đo trên YouTube. |

DOM: 2 lượt search read-only có renderer, 1 lượt không ready; mẫu quá nhỏ để
ước lượng tỷ lệ. Vision: 0 proposal, 0 score. Click video: 0; đúng/sai/
uncertain native đều chưa có mẫu. Latency: chưa lưu chuỗi đo đồng nhất nên N/A.
