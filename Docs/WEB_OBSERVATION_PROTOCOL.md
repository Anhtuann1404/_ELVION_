# ELVION: giao thức đánh giá Vision trên website công khai

Ngày lập: 30/10/2026. Đây là **manifest ứng viên và quy trình chấm**, chưa phải
dataset có ground truth. `benchmarks/web_observation_cases/cases.py` có 24 ca:
12 `dev`, 12 `held_out`, trên sáu trang/sáu domain. **Confirmed: 0;
provisional: 24.** Chưa có screenshot viewport được capture và chú giải độc lập.
Nguồn web xác nhận URL và một số chữ/điều hướng của trang, không xác nhận vị trí,
role, trạng thái hay khả năng nhìn thấy trong ảnh. `expected_status` của mọi ca
hiện là `undetermined`; không có truth box giả.

## Phạm vi

Chỉ mở trang công khai trong Chromium riêng và quan sát viewport. Không click,
gõ, submit, đăng nhập, tải file, cấp quyền, vượt CAPTCHA/paywall, dùng browser
profile cá nhân, chụp desktop người dùng hoặc gọi model trong Task B. Nếu
control cần tương tác để lộ ra, đánh dấu blocked/excluded có lý do. Kết quả
`grounder.locate(frame, target, role)` chỉ đo proposal trên ảnh; không chứng
minh click, điều hướng, verifier hoặc freshness trên public web. Regression
synthetic v4 trước đó không phải điểm generalization; không dùng nó làm oracle.

## Trang và phân tách

