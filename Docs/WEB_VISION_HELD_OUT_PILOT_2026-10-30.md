# Vision trên website thật: lượt held-out đầu tiên

Ngày: 30/10/2026 (giờ Việt Nam). Chỉ quan sát ảnh, actions=0.

## Kết quả và tính toàn vẹn

Báo cáo gốc: `artifacts/benchmarks/web-observation/plan-run-0d240437b49b.json`.
Plan: `artifacts/benchmarks/web-observation/held-out-plan-frozen-01.json`.
Đã đối chiếu plan SHA, core source, freeze, metadata, ảnh, annotation và mọi
proposal; tính lại summary khớp. Lượt chạy đầy đủ, quality_valid=true nghĩa
là dữ liệu hợp lệ, không có nghĩa chất lượng model đạt yêu cầu.

| Chỉ số | Kết quả |
|---|---:|
| Ca dự định | 12 |
| Ca chấm được | 9 |
| Ca đúng | 5/9 |
| Positive chọn đúng | 1/4 (25%) |
| Positive từ chối nhầm | 3/4 |
| Positive chọn sai vùng | 0/4 |
| Negative từ chối đúng | 4/4 |
| Ambiguity xử lý đúng | 0/1 |
| Ambiguity bị nhận thành found | 1/1 |
| Lỗi grounder/provider | 0/9 |
| Không chấm được | 3/12 (25%) |
| Ảnh duy nhất / domain | 3 / 3 |
| Median locate, mọi ca đã gọi | 1091 ms (n=9) |
| p95 nearest-rank | 9353 ms (n=9) |

Không gộp ambiguous false acceptance vào con số 0/4 negative false acceptance
rồi kết luận không chọn sai. Lượt này có một proposal không nên được nhận.
Không có click nên chưa có wrong click được quan sát hay end-to-end verifier.

## Chín kết quả

| Case | Kết quả | Bằng chứng hiện có |
|---|---|---|
| GitHub Get started | Đúng vùng | correct_target, 9353 ms |
| GitHub Migrations | Từ chối nhầm | Một OCR candidate/exact match, label_read_rejected |
| GitHub Docs yêu cầu button | Từ chối đúng | correct_rejection |
| W3C Recommendation | Từ chối nhầm | candidate_count=0, ocr_no_exact_match |
| W3C Latest published version: yêu cầu link | Từ chối đúng | correct_rejection |
| W3C Pay invoice | Từ chối đúng | correct_rejection |
| Chrome Docs | Nhận sai ca trùng tên | found cho một vùng; full_image_match_count=one |
| Chrome Get started | Từ chối nhầm | candidate_count=0, ocr_no_exact_match |
| Chrome Filter | Từ chối đúng trong viewport | correct_rejection |

GitHub Search, W3C Errata và Chrome Search button đã khóa undetermined trước
model nên không được gọi/chấm; không coi chúng là từ chối đúng.

## Kết luận và bước xử lý

**No-go cho mở rộng Vision thao tác public web.** Positive hit không đạt90%,
ambiguity không đạt80%; coverage cũng không đạt do25% không chấm được, chỉ
một ambiguity và chỉ ba ảnh/domain ở held-out. Ảnh Chrome hiển thị thiếu
styling; kết quả phản ánh ảnh đã chụp đó, không đại diện trang render đầy đủ.
Nhãn gồm người dùng đo + assistant review và assistant self-review; không
phải hai annotator con người độc lập. Model tag đã ghi, weight digest chưa pin.

Ưu tiên điều tra duplicate Docs trước: vì sao pipeline chỉ tạo một candidate
và full-image count chấp nhận one dù ảnh có nhiều nhãn. Sau đó điều tra OCR
recall/merged lines ở W3C và Get started, rồi blind label read ở Migrations.
Hiện chưa có raw OCR/model response của lượt này để khẳng định nguyên nhân
sâu hơn. Không suy từ decision stage thành nguyên nhân cuối cùng.

Giữ nguyên report, freeze, oracle và source baseline. Không chạy lại để thay
điểm bằng lượt tốt hơn. Nếu sửa theo các ca này, chúng trở thành regression
đã thấy, cần tập chưa thấy mới để đo generalization. Chưa sửa grounder trong
lượt tổng hợp; live Vision vẫn tắt. Task B desktop AX chỉ đọc có thể làm
song song vì không sửa module hay bộ dữ liệu Vision này.
