# Quan sát web thật — Task A

Công cụ `benchmarks.web_observation.runner` tách capture, khóa annotation, rồi
mới chạy model trên PNG đã lưu. Không import controller, không click/gõ/scroll,
không đăng nhập hoặc dùng profile cá nhân. Dữ liệu lưu cục bộ trong artifacts,
không gửi ảnh ra ngoài: model qua Ollama loopback. Việc mở URL vẫn gửi GET tới
website. Không bật live Vision trong CLI/voice/GUI.

## 1. Capture

Khi Task B đã có manifest, dùng ID case từ manifest:

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner capture --manifest-case CASE_ID
```

Hoặc capture thủ công với URL HTTPS, target và role do người chấm chọn:

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner capture --url 'https://docs.python.org/3/' --target 'Tutorial' --role link
```

Đây chỉ là ví dụ yêu cầu, không khẳng định target đang có trong viewport.
Capture được in ra dạng `artifacts/benchmarks/web-observation/capture-...`.
Mở `original.html` của capture bằng trình duyệt để xem ảnh nhúng offline. Kéo
chuột quanh phần tử để hiện `[x,y,width,height]` theo CSS pixels; thao tác này
chỉ đo ảnh trong viewer cục bộ, không tác động website đã capture.

Chromium viewport 1280x800, scale1, chờ 1 giây sau domcontentloaded rồi chụp.
Không xóa banner hoặc sửa DOM. BrowserSession chỉ cho GET/HEAD tới cùng host,
kiểm tra public DNS, block popup/download/serviceworker/websocket theo cơ chế
hiện có. CDN khác host có thể bị chặn, trang có thể thiếu style/font/ảnh.
Đánh dấu unscorable nếu không đủ bằng chứng. Đây không phải capture đầy đủ mọi
website hay sandbox mạng hoàn hảo. Không nhập URL có secrets hoặc trang riêng tư.
Lỗi capture tạo blocked.json với quality_score=null, không được tính là rejection.

## 2. Chấm ảnh gốc, chưa xem proposal

Người chấm xem original.html, chọn đúng expected status và vẽ truth boxes.
Một found cần đúng một vùng; ambiguous cần từ hai vùng trở lên; not_found và
undetermined không có truth box. Dùng undetermined nếu tải thiếu/che khuất
khiến không thể chấm; rationale phải nêu rõ. Không dùng output model để đặt
truth box. Ví dụ bbox dưới đây là placeholder, phải thay bằng số đo thực tế:

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner annotate CAPTURE_DIR --status found --truth '[[100,200,120,30]]' --annotator 'annotator-01' --reviewer 'reviewer-01' --rationale 'Một link đúng nhãn, nhìn thấy đầy đủ'
```

`--distractors '[[...]]'` tùy chọn; expected not_found dùng `--truth '[]'`.
Annotation.lock.json không ghi đè. Không khóa lại sau khi có proposal; nếu
annotation sai, giữ lịch sử và tạo capture mới. Checksum ràng buộc ảnh và
metadata với annotation, phát hiện thay đổi vô ý; không chống người cố tình
sửa mọi checksum/file. Việc người chấm chưa xem model là quy trình con người,
không thể chứng minh chỉ bằng tên file.

## 3. Chạy v4 trên ảnh đã khóa

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner evaluate CAPTURE_DIR --model qwen3.5:4b
```

Cần native OCR và model local đã cài. Grounder chỉ nhận VisionFrame, target,
role; không nhận DOM, annotation, case ID hoặc truth bbox. PNG được kiểm tra
checksum/định dạng. Annotation undetermined không gọi model. Mỗi evaluate tạo
proposal-*.json và HTML mới; không ghi đè. HTML vẽ truth xanh/proposal đỏ.
Original.html không có truth/proposal. Viewer không tải tài nguyên bên ngoài.

Scorer yêu cầu đúng frame, status, bounds và tâm bbox nằm trong truth, không
nằm trong distractor. Error không tính là correct rejection. Report một
observation, không suy ra tỷ lệ từ một ca; chưa có aggregator/p95 hoặc dataset
score trong Task A. Task B cung cấp protocol/manifest; tổng hợp metrics theo
protocol sau khi đủ annotation được review. Lặp cùng ảnh không là scene mới.

Offline inference dùng timestamp mới chỉ để cấu trúc frame; không chứng minh
freshness so với trang đang chạy, không kiểm chứng điều hướng/click. Report
luôn `actions=0`, `freshness_verified=false`. Chế độ này không dùng để thực thi.

## Kiểm chứng hiện tại

7 fake tests kiểm tra khóa annotation, chỉnh ảnh/metadata, output sai, input
oracle không lọt vào grounder, unscorable và blocked capture. Chưa có native
capture/model thật trên public web trong lượt triển khai. Nếu sandbox chặn
Chromium, chạy capture từ Terminal desktop; không nới quyền hoặc giả score.

Toàn suite sau tích hợp Task A: 511 tests đạt; git diff --check đạt.

Task B protocol integration: annotation có reviewer/evidence_source và manifest
checksum trong capture/report. Mã reviewer là người thực sự review; không bịa
review độc lập nếu chỉ có một người chấm. Dùng dom_assisted nếu cần DOM xác
nhận role, và báo riêng khi tổng hợp. Các case manifest vẫn provisional cho tới
khi có ảnh và annotation khóa; công cụ không sửa manifest sau mỗi capture.