| Split | Domain | URL capture | Lý do chọn / nguồn đã kiểm tra |
|---|---|---|---|
| dev | python.org | [Python Tutorial](https://docs.python.org/3/tutorial/index.html) | Tài liệu chính thức, mục lục dài và vùng tìm kiếm. |
| dev | mozilla.org | [MDN HTML](https://developer.mozilla.org/en-US/docs/Web/HTML) | Nhiều liên kết điều hướng, nhãn ngắn/dài, dễ kiểm tra role sai. |
| dev | wikipedia.org | [Wikipedia tiếng Việt](https://vi.wikipedia.org/wiki/Trang_Ch%C3%ADnh) | Tiếng Việt có dấu, search field/button và nhãn lặp trong nguồn trang. |
| held_out | github.com | [GitHub Docs](https://docs.github.com/en) | Bố cục docs khác, nhiều danh mục và UI tìm kiếm. |
| held_out | w3.org | [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Trang tiêu chuẩn dài, nhiều metadata links và văn bản gần link. |
| held_out | chrome.com | [Chrome DevTools](https://developer.chrome.com/docs/devtools/) | Điều hướng tài liệu, filter field, một số button không có nhãn trong nguồn text. |

Đã mở sáu URL qua tra cứu web ngày 30/10/2026. Link ở bảng là nguồn sơ cấp
được kiểm tra. Trang thật có thể đổi, redirect hoặc bản dịch khác lúc Task A
capture. Các nhóm `off_viewport`, `duplicate_candidate`, `wrong_role`,
`near_punctuation`, `unlabeled_icon`, `absent_candidate` là **giả thuyết cần
kiểm tra ảnh**, không phải nhãn kết quả. Không bổ sung trang để thay riêng ca
model đoán sai. `check_cases` chỉ kiểm tra URL dạng HTTPS và tách domain theo
đuôi hai nhãn của sáu domain này; nó không phải bộ lọc SSRF runtime.

## Capture và annotation

Baseline: viewport **1280×800 CSS pixels**, device scale factor **1**, zoom
mặc định, screenshot **viewport** (không full page), không scroll. Cùng một ảnh
có thể dùng cho nhiều target/role; `capture_id` và `image_sha256` xác định scene
duy nhất. Mỗi capture cần lưu ít nhất `capture_id`, `image_sha256`, viewport,
device scale factor, zoom, requested URL, `final_url`, `captured_at` có timezone,
trạng thái tải/redirect/ngôn ngữ/banner, version browser, và trạng thái
`captured | blocked | excluded` kèm lý do. Không lưu cookies/profile cá nhân.

Mỗi annotation là record riêng gắn `case_id` + `capture_id` + `image_sha256`:

- `expected_status`: `found | not_found | ambiguous | undetermined`.
- `truth_boxes`: một hoặc nhiều `[x,y,width,height]` CSS pixel nếu có bằng
  chứng thị giác; `distractor_boxes` khi có đối tượng dễ nhầm. Bbox hữu hạn,
  kích thước dương và trong viewport. `found` cần đúng **một** vùng target
  phù hợp role; `ambiguous` cần từ hai vùng cùng role/nhãn không thể phân biệt.
- `annotator`, thời gian, `reviewer`, `review_status` (`draft | reviewed |
  locked`), checksum của annotation khóa và nguồn bằng chứng role
  (`vision_only | dom_assisted`). Không ghi tên người dùng/cá nhân vào báo cáo
  công khai; dùng mã annotator nội bộ.
- `uncertain_reason` hoặc `blocked_reason` khi ảnh không đủ bằng chứng, overlay
  che, CAPTCHA, lỗi mạng, trang đòi tương tác, icon không nhãn hoặc role không
  phân biệt được. `undetermined`/blocked không được biến thành `not_found`.

Một target chỉ nằm ngoài viewport được chấm theo **ảnh viewport**, tức có thể
`not_found` nếu ảnh chứng minh sự vắng mặt; sự tồn tại ở DOM/full page không
đủ. Overlay tự nhiên có thể làm mục tiêu không quan sát được: ghi
`undetermined` hoặc blocked theo mức che, không xóa banner. Icon không nhãn
không được suy ra ý nghĩa từ class/DOM. Nếu một trang đổi, capture lại và tạo
version mới, giữ ảnh/annotation cũ cùng checksum; không sửa oracle cũ theo
proposal. Có thể dùng DOM sau annotation đầu để review role, nhưng ghi
`dom_assisted` và báo riêng, không gọi đó là chấm vision-only.

## Khóa oracle trước inference

1. Task A capture ảnh và metadata, chưa mở proposal model cho annotator.
2. Annotator xem **ảnh gốc** rồi ghi status, truth/distractor boxes và lý do.
3. Reviewer đối chiếu ảnh, khóa annotation và checksum. Ca bất đồng còn
   `undetermined` cho đến khi thống nhất; không dùng bbox model để vẽ truth.
4. Sau khi manifest/capture/annotation đã đóng băng, mới chạy grounder và chấm.

Payload grounder chỉ chứa screenshot `VisionFrame`, target và role. Không đưa
case ID, group, rationale, expected, truth box, DOM, accessibility tree hoặc
annotation. Đối với `held_out`, domain tách khỏi `dev`; không sửa manifest
held_out sau khi xem kết quả. Lần đo sau khi đã xem/sửa theo held_out phải ghi
**regression**, không tiếp tục gọi blind. Lưu SHA256 manifest, annotation và
ảnh trong báo cáo, cùng grounder/model/OCR version, viewport và thời gian.

## Scoring và mẫu số

Một **observation** là một lần `locate` của một `case_id` trên một `capture_id`.
Một **unique scene** là một `image_sha256`; bốn target trên cùng ảnh vẫn là
đánh giá khác nhau nhưng cùng scene. Báo cả tỷ lệ observation và kết quả
gom theo unique scene/case; ba lần lặp không phải ba scene độc lập. Giữ mọi
observation đã chạy trong sổ; setup blocked/unscorable có sổ và lý do riêng,
không đưa vào mẫu số chất lượng hay coi là từ chối đúng. Báo `N/A` khi mẫu số 0.

| Chỉ số | Tử số / mẫu số |
|---|---|
| Positive target hit | `found` với bbox hữu hạn, trong viewport, tâm trong đúng truth region và ngoài mọi distractor / mọi observation scorable có expected=`found`. |
| False abstention | `not_found` hoặc `ambiguous` / mọi observation scorable có expected=`found`. |
| Wrong target | `found` nhưng tâm không ở truth hoặc ở distractor / mọi observation scorable có expected=`found`. |
| Negative false acceptance | `found` / mọi observation scorable có expected=`not_found`. |
| Correct ambiguity | `ambiguous` / mọi observation scorable có expected=`ambiguous`. |
| Provider/grounder error | `error`, exception, sai frame hoặc bbox không hợp lệ / mọi observation scorable đã chạy, mọi expected đã xác định. |
| Blocked/unscorable | Số ca/capture không chấm được theo lý do / toàn bộ ca/capture dự định; công bố riêng, không trộn với quality rate. |
| Full locate time | Median và p95 milliseconds của toàn lời gọi `locate` trên mọi observation đã gọi (kể cả lỗi), cùng số mẫu; không chỉ inference. |

`found` trên `ambiguous` cũng là false acceptance riêng; `not_found` trên
negative là correct rejection. Các loại lỗi và tỷ lệ không nhất thiết cộng
thành 100% giữa các nhóm expected khác nhau. Mọi phép chia phải xuất cả tử
số/mẫu số. Nếu provider không được gọi vì capture blocked, không gán `error`.

Ngưỡng nghiên cứu **đề xuất trước inference**: chỉ xem xét mở rộng thử nghiệm
khi có ít nhất 6 unique scenes chấm được trên ít nhất 4 domain, ít nhất 3
negative và 2 ambiguity đã xác minh bằng ảnh; held_out positive hit ≥90%,
wrong target =0, negative false acceptance =0, correct ambiguity ≥80%,
provider/grounder error ≤5%, blocked/unscorable ≤20% tổng dự định. Báo median
và p95, so với TTL hiện hành nhưng không sửa TTL hay tự suy ra đủ freshness.
Nếu thiếu mẫu hoặc không đạt một ngưỡng, **no-go cho việc kết luận**; ngưỡng
này không đảm bảo an toàn trên mọi website và không bật live Vision.

## Bàn giao cho Task A

Task A cần đọc `CASES`, gọi `check_cases`, ghi `manifest_sha256`, capture read-only
với browser profile tách biệt; kiểm tra DNS/IP sau resolve và mọi redirect theo
policy của sản phẩm (kiểm tra cấu trúc URL trong manifest không đủ chống SSRF).
Runner phải phân biệt network/CAPTCHA/consent blocker với grounder error;
không click/gõ/scroll để tạo bằng chứng. Xuất ảnh/metadata và giao diện duyệt
ảnh gốc trước proposal; khóa annotation rồi mới mở/chấm proposal. Không để
grounder thấy oracle. Báo cả các ca blocked, số confirmed/provisional và
checksum. Nếu muốn thay manifest contract, đề xuất nhánh chính thay vì Task B
tự sửa runner hoặc sản phẩm.

### Nội dung đề xuất ghi `Docs/BUG_LOG.md` ở nhánh chính

`LIMIT — Public-web Vision observation chưa có oracle ảnh: 24/24 ca Task B là
provisional trên sáu URL đã tra cứu; chưa có viewport capture hay annotation
độc lập, nên chưa thể báo điểm generalization. Task A cần capture/khóa oracle,
ghi blocked/redirect/banner và báo theo observation + unique scene. Đây là
giới hạn đánh giá, không phải lỗi grounder đã xác minh.`
