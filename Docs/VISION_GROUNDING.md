# Vision grounding local cho browser ELVION

## Ranh giới API

`LocalVisionGrounder(OllamaVisionProvider(model="qwen3.5:4b"))` triển khai `VisionGrounder.locate(frame: VisionFrame, *, target: str, role: str) -> GroundingResult` từ `src/elvion/browser/contracts.py`. `role` chỉ nhận `textbox`, `button`, `link`. Đầu vào là PNG viewport nguyên vẹn, mô tả một mục tiêu và role. Đầu ra là `found` với bbox CSS pixel hoặc `not_found`/`ambiguous`/`error` với reason cố định. Grounder không click, gõ, điều hướng, cấp quyền hoặc kiểm tra độ mới của frame. Task A phải kiểm tra `frame_id`, page/revision, tuổi `captured_at` bằng monotonic clock, rồi mới cân nhắc thao tác và verifier.

```python
from elvion.vision import LocalVisionGrounder, OllamaVisionProvider

grounder = LocalVisionGrounder(OllamaVisionProvider(model="qwen3.5:4b"))
result = grounder.locate(frame, target="Search", role="textbox")
```

`VisionFrame` là contract chung frozen của Task A; B không tạo bản sao. B kiểm tra đầy đủ signature/chunk CRC/luồng pixel PNG RGB hoặc RGBA 8-bit, kích thước khớp, tối đa 5 MiB, target tối đa 160 ký tự và role hợp lệ trước khi gọi model. Không crop, resize hoặc sửa timestamp. Proposal v1 chỉ có `version=1`, `status` và `box` nguyên 0–1000 theo toàn ảnh. `[x,y,width,height]` đổi sang CSS pixel bằng width/height của frame; box âm, rỗng hoặc vượt viewport bị từ chối, không clamp. `not_found` và `ambiguous` bắt buộc box null. Schema dư trường, code, URL, chuỗi hành động hoặc output sai kiểu trả lỗi; raw response/exception không đi ra caller.

Provider dùng `/api/show` để yêu cầu metadata local có `capabilities` chứa `vision`, `model_info` không rỗng và không có dấu hiệu remote; sau đó `/api/chat` với PNG base64 trong `images` và JSON schema trong `format`. Chỉ endpoint HTTP numeric `127.0.0.1`, không proxy/redirect, không retry hoặc cloud; request/response và timeout đều hữu hạn. Ảnh và target không ghi vào log hay báo cáo. Không dùng confidence model tự khai làm xác suất đúng.

## Preflight và model

Ngày 30/10/2026, `ollama list` trên host có `qwen3.5:4b`; `ollama show qwen3.5:4b` liệt kê capability `vision`. Sandbox mặc định chặn loopback, nên kiểm tra metadata/model thật cần quyền chạy local tương ứng hoặc Terminal desktop. Không cần tải thêm model để chạy bộ hiện tại. Metadata có vision là prerequisite, không chứng minh grounding chính xác; kết quả benchmark thật ở dưới cần đọc riêng.

