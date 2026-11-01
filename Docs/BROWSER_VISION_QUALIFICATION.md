# Web + Vision và AIMS — kế hoạch 30/10/2026

Mốc hiện tại: 72/72 lượt grounding trên 24 ảnh x3, và desktop đã xác nhận
canvas Chromium vision-only click + independent state read PASS 1280×800.
Vision trong phiên người dùng vẫn tắt.

| Task | Sở hữu | Phạm vi | Đầu ra |
| --- | --- | --- | --- |
| A | Nhánh chính | browser controller/session, benchmarks/browser_vision, test tương ứng | Fixture browser mới, sai role/disabled, ảnh thay đổi/quyền bị thu hồi, verifier thật |
| B | AI phụ | benchmarks/aims, tests/test_aims_benchmark.py, Docs/AIMS_BENCHMARKS.md | Benchmark chọn phương thức offline, oracle độc lập và fault injection |

Task B chỉ đọc Method/ProbeResult/select; không sửa selector hoặc file A. Task A
không sửa file B. Không commit/push/reset workspace hoặc nới cách chấm cho đạt.

Task A sẽ tạo layout/nhãn mới trước inference, gồm button/input/link/canvas,
chữ nhỏ, nhãn vắng/trùng, heading/input sai role, nút disabled, page injection.
Ảnh đổi vị trí trong lúc grounding phải bị chặn; kiểm tra thêm quyền thu hồi
và tuổi ảnh qua clock fault injection. Các ca guard phải có proposal found hợp
lệ trước khi chặn, không tính model lỗi là guard đạt.

Đếm Mouse.click dispatch và DOM counters độc lập. Positive phải có đúng một
click trúng; negative phải có zero mouse attempts và zero page click events.
Model/driver error luôn trượt. Gate đòi mọi ca đạt; không tự bật Vision dù pass.
Chỉ fixture nội bộ, network chặn, context riêng, không profile/tài khoản cá nhân.

Visual recheck dùng PNG mới ngay trước click, giữ nguyên timestamp/ID cũ. So byte
bảo thủ nên thay đổi vô hại cũng có thể bị chặn. Không nguyên tử: vẫn có khoảng
thời gian giữa screenshot và click, chưa đủ chứng minh mọi web động an toàn.

## Prompt Task B

