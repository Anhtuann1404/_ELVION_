# So sánh Vision4B/9B — bốn ca hồi quy đã thấy

Ngày31/10/2026. Báo cáo gốc:
`artifacts/benchmarks/web-observation/model-comparison-637f29445f0f.json`.

Lượt chạy đầy đủ8observations,actions0. Đã đối chiếu checksum ảnh/metadata/
annotation/diagnostic/source, tính lại summary và so image hashes ở các phase
chung giữa hai model. Digest model hiện tại vẫn khớp báo cáo. Không inference
lại trong lượt tổng hợp. Runner ghi outcome nhưng không ghi result bbox vào
row; việc đối chiếu này xác nhận summary/bindings, không chấm bbox độc lập lại.

## Kết quả

| Ca | qwen3.5:4b | qwen3.5:9b |
|---|---|---|
| GitHub Migrations | Từ chối nhầm | Chọn đúng mục tiêu |
| W3C Recommendation | Từ chối nhầm | Chọn đúng mục tiêu |
| Chrome Docs trùng nhãn | Báo ambiguous sau hai label reads và local link classifications | Báo ambiguous vì hai label reads rỗng |
| Chrome Get started | Từ chối nhầm: full-frame role=text | Từ chối nhầm: label read rỗng |

4B đạt1/4,positive0/3.9B đạt3/4,positive2/3. Cả hai0wrong-target trên3positive,
0grounder errors; không có absent-target negatives nên false acceptance loại
đó có mẫu số0, không được ghi thành0% đã kiểm chứng. Ca ambiguity9B được
scorer chấm đúng trạng thái, nhưng cơ chế là uncertainty/empty_label_read,
verified_candidate_count0; chưa chứng minh model đếm đúng hai target. Không
gọi đây là cải thiện phát hiện duplicate của9B.

Trên Migrations/W3C,9B giữ đúng rolelink trong cả crop và full-frame, trong
khi4B nhận crop làlink nhưng full-frame làtext. Đây là bằng chứng cải thiện
phân loại role trên hai ảnh cụ thể, không phải bảo đảm model lớn hơn tốt
hơn trên mọi website.

## Thời gian

| Ca | 4B locate | 9B locate |
|---|---:|---:|
| Migrations | 7,51s | 11,38s |
| W3C Recommendation | 4,55s | 5,61s |
| Docs | 3,18s | 1,81s |
| Get started | 3,72s | 0,72s |

Median4B4,14s/9B3,71s không chứng minh9Bnhanh hơn.9Bdừngsớm ở hai caChrome
nên chỉ gọi2/1phase so với4/3phase của4B. Lượt đầu mỗi nhóm có cold-start,
thứ tự nhóm4B→9B chưa cân bằng và chỉ một lượt mỗi ca. Chưa đo memory peak,
không dùng kích thước model trên disk thay RAM usage.

## Nguồn và quyết định

- 4B digest `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.
- 9B digest `d63f830f28d515fefea546f213fca7a75e9dd5176ef51a6deabc952d1c99a911`.
- Model local đã sẵn; trở ngại tải9B củaLIMIT-003 đã vượt qua theo lượt này.
- Cùng OCR desktop đã lưu, crop native và model thật; chưa là native OCR
  end-to-end. Bốn ca đã thấy, không phải held-out mới. Chrome render suy giảm,
  annotation có assistant review/self-review; không có quyền suy ra go-live.

Giữ9B làm ứng viên nghiên cứu; chưa đổi model mặc định sản phẩm, guard,
scorer hay bật Vision hành động. Bước điều tra tiếp theo là label read rỗng
trên cropChrome: kiểm tra kích thước/cách trình bày ảnh bằng phép so sánh
có kiểm soát, giữ nguyên independent read và role/state veto. Kích thước
crop hay marker là giả thuyết cần thử, chưa là nguyên nhân đã xác minh.
Sau đó mở rộng negative/synthetic regression và native end-to-end trước
bất kỳ tích hợp nào. Giữ nguyên baseline held-out5/9 và các probe trước.
