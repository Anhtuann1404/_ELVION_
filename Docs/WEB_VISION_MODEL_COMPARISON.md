# So sánh model Vision trên bốn ca đã thấy

## Mục tiêu và trạng thái

Đo `qwen3.5:4b` và `qwen3.5:9b` trên bốn diagnostic cố định: Migrations,
W3C Recommendation, Chrome Docs trùng tên và Chrome Get started. Trang model
chính thức: https://ollama.com/library/qwen3.5:9b (kiểm tra30/10/2026: có
Vision, bản tải khoảng7,6GB). Chọn model cùng họ nhưng lớn hơn là giả thuyết
cần đo, không phải bảo đảm chất lượng tốt hơn hoặc chạy nhanh trên máy16GB.

Runner: `benchmarks/web_observation/compare_models.py`. Không đổi model mặc
định sản phẩm, grounder, prompts, guards, oracle hoặc scorer giữa hai model.
Chỉ quan sát; không browser click/gõ. Đây là regression có chủ đích trên
bốn ca thất bại đã thấy, **không phải held-out mới**.

## Chạy trên desktop

Từ thư mục ELVION:

```bash
ollama pull qwen3.5:9b
```

Sau khi model tải xong:

```bash
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.web_observation.compare_models
```

Chạy một lượt, gửi đường dẫn `Comparison report:`. Nếu model chưa có hoặc
không hỗ trợ Vision local, runner dừng ở preflight trước inference và giữ
báo cáo incomplete; không coi đó là chất lượng model thấp. Lượt thử preflight
`model-comparison-5a64450351bd.json` chưa có9B nên0observations,complete=false.
Lượt tải do agent khởi động đã dừng vì tốc độ khoảng0,25–0,35MB/s, không báo
model đã cài. Không cần thay cấu hình model của phiên CLI/voice.

## Kiểm soát phép đo

- Ảnh gốc và OCR desktop đã lưu giữ cố định cho cả hai model. Native helper
  chỉ crop ảnh; không chạy OCR native trong lượt so sánh. Dữ liệu OCR được
  kiểm tra lại bằng decoder bounds/schema, subline query phải khớp target.
- Ghi checksum ảnh, metadata, annotation, diagnostic OCR và sáu source Vision;
  kiểm tra trước mỗi ca. Giữ model digest từ Ollama tags trước/sau mỗi nhóm.
- Giữ context4096,temperature0,max_tokens512,timeout120giây mỗi request cho
  cả hai model. Không retry/fallback theo output. Mọi outcome, kể cả error,
  được giữ trong report. Các lượt baseline/probe trước không bị ghi đè.
- Đo theo nhóm4B rồi9B, gỡ model trước khi nạp nhóm sau để hạn chế RAM.
  Cold start tính vào locate time; lịch chưa cân bằng nên chưa suy ra thống
  kê tốc độ model từ một lượt nhỏ. Nếu RAM/timeout gây lỗi, ghi nhận thật.
- Ghi từng phản hồi model, decision stage và outcome; ghi summary theo model.
  Báo cáo progress ghi sau mỗi ca; incomplete không được xem là batch đầy đủ.

## Giới hạn

Chỉ có3positive và1ambiguity, không có absent-target negatives. OCR gốc
không có image hash trong chính file diagnostic; phép ghép diagnostic/capture
dựa vào các artifact đã cung cấp, rồi khóa checksum lúc chuẩn bị phép đo.
Không coi đây là provenance native hoàn chỉnh. Chrome hiển thị suy giảm;
annotation có assistant review/self-review. Chưa chấm website chưa thấy,
freshness hay thao tác. Dù9B đạt4/4, cần mở rộng negative/regression và đo
native end-to-end trước xem xét tích hợp. Live Vision vẫn tắt.

## Kết quả đầu tiên —31/10/2026

Model9Bđã tải xong, reportmodel-comparison-637f29445f0f.json complete8obs.
4B1/4,9B3/4;positive0/3vs2/3. Docs9Bđúngtrạngtháirefusalnhưngemptylabelread,
không xácnhậnduplicate;Getstartedcũngemptyread. Xemphântíchđầydro
Docs/WEB_VISION_MODEL_RESULTS_2026-10-31.md. Chưa đổi model sản phẩm hoặc
bật Vision thao tác. Mục tải/preflightbêndưới/trướcđólà lịch sử.

## Opt-in label scaling

Runner so sánh nhận thêm --label-scale2 (cú phápCLI:--label-scale 2),
mặc định1để giữ control cũ. Reportmới ghi labelscale và bbox target gốc.
Đã có cached replaymodel-comparison-f3f83f7c307a.json:4B1/4,9B3/4,
nhưngDocs9Bnay xácnhận2label/role thay vìemptyread. Chi tiết thínghiệm
và native regression tiếp theo tạiDocs/VISION_IMAGE_PRESENTATION.md.
