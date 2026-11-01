# Nhãn nhỏ: thử nghiệm trình bày ảnh, 31/10/2026

## Phạm vi và kết quả

Thử có kế hoạch trước inference:6profiles ×5vùng nhãn đã thấy, một lượt mỗi
vùng/profile, cùng model9B/digest và OCR desktop đã lưu. Target không đưa
vào lời gọi transcription. Marker và câu hướng dẫn marker đi theo profile;
tọa độ anchor thay đổi cơ học theo ảnh, không lấy bbox từ output model.

Kết quả: `artifacts/benchmarks/web-observation/label-presentation-253630be6d5d/report.json`.
Plan và ảnh input từng lượt lưu cùng thư mục trước/cùng inference.

| Profile | Đọc đúng | Đọc rỗng | Lỗi |
|---|---:|---:|---:|
| Hiện tại:padding12,selective marker | 2/5 | 3 | 0 |
| Đổi anchor key sang image pixels | 2/5 | 3 | 0 |
| Không marker | 2/5 | 3 | 0 |
| Phóng2×,selective marker | 5/5 | 0 | 0 |
| Phóng4×,selective marker | 5/5 | 0 | 0 |
| Contextpadding96 | 3/5 | 2 | 0 |

Hai vùng Docs có ảnh gốc56×42 và62×42; Get started95×42. Phóng2× làm đọc
được ba vùng này trong lượt thử. Đổi key hoặc bỏ marker riêng không đủ.
Đây là bằng chứng độ phân giải/cách trình bày ảnh ảnh hưởng đến các mẫu này,
không xác minh cơ chế nội bộ encoder hay bảo đảm mọi crop nhỏ sẽ được sửa.
Không chọn output tốt nhất giữa các profile ở runtime; giữ mọi observation.

## Triển khai có giới hạn

`OCRLabelGrounder(...,label_scale=1)` giữ mặc định cũ. Cho opt-in2hoặc4;
`presentation.py`/`ResizeImage.swift` phóng PNG qua stdin/stdout có giới hạn
5MiB/4096pixels,không OCR,không model hoặc thao tác. Chỉ phóng ảnh đọc nhãn.
Anchor mới là bbox_image_pixels trong ảnh phóng; bboxCSS mục tiêu,rolecrop
và ảnh toàn trang giữ nguyên. Test xác nhận không đưa bboxphóng thành tọa độ
target. Markerpolicy giữ nguyên,không retry/fallback theo output.

SOURCES cho các lượt mới đã gồm presentation.py và ResizeImage.swift. Freeze
held-out cũ giữ nguyên,không chạy nó như một lượt chưa thấy mới.

## Toàn pipeline với label_scale2

`model-comparison-f3f83f7c307a.json`:4B1/4,9B3/4 như trước về tổng điểm,
nhưng Docs9Bnay đọc đúng cả hai nhãn và local classify cả hai link nên
verified_candidate_count2/ambiguous. Trước đó9Bchỉ abstain vì empty reads.
Migrations/W3C9Bđúng; Get started nay đọc đúng/local link nhưng full-frame
matching_labelszero/roletext nên vẫn false_abstention. Giữ veto đó.

Thử riêng full-frame3profiles ×4scenes ở
`fullframe-presentation-125fd64cc2aa.json`: đổi key hoặc phóng toàn ảnh2×
không sửa Get started; Docsfullframevẫn thườngđếmone dù cóhai nhãn. Không
đưa full-frame scaling vào sản phẩm vì chưa có bằng chứng cải thiện. Driver,
plan và mọi output giữ lại.

Thử4negativepublic có oracle cũ trên ảnh byte-identical dùngcachedOCR:
`scaled-negative-replay-940ced048136.json`:3correct_rejection,1grounder_error,
0found. Lỗi GitHubwrong-role do cache không có query subline cho targetđó;
không lấy rowerror thành correct rejection,không quy lỗi đó cho chất lượng
model. Hai caabsent không gọi model, W3Cmetadata từchối ở label read nên bộ
nhỏ này chưa chứng minh semanticnegative coverage rộng.

## Kiểm chứng native tiếp theo

Chạy một lượt30ca synthetic có cả dấu câu, wrong-role,disabled,duplicates,
near labels và absent trên desktop (không click):

```bash
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner --model qwen3.5:9b --grounder ocr-verified-v4 --label-scale 2 --split all --headless
```

Đây là regression đã thấy,cần báo đầy đủ cả trượt. Không đổi model mặc định
CLI/voice/planner hoặc bật liveVision. Vẫn cần tập chưa thấy có oracle độc lập
và nativeend-to-end trước tuyên bố tổng quát. Các phép đo ở đây là cached
desktopOCR + crop/resize native + model thật,không phải toàn bộ OCR native.
