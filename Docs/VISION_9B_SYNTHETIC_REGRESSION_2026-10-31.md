# Vision9B,labelscale2: native synthetic regression26/30

Nguồn do người dùng chạy trên desktop:
`artifacts/benchmarks/vision-labels/vision-labels-20261031T032101-b142c710.json`.
Đã đối chiếu manifestSHA,HTMLSHA của30ca,caseIDs và số pass/positive hit.
Không inference lại trong bước đối chiếu. Report này không lưu source digest
hoặc model digest,bbox/proposal/raw replies nên không chấm tọa độ độc lập
lại; chỉ kiểm tra cấu hình,oraclemanifest và consistency các outcome đã ghi.

## Kết quả

- Modelqwen3.5:9b,ocr-verified-v4,nativeOCRupscale2x,label_scale2,512tokens.
- Một lượt30ca:26đúng,4trượt. Positive19/22 (86,36%),3falseabstentions.
- Negative8ca:5correctnot_found,2correctambiguity,1wrongabstention.
- Không falseacceptances,wrongtarget hoặc provider/groundererrors trong lượt.
- Hai duplicate cases đềuverified_candidate_count2,không dựa vàoemptyread.
- Medianlocate6,385s;không suy ra mọi request có cùng sốphase/coldload.

| Ca trượt | Kết quả | Stage/bằng chứng |
|---|---|---|
| vl_d06_exclamation_link:Proceed! | not_found thayfound | Localrolebutton thaylink |
| vl_d12_changed_word:Save file/Save files | ambiguous thaynot_found | unresolved_merged_label,candidate0 |
| vl_h04_colon_link:Methods: | not_found thayfound | Locallink nhưngfullframetext |
| vl_h08_internal_punctuation:Status: ready | not_found thayfound | Localroletext thaylink |

Đây là regression đã thấy,không phảiheld-out mới hoặc đánh giá website thật.
Không đủ cơ sở bật liveVision hay thay model mặc định sản phẩm.

## Sửa code và diagnostic tiếp theo

Đã tái hiện một buggeneric: substringSave filetrongSave files bị đưa vào
nhómmergedlabel,subline không tách được và thànhambiguous. Bổ sung ranh giới
từ trong label_candidates.embedded_label; giữ cùng normalizer,NFC/diacritics/
punctuation và nativegeometry. Không requestsubline hay gọi model chỉ vì
target làprefix của từkhác. Test vẫn tách Docs Case studies,W3CRecommendation
kèmdate và giữ các bước independentread/role/state/fullimageveto.
Chưa tuyên bố ca desktop đạt sau sửa,native26/30cũ giữ nguyên.

Ba ca role còn lại chưa có raw replies/crop/OCR để phân tích presentation.
Marker/context có thể ảnh hưởng nhưng chưa xác minh nguyên nhân. Không
đổi expected,scorer hoặc loại bỏfullveto để lấy pass.

Thêm --diagnose-model cho runner synthetic. Mặc định report vẫn sanitized.
Opt-in lưu sidecar *.diagnostics.json cùng PNGfixture,OCRnative,querysubline,
response/phase/crophash,sourceSHA và resultbbox; không truyền oracle vào
grounder/model. Chỉ ghi những fixture tổng hợp đã chọn,không chụp desktop
người dùng. Mọiattempt/exception giữ lại; không lựa chọn lượt tốt nhất.

Chạy4ca một lần trên desktop:

```bash
PYTHONPATH=src:. .venv-browser/bin/python -m benchmarks.vision_labels.runner --model qwen3.5:9b --grounder ocr-verified-v4 --label-scale 2 --split all --case vl_d06_exclamation_link --case vl_d12_changed_word --case vl_h04_colon_link --case vl_h08_internal_punctuation --headless --diagnose-model
```

Gửi JSON và Diagnostics paths. PNG/trace sẽ cho phép replay với OCR đã lưu,
giảm số lần phải chạy native trên desktop. Chưa cần chạy lại toàn bộ30ca
cho tới khi có thay đổi hoặc cần xác minh hồi quy rộng hơn.
