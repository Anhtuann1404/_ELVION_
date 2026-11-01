# Benchmark độc lập: nhãn Vision có dấu câu và gần giống

## Phạm vi

Bộ này chỉ chấm `grounder.locate(VisionFrame, target=..., role=...) -> GroundingResult`. Nó **không click**, không gõ, không mở website công khai và không kiểm chứng tác dụng sau thao tác. Grounder chỉ nhận screenshot viewport, target và role. ID ca, expected status, HTML, DOM, ground-truth bbox và rationale không được truyền vào grounder. DOM chỉ dùng sau khi dựng trang để lấy vùng chuẩn cho scorer.

`benchmarks/vision_labels/cases.py` là manifest cố định trước inference: 30 cảnh tổng hợp, 15 `dev` và 15 `held_out`, gồm 22 positive, 6 `not_found` và 2 `ambiguous`. Mỗi ca có expected status và giải thích riêng. Nhãn/layout khác regression và challenge hiện có. Dấu câu cuối `. , : ; ! ?`, dấu câu ở giữa, nhiều dấu cuối và tiếng Việt có dấu đều được kiểm tra. Ca negative gồm thiếu dấu câu thật, đổi một chữ, target vắng, heading/prose sai role, textbox bị hỏi như button và disabled. Ca có cả `Publish` lẫn `Publish.` yêu cầu chọn đúng đối tượng, không được nhận nhãn gần giống. Hai nhãn hệt nhau cùng role phải `ambiguous`.

Fixture được render bằng Chromium riêng qua `set_content`, không tải tài nguyên ngoài. Viewport 1280×800, device scale factor 1, screenshot viewport. Mỗi observation có `frame_id`, `page_id` và revision mới. `--check-cases` dựng đủ 30 trang, đối chiếu geometry DOM với thông số fixture và chụp PNG nhưng không gọi model/OCR hay click. Renderer dùng `BrowserSession` của sản phẩm; vì vậy benchmark chia sẻ giới hạn font/Chromium của renderer đó. Đây là trang tổng hợp, không phải website thật.

## Chạy

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner --check-cases
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_vision_labels_benchmark.py'
```

Sau khi nhánh chính xác nhận không chạy inference Ollama đồng thời:

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner \
  --model qwen3.5:4b --grounder ocr-verified-v3 --split dev --headless --repetitions 3

PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner \
  --model qwen3.5:4b --grounder ocr-verified-v3 --split held_out --headless --repetitions 3
```

`--grounder` nhận `ocr-verified-v2` hoặc `ocr-verified-v3`; `--case` chọn ID, `--split` nhận `dev`, `held_out`, `all`; số lần lặp 1–5. `--list` liệt kê ca. CLI dùng public interface hiện có của `OllamaVisionProvider`, `AppleVisionOCR` và grounder, không sửa nội bộ. OCR profile cố định `upscale2x-v2`, token budget 512. Cần `.venv-browser` có Playwright/Chromium, Apple Vision OCR và Ollama local; không thêm dependency runtime. Nếu prerequisite lỗi, runner trả exit code 2 và không tạo điểm chất lượng. Ca chấm trượt trả exit code 1; tất cả đạt trả 0.

## Oracle và báo cáo

Positive chỉ đạt khi status `found`, bbox hữu hạn/dương/trong viewport và tâm bbox nằm trong đúng vùng chuẩn, không nằm trong vùng gây nhiễu. `not_found` hoặc `ambiguous` trên positive là false abstention. Negative `not_found` chỉ đạt nếu expected đúng là `not_found`; trùng nhãn thật phải `ambiguous`. `found` trên negative là false acceptance. `error` và sai frame là lỗi, không được coi là từ chối đúng.

JSON/Markdown xuất dưới `artifacts/benchmarks/vision-labels/` với tên duy nhất và quyền 0600. Báo cáo giữ mọi observation trong mẫu số, gồm tỷ lệ positive hit và false abstention với numerator/denominator, wrong target, false acceptance, correct ambiguity, provider/grounder error và median `locate_ms` đo **toàn lời gọi** `locate`, không phải inference riêng. Báo cáo ghi model, grounder version, OCR profile, token budget, viewport, split, repetitions, `synthetic_only=true`, SHA256 manifest và SHA256 HTML từng ca. Không lưu raw screenshot, DOM, label OCR, model response hoặc exception.

SHA256 manifest lúc dựng bộ: `f27056317dd1e2c87aeb0468d1ccbbdfb2dc345729f2f8963673cf0f72bb3ff5`. `held_out` không được đổi sau khi xem kết quả; mọi lần chạy lại sau lần xem đầu phải gọi là **regression**. Trường `held_out_use` trong báo cáo nhắc rõ quy tắc này.

## Bằng chứng hiện tại và giới hạn

Ngày 30/10/2026, 7 fake-grounder tests đạt. Chúng chứng minh oracle phát hiện chọn nhầm, từ chối hết, luôn `found`, lỗi provider và `ambiguous` sai chỗ; **không** chứng minh model v3 có chất lượng tốt. Chromium headless đã render đủ 30 fixture và đối chiếu DOM geometry thành công khi chạy ngoài giới hạn sandbox. Sandbox mặc định chặn Chromium Mach port, nên lệnh này cần Terminal desktop hoặc quyền chạy tương đương. Chưa chạy inference thật vì Ollama đang dùng chung với nhánh chính; không có điểm model v2/v3 cho bộ mới ở lượt bàn giao này.

## Thử nghiệm v4 sau khi đã xem held_out

Runner nhận thêm `--grounder ocr-verified-v4`. V4 dùng OCR primary upscale và
secondary native, merge cùng vùng bằng IoU, đọc label từ crop không cung cấp
expected label cho bước đọc. Khác dấu chỉ sinh hypotheses; acceptance vẫn
cần nhãn đọc từ ảnh khớp exact và semantic guards. Unknown không được bỏ qua
để chọn vùng còn lại. Tối đa bốn hypotheses; các ngưỡng này chưa được hiệu
chuẩn trên website thật. Hai lần OCR và nhiều model calls làm tăng latency.
Dev/held_out cũ đã xem nên đánh giá sau sửa là regression. Chưa có điểm thật
v4 tại lúc thêm option; không click và không bật live Vision.
