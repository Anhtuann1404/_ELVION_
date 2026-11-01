# Task B — đánh giá nhãn gần giống độc lập

Mục tiêu: xây bộ dữ liệu và oracle độc lập kiểm tra recovery dấu câu; không sửa
sản phẩm, prompt, grounder, benchmark hiện có hoặc kết quả cũ.

Phạm vi file được tạo: benchmarks/vision_labels/ (cases.py, runner.py,
__init__.py), tests/test_vision_labels_benchmark.py, Docs/VISION_LABELS_BENCHMARK.md.
Không sửa file ngoài phạm vi; không commit/push. Chỉ dùng trang tổng hợp riêng,
không truy cập tài khoản, dữ liệu thật hay website công khai.

Hợp đồng: gọi grounder.locate(VisionFrame, target=..., role=...) -> GroundingResult.
Grounder chỉ nhận ảnh/target/role, tuyệt đối không nhận expected answer, ID ca,
bbox ground truth hoặc DOM. Runner có thể dùng DOM để tạo fixture và chấm độc lập.
Không click: chỉ chấm proposal; báo rõ đây không phải end-to-end.
Nhận grounder qua evaluate(cases, grounder=...), không import hay sửa internals
của semantic.py. CLI có thể tạo provider/grounder v2 hoặc v3 hiện có.

Tạo tối thiểu 24 cảnh với kỳ vọng viết tay trước inference:
- Nhãn không dấu câu, dấu câu thật ở cuối (. , : ; ! ?), dấu câu ở giữa,
  nhiều dấu cuối, chữ gần giống và tiếng Việt có dấu.
- Hai phần tử chỉ khác dấu câu, hai nhãn giống hệt nhau, nhãn vắng.
- Nhãn trùng ở xa nhau, plain heading, textbox bị yêu cầu button, disabled.
- Có cả button, textbox, link; thay đổi vị trí/kích thước và target text.
Không tự đặt kỳ vọng chỉ vì grounder đang trả kết quả nào đó. Nhãn có dấu thật
khác target không dấu phải bị từ chối nếu không tồn tại phần tử khớp khác;
nhãn chính xác có dấu thật vẫn là positive hợp lệ.

Giữ tập dev và held_out tách nhãn/layout, cố định trước inference; không chỉnh
held_out sau khi xem kết quả. Xuất manifest checksum/config/model/repetition.
Chấm centerclick trong bbox ground truth cho found; negative phải abstain,
error không được tính đúng. Báo positive coverage, false abstention, wrong target,
error và ambiguity; không dùng accuracy chung để che sai ở negative.
Test fake grounder: always-found, always-abstain, wrong-box, provider-error,
đảm bảo mỗi cách sai làm benchmark trượt. Không thêm dependency runtime.

Báo cáo cuối: files thay đổi, lệnh chạy, số liệu thực sự đo, giới hạn. Nếu
browser/OCR bị chặn, dừng ở blocked, không tự sinh điểm model thật. Có thể tạo
fixture/spec/tests trong lúc Task A sửa grounder, chạy inference sau khi tích hợp.
