# Vision role regression — 31/10/2026

## Native baseline

`artifacts/benchmarks/vision-labels/vision-labels-20261031T040148-8df207b3.json`
đạt 28/30, positive 21/22, 0 wrong targets và 0 false acceptances. Cấu hình:
9B, label scale 2, role marker off, full scale 2. Đây là regression đã xem.

Hai lỗi:

- `vl_h04_colon_link`: label/local role đúng, full-frame role là text.
- `vl_d14_wrong_role_text`: hai vùng heading/prose bị local model nhận là
  link; grounder trả ambiguous thay vì not_found. Không có proposal click.

## Thử nghiệm đã giữ lại

Tất cả đường dẫn dưới `artifacts/benchmarks/vision-labels/`.

| Báo cáo | Thiết kế | Kết quả |
| --- | --- | --- |
| `fixture-replay-16c9899e7ed8.json` | Hai ca lỗi, mỗi ca hai lượt, cấu hình cũ | Methods đúng 2/2; Open guide sai 2/2 |
| `fixture-replay-3c398f615cfc.json` | Tám ca, lời nhắc visual-evidence-v1 | 7/8, không sửa Open guide |
| `duplicate-role-probe/probe-9f6098b146b5.json` | Full-frame, hai anchor trên mỗi cảnh d13/d14 | Hai vùng Open guide đều text/multiple; hai nút d13 đều button nhưng model đếm one sai |
| `duplicate-role-probe/probe-70903a422daa.json` | Context 8192, cùng bốn anchor và thêm Methods | Bốn kết quả chung không đổi; Methods là link |
| `fixture-replay-23cb45d55938.json` | Tám ca, prompt current + duplicate text check | 7/8; Open guide đã đúng, Methods bị từ chối |

Không kết luận lời nhắc mới tốt hơn từ 7/8: baseline hai ca đã cho thấy Methods
có thể đúng khi chạy lại. Không áp dụng lời nhắc thử nghiệm vào sản phẩm.

Telemetry full-frame 2× báo khoảng 4315–4319 prompt tokens trong cấu hình
context 4096. Đây chưa là bằng chứng truncation; tăng context lên 8192 không
sửa count sai trên hai anchor d13 đã đo. Không đổi context mặc định.

## Thay đổi opt-in: tinh chỉnh lời báo từ chối

`OCRLabelGrounder(..., duplicate_text_check=True)` chỉ bổ sung bước kiểm tra
khi có nhiều match và không có uncertainty từ bước đọc/phân loại trước đó.
Mỗi candidate được kiểm tra trên ảnh toàn trang bằng schema full-frame hiện có.

Chỉ trả not_found khi **mọi** candidate đều có observed_role=text và
matching_labels=multiple. Control, unknown hoặc count khác multiple giữ
ambiguous; protocol lỗi trả error. Không chọn candidate, trả bbox hay tạo found.

Mặc định False. Không đổi local/full veto cho ca một mục tiêu, scorer, oracle,
TTL, quyền hoặc trạng thái live Vision. Các duplicate thật vẫn phải được giữ
lại; full-frame count=one không được dùng để chọn một trong hai nút.

Giới hạn: đây vẫn là phân loại model, có thể từ chối nhầm; thêm full-image
inference làm ca duplicate chậm hơn. Không giải quyết TOCTOU/freshness.
Lượt tám ca sau sửa: d13 duplicate thật giữ ambiguous, khoảng 18 giây;
d14 trả not_found sau hai full observations, khoảng 32 giây. Đây không phải
đường xử lý có độ trễ phù hợp execution TTL hiện tại.

## Công cụ replay

Replay thêm --case, --repetitions và --role-profile. Selection phải có trong
diagnostic, không trùng, giữ thứ tự nguồn. Plan ghi đủ case, số lượt, cấu hình,
input/source hashes và driver hash. Lời nhắc thử nghiệm chỉ có trong replay.

Ví dụ chạy toàn bộ ảnh/OCR đã lưu, không browser, không click:

```sh
PYTHONPATH=src:. python3 -m benchmarks.vision_labels.replay \
  artifacts/benchmarks/vision-labels/vision-labels-20261031T040148-8df207b3.diagnostics.json \
  --role-marker off --full-scale 2 --duplicate-text-check
```

Đây là cached native OCR + ảnh đã lưu + model thật, không phải native OCR
end-to-end hoặc blind evaluation. Không lấy attempt tốt nhất để chấm.

Runner native cũng hỗ trợ --duplicate-text-check, chỉ với ocr-verified-v4.
Không cần thu lại corpus để điều tra offline.

Profile lời nhắc nghiên cứu cũng có trong runner native, mặc định current.
`role_profiles.py` giữ nguyên ảnh, schema, anchor và bước đọc nhãn; chỉ bổ sung
hướng dẫn vào hai bước phân loại role. Config lưu profile và source hash.

Lệnh native để đối chiếu sau nghiên cứu (không click):

```sh
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner \
  --model qwen3.5:9b --grounder ocr-verified-v4 \
  --label-scale 2 --role-marker off --full-scale 2 \
  --role-profile visual-evidence-v1 --duplicate-text-check \
  --split all --headless --diagnose-model
```

## Kiểm thử

48 tests liên quan đạt; sau thêm shared research profile, toàn suite 611 tests đạt.
Test bao phủ yêu cầu tất cả candidate, control/unknown/count mismatch,
protocol lỗi và giữ ambiguous khi có label read chưa rõ. Defaults giữ nguyên.
Kết hợp visual-evidence-v1 + duplicate text check đạt **30/30** trên toàn bộ
30 frame cached: 22/22 target hits, 6 correct rejections, 2 correct ambiguities,
0 false acceptances, 0 wrong targets, 0 errors, actions=0.
Báo cáo `fixture-replay-3046254907a8.json`.

Methods: đúng thêm **3/3** ở `fixture-replay-993f839ae05b.json`. Lượt lặp cùng
ảnh có thể hưởng cache/warm-up; không coi đó là bằng chứng độ trễ tổng thể.
Median toàn corpus khoảng **17.66 giây**; chưa phù hợp TTL thực thi hiện tại.

Đã kiểm tra input/source bindings, đủ case và planned observations. Chưa có
native OCR end-to-end sau sửa hoặc public/blind validation cho cấu hình mới.
Không đổi defaults; live Vision vẫn tắt. Sau gom lời nhắc vào shared helper,
nội dung đã đối chiếu bằng nhau và 6 tests liên quan đạt.