Làm benchmark offline cho elvion.aims.selector.select(probes, policy_allowed).
Chỉ sửa benchmarks/aims/**, tests/test_aims_benchmark.py, Docs/AIMS_BENCHMARKS.md.
Ít nhất 40 ca, expected winner/reasons khai báo độc lập, không lấy oracle từ
select hoặc PRIORITY đang kiểm tra. Bao phủ policy deny, unsupported, thiếu
prerequisite, thứ tự native/accessibility/DOM/vision, không eligible, hoán vị
input và tie theo thứ tự input hiện có. Không gọi baseline priority là thuật
toán tối ưu reliability/latency.

Runner: PYTHONPATH=src:. python3 -m benchmarks.aims.runner. Xuất JSON/Markdown
tên duy nhất trong artifacts/benchmarks/aims: accuracy, policy violations,
per-category, no-eligible, method usage, timing chỉ cho selector. Fault injection
phải bắt winner sai/vi phạm policy. Không browser/Ollama/native action, không sửa
runtime, không gọi selection pass là task success. Chạy unittest và diff --check,
báo file/số ca/giới hạn chính xác.

## Triển khai trong lượt này

Task B hoàn tất: 48 ca/7 nhóm offline, 48/48 đúng winner/diagnostics, 0 policy
violation, 14/14 no-eligible đúng. Có 7 test, bao gồm tiêm lỗi chọn sai, bỏ policy,
sai diagnostics và output malformed. Nhánh chính đã đọc code và chạy runner lại
để đối chiếu. Kết quả không chứng minh adapter thật tối ưu hay tác vụ thành công.
Xem AIMS_BENCHMARKS.md.

Task A đã tạo 15 scene mới trong benchmarks/browser_vision/cases.py và runner
thực thi Chromium. Thêm BrowserSession.frame_is_current so PNG mới với ảnh gốc,
kiểm tra identity/revision trước và sau capture, giữ nguyên tuổi frame. Chụp ảnh
hide caret ở cả hai lần để bớt false stale do con trỏ văn bản. Kiểm tra lại age
và authority sau final screenshot. Không dùng DOM locator để định vị Vision.

Negative sai role/disabled chỉ được tính đạt nếu OCR đã có candidate và model
thực sự từ chối; OCR bỏ sót không được tính là semantic guard đạt. Duplicate
phải trả ambiguous. Stale/revoked/expired phải có proposal found trước khi
controller chặn, zero mouse attempt và zero DOM event. Expiry là fault injection
clock, không phải cố ý ngủ 11 giây. Positive cần một dispatch và một target click.
Các Mouse.call được instrument nhưng vẫn chuyển tiếp sang Playwright thật.
DOM chỉ dựng fixture/mutate trong fault case và đọc postcondition, không cung
cấp định vị hay truth cho grounder. Các tọa độ trong renderer chỉ là oracle của
fixture. Không tải resource mạng; mỗi case context/browser riêng.

Kiểm tra spec mà không mở browser/model:

```sh
PYTHONPATH=src:. python3 -m benchmarks.browser_vision.runner --check-cases
```

Chạy thật trong Terminal desktop, tại thư mục ELVION:

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.browser_vision.runner --model qwen3.5:4b --headless
```

Bỏ --headless nếu muốn quan sát các cửa sổ thử nghiệm. Một lượt 15 scene; thêm
--repetitions 3 để lặp sau khi smoke đạt. Đây là chủ động click trên fixture,
không cần grants CLI vì không chạy tác vụ người dùng hoặc public website.
Model/OCR lỗi, abstain sai, click sai hoặc click khi phải chặn đều làm gate trượt.
Không retry scene lỗi và không đổi phương thức sau uncertain. File JSON/Markdown
và PNG synthetic frame của ca trượt lưu trong artifacts/benchmarks/browser-vision.
Không raw model response hay ảnh desktop cá nhân. Exit 2 là prerequisite chưa
đạt và chưa đo quality; exit 1 là gate có ca trượt; exit 0 chỉ chốt bộ fixture này.

Agent đã kiểm tra 15 spec và unit guard/oracle. Lần preflight browser thật trong
agent trả prerequisite failure, không có kết quả mới cho 15 scene. Cần desktop
chạy lệnh trên; không gán điểm 72/72 cũ hoặc smoke canvas trước cho bộ mới.

Kiểm tra tích hợp: toàn suite 453/453 đạt. Sau rà soát cuối, 30 test liên quan
qualification/browser/AIMS đạt; 16 script block trong 15 HTML fixture đều parse
được bằng JavaScript engine. Đây chỉ là kiểm tra code/spec, không phải 15 scene
đã chạy browser thật. git diff --check sạch.

## V1 thất bại và candidate semantic v2

Desktop v1: 32/45, 13 unexpected mouse attempts. OCR bỏ sót một nhãn trùng;
model xác nhận sai role/input/prose/disabled. Freshness/revoke/expiry đạt 9/9.
Không bật Vision web thật.

Thêm OCRVerifiedGrounder (ocr-verified-v2): full image kiểm tra số nhãn, rồi
một crop ngữ cảnh riêng để phân loại observed_role và availability. Không đưa
role người dùng yêu cầu vào hai lời gọi phân loại; so sánh ở Python sau đó.
Unknown/mismatch/disabled bị từ chối; multiple trả ambiguous ngay cả khi OCR
chỉ tìm một nhãn. Crop native không thêm dependency, không đổi box click hoặc
tuổi ảnh; crop-only đã kiểm tra pixel khớp Pillow (QA, không runtime).

Diagnostic replay thực tế:
artifacts/benchmarks/browser-vision/semantic-v2-replay-e94f6d59.json .
13/13 ảnh từng sai được từ chối đúng. Tuy nhiên 8/18 ca dương fixture cũ bị từ
chối (link/narrow textbox/low contrast). Tổng replay 23/31, không phải quality
gate pass. Candidate OCR được tái dựng từ bbox exact-match đã ghi, không chạy
OCR native mới hoặc browser click. Không dùng replay để tuyên bố end-to-end.
Giữ nguyên scorer và dữ liệu cũ. Các scene browser mới nay là regression sau
khi đã xem kết quả; cần challenge độc lập tiếp theo trước production.

Chạy candidate mới (v1 vẫn là default để tái lập baseline):

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.browser_vision.runner --model qwen3.5:4b --headless --repetitions 3 --grounder ocr-verified-v2
```

Không chạy lại v1 nếu đang muốn đo bản sửa. 463/463 unit tests đạt, gồm semantic
schema, role withholding, duplicates, disabled/unknown, crop errors, và native
crop QA. Chưa có browser end-to-end score cho v2. Vision phiên người dùng tắt.

## V2 browser desktop đạt 45/45 — 30/10/2026

Đã đọc và đối chiếu artifacts/benchmarks/browser-vision/browser-vision-20261030T021626-03235b4c.json:
ocr-verified-v2 + upscale2x-v2, 15 scene x3, 45/45 đạt. Verified target clicks 18,
guard passes 9, unexpected mouse attempts 0, wrong click observations 0.
Đây là Chromium thật trên fixture nội bộ, không phải website công khai. V1 trước
đó 32/45 với 13 unexpected attempts. Không thay scorer hoặc kỳ vọng scene.

Chốt mốc qualification cho bộ scene hiện tại. Giữ nguyên hạn chế: replay các
ảnh fixture cũ có 8/18 ca dương bị v2 từ chối; kết quả mới không xóa hồi quy đó.
Các scene hiện tại đã được xem khi sửa nên là regression, chưa phải đánh giá
mù độc lập. Vision trong CLI/voice/GUI và public web vẫn tắt. Tiếp theo cần bộ
challenge độc lập và đo coverage/false abstention trên trang thật trước khi mở.

## Challenge tiếp theo — 18 scene chưa chạy inference

Thêm --suite challenge (18 scene: 9 positive, 6 negative, 3 guard) riêng khỏi
--suite regression (15 scene cũ). Nhãn và ID không trùng nhau. Dùng cùng renderer,
viewport và tiếng Anh nên đây chỉ là kiểm tra nhãn/layout mới trong cùng họ
fixture; không phải benchmark độc lập do bên ngoài thiết kế hoặc web thật.
Không chỉnh grounder/prompt/model theo bộ mới. Snapshot source và cấu hình trước
inference lưu configs/vision-challenge-snapshot.json; không phải runtime setting.

Thêm positive_success_rate và false_abstention_rate, với mẫu số là các ca cần
click. Model error không tính thành abstention hoặc success; vẫn nằm trong tổng
failed. Tất cả positive bị từ chối cho coverage 0, không được tính là an toàn và
hoàn thành. Giữ nguyên rule negative sai role cần model rejection, kể cả ID mới.

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.browser_vision.runner --model qwen3.5:4b --suite challenge --grounder ocr-verified-v2 --headless --repetitions 3
```

54 quan sát, mỗi scene 3 lần. Model/OCR/driver error và false abstention vẫn làm
gate trượt. 18 spec và tests code đạt; preflight agent chưa khởi chạy được browser,
chưa có điểm model/browser cho challenge. Không gán 45/45 regression cho bộ mới.
Bộ cũ 8/18 false refusals trong replay vẫn chưa giải quyết, không xóa bằng thêm
bộ mới. Public web và Vision trong phiên người dùng vẫn tắt. Sau qualification,
việc thử trang thật cần giai đoạn chỉ quan sát/proposal trước khi cho phép click.


## V3 desktop challenge đạt 54/54 — 30/10/2026

Đã đối chiếu browser-vision-20261030T094506-4afd6a9c.json: grounder
ocr-verified-v3, upscale2x-v2, 512 tokens, 18 scene x3, Chromium headless.
54/54 đạt, 27/27 positive verified, false abstentions 0, wrong clicks 0,
unexpected mouse attempts 0, guard passes 9. Read policy cả ba lượt có
exact_match_count=0 và label_verification=independent_image_read; bước đọc
ảnh đã phục hồi nhãn trước khi qua semantic guards và controller/verifier.
So với v2 51/54, ba false abstentions được khắc phục trên cùng scene đã xem.
Đây là regression sau sửa, không phải đánh giá mù hoặc website công khai.
Chưa có kết quả v3 trên suite regression 15 scene; Task B đánh giá nhãn/dấu
câu độc lập đang chờ. Hồi quy false refusals trên fixture ảnh cũ vẫn chưa
được giải quyết. Giữ live Vision tắt.


## V3 desktop regression đạt 45/45 — 30/10/2026

Đã đối chiếu browser-vision-20261030T095129-d86136af.json: ocr-verified-v3,
upscale2x-v2, 15 scene x3. 45/45 đạt, 18/18 positive verified, 0 false
abstentions, 0 unexpected mouse attempts, 0 wrong clicks, 9 guard passes.
Cộng challenge v3 đã đo: 99/99 observations trên 33 scene lặp ba lần,
45 verified target clicks và 18 guard passes. Không phải 99 scene độc lập.
Task B nhãn/dấu câu độc lập chưa có kết quả; live Vision vẫn tắt.
Các false refusals trên bộ ảnh static cũ chưa được đo lại/giải quyết.