Ollama ghi REST API nhận ảnh dạng base64 trong mảng `images` và JSON schema trong trường `format`: [Vision](https://docs.ollama.com/capabilities/vision), [Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs).

## Fixture và chấm điểm

`benchmarks/vision/fixtures/manifest.json` khai báo 24 ca tổng hợp, chia dev/test trước khi chạy model. PNG và HTML cùng ID, viewport 800×600, device scale 1. Fixture gồm textbox/button/link nhiều vị trí, nút gần biên, layout đổi, chữ nhỏ/độ tương phản khác nhau, trùng mục tiêu, vắng mục tiêu, chữ gây nhiễu và canvas. `generate_fixtures.py` dùng Pillow chỉ để tạo lại fixture PNG/HTML; runtime grounder/runner dùng stdlib, không cần Pillow. Chưa dùng browser renderer để chụp HTML; hai bản được tạo từ cùng tọa độ khai báo và validator đối chiếu tọa độ HTML với manifest. Task A có thể dùng HTML/canvas trong browser fixture riêng để kiểm tra đường DOM thiếu locator.

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --check-fixtures
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --list
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --split dev
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --split test
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --case button_center --repetitions 2
```

`--model` bắt buộc cho inference, `--case` chọn ID, `--repetitions` nhận 1–10, `--output-dir` đổi nơi xuất. Chế độ `--check-fixtures` không gọi model. Exit code 0 khi mọi ca đạt; 1 nếu có ca trượt; 2 nếu chọn/tham số/prerequisite hoặc fixture lỗi. Mỗi run xuất JSON và Markdown tên duy nhất, quyền file 0600. Báo cáo ghi `target_hit` khi tâm bbox nằm trong vùng chuẩn, `wrong_target`, `correct_abstain`, `wrong_abstain`, `unexpected_abstain`, `provider_error`, `timeout`; mọi lỗi nằm trong mẫu số. `grounding_ms` gồm metadata + inference local, `inference_ms` đo riêng `/api/chat`; không phải latency browser hoặc thành công tác vụ.

Tests fake provider chỉ kiểm tra guard/schema/chấm điểm. Điểm fake không chứng minh model thật. `test` không dùng để chỉnh prompt theo kết quả dev. Grounder chỉ nhận PNG/target/role; manifest và đáp án không đưa vào prompt. Screenshot desktop thật không được lưu mặc định.

### Kết quả model local trên fixture (30/10/2026)

`qwen3.5:4b` chạy inference thật qua Ollama loopback trên PNG tổng hợp. Một ca smoke `button_center` đã trả `found` nhưng tâm box sai. Chạy toàn split:

| Split | Pass | Target hit | Đúng abstain | Chọn sai | Box/schema/provider lỗi | Timeout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | 3/10 | 1 | 2 | 4 | 3 | 0 |
| test | 2/14 | 1 | 1 | 6 | 6 | 0 |

Chín lỗi trong cột lỗi là `INVALID_BOX`: proposal vượt biên chuẩn hóa và bị từ chối, không được clamp. Các ca trùng mục tiêu `ambiguous_buttons`, `ambiguous_links`, `ambiguous_canvas` đều bị dự đoán `found`, nên chấm sai. `textbox_canvas` (test) là một ca target hit, nhưng đó chỉ là định vị; chưa click hoặc verify. Như vậy model hiện tại chưa đủ tin cậy để Task A cho phép đường vision tự thao tác. Không nới guard để làm điểm đẹp hơn. Kết quả này là 24 ảnh fixture, mỗi ảnh một lượt; chưa có đo lặp hoặc website thật.

## Giới hạn hiện tại

Vision B chỉ đề xuất box. Nó không phải vision end-to-end: chưa có driver click, freshness gate, grant, confirmation hay verifier của Task A trong đường này. Mẫu canvas HTML là fixture tổng hợp, không phải bằng chứng thao tác canvas trên browser thật. Không suy ra chất lượng trên website công khai hoặc desktop cá nhân từ 24 ảnh này.

## Thử nghiệm giao thức v2 — 30/10/2026

Đây là candidate nghiên cứu, chưa chứng minh tăng chất lượng và chưa bật click
trong CLI/voice/GUI. Default `LocalVisionGrounder(provider)` vẫn là `xywh-v1`;
chọn rõ `LocalVisionGrounder(provider, protocol="xyxy-v2")` để thử phương án mới.
Shared `VisionFrame` / `GroundingResult` không đổi.

Giả thuyết: v1 yêu cầu `[x,y,width,height]` trong khi ví dụ grounding của Qwen
sử dụng `[x1,y1,x2,y2]` chuẩn hóa 0–1000. Điều này có thể góp phần gây nhầm tọa độ,
nhưng chưa có raw proposal từ baseline để kết luận 9 INVALID_BOX đều do nguyên
nhân này. Tham khảo mã chính thức:
https://github.com/QwenLM/Qwen-MM-Plugins/blob/main/src/capabilities/api/qwen_mm_plugins_api/vl/grounding.py
và cookbook https://github.com/QwenLM/Qwen3-VL/blob/main/cookbooks/2d_grounding.ipynb .
Không suy ra mọi model Qwen có cùng mức chất lượng từ các ví dụ đó.

Proposal v2 chỉ có `{"version":2,"boxes":[[x1,y1,x2,y2], ...]}`; tối đa 8 box.
Mỗi tọa độ là integer 0–1000; x1<x2, y1<y2. Compiler kiểm tra TẤT CẢ box trước
khi quyết định: 0 box -> not_found; 1 -> bbox CSS pixel; nhiều box -> ambiguous.
Không clamp, không tự đoán định dạng, không lấy box đầu, không sửa v1 thành v2
ngầm. Box sai trong danh sách nhiều mục tiêu vẫn là error. Model còn có thể bỏ
sót mục tiêu trùng và chỉ trả một box; quy tắc đếm không chứng minh uniqueness
trên ảnh. Vì vậy chưa cho phép click thật chỉ dựa trên phương án này.

Không crop/resize/overlay ảnh, không đọc đáp án manifest vào prompt, không đổi
fixture hoặc tiêu chí target_hit. Không thêm dependency runtime. Provider giữ
mặc định 128 token để tương thích; phép so sánh dưới dùng rõ 512 cho CẢ HAI
phương án để danh sách nhiều box không bị thiếu ngân sách. Đây là baseline mới
có cùng ngân sách, không thay thế kết quả lịch sử v1 128 token (5/24).

Chạy từ thư mục repository:

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --split dev --compare-protocols --max-tokens 512
```

10 ảnh dev x 2 phương án = 20 lượt suy luận. Mỗi cặp giữ nguyên ảnh/target/role,
model và token budget, thứ tự phương án luân phiên; không click browser. Có
progress và hai cặp JSON/Markdown tại artifacts/benchmarks/vision. Báo cáo ghi
protocol, max_tokens, paired order, số wrong_target và reason_counts. Mọi error
vẫn nằm trong mẫu số; exit 1 nghĩa có ca không đạt, không phải runner bị hỏng.
Không chọn phương án chỉ theo tổng pass nếu chọn sai mục tiêu còn nhiều.

Sau khi đọc dev, cố định code/config rồi mới đánh giá test:

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --split test --compare-protocols --max-tokens 512
```

Split test này đã có kết quả được xem ở baseline; không coi nó là tập mù mới.
Trước khi mở Vision cho thao tác thật cần thêm tập ảnh độc lập chưa dùng chỉnh
prompt, đo lặp, đánh giá ca trùng/vắng mục tiêu và kiểm chứng driver riêng.

Kiểm tra trong lượt này: fixture 24/24 hợp lệ và unit test backend giả đạt.
Gọi preflight Ollama từ agent trả MODEL_UNAVAILABLE nên chưa có điểm model thật
cho candidate v2. Không gán điểm fake hoặc điểm v1 cũ cho v2.

## Point và OCR candidate — 30/10/2026

Đã thử model thật `point-v3`: yêu cầu các điểm tâm chuẩn hóa, compile thành box
1×1 CSS px với tâm đúng điểm đã yêu cầu. Không clamp điểm biên hoặc tự đoán hệ
tọa độ. 10 ảnh dev, qwen3.5:4b, 512 token, một lượt: **3/10**, gồm 2 target hit,
1 abstain đúng, 7 wrong_target, 0 provider error. Thấp hơn xyxy-v2 5/10; chưa chọn
point-v3 làm phương án cải thiện. Report:
artifacts/benchmarks/vision/point-dev/vision-20261030T003657-e733faa9.json .

Phương án `ocr-candidates-v1` tách tọa độ khỏi model:

1. Helper `src/elvion/vision/recognize.swift` dùng Apple VNRecognizeTextRequest
   accurate, en-US, không language correction, chỉ nhận PNG stdin và trả JSON.
2. Python kiểm tra toàn bộ OCR protocol và bbox nằm trong viewport. Tọa độ Apple
   lower-left được chuyển top-left trong helper. Không crop hoặc sửa frame timestamp.
3. Chỉ khớp nguyên dòng nhãn, NFC + casefold + whitespace; không fuzzy matching,
   không bỏ dấu hoặc cắt lấy từ gần giống. Không có nhãn -> not_found; nhiều nhãn
   giống -> ambiguous, không nhờ model chọn một cái.
4. Với đúng một nhãn, gửi ảnh gốc và candidate OCR (không phải đáp án) cho model
   kiểm tra nhãn có phải role được yêu cầu và tâm nhãn nằm trong control hay không.
   Model chỉ được chọn candidate ID 0 hoặc từ chối; không được thay tọa độ.
5. Kết quả found dùng box CHỮ từ OCR, không phải box đầy đủ control. Đây vẫn là
   click proposal, chưa chứng minh có thể click được trên website thật. Model có
   thể duyệt nhầm text thường hoặc nhầm role; OCR cũng có thể đọc nhầm hoặc bỏ sót.

Helper build theo fingerprint source vào artifacts/native, input không ghi file,
không đọc DOM, manifest, truth box, profile hoặc dữ liệu cá nhân. Không ghi raw
OCR text vào trace/report. Confidence OCR không được xem là xác suất đúng hoặc
sử dụng để tự cấp quyền. Runtime không thêm package Python; cần Swift + Vision
framework trên macOS. Hiện chỉ đo nhãn tiếng Anh, chưa tuyên bố hỗ trợ nhãn tiếng
Việt, biểu tượng hoặc nhiều dòng. Không dùng phương án này làm fallback ngầm khi
OCR/model lỗi.

### Kiểm chứng trạng thái hiện tại

Helper đã compile thành công, nhưng native OCR thật từ agent trả lỗi hệ thống
Foundation._GenericObjCError code 0. Đã thử riêng revision 1/2/3 và CPU-only trong
probe, kết quả vẫn lỗi. Chưa xác định lỗi do môi trường hay framework/runtime;
không tính lỗi OCR là not_found, không gán điểm chất lượng cho phương án OCR.
Code chính dùng device mặc định, không giữ override CPU-only đã thử.

Unit tests dùng backend giả bao phủ nhãn khác không gọi model, nhãn trùng không
chọn một cái, không nhận tọa độ/action do model tự thêm, lỗi OCR là error, bounds
của OCR response, point compiler, và gate dừng trước test khi dev trượt. Đây là
kiểm chứng code/guard, không phải bằng chứng chất lượng OCR thật.

### Một lệnh kiểm tra trên Terminal desktop

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.validate_candidate --model qwen3.5:4b
```

Lệnh build helper khi source đổi, thử OCR thật trước inference, kiểm tra local
model, rồi chạy 10 ảnh dev × 3 lượt. Chỉ khi **30/30** đúng mới chạy 14 ảnh test
cũ × 3 lượt. Gate nghiên cứu đòi **42/42** regression đúng; bất kỳ lỗi, chọn sai,
hoặc abstain sai nào cũng trượt. Thứ tự code/config được cố định trước khi đọc
regression. Split test này đã từng được xem nên không gọi là held-out mù mới.

Output JSON/Markdown ở artifacts/benchmarks/vision/ocr-validation; có config
ngôn ngữ OCR, cách khớp nhãn và nguồn tọa độ. Exit 0: gate fixture đạt; exit 1:
chất lượng còn trượt; exit 2: prerequisite lỗi, chưa đo chất lượng. Ngay cả gate
đạt cũng giữ live_vision_enabled=false; còn cần challenge độc lập, role negatives,
icon-only/multiline, browser screenshots thật, freshness/driver/verifier và kiểm
chứng click riêng trước khi bật trong phiên người dùng.

Chạy riêng candidate khác qua runner:

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --split dev --protocol point-v3 --max-tokens 512
PYTHONPATH=src:. python3 -m benchmarks.vision.runner --model qwen3.5:4b --split dev --protocol ocr-candidates-v1 --max-tokens 512
```

Tham khảo Apple: https://developer.apple.com/documentation/vision/vnrecognizetextrequest
và https://developer.apple.com/documentation/vision/recognizing-text-in-images .

## Dev OCR 27/30 và profile chữ nhỏ — 30/10/2026

Người dùng đã chạy native OCR trên Terminal thành công. Report
artifacts/benchmarks/vision/ocr-validation/vision-20261030T011626-d0c1dfee.json
đạt 27/30 dev, 0 wrong_target, 0 error; chỉ button_center unexpected_abstain cả
3 lượt. Cả ba có inference_ms=null, nên nhánh OCR không tìm thấy nhãn nguyên
dòng khớp Submit; model chưa được gọi. Chưa có raw OCR của ca này để xác định
chính xác OCR đọc sai chữ, gộp dòng hay bỏ sót. Không hardcode Submit hoặc sửa
nhãn sai bằng fuzzy matching. Giá trị minimumTextHeight của request mặc định
đã kiểm tra là 0.0, vì vậy giảm ngưỡng đó không giải quyết được vấn đề.

Đã thêm profile `upscale2x-v2` để thử đọc nhãn nhỏ: phóng toàn ảnh 2× bằng
CoreGraphics interpolation high trước OCR, không crop, đổi màu hoặc vẽ chữ đáp
án. Chỉ phóng ảnh có cả hai chiều <=2048 để giữ ảnh xử lý <=4096 mỗi chiều;
ảnh lớn hơn giữ nguyên. VN box normalized luôn map về kích thước ORIGINAL, do
đó bbox CSS không nhân 2, frame ID/revision/timestamp không đổi. Model vẫn nhận
PNG gốc, không nhận ảnh đã phóng. Profile `native-v1` giữ nguyên mặc định; không
auto retry hoặc đổi profile sau lỗi. Đây là candidate cần đo, chưa chứng minh
khắc phục button_center hoặc tăng tổng điểm. Helper fingerprint đổi nên build
lại tự động. Guard và quality gate không thay đổi.

Một lệnh chạy profile mới đồng thời thu chẩn đoán OCR tổng hợp:

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.validate_candidate --model qwen3.5:4b --ocr-profile upscale2x-v2 --diagnose-ocr
```

Flag `--diagnose-ocr` là opt-in riêng: chạy cả hai OCR profile trên 10 ảnh dev,
lưu text/bbox OCR và SHA256 ảnh vào file 0600 trong output-dir/ocr-diagnostics.
Đây chỉ là nhãn trong fixture tổng hợp đã biết, không ảnh desktop hoặc nội dung
website. Dữ liệu này không đưa vào runtime trace và không cung cấp đáp án cho
model. Nó cho phép đối chiếu chữ OCR thực sự đọc thay vì đoán nguyên nhân.
Sau đó mới chạy gate model với duy nhất profile được chỉ định; không chọn
profile tốt nhất theo từng ảnh. Report config ghi ocr_profile rõ ràng.

Muốn chỉ lấy chẩn đoán, không gọi Ollama:

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision.ocr_diagnose --case button_center
```

Row benchmark mới có decision_stage và số dòng/nhãn khớp, không raw text. Nhờ
đó phân biệt ocr_no_exact_match, ocr_duplicate_matches và model_rejected_candidate.
Lỗi OCR vẫn là error, không được đổi thành not_found. Agent chưa chạy được
native OCR trong tiến trình này; helper build/unit test không thay điểm model thật.

## Baseline OCR đã đạt gate fixture — 30/10/2026

Đã đối chiếu báo cáo desktop thực tế:

| Split | Ảnh | Lượt | Target hit | Abstain đúng | Sai mục tiêu / lỗi | Median grounding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | 10 | 30 | 21 | 9 | 0 / 0 | 581.9 ms |
| regression test | 14 | 42 | 33 | 9 | 0 / 0 | 600.2 ms |

72/72 lượt đúng, trên 24 ảnh riêng biệt, mỗi ảnh lặp 3 lần; không phải 72 ảnh
độc lập. Model qwen3.5:4b, 512 token, ocr-candidates-v1 + upscale2x-v2. Thời gian
là locate (OCR + model nếu cần), không phải browser task latency. Split test cũ
được gọi regression vì đã từng xem ở baseline trước.

Nguồn dev: artifacts/benchmarks/vision/ocr-validation/vision-20261030T012437-0cc7344c.json
Nguồn test: artifacts/benchmarks/vision/ocr-validation/vision-20261030T012437-e33e9b9f.json
Chẩn đoán OCR: artifacts/benchmarks/vision/ocr-validation/ocr-diagnostics/ocr-diagnostic-811086d70694.json

Chẩn đoán đã cho biết nguyên nhân cụ thể ở button_center: native-v1 nhận
`Submit |`, upscale2x-v2 nhận `Submit`. Giữ nguyên so khớp nhãn nguyên dòng,
không bỏ dấu câu hoặc thêm ngoại lệ cho Submit. Các ca mục tiêu vắng/trùng đều
đúng trên bộ hiện có. Không suy ra mọi heading/text thường, role sai, biểu tượng
hoặc nhãn tiếng Việt đã được kiểm chứng từ kết quả này.

Đã lưu configs/vision-research-baseline.json gồm cấu hình, checksum các báo cáo,
source và fixture để theo dõi thay đổi sau mốc này. Đây là snapshot nghiên cứu,
không được runtime dùng để cấp quyền hoặc bật Vision. Input report chưa ghi
full digest model weights, nên không tuyên bố tái lập bit-for-bit chỉ từ file này.

### Tiếp theo: browser fixture vision-only

Đã bổ sung lựa chọn grounder OCR vào script check_browser hiện có:

```sh
./elvion --browser-check --mode vision --vision-model qwen3.5:4b --grounder ocr-candidates-v1
```

Lệnh opt-in mở Chromium riêng với canvas HTML tổng hợp trong bộ nhớ, không
public network hoặc profile cá nhân. Target mới là `Fixture search`. Screenshot
viewport 1280×800 được đưa cho OCR và model; không có DOM locator nút để định vị,
không truyền tọa độ chuẩn vào grounder. BrowserController kiểm tra freshness,
frame ID/page/revision, bbox và authorization trước click. Verifier đọc dataset
body do fixture cập nhật sau khi click trúng. Không dùng assert có thể bị tắt
bằng Python -O cho bước verifier này.

Đây vẫn là test fixture có chủ động click, không bật adapter Vision trong phiên
CLI/voice/GUI. Chưa có kết quả desktop cho smoke test OCR này. Một smoke pass
cũng chưa thay thế challenge độc lập, role negatives và browser layouts khác.