## Khi ảnh không đủ phân biệt link và disclosure button

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner review-dom CAPTURE_DIR
```

Chỉ đọc tags/roles và bbox của exact text trong trang mới mở. Evidence chỉ
được xuất nếu PNG và URL khớp capture cũ trước/sau DOM read. Nếu status là
capture_changed/blocked, không dùng để chấm ảnh cũ; giữ undetermined hoặc tạo
capture mới. Nếu image_matched, reviewer vẫn phải đối chiếu vị trí/role,
không tự đổi expected từ manifest. Khóa annotation với evidence-source
`dom_assisted` khi dùng DOM. Không gọi đây là vision-only oracle. Semantic
mapping giới hạn HTML native và explicit role; không là AX tree toàn diện.

## Thu thập tái hiện lỗi trên cùng ảnh

`evaluate CAPTURE_DIR --diagnose-model --repetitions 3` giữ mọi proposal và
raw native OCR/model diagnostics cục bộ, xuất reproduction-*.json liên kết
ba lượt. Không tự chọn lượt thành công; ba lượt cùng PNG vẫn là một scene.
Diagnostics có thể chứa chữ trên trang công khai đã capture; không publish
nguyên file nếu có thông tin không muốn chia sẻ. Không chụp hoặc gửi thêm
ảnh desktop. Inference vẫn local; không click hoặc mở lại trang.

Bản thử nghiệm mới đánh dấu vùng OCR bằng outline trên transcription crop;
semantic/full-image dùng ảnh gốc. Marker lấy OCR, không annotation oracle.
Không lấy điểm snapshot source trước đó làm điểm cho cấu hình marker mới.

## DOM evidence cùng session để tránh mở lại trang

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner capture --manifest-case CASE_ID --record-dom
```

Lưu thêm dom-at-capture.json, chỉ có candidates nếu PNG và final URL giữ nguyên
trước/sau DOM read trong cùng session. Không tự khóa annotation hoặc chạy model.
Nếu cần dùng evidence này, annotation phải dom_assisted. Mismatch vẫn unscorable
cho việc suy role, không tự chụp lặp tới khi được ảnh thuận ý. Captures cũ giữ
nguyên và tính riêng trong ledger; snapshot mới không xóa blocked/unscorable cũ.

## Frozen dev run plan — không cộng điểm các phiên bản khác nhau

`benchmarks.web_observation.plan.make_plan` cố định một capture/annotation cho
mỗi case dev, kèm checksum ảnh/metadata/annotation và sáu file grounder source.
Kế hoạch đầu tiên: artifacts/benchmarks/web-observation/dev-plan-subline-01.json.
12 ca manifest gồm10 scorable (3 found/7 not_found) và2 undetermined. Đây là
pilot đã xem trong phát triển; nhiều annotation do AI self-review, không đủ
để gọi blind generalization hoặc review độc lập bởi hai người.

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner evaluate-plan artifacts/benchmarks/web-observation/dev-plan-subline-01.json
```

Một lượt inference mỗi ca scorable trên cùng source, không gọi model cho hai
undetermined, không retry để chọn success. Validate toàn bộ nguồn/oracle trước
inference và kiểm tra lại giữa các ca. Nếu source thay, dừng; không gộp report
cũ. Mọi proposal lưu riêng. plan-run-*.json giữ tiến độ sau từng observation,
kể cả lỗi/partial run. Nếu prerequisite lỗi, incomplete được ghi rõ; không
tính các ca chưa gọi thành correct rejection. Có thể chạy kế hoạch lần khác,
nhưng phải giữ riêng run, không tự lấy best hoặc latest làm điểm chính thức.

Summary có numerator/denominator, negative/ambiguity riêng, errors, unscorable,
median/p95 nearest-rank toàn locate và kết quả theo image hash. Cùng ảnh với
nhiều target không là nhiều scene; pixel hash khác nhẹ không chứng minh layout
hay domain độc lập. Gate generalization vẫn false: dev đã xem và chưa có
held_out. Các capture cũ/blocked không nằm trong plan vẫn giữ lịch sử, cần
báo riêng khi mô tả toàn bộ quá trình thu thập, không xóa khỏi ledger.

## Nhiều target trên cùng trang, chỉ capture một lần

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner capture --manifest-case CASE_ID --page-cases
```

Chụp một lần, tạo capture dirs cho các goals cùng URL/split trong manifest.
Child giữ image hash/capture time, ghi shared_page_capture_id; target/role và
case ID riêng. Không copy annotation/model output; vẫn chấm từng goal trước
inference. Không dùng cùng --record-dom. Đây là cách giảm navigation và giữ
cùng scene khi so nhiều target, không tăng số unique scenes. Failed capture
không tự retry hoặc sinh case dirs từ ảnh thiếu.

## Lượt held-out đã khóa — 30/10/2026

Plan `artifacts/benchmarks/web-observation/held-out-plan-frozen-01.json` khóa
12 ca trước model, 3 ảnh/3 domain; 4 found,4 not_found,1 ambiguous,3 undetermined.
Tạo qua make_plan(...,split='held_out'); mặc định vẫn dev. Runner kiểm tra
freeze nguồn/model/manifest và bindings trước khi inference. Không sửa code
Vision giữa lượt đo; không lấy lượt tốt nhất. Chạy một lần trong Terminal desktop:

```bash
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.runner evaluate-plan artifacts/benchmarks/web-observation/held-out-plan-frozen-01.json
```

Giữ cả báo cáo lỗi/partial nếu có. Không có click/gõ hay điều hướng trong
inference. Oracle gồm user đo + assistant review và assistant self-review;
Chrome render suy giảm; không chứng minh website đầy đủ. 3/12 unscorable và
1 ambiguity không đạt coverage protocol; không bật live Vision dù điểm cao.
