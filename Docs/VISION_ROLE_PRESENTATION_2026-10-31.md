# Visibility of labels versus classification of controls: role presentation experiments

Ngày31/10/2026. Đây là nghiên cứu Vision trên ảnh đã lưu, không phải module
visibility desktop của TaskB và không có click. Không đổi model/default sản
phẩm hoặc oracle để lấy điểm.

## Baseline native và bug đã xác minh

Native four-case report `vision-labels-20261031T033137-e4158aca.json` đạt1/4:
Savefile/Savefiles đã not_found đúng; ba link còn lại đều đọc đúng chữ nhưng
trượt ởrole. Diag/frames/OCR cùngstem cho phép replay mà không cần nativeOCR
hoặc browser của người dùng. Lỗi boundaryBUG-018 đã nativeconfirmed trongca
này. Không sửa điểm26/30cũ hoặc gọi1/4chọnlọc là chất lượng toàn bộdataset.

## Ảnh role cắt: sáu vùng × bốn profile

Artifact: `role-presentation-cde9b7956c40/report.json`,plan/ảnh/inputhash trong
cùngfolder. Ba links lỗi, một buttonđối chứng và hai textcontrols công khai.

| Profile role | Đúng role |
|---|---:|
| Markerđỏ96padding hiện tại | 2/6 |
| Bỏ marker và câu hướng dẫn marker | 5/6 |
| Markerđỏ,phóng2× | 3/6 |
| Không marker,phóng2× | 5/6 |

Proceed! đổi từbutton sanglink khi bỏmarker;Status:ready đổi từtext sanglink.
ButtonSavefiles vẫnbutton. Headingcontrol tốt hơn khi bỏmarker. Riêng
metadataLatest published version: vẫn bị localclassifier nhậnlink ởcả4mode;
đây là lỗi còn lại, không được giấu để gọi profile mới là hoàn hảo.

Factor thay đổi gồm cả nét đánh dấu và câu mô tả nét đánh dấu. Chưa tách
được riêng hiệu ứng pixelđỏ khỏi wording của systemprompt, nên chỉ kết luận
policy trình bày role có ảnh hưởng trên các vùng này. Không suyra mọi marker
đều xấu. Giữ markerlabel theo policy cũ vì đây là phase khác.

Replay toàn pipeline với labelscale2/rolemarkeroff/fullscale1:
`fixture-replay-4afb56c85e04.json` đạt2/4. Proceed! vànearwordđúng;Methods:
vàStatus:ready localroleđúng nhưng vẫn bịfull-frame textveto. Giữveto.

## Ảnh toàn trang: năm vùng × ba profile

Artifact: `full-role-cb55d60aeb45.json`,plan/driver/provenance cùng thư mục.

| Profile full-frame | Đúng role |
|---|---:|
| Hiện tại | 3/5 |
| Thêm outline nguyênảnh | 2/5 |
| Phóng2×,anchor theo imagepixels | 5/5 |

Phóng2× giúpMethods:/Status:ready thànhlink;metadata/heading giữtext. Tuy
nhiênheadingGitHubDocs full-frame vẫncountone dù ảnh có brand/title trùng
chữ. Vì vậy5/5ởđây là **role**, không chứng minh count/uniquenesshoàn hảo.
Profile phóng đồng thời chuyển anchor sang imagepixel coordinates; không
quy kết duy nhất độ phân giải là cơ chế nội bộ. Mọi output giữ lại.

## Cấu hình kết hợp và giới hạn

Grounder thêm opt-in `role_marker=False` và `full_scale=2`;defaults vẫnTrue/1.
Ảnh labelscale2 riêng, ảnhrole không marker, ảnhfull đượcphóng nhưng giữ toàn
bộ nội dung; CSSbbox/định danh frame/snapshot không thay theo ảnhmodel.
Strictrole/state/countveto vẫn chạy. Không output-driven retry/fallback.

`fixture-replay-a9b7fd3667d5.json` đạt4/4 trên bốn ảnh/OCRnative đã lưu.
Đã tính lại scorer từ bbox đã lưu và authoredfixturegeometry,đối chiếuinput/
sourcebinding. Ba positive mất khoảng17,6–22giây tronglượt replay; không
nớiTTLcontroller để bấm. Chưa đoexecutionfreshness/visibility/action.

Publicregression cùng cấu hình ở `model-comparison-ce218ae01e84.json`:
4B1/4,9B3/4. Migrations/W3C/Docs giữ kết quả; Getstarted vẫn bịfullframeveto.
Không gọi4/4syntheticselected là4/4website haygeneralization. CachedOCR vẫn
khác nativeOCRend-to-end. Cần native rộng hơn trước áp dụng.

## Kiểm tra30ca native một lượt, lưu đủ để replay sau này

```bash
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner --model qwen3.5:9b --grounder ocr-verified-v4 --label-scale 2 --role-marker off --full-scale 2 --split all --headless --diagnose-model
```

Giữ cả pass/fail/error. `--diagnose-model` chỉ lưu fixture tổng hợp,không chụp
desktop riêng tư. Sau lượt này có thể replay toàn30ca bằng ảnh/OCR đã khóa,
không nhờ người dùng chạy lại native cho từng thí nghiệm. Chạy replay:

```bash
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.replay PATH_TO_DIAGNOSTICS --label-scale 2 --role-marker off --full-scale 2
```

589tests trước thay đổirole đã được mởrộng, toànsuite hiện605testsđạt. Các
tests mới xác nhận scopedcoordinate/targetbboxkhôngđổi,fullroleveto còn hiệu
lực,ảnh/HTML/goalbinding và từ chối đườngdẫnframe nằm ngoài diagnosticfolder.
Không nối TaskBvisibility, không bậtliveVision hoặcactionadapter.
