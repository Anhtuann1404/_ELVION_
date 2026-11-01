# Đối chiếu box Vision dev — 30/10/2026

Đọc hai báo cáo đã lưu, không chạy model, không click, không chỉnh prompt hoặc
ngưỡng chấm. Không phân tích ảnh split test trong lượt này.

Nguồn:
- artifacts/benchmarks/vision/vision-20261030T002706-d831fcc6.json — xywh-v1
- artifacts/benchmarks/vision/vision-20261030T002706-a73a99f6.json — xyxy-v2

Cả hai dùng qwen3.5:4b, 10 ảnh dev, một lượt, ngân sách 512 token. V1 đạt 3/10
(1 target hit, 2 abstain đúng), V2 đạt 5/10 (3 hit, 2 abstain đúng). Ba INVALID_BOX
v1 không còn ở v2, nhưng số wrong_target từ 4 lên 5; giảm lỗi schema không đồng
nghĩa mọi đề xuất trở nên đúng.

## Bốn ca found có mục tiêu nhưng tâm dự đoán sai

Mọi ca dưới đây có tâm dự đoán nằm trong khoảng ngang của vùng chuẩn, nhưng nằm
ngoài khoảng dọc. dy là chênh lệch với TÂM vùng chuẩn, không phải khoảng cách tới
mép control. Các số là CSS pixel trên ảnh 800×600.

| Ca v2 | Tâm dự đoán (x,y) | dy | IoU | Quan sát |
| --- | --- | ---: | ---: | --- |
| textbox_top | 173.6, 104.7 | +27.2 | 0.2086 | Tâm nằm thấp hơn đáy control 4.7 px |
| textbox_bottom | 180.8, 441.9 | -52.1 | 0 | Box ở phía trên ô Email |
| button_low_contrast | 308.8, 133.8 | -29.2 | 0.0859 | Tâm phía trên nút Apply |
| link_first | 98.0, 111.9 | -44.6 | 0 | Box phía trên link Read guide |

Sai lệch không có cùng dấu hoặc cùng độ lớn. Chưa có bằng chứng cho một phép
cộng offset hoặc một phép nhân scale cố định sửa được các ca này. Việc x nằm
trong khoảng đúng không chứng minh model đã đọc đúng nhãn hoặc hiểu đúng target.
Không di chuyển tâm theo đáp án để làm tăng điểm.

## Ca mục tiêu vắng mặt

absent_textbox yêu cầu textbox Search nhưng ảnh chỉ có ô Username. V2 trả found
với box (280, 280.8, 53.6, 24.6), tâm (306.8, 293.1), ở sát mép trái ô Username.
Đây là false acceptance khi mục tiêu không có, không thể giải quyết chỉ bằng
đổi định dạng tọa độ. Cần đo riêng khả năng đọc và kiểm tra nhãn mục tiêu.

ambiguous_buttons hiện v2 abstain đúng. Đây mới là một ảnh dev, chưa chứng minh
khả năng xử lý mọi bố cục trùng. Model vẫn có thể chỉ trả một trong nhiều mục tiêu.

## Kết luận kỹ thuật

Giữ v2 là candidate nghiên cứu; adapter Vision vẫn tắt trong phiên người dùng.
Chưa có lý do để nới biên hoặc tăng độ dung sai của phép chấm. Sau này cần kiểm
tra riêng nhận diện nhãn bằng bằng chứng độc lập và độ chính xác điểm click;
không dùng riêng tổng pass hoặc confidence model tự khai để bật thao tác.

Hướng thử tiếp theo có thể tách thành hai thí nghiệm trên dev: đề xuất trực tiếp
điểm ở tâm control để kiểm tra lỗi hình học; kiểm tra nhãn bằng OCR local để đo
false acceptance. Cả hai cần đối chứng riêng trước khi chọn, không mặc định là
đã cải thiện. Sau khi cố định phương án, cần bộ ảnh độc lập mới để đánh giá.

## Công cụ và kết quả trực quan

Chạy lại phân tích từ report đã lưu (stdlib, không cần Pillow/matplotlib):

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.diagnose artifacts/benchmarks/vision/vision-20261030T002706-d831fcc6.json artifacts/benchmarks/vision/vision-20261030T002706-a73a99f6.json
```

Công cụ kiểm tra lại outcome bằng scorer cũ, chỉ nhận split dev tổng hợp, không
import provider hoặc gửi ground truth cho model. IoU và delta thêm để chẩn đoán,
không thay đổi outcome đã chấm.

Mở artifacts/benchmarks/vision/dev-diagnostics/comparison.html để xem 20 kết quả
v1/v2 cạnh nhau, ảnh tự chứa, không JavaScript hoặc tài nguyên mạng. Xanh liền là
vùng chuẩn; đỏ đứt là dự đoán; chấm đỏ là tâm dự kiến click.

Đã tạo thêm v2-misses.png bằng matplotlib để xem nhanh năm ca v2 sai. Đã mở và
kiểm tra ảnh tổng hợp bằng mắt. Bảng số đo ở comparison.json và comparison.md.
HTML/JSON/Markdown có thể tái tạo bằng công cụ trên; PNG tổng hợp không là input
benchmark hoặc runtime.
