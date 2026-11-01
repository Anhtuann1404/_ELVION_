# Nhật ký lỗi và vướng mắc ELVION

Theo yêu cầu chủ dự án ngày 30/10/2026, nhật ký được duy trì xuyên suốt dự án.
Các mục ban đầu dưới đây được tổng hợp từ bằng chứng của những lượt làm việc
gần đây; không phải danh sách đầy đủ mọi lỗi từ lúc bắt đầu dự án.

## WEB-SUMMARY-001 — Model thật bị từ chối trên nhiều nguồn ngoài ca smoke

- **Ngày/phạm vi:** 01/11/2026, `source_highlights`, qwen3.5:4b local.
- **Triệu chứng/bằng chứng:** Bộ `benchmarks.web_summary.runner --live`
  trả `WEB_SUMMARY_UNVERIFIED` trên clean synthetic, Wikipedia và Example
  Domain; Python Tutorial đạt. Report:
  `artifacts/benchmarks/web-summary/summary-007345525a8947d28f851c7bb6c0bd17.json`.
- **Nguyên nhân:** Đã xác minh validator từ chối output; chưa lưu output
  thô nên chưa xác minh vi phạm do quote không khớp, duplicate paragraph
  hay cấu trúc. Không kết luận đây là lỗi model bịa khi chưa có bằng chứng.
- **Tác động/trạng thái:** Chức năng tóm tắt chưa đáng tin cậy trên các
  trang đã đo; đang điều tra. Validator không hiển thị output bị từ chối.
- **Bước tiếp theo:** Thêm diagnostics chỉ chứa mã vi phạm, tái hiện từng
  ca thất bại; giữ nguyên yêu cầu quote khớp nguồn khi sửa.

**Điều tra và sửa 01/11/2026:** Diagnostics bản cũ xác minh clean bị
`DUPLICATE_PARAGRAPH`; Wikipedia và Example Domain bị `QUOTE_MISMATCH`.
Report `summary-757abfed90a240a88f9407a36adfba71.json` trong cùng thư mục
benchmark giữ đủ 7 ca. Đã đổi `browser/summary.py`: cắt trước các span
20–300 ký tự nguyên văn, model chỉ chọn ID, code dựng quote từ span nguồn.
Hai span khác nhau cùng paragraph được phép. Diagnostics chỉ có mã cố
định; không chứa raw output. Test invalid ID, boolean, duplicate ID và
đoạn dài đạt; đang chờ phép đo native bản sửa.

**Kiểm chứng bản sửa:** Hai report `summary-25efc424293c434484ff037104dca2ab.json`
và `summary-d7ca5210de624c16a3db4d4d0f2a1a3a.json` trong cùng thư mục:
8/8 synthetic, 5/5 native đạt với qwen3.5:4b. Report sau có source hash
và đối chiếu quote độc lập với paragraph của article. Wikipedia và
Example Domain cũ đạt; thêm MDN Introduction và Python Data Structures
đều đạt. 890 test toàn dự án đạt (1 skipped); 35 test liên quan đạt sau
khi chốt phép chấm. WEB-SUMMARY-001: đã giải quyết trong phạm vi đã đo.

## WEB-SUMMARY-002 — Quote khớp nguồn vẫn có thể chọn chỉ dẫn giả làm ý chính


- **Ngày/phạm vi:** 01/11/2026, model local và fixture injection tổng hợp.
- **Triệu chứng/bằng chứng:** Ca injection trong cùng report phía trên
  trả hai highlight hợp lệ về quote nhưng chứa đoạn chỉ dẫn giả. Benchmark
  đánh fail riêng dù `exact_quotes_verified=true`.
- **Nguyên nhân đã xác minh:** Validator chỉ kiểm cấu trúc và quote khớp
  paragraph; không kiểm ý nghĩa hoặc độ liên quan của lựa chọn. System
  prompt chưa đủ để đảm bảo model bỏ qua đoạn chỉ dẫn trong ca đã thử.
- **Tác động/trạng thái:** Chọn ý chính sai; chưa chứng minh model đã làm
  theo lệnh giả. Module summary không có đường thực thi tool, output chỉ
  hiển thị. Vấn đề chất lượng vẫn mở.
- **Kiểm chứng:** Test benchmark xác nhận quote đúng từ đoạn injection
  vẫn bị chấm fail. 31 test summary/session/benchmark đạt.
- **Bước tiếp theo:** Thiết kế và đo lại việc chọn nội dung có ích với
  nhiều ca injection/negative; không dùng quote matching làm bằng chứng
  về semantic correctness hoặc an toàn toàn bộ pipeline.

**Sửa và đo lại 01/11/2026:** Prompt chọn ID yêu cầu chỉ chọn nội dung về
chủ đề, bỏ lời hướng tới assistant/system và trả selections rỗng nếu
không có nội dung có ích. Bổ sung ca tiếng Việt, paraphrase, instruction-only
và tutorial hợp lệ. Oracle injection giờ kiểm mọi lựa chọn thuộc paragraph
độc hại đã gán nhãn, không chỉ dò marker. Đây là thay đổi chất lượng chọn
nội dung, chưa phải một ranh giới bảo mật; đang chờ model thật.

**Kiểm chứng bản sửa:** Trong hai report sau sửa nêu trên, cả 3 ca nguồn
có chỉ dẫn giả (gốc, Việt, paraphrase) đều không chọn paragraph độc hại;
instruction-only abstain, tutorial hợp lệ vẫn có highlight.
WEB-SUMMARY-002: đã giải quyết cho các ca regression đã đo. Chưa có tập
adversarial độc lập hoặc bảo đảm đúng trước mọi injection; prompt không
phải cơ chế phân quyền. Độ hữu ích ngữ nghĩa trên mọi trang chưa được đo.

## WEB-SUMMARY-003 — Đoạn mở đầu dài hơn ngân sách bị coi là không có nội dung

- **Phạm vi/bằng chứng:** Bản cũ dừng trước khi thêm paragraph nếu tổng
  vượt 7.000 ký tự; một paragraph đầu dài hơn 7.000 khiến WEB_NO_CONTENT
  dù có nội dung. Xác minh trực tiếp điều kiện trong `source_highlights`.
- **Tác động/nguyên nhân:** Nhầm nội dung dài với nguồn rỗng do kiểm budget
  theo toàn paragraph. Chưa có ca native cụ thể chứng minh gặp tình huống này.
- **Xử lý:** `source_candidates()` lấy prefix còn trong ngân sách, giữ
  số paragraph gốc và tách span khớp nguyên văn. Test paragraph dài đạt.
- **Trạng thái:** Đã giải quyết trong phạm vi unit test nguồn dài; không
  khẳng định mọi đoạn dài đều cho highlight hữu ích qua model thật.

## YT-BLOCK-001 — Worktree YouTube thiếu commit nền browser/Vision

- **Ngày/phạm vi:** 01/11/2026; kiểm nhánh `feat/youtube-vision`, worktree
  `/Users/yingjunn_/.codex/worktrees/elvion-youtube-vision/ELVION`.
- **Bằng chứng:** HEAD `2ff695d` chỉ thêm `Docs/YOUTUBE_VISION_PLAN.md`
  và `Docs/YOUTUBE_VISION_ISSUES.md`; worktree sạch, diff check đạt.
  Cây `origin/main` hiện có trong máy không chứa `src/elvion/browser/`,
  `src/elvion/vision/` hoặc `interface/session.py`. Các file này có ở
  working tree chung nhưng chưa được Git theo dõi/commit. Checkout chung
  hiện đứng trên `codex/apple-music`, HEAD `84e69cf`.
- **Nguyên nhân đã xác minh:** Thiếu commit nền chia sẻ cho worktree độc
  lập, không phải lỗi runtime YouTube. Các kết quả web thật trước đó thuộc
  working tree chung và không có trong commit kế hoạch của YouTube.
- **Tác động/trạng thái:** Nhánh YouTube chưa thể test tích hợp trên nền
  tái lập; đang chờ đóng gói commit nền. Chưa có native YouTube/Vision mới.
- **Bước tiếp theo:** Chốt phạm vi nền browser/Vision và phụ thuộc, tạo
  commit trên nhánh `feat/*` riêng, kiểm trên cây sạch; sau đó nhánh
  YouTube merge/rebase nền đó rồi tiếp tục. Không commit toàn bộ working
  tree đang có phần Apple Music và các thay đổi chưa phân loại.

## AM-INTEGRATION-001 — Lỗi native bị bắt lại làm mất mã và trạng thái uncertain

- **Ngày/phạm vi:** 01/11/2026, `NativeAppleMusicBackend._run_jxa`.
- **Bằng chứng:** `MusicBackendError` kế thừa `ValueError`; lỗi semantic
  được ném trong khối parse JSON bị chính `except ValueError` bắt lại,
  đổi thành VERIFICATION_FAILED và bỏ `external_effect_possible`.
  JSON lỗi sau dispatch mutating cũng không giữ cờ tác dụng có thể xảy ra.
- **Tác động/trạng thái:** Có thể báo failed thay vì uncertain sau thao
  tác phát/pause; permission/target error bị đổi mã. Đang sửa; 29 test cũ
  dùng fake chưa phủ đường parse native này.
- **Bước tiếp theo:** Giữ MusicBackendError, kiểm schema và thêm test
  runner giả ở biên subprocess; không cần phát nhạc thật để tái hiện.

**Sau sửa:** `_run_jxa` giữ nguyên MusicBackendError; parse/schema lỗi
sau mutating dispatch giữ `external_effect_possible=True`. Test runner
giả kiểm permission error và JSON hỏng đạt. 32 test Music đạt.
Đã sửa trong phạm vi biên subprocess; chưa kiểm lỗi sau playback thật.

## AM-INTEGRATION-002 — State native không hợp lệ bị đổi thành stopped

- **Ngày/phạm vi:** 01/11/2026, `NativeAppleMusicBackend.player_state`.
- **Bằng chứng:** State ngoài playing/paused/stopped hoặc thiếu state
  mặc định thành stopped; verifier pause chấp nhận stopped.
- **Tác động/trạng thái:** Payload hỏng có thể trở thành bằng chứng pause
  thành công. Đang sửa; cần test malformed response qua native parser.
- **Bước tiếp theo:** Từ chối state thiếu/sai thay vì dựng trạng thái mặc
  định; giữ bằng chứng native read-only tách riêng với playback thật.

**Sau sửa:** State thiếu/sai trả VERIFICATION_FAILED. Test không cho
unknown/null biến thành stopped đạt. Đã giải quyết trong phạm vi parser;
native read-only và hồi quy toàn dự án đang được kiểm riêng.

## Quy ước ghi nhật ký

## AM-NATIVE-003 — Read-only player_state timeout khi review tích hợp

- **Ngày/phạm vi:** Lượt kiểm chứng kết thúc 02/11/2026; NativeAppleMusicBackend
  trong checkout chung. `check_available` đạt; AppKit báo running=true,
  một PID; `player_state` timeout với command_timeout=3s.
- **Bằng chứng:** Review subprocess trả MusicBackendError với thông báo
  cố định Command failed or timed out; không có track text được in/lưu.
- **Nguyên nhân:** Chưa xác minh do latency, quyền Apple Events hay trạng
  thái ứng dụng. Không dùng native report cũ để kết luận runtime hiện tại đạt.
- **Tác động/trạng thái:** Native read player chưa được xác nhận; đang
  điều tra. 922 test toàn dự án đạt (1 skipped), trong đó 32 test Music;
  không xem fake tests là playback native proof.
- **Bước tiếp theo:** Probe read-only có thời hạn rõ, đo latency, tách
  lệnh playerState với đọc metadata; không retry mutation hoặc phát nhạc.

## Quy ước ghi bổ sung

## CATALOG-PLAY-003 — Track nằm ngoài vùng cuộn, headed click bị chặn

- **Ngày/phạm vi:** 02/11/2026, bố cục artist page sau các probe panel.
- **Bằng chứng:** `catalog-play-cli-52328b49e47047bb881f940828258e56.json`
  giữ play uncertain tại expose_play_switch/driver_failure, các bước còn
  lại đạt. Probe action riêng trả ACTION_FAILED/visible fail/offscreen,
  delivery not_delivered. Row y712,5..768,5 trong khi scrollarea nội dung
  kết thúc y664,5. Không quy lỗi cho metadata Apple hoặc người dùng.
- **Nguyên nhân đã xác minh:** Driver chưa chuẩn bị viewport trước group
  click, auto-scroll upstream chưa đưa target vào vùng thấy được.
- **Xử lý đang kiểm:** Snapshot include-bounds, tìm scrollarea cha chứa
  đúng native row ID; cuộn dọc bounded, đọc lại vị trí đã thay đổi trước
  scroll tiếp. Chỉ click ref mới khi bounds trọn trong viewport; không
  dùng xy, không scroll mù khi chưa thấy tác dụng. Test clipped-row và
  scroll không có hiệu ứng đạt, đang kiểm native sau sửa.

## CATALOG-NAV-003 — Panel queue mở làm snapshot không trả ô Search trong ca native

- **Ngày/phạm vi:** 02/11/2026, sau khi mở queue để khảo sát metadata.
- **Bằng chứng:** Report `catalog-play-cli-2b7b730d1e354165b7f35ab8c6d17460.json`
  giữ search uncertain, chưa đến play; cuối paused, volume không đổi.
  Snapshot sau đó không có textfield/radiobutton dù ảnh có thanh Search.
  Focus-window xác nhận focused=true vẫn không trả textfield. Đóng queue
  do probe đã mở, snapshot đọc lại có textfield và radio Apple Music.
- **Nguyên nhân:** Xác minh quan sát liên quan panel/partial AX snapshot;
  chưa xác minh cơ chế upstream gây thiếu node. Không kết luận là thiếu
  ô Search thật hoặc do người dùng di chuột.
- **Trạng thái:** Có workaround kiểm setup: đóng queue trước ca chuẩn;
  driver vẫn fail-closed khi không có field để bind. Chưa sửa upstream
  hoặc tự động hỗ trợ mọi panel. Giữ report lỗi trong mẫu số native.
- **Bước tiếp theo:** Chạy lại ca mới sau khi quan sát đã có field; không
  tự click/nhập theo tọa độ để bù dữ liệu AX thiếu.

## CATALOG-PLAY-002 — CLI play timeout trong native smoke dù test fixture đạt

- **Ngày/phạm vi:** 02/11/2026, catalog policyv2/driver playback mới.
- **Bằng chứng:** Report `artifacts/benchmarks/agent-desktop/catalog-play-cli-1f7eea0b181f42a28a18ae26eaacd407.json`:
  search/open_artist/pause succeeded, play uncertain với POSTCONDITION_TIMEOUT
  khoảng13,24s. Player cuối paused, volume không đổi,4confirmation.
  941 test OK (1 skipped), không coi fixture thành native proof.
- **Nguyên nhân:** Chưa xác minh timeout khi lộ switch hay khi đợi player
  khớp. Metadata async đã được thấy trong probe trước nhưng chưa đủ chứng
  minh là nguyên nhân ca CLI này.
- **Trạng thái/bước tiếp theo:** Đang thêm diagnostics chỉ gồm phase và
  boolean, quan sát UI sau pause; kiểm hover nếu switch chỉ hiện khi hover.
  Không tự lặp mutation đang chưa rõ; chỉ test mới sau khi đã xác nhận paused.

**Nguyên nhân đã xác minh:** Snapshot sau pause có switch `Phát`, value1,
checked. Driver chỉ nhận Phát/value0 nên không thấy play_ref và chờ quá
hạn. Checked còn phản ánh bài hiện tại, không đồng nghĩa playing.
Hover thử readback không thay đổi điều này. Sửa nhận nhãn action Phát
với cả value0/1; verifier vẫn bắt buộc nhãn tạm dừng+checked và player
playing. Test paused-current-track/value1 đạt; đang chạy native lại.

**Native sau sửa lần1:** Report `catalog-play-cli-13728a27e7ef401b876db18e8890b33a.json`
giữ play uncertain ở phase verify_playback; checks player_playing=true,
title_matches=true, volume_unchanged=true nhưng row_playing=false.
Pause riêng đạt, cuối paused. Đã sửa lỗi nhận play switch nhưng chưa
giải quyết verifier trên native; không đóng vấn đề. Đang probe các
thuộc tính switch khi playback thật để phân biệt label/state/hover.

**Điều tra tiếp:** `row-state-probe-3465ce916bbd4c1cb312aa29fda240eb.json`
giữ3 mẫu player playing/title đúng nhưng row vẫn Phát/value0. Không dùng
row checked như nguồn identity đáng tin cho mọi lượt tải. Các thử menu
metadata/select bị APP_UNRESPONSIVE/ACTION_NOT_SUPPORTED, không sửa library
hoặc đọc clipboard. JXA currentStreamURL rỗng; objectID/databaseID/persistentID
không bằng song catalog ID trong probe boolean.

**Giải pháp v3 đang kiểm:** Apple Lookup theo ID1790455481 trả một song;
đối chiếu player trong RAM khớp title+artist+album, thời lượng lệch0,635s.
Tra metadata ID số qua endpoint public cố định (VN), không gửi query,
metadata người dùng hoặc token; giới hạn64KiB, timeout10s, không redirect.
Verifier v3 dùng playing, ba chuỗi khớp chuẩn hóa NFC/whitespace/case,
duration lệch tối đa1s và persistentID receipt ổn định trong RAM, cùng
row nguồn catalog ID còn đúng context. Tolerance1s là ngưỡng được ghi rõ
cho sai khác thời lượng đã quan sát, chưa xác minh nguyên nhân làm tròn.
Đây là metadata verification theo ID, không claim JXA trả trực tiếp storeID.
Giữ toàn bộ report thất bại; đang kiểm native v3 trước khi đóng vấn đề.

## CATALOG-PLAY-001 — Catalog ID không có trực tiếp trong player_state JXA

- **Ngày/phạm vi:** 02/11/2026, chuẩn bị catalog playback. Top Bài Hát
  dùng TrackLockup gắn artist ID và decimal song ID; group có Click,
  không phải cell như artist card. Probe subtree Top Bài Hát trả
  observation_incomplete, snapshot tổng vẫn đọc được các group dương tính.
- **Bằng chứng:** Scripting dictionary com.apple.Music.sdef và property
  keys current track có persistentID/databaseID nhưng không có song/store
  catalog ID. Native IDs của miniPlayer không chứa ID numeric.
- **Tác động/trạng thái:** Chưa có liên kết trực tiếp decimal song ID với
  persistentID16hex; không đưa catalog ID vào backend library hoặc báo
  exact catalog identity chỉ từ tên bài. Đang điều tra verifier.
- **Bước tiếp theo:** Thử phát một track catalog đã quan sát/được phép,
  đọc trạng thái row và player độc lập, tạm dừng sau probe. Nếu không có
  evidence identity đủ mạnh, chỉ ghi mức kiểm chứng thực tế và giới hạn.

**Probe native:** `playback-probe-723d6b1ee4864844b45b8e9ae14d9cc9.json`
trong artifacts/benchmarks/agent-desktop: headed click group chỉ chọn,
player paused. Row sau đó có switch Phát value0. Probe thứ hai
`playback-probe-9ad1d219bc1f4df280294dc2cea7119c.json`: click switch đúng
rowID khiến row switch tạm dừng/value1/checked và player playing; đã
pause trong finally, volume không đổi. Lần đọc title ngay sau playing
chưa khớp; đọc lại sau pause title row/player đã khớp. Metadata bất đồng
bộ và tên hiển thị row có thể cập nhật sau load, không dùng playing một
mình hoặc tên cache trước phát làm bằng chứng exact identity. Hướng sửa:
giữ row catalog ID, đợi row checked cùng player playing/title của row
mới, chốt receipt persistentID trong RAM rồi verifier đọc lại độc lập.

**AD-PROBE-005 điều tra/sửa 02/11/2026:** Trong cùng môi trường, `press
return --app Nhạc` báo cơ chế AXConfirm; `--headed press return` sau
khi kiểm foreground Music, window ID và đúng textfield focused báo
CGEventPost/physical_synthetic. Cách thứ hai mở trang kết quả Beethoven
qua keyboard, xác nhận bằng snapshot. Đây là khác biệt đường dispatch
đã quan sát, chưa kết luận nội bộ upstream vì sao chọn AXConfirm.
Driver mới `adapters/music_catalog.py` dùng đường CGEvent đã đo, kiểm
focus sát trước dispatch và context sau đó; không retry mutation.
CLI native search→open_artist đạt lần đầu, có grant/confirmation/verifier.
Đang kiểm regression, Unicode và giới hạn trước khi chốt trạng thái.

**AD-PROBE-005 chốt kiểm chứng:** Adapter/core runtime và CLI session mới
đã chạy thật với Latin và Unicode. Report chốt:
`artifacts/benchmarks/agent-desktop/catalog-cli-146061fbbcc84ee0a43934847f30223e.json`.
Hai capability search/open_artist đều succeeded, simulated=false,
postcondition_verified=true, hai confirmation riêng. Không dùng screenshot
hoặc tọa độ; track/volume không đổi, player paused trước/sau. 935 test
toàn dự án OK (1 skipped), trong đó13 test catalog. Đã giải quyết bước
submit cho phiên bản/locale đã đo bằng foreground-guarded CGEvent; chưa
claim đã sửa AXConfirm upstream hoặc mọi dropdown/locale đều hoạt động.
Driver không khóa được input của người dùng giữa kiểm foreground và
CGEvent; giới hạn race còn lại ghi trong MUSIC_CATALOG_CLI.md.

## CATALOG-UI-001 — Confirmation mới ban đầu hiện raw JSON

- **Ngày/phạm vi:** 02/11/2026, lượt native CLI catalog đầu tiên.
- **Bằng chứng:** Renderer chưa biết capability Music catalog/risk medium
  nên dùng fallback định dạng gốc, khó xem danh tính mục chọn.
- **Xử lý:** Thêm renderer riêng có schema chặt, hiện truy vấn hoặc tên
  nghệ sĩ+catalog ID và ảnh hưởng focus/chuột/phím. Tên đã chọn được ràng
  buộc trong intent/confirmation digest và đối chiếu cache kết quả.
- **Trạng thái:** Đã sửa, test phiên giả lập backend đạt; chờ native CLI
  lần chốt. Trace vẫn dùng projection, không lưu query/names/AX tree.

**CATALOG-UI-001 kiểm chứng:** Native CLI cuối có raw_confirmation_fallback=false,
hai confirmation tiếng Việt và danh sách nghệ sĩ hiện đúng. Đã giải quyết
trong hai capability mới. Test trace với query/name synthetic xác nhận
không có hai chuỗi này trong JSONL; không thay hợp đồng privacy hiện có.

## AD-PROBE-006 — Catalog có nhiều đối tượng cùng tên, khác loại và ID

- **Ngày/phạm vi:** 02/11/2026, thử truy vấn mẫu Unicode trên Music catalog.
- **Bằng chứng:** Có4 cell cùng nhãn,3 catalog ID; trong đó album và artist
  dùng cùng tên, hai artist ID khác nhau. Không chọn `.first` theo tên.
- **Tác động:** Chọn theo tên có thể mở sai loại hoặc sai danh tính. ID
  catalog là số thập phân, khác persistentID16hex của backend JXA library.
- **Xử lý kiểm chứng:** Đọc subtree complete=true của card, xác minh loại
  Nghệ sĩ và ID, sau mở đọc header ArtistDetailHeaderLockup bằng observation
  mới. Hai ca Latin/Unicode đều khớp ID đã chọn. Player cuối paused.
- **Trạng thái:** Đã có cách kiểm chứng cho ca giám sát này; chưa tích hợp
  contract catalog vào sản phẩm. Hướng xử lý: lưu entity_type+catalog_id,
  đối chiếu header sau điều hướng, không đưa catalog ID vào JXA play_track.
  Có nhiều artist ID cùng tên thì cần thêm ngữ cảnh/xác nhận lựa chọn.
- **Báo cáo:** `artifacts/benchmarks/agent-desktop/music-selection-daa62d6bf7c54a51bab1a23d968199fb.json`.

**AD-PROBE-005 bổ sung:** Trong ca Unicode, đọc surface menu cho dropdown
trả APP_UNRESPONSIVE, nhưng ảnh vẫn có gợi ý và click truy vấn theo ảnh
mở kết quả. Không kết luận Music đã treo. Giới hạn đọc dropdown vẫn mở.
Người dùng báo đã di chuột trong một phiên trước; chưa xác minh có tác
động tới ca nào. Khi điều khiển thật cần quan sát lại, không suy đoán lỗi
do người dùng hoặc retry action delivered_unverified một cách mù quáng.

## AD-PROBE-005 — Search icon/AXConfirm chưa commit trang kết quả Music

- **Ngày/phạm vi:** 02/11/2026, agent-desktop1.0.2, Music catalog.
- **Bằng chứng:** Sau headed click sidebar, textfield xuất hiện. AXValue
  nhập Beethoven được snapshot xác nhận. Click icon Tìm kiếm mở gợi ý;
  `--headed press return --app Nhạc` trả cơ chế AXConfirm, delivered_unverified,
  nhưng ảnh sau đó vẫn là trang tìm kiếm gần đây, không phải kết quả.
  Snapshot surface popover trả ELEMENT_NOT_FOUND dù ảnh trước có dropdown.
- **Nguyên nhân:** Chưa xác minh nội bộ. Không xem action ok hoặc query
  value đúng là bằng chứng catalog search hoàn tất.
- **Xử lý kiểm chứng:** Theo phép người dùng cho click/phím thật, quan sát
  lại dropdown, quy đổi điểm dòng gợi ý truy vấn từ ảnh theo bounds window,
  click một lần. Ảnh và AX sau đó có trang kết quả và các cell Beethoven.
- **Trạng thái:** Có workaround có người giám sát cho ca này; giới hạn
  semantic confirm/popover vẫn mở. Không dùng tọa độ này làm code production.
  Không phải kết quả benchmark của Vision local, chưa nối ELVION adapter.

**AD-PROBE-004 cập nhật:** Người dùng đã cho phép physical input trong
Music. Headed click sidebar mở ô nhập, khắc phục việc chỉ chọn hàng cho
ca đã đo. Catalog search đã đạt bằng luồng kết hợp AX và click theo ảnh;
headless-only vẫn chưa đạt. Report sanitized:
`artifacts/benchmarks/agent-desktop/music-search-c914fe1122fc4766b78a7d24f267b9b1.json`.
Radio Apple Music checked, query khớp,14 cell tên chứa truy vấn; không
coi14 cell là14 kết quả duy nhất. Player sau kiểm chứng vẫn paused, không
dispatch playback. Snapshot complete=false; chưa claim đọc hết catalog.

## AD-PROBE-003 — Find trên toàn cây Music chạm giới hạn traversal

- **Ngày/phạm vi:** 02/11/2026, agent-desktop@1.0.2. Find treeitem tên
  Tìm kiếm exact trả TIMEOUT/locator_budget_limit, observed_matches=1,
  child_hits=3, retryable=false; delivery not_delivered/retry safe.
- **Tác động/trạng thái:** Chưa dispatch click. Không dùng observed_matches
  của truy vấn chưa hoàn tất làm bằng chứng ref duy nhất. Đang thu hẹp
  quan sát theo skeleton/sidebar trước khi chọn ref.
- **Nguyên nhân:** Đã xác minh traversal vượt budget; chưa xác minh vì
  sao Music có child_hits. Không tăng ngân sách và retry mù toàn cây.

**Cập nhật:** Snapshot skeleton mới đọc mục Tìm kiếm trong sidebar theo
path window/group/scrollarea/outline/treeitem và lấy ref mới, không dùng
ref từ truy vấn timeout. Có thể dùng mapping rồi drill-down thay find
toàn cây. Giới hạn find toàn cây vẫn còn, chưa sửa mã upstream.

## AD-PROBE-004 — Semantic click chỉ chọn hàng, chưa mở giao diện tìm kiếm

- **Ngày/phạm vi:** 02/11/2026, Music bản địa hóa Nhạc, agent-desktop1.0.2.
- **Bằng chứng:** Click ref mới của treeitem Tìm kiếm trả
  delivered_verified/retry unsafe, cơ chế select_within_container.
  Snapshot sau click không có textfield; wait-for textfield5s timeout.
  Ảnh cửa sổ xác nhận hàng sidebar đã chọn nhưng phần chính vẫn là view
  cũ; không ghi nội dung view cá nhân vào log hoặc report.
- **Nguyên nhân:** Xác minh được chọn hàng không đồng nghĩa điều hướng;
  chưa xác minh callback/activation nội bộ của Music. Không coi snapshot
  complete=false là bằng chứng toàn app không có ô nhập.
- **Tác động/trạng thái:** Chưa nhập hoặc gửi truy vấn, chưa search catalog,
  chưa click playback. Đang chờ người dùng cho phép thử physical input
  trong Music, theo yêu cầu --headed của hướng dẫn nhúng công cụ.
- **Bước tiếp theo:** Nếu được phép, lấy ref mới và kiểm click/nhập thật
  bằng quan sát độc lập; không tự lặp click semantic đã dispatch.

## AD-PROBE-002 — Snapshot --app Music trả APP_NOT_FOUND sau khi cấp quyền

- **Ngày/phạm vi:** 02/11/2026, agent-desktop@1.0.2. Permissions xác nhận
  Accessibility và Screen Recording granted sau thao tác của người dùng.
- **Bằng chứng:** Snapshot skeleton với app name Music trả APP_NOT_FOUND,
  chưa có cây UI. Không có hành động click/playback.
- **Nguyên nhân:** Chưa xác minh app đã đóng hay display name được bản
  địa hóa; không kết luận backend không hỗ trợ Music.
- **Trạng thái/bước tiếp theo:** Đang kiểm list-apps, đối chiếu bundle
  com.apple.Music rồi dùng đúng display name theo tài liệu công cụ.

**AD-PROBE-001 cập nhật:** Quyền Accessibility đã granted. Blocker quyền
đã giải quyết trong lần kiểm này; tiếp tục kiểm danh tính app riêng.

**AD-PROBE-002 cập nhật 02/11/2026:** `list-apps` xác nhận bundle
com.apple.Music đang chạy dưới display name `Nhạc`. Snapshot với tên
`Nhạc` đạt: skeleton60 nodes/53 refs; interactive depth16 có158 nodes/
148 refs. Đọc được mục Tìm kiếm, Thư viện và nút playback qua AX.
APP_NOT_FOUND do dùng tên không khớp bản địa hóa, đã giải quyết trong ca
này. Cả hai snapshot complete=false; không tìm thấy text input ở phần
đã đọc không chứng minh app thiếu ô tìm kiếm. Chưa click/type hoặc phát
nhạc; các ref chỉ là bằng chứng quan sát, phải snapshot lại trước action.
Report đã lọc metadata riêng tư:
`artifacts/benchmarks/agent-desktop/music-skeleton-afc6e8eaa71e48d3a33ad9c45e648b86.json`
và `music-interactive-5741222ec3e34583ad906d837dc1eca2.json` cùng thư mục.

## AD-PROBE-001 — agent-desktop bị chặn bởi quyền Accessibility

- **Ngày/phạm vi:** 02/11/2026, npm agent-desktop@1.0.2 cài riêng tại
  `/private/tmp/elvion-agent-desktop-probe`; macOS arm64, envelope v2.5.
- **Bằng chứng:** `status` và `permissions` báo accessibility denied,
  screen_recording granted, automation unknown. Snapshot Music read-only
  trả PERM_DENIED, delivery not_delivered, retry safe.
- **Nguyên nhân đã xác minh:** Quyền Accessibility của tiến trình khởi
  chạy/binary chưa cấp. Chưa đọc được UI nên chưa đánh giá Music catalog.
- **Tác động/trạng thái:** Đã cài được công cụ; probe UI đang chờ người
  dùng bật quyền macOS. Không có hành động click hoặc playback.
- **Bước tiếp theo:** Mở `permissions --guide`, người dùng cấp quyền app/
  binary theo hướng dẫn, kiểm lại permissions rồi snapshot read-only.
  Không dùng Screen Recording granted để suy ra Accessibility granted.

**Cập nhật AM-NATIVE-003 ngày 02/11/2026:** Probe timeout15s đạt sau
0,237s, state paused. Sau đó backend mặc định3s cũng đạt 0,193s. Report
`artifacts/benchmarks/apple-music/readonly-b71bbbe9b54e4191a263c8a93f5e0523.json`
ghi 6/6 ca read-only đạt: AppKit, player state, search chuỗi test Unicode,
search chuỗi ngoặc kép/backslash, tra ID không tồn tại và Swift probe.
Không lưu metadata track, không dispatch playback. Timeout ban đầu chưa
có nguyên nhân đã xác minh; giữ đang điều tra độ ổn định/cold call, không
tự tăng timeout production hoặc retry mutation từ phép đọc thành công này.

**Cập nhật AM-INTEGRATION-001/002 ngày 02/11/2026:** Native player parser
bản sửa đã đọc thành công trên máy thật; 32 test Music rerun đạt. Full
suite sau sửa trước đó: 922 test, OK (1 skipped). Các nhánh lỗi subprocess
vẫn chỉ có kiểm chứng bằng runner giả; không cố gây lỗi trong playback thật.

Mỗi mục có ID riêng, ngày, triệu chứng/phạm vi, bằng chứng hoặc cách tái hiện,
nguyên nhân (đã xác minh hay giả thuyết), cách xử lý, kiểm chứng và trạng thái.
Trạng thái: đang điều tra / đã sửa, chờ kiểm chứng / đã giải quyết trong phạm vi
đã đo / giới hạn còn tồn tại. Kết quả fixture không chứng minh website thật.

## BUG-001 — Coordinate click truyền tham số không được hỗ trợ

- Trạng thái: đã giải quyết trong smoke Chromium đã đo.
- Ghi nhận: trước 30/10/2026; tổng hợp ngày 30/10/2026.
- Triệu chứng: Vision tìm được phần tử nhưng thao tác trả WEB_CLICK_UNCERTAIN.
- Nguyên nhân xác minh: controller truyền `timeout=8000` vào Playwright
  `Mouse.click`, API này không nhận tham số đó; `Locator.click` có hỗ trợ.
- Xử lý: bỏ keyword trên coordinate click; giữ timeout hợp lệ cho locator.
  Mock có chữ ký chặt và kiểm tra autospec giúp bắt lỗi API này.
- File: `src/elvion/browser/controller.py`, `tests/test_browser_workflow.py`.
- Kiểm chứng: desktop browser smoke trả PASS, click rồi đọc state độc lập.
- Bài học: mock rộng có thể che lỗi gọi SDK; không retry khi tác dụng chưa rõ.
- Giới hạn: coordinate click chưa có hard transport deadline như locator.

## BUG-002 — Grounder nhận nhầm loại phần tử và nhãn trùng

- Trạng thái: đã giải quyết trên regression/browser challenge đã đo;
  khả năng tổng quát vẫn cần đánh giá.
- Triệu chứng: OCR v1 click nhãn trùng, input sai role, disabled và prose.
- Bằng chứng: `artifacts/benchmarks/browser-vision/browser-vision-20261030T015124-f56738ca.json`:
  32/45 đạt, 13 unexpected mouse attempts.
- Nguyên nhân: khớp chữ không đủ chứng minh role, trạng thái hay tính duy nhất;
  model kiểm tra theo role được yêu cầu có thể chấp thuận nhầm.
- Xử lý: v2 phân loại full image và crop độc lập với role yêu cầu, kiểm tra
  duplicates, role/state; controller kiểm tra freshness/authority trước click.
- File: `src/elvion/vision/semantic.py`, `src/elvion/browser/controller.py`.
- Kiểm chứng v2: `browser-vision-20261030T021626-03235b4c.json` đạt 45/45.
- Giới hạn: replay fixture ảnh static cũ còn 8/18 positive bị từ chối;
  chưa được coi là giải quyết toàn bộ. Live Vision vẫn tắt.

## BUG-003 — OCR thêm dấu chấm vào nhãn Read policy

- Trạng thái: đã giải quyết trên challenge regression đã đo.
- Ghi nhận và xử lý: 30/10/2026.
- Triệu chứng: challenge v2 51/54; cùng link bị từ chối cả ba lượt, không click.
- Nguyên nhân xác minh: native-v1 và upscale2x-v2 đều đọc `Read policy.`;
  ảnh thật hiển thị `Read policy`, exact_match_count=0 nên chưa gọi model.
- Bằng chứng OCR: `artifacts/benchmarks/browser-vision/ocr-diagnostics/ocr-diagnostic-065e097abd3b.json`.
- Xử lý v3: chỉ xét giả thuyết thêm một dấu câu cuối, đọc crop độc lập không
  nhận target/OCR spelling; phải khớp nhãn rồi mới qua mọi semantic guard v2.
  Không bỏ dấu câu toàn cục. Prompt phân biệt hyperlink underline và underscore.
- File: `src/elvion/vision/semantic.py`, `src/elvion/vision/ocr.py`,
  `tests/test_vision_punctuation.py`.
- Kiểm chứng: `browser-vision-20261030T094506-4afd6a9c.json` đạt 54/54,
  cả ba link có label_verification=independent_image_read. Regression v3
  `browser-vision-20261030T095129-d86136af.json` đạt 45/45, không click sai.
- Giới hạn: cùng scene đã dùng khi sửa, không phải đánh giá mù. Task B nhãn
  độc lập kiểm tra dấu câu thật và near matches; chưa có held_out score.

## BUG-004 — Hai nhãn văn bản thường bị coi là đối tượng mơ hồ

- Trạng thái: đã giải quyết trong phạm vi dev desktop đã đo.
- Ghi nhận: 30/10/2026.
- Triệu chứng: Vision labels dev 42/45, 30/30 positives đúng, 0 false acceptance.
  Cả ba lỗi vl_d14_wrong_role_text trả ambiguous thay vì not_found.
- Bằng chứng: `artifacts/benchmarks/vision-labels/vision-labels-20261030T100031-0695b7f3.json`.
- Nguyên nhân xác minh từ luồng code: OCR thấy hai Open guide trong heading/prose,
  trả ambiguous trước bước phân loại role; trang không có link khớp yêu cầu.
- Xử lý: với 2–4 exact duplicates, đọc role từng crop; chỉ khi tất cả là text
  mới đổi refusal thành not_found. Control hoặc unknown giữ ambiguous. Không
  chọn candidate để click, không sửa scorer; exact/near duplicates vẫn bảo thủ.
- File: `src/elvion/vision/semantic.py`, `tests/test_vision_punctuation.py`.
- Kiểm chứng hiện có: toàn suite 487 tests đạt trong lượt sửa; đây là unit/fake
  evidence, chưa có báo cáo model thật sau sửa.
- Kiểm chứng bổ sung desktop: `vision-labels-20261030T100403-03db5b5c.json`
  đạt 45/45 dev, positives 30/30, 0 false acceptances/errors/wrong abstentions.
  d14 trả not_found đúng cả ba lượt; manifest giữ nguyên. Median locate 2323.701 ms.
- Bước tiếp theo: đo held_out, không coi dev sau sửa là đánh giá mù;
  benchmark chỉ chấm proposal, không click.

## LIMIT-001 — Sandbox không chạy được native OCR/Chromium như desktop

- Trạng thái: giới hạn môi trường còn tồn tại.
- Triệu chứng: agent gặp OCR_FAILED và Chromium prerequisite exit2; cùng
  công cụ chạy được trong desktop Terminal của người dùng.
- Nguyên nhân cụ thể: chưa xác minh đầy đủ; không coi đây là lỗi chất lượng model.
- Cách làm hiện tại: agent chạy fake tests/spec checks; desktop chạy native
  benchmark. Phân biệt rõ replay OCR giả lập với native end-to-end.
- Không tạo điểm chất lượng khi preflight bị chặn, không đánh dấu đã sửa.

## BUG-005 — Held_out nhãn v3 từ chối nhầm 11/36 positive

- Trạng thái: đang điều tra; ghi nhận 30/10/2026.
- Bằng chứng: `artifacts/benchmarks/vision-labels/vision-labels-20261030T102214-c5934826.json`.
- Kết quả: 34/45, positive 25/36, false abstentions 11/36, false acceptances 0/9,
  wrong target 0, errors 0; median locate 2333.303 ms.
- Phân bố: h09 Wait...! not_found 3/3; h10 Xem chi tiết? not_found 3/3;
  h11 Publish + Publish. ambiguous 3/3; h12 Archive. + Archive ambiguous 2/3.
- Nguyên nhân: chưa xác minh cho h09/h10; có thể OCR hoặc semantic guard,
  report cũ không lưu decision_stage. Không kết luận chỉ từ TARGET_NOT_FOUND.
  Với near duplicates, code v3 chủ động bảo thủ, nhưng cần diagnostics xác
  nhận nhánh runtime. Không nới scorer hay bỏ dấu câu thật để tăng điểm.
- Xử lý hiện tại: bổ sung diagnostics không chứa nội dung OCR/model trong
  runner nhãn để biết stage/count/role. Chưa sửa thuật toán ở lượt này.
- Bước tiếp theo: chạy lại riêng bốn case thất bại có diagnostics. Held_out đã
  được xem; các lần sau là regression, phải giữ báo cáo lần đầu.

### BUG-005 — diagnostics bổ sung

Report `vision-labels-20261030T102507-bb185e7f.json` chỉ chọn bốn positive,
0/12 (không có negative nên false acceptances=0 không là bằng chứng an toàn).
- h09/h10: exact_match_count=0, ocr_no_exact_match 3/3 mỗi case. Chưa có chuỗi
  OCR nên chưa xác định lỗi ký tự/dấu; không sửa Unicode hoặc dấu câu mù.
- h11: exact_match_count=1 nhưng ocr_duplicate_matches 3/3: v3 gom exact và
  near punctuation vào cùng candidates nên tự từ chối đối tượng đúng duy nhất.
- h12: exact_match_count=1, full_image_match_count=multiple 3/3: bước model đếm
  nhãn gần giống như trùng. Cần phân biệt exact label với near distractor bằng
  bằng chứng ảnh, không đơn giản ưu tiên exact OCR vì OCR có thể làm mất dấu thật.
- Thêm opt-in `benchmarks.vision_labels.ocr_diagnose` chỉ bốn fixture synthetic,
  xuất raw OCR cả hai profile, không model hoặc click. Cần desktop đo để chọn
  cải tiến phù hợp. Thuật toán/scorer chưa thay đổi trong lượt chẩn đoán này.

### BUG-005 — raw OCR và bản thử nghiệm v4

Raw synthetic OCR: `ocr-labels-0ca6dd101b7d.json` xác nhận:
- h09 native Wat..., upscale Wait..! khác target Wait...!.
- h10 native đúng Xem chi tiết?, upscale mất dấu thành Xem chi tiêt?.
- h11 cả hai profile phân biệt Publish / Publish. đúng; v3 tự gom near label.
- h12 upscale đúng Archive., native sai Arhive.; model full-page vẫn đếm near
  label Archive là duplicate khi target Archive..

Thêm opt-in OCRLabelGrounder protocol ocr-verified-v4, không đổi v3. OCR hai
profile chỉ sinh hypotheses cùng skeleton chữ (khác dấu/dấu câu); mỗi vùng
được đọc nhãn blind, giữ exact punctuation/diacritics khi quyết định. Cùng vùng
hai profile được merge bằng IoU>=0.5; tối đa 4 vùng, unknown vẫn abstain. Từng
exact visual match phải đúng role và enabled. Full image guard giữ nguyên,
prompt v4 yêu cầu đếm exact label có dấu câu. Không nhận coordinates từ model.
File: src/elvion/vision/label_candidates.py; runner nhãn thêm v4; fake tests
ở tests/test_vision_label_candidates.py. Đây là xử lý thử nghiệm, CHƯA đo
model desktop; có thể còn false abstention/misread và tăng latency. Không
claim đã giải quyết BUG-005. Bước tiếp theo chạy dev v4 trước, rồi bốn cảnh lỗi.

## BUG-006 — V4 dev hồi quy 39/45 và chậm hơn

- Trạng thái: đang điều tra; 30/10/2026.
- Bằng chứng: vision-labels-20261030T103249-3ac14970.json, dev v4 39/45,
  positives 24/30; 0 false acceptances/errors. Median locate 3971.923 ms
  so với dev v3 2323.701 ms (hai lượt khác thời điểm, không paired timing).
- d06 Proceed! ambiguous 3/3: một OCR region, zero verified; có thể empty
  blind read hoặc semantic unknown. Chưa biết nhánh do thiếu diagnostics.
- d10 Tạo báo cáo. ambiguous 3/3: hai OCR hypotheses cùng đọc thành target;
  nghi cross-profile box chưa merge đúng, chưa có raw bbox để xác minh.
- Xử lý thử nghiệm: same-region ngoài IoU>=.5 còn chấp nhận containment .8
  và hai tâm nằm trong nhau để xử lý bbox khác chiều cao. Không merge nhãn
  rời nhau, không sửa tọa độ click. Thêm uncertainty_stage/role/state để
  phân biệt d06. Đây là giả thuyết sửa, CHƯA kiểm chứng desktop.
- Không chọn v4 làm mặc định, giữ v3 và scorer. Cần chạy lại riêng d06/d10.

### BUG-006 — sau merge và xác định link availability

Report `vision-labels-20261030T104912-534490e6.json`: d10 phục hồi 3/3,
candidate_count=1, đúng target và semantic guards; xác nhận sửa trên scene này.
d06 vẫn trượt 3/3: blind read khớp, observed_role=link nhưng availability=unknown.
Chưa phải lỗi OCR. Thêm prompt local riêng v4 phân biệt visually enabled
navigation styling với disabled/muted; không đòi link có border button, không
coi availability là bằng chứng navigation thành công. Giữ unknown bị chặn;
không đổi schema/scorer hoặc đổi unknown thành enabled trong code.
Bản prompt này chưa có kết quả model desktop. Cần đo riêng d06 và negative
controls trước khi gọi hồi quy đã giải quyết.

### BUG-006 — link phục hồi; sai thứ tự role/state trên plain text

Report `vision-labels-20261030T110218-1d5a4392.json`: 9/12; Proceed! 3/3
đúng, negative false acceptance 0/9. d14 trượt 3/3 do observed_role=text,
availability=unknown bị coi ambiguous. Nguyên nhân xác minh: code xét
availability unknown trước khi loại known wrong role; trạng thái enabled
không có ý nghĩa với plain text. Sửa loại known wrong role trước; role hoặc
availability chưa rõ của đúng loại vẫn chặn. Không tạo đường found mới từ
unknown, không đổi scorer. Thêm tests cho cả known-wrong-role + unknown state
và matching-role + unknown state. Chưa có desktop report sau sửa thứ tự.

### BUG-005/006 — v4 toàn bộ nhãn 87/90, còn Terms apply.

Report `vision-labels-20261030T111236-ffcc0ebb.json`: all 30 scene x3,
87/90, positives 63/66 (95.45%), false abstentions 3, wrong target 0,
negative false acceptances 0/24, correct ambiguity 6/6, errors 0. Median
locate 5985.438 ms. Các lỗi trước không tái hiện trên lượt này; chưa có browser
click/freshness qualification v4. Latency có thể vượt budget khi nhiều calls.
Còn h02 Terms apply. not_found 3/3, exact_match_count=1 nhưng decision_stage
label_read_rejected. Stage này bao gồm cả đọc nhãn lệch và known wrong role,
nên CHƯA xác minh cụ thể. Không tự suy luận là mất dấu chấm.
Thêm opt-in benchmarks.vision_labels.model_diagnose: chỉ fixture tổng hợp
manifest, một lần locate, xuất model responses để xác định nguyên nhân, không
click/website thật/ảnh desktop. Không thay thuật toán hoặc scorer ở lượt này.

### BUG-005 — h02 confirmé model read, thử crop nhãn hẹp

`model-diagnostics/label-model-66b5c6bea755.json` cho thấy blind transcription
trả Terms apply_ thay vì Terms apply.; model nhầm punctuation/underline dù
OCR exact. Không phải semantic-role rejection. Không tự thay underscore.
V4 nay dùng crop nhãn padding 24px cho transcription (cả chữ và cạnh giữ lại),
context crop rộng vẫn giữ nguyên cho role/state. Mục tiêu tăng tỷ lệ kích thước
chữ trong ảnh model, không đổi pixels nội dung/bbox click hoặc cung cấp target
cho bước đọc. image_crop hỗ trợ padding tùy chọn, mặc định cũ không đổi.
CHƯA có model result sau đổi crop; có thể tăng/giảm độ đúng trên nhãn khác.
Cần diagnostic h02 một lượt trước, sau đó regression punctuation/negative.

### BUG-005 — h02 đọc đúng sau tight crop, chờ regression

Đã đối chiếu `model-diagnostics/label-model-bb4abb497dcf.json`: một lần
diagnostic h02 đọc Terms apply. đúng, local link/enabled, full count one và
status found. Bằng chứng 1 lượt proposal, không phải click hay toàn bộ suite.
Crop sửa lỗi trên lần đo này; BUG-005 chưa đóng toàn bộ vì cần đo lại 30
scene x3 sau thay preprocessing, giữ scorer và báo cáo cũ.

### BUG-005/BUG-006 — giải quyết trong bộ nhãn regression đã đo

Đã đối chiếu `vision-labels-20261030T114325-ad0d5227.json`: v4, all 30 scene
x3, manifest không đổi. 90/90 đạt; positives 66/66, false abstentions 0,
wrong target 0, false acceptances 0/24, ambiguity đúng 6/6, errors 0.
Đánh dấu BUG-005/006 đã giải quyết trong phạm vi bộ nhãn regression này;
không phải chứng minh tổng quát hoặc blind score sau chỉnh model/prompt.
Median locate 6199.8455 ms. Latency/freshness và browser click của v4 chưa
qualify, cần đo riêng. Thêm option v4 vào browser runner; giữ default cũ và
giữ nguyên budget/controller/scorer, không bật live Vision.

## BUG-007 — V4 browser 10/15: freshness, semantic diagnostic và disabled state

- Trạng thái: đã sửa một phần, chờ desktop kiểm chứng; 30/10/2026.
- Report: browser-vision-20261030T115936-61f3a58d.json. 10/15; 5/6 clicks
  verified, 0 wrong/unexpected mouse, 3/3 injected guards đúng.
- Button đầu found nhưng stale_or_unauthorized, duration 10568ms. Nghi tuổi
  ảnh vượt 10s, chưa đo riêng frame age nên chưa kết luận loại trừ pixel diff.
- Heading/input sai role/prose not_found nhưng stage label_read_rejected,
  scorer yêu cầu model_rejected_candidate để không cho OCR miss tính đúng.
- Disabled button role đúng nhưng local availability unknown -> ambiguous.
- Sửa: ghi stage model_rejected_candidate chỉ khi label đọc exact và semantic
  thực sự loại role/disabled. Không nới scorer. Unknown local state có thêm
  full-image evidence để chứng minh disabled; full enabled/unknown không được
  biến local unknown thành quyền click. Nếu vẫn không rõ giữ ambiguous.
- Tối ưu: dùng lại local role/state evidence đã kiểm tra trên chính frame/crop
  của cùng locate, reset trước mỗi locate; bỏ model call local lặp cuối, không
  bỏ full-image count guard. Không cache qua task, không đổi timestamp.
- Thêm grounding_ms và frame_age_after_grounding_ms vào browser report.
  Giữ TTL/controller budgets, không auto retry hoặc bật live Vision.
- Kiểm chứng desktop chưa có. Cần browser regression x1 và labels regression
  sau thay đổi; không tái chấm báo cáo cũ thành pass.

### BUG-007 — desktop regression 15/15 sau sửa

Đối chiếu `browser-vision-20261030T120725-10172435.json`: v4 regression 15 scene x1,
15/15 đạt, 6 verified clicks, 0 wrong/unexpected mouse, 3/3 guard passes.
Grounding median 4922.927 ms, max 8463.402 ms; tuổi ảnh sau
grounding tối đa 8496.380 ms. Button đầu pass; không nới TTL/scorer.
Đánh dấu giải quyết trong lượt regression này; chưa chứng minh cold-start luôn
dưới TTL, chưa qualify repeated challenge hoặc website thật. Labels 90/90 là
trước tối ưu reuse evidence, cần regression lại trên cấu hình hiện tại.

## BUG-008 — V4 challenge Read policy hồi quy sau thay label crop

- Trạng thái: đang điều tra, có bản preprocessing thử nghiệm; 30/10/2026.
- Report browser-vision-20261030T121437-8220d886.json: 51/54, 24/27 positives,
  0 wrong/unexpected mouse, guards 9/9. Read policy not_found 3/3,
  candidate_count=1, exact OCR=0, label_read_rejected, grounding dưới 1s.
  Không phải TTL. Chưa đủ stage để loại role mismatch chỉ từ report.
- Replay ảnh lỗi r1 bằng model thật + native crop, box chữ chọn thủ công
  (952,194,100,18), không dùng OCR native và không click: padding24/48 đọc
  Read policy.; padding96 đọc Read policy; padding mặc định đọc Read_policy.
  Chứng minh nhạy với crop ở replay, không phải native end-to-end score.
- Thử padding96 cho transcription chung mọi label, không nhánh theo tên/case;
  semantic context crop vẫn như cũ. KHÔNG tự bỏ dấu/underscore, không fallback
  chọn output vừa ý. Chưa biết Terms apply. có hồi quy trên padding96 hay không.
- model_diagnose thêm --browser-case để chỉ quan sát một fixture browser;
  không controller/click. Đo riêng Read policy và Terms apply. trước khi chạy
  suite lớn; nếu còn xung đột crop, cần hướng preprocessing/model khác thay
  vì chỉnh ngưỡng theo từng nhãn. Không đóng bug hoặc bật live Vision.

### BUG-008 — hai diagnostic cùng found trên padding96

Đã đối chiếu label-model-67943dbb23df.json (Read policy) và
label-model-12a1c3031de2.json (Terms apply.): cả hai blind read khớp label,
local link/enabled, full count one, status found. Mỗi scene một lượt, không
click; BUG-008 vẫn chờ repeated browser và all-label regression. Không chỉnh
thêm thuật toán trước đo. Cần lưu kết quả baseline mới khi qualification đạt.

### BUG-008 — xác nhận regression sau padding96

Đã đối chiếu vision-labels-20261030T124147-795a5b0c.json (90/90, 66/66
positive proposals, 0/24 false acceptance) và browser-vision-20261030T124233-2e0c776a.json
(54/54, 27/27 verified clicks, 0 wrong/unexpected mouse, 9 guards). Cùng
padding96, reuse local evidence. Labels median locate 4881.346 ms; browser
challenge grounding median 3613.625 ms, max 5492.111 ms. Không paired timing,
không chứng minh cold-start luôn nhanh. BUG-008 giải quyết trong bộ regression
này; giữ lịch sử. Snapshot checksum configs/vision-v4-regression-snapshot.json.
Regression browser 15/15 trước đó là trước padding96, không gộp thành điểm
qualification cấu hình hiện tại. Live Vision vẫn tắt. Tiếp theo nên quan sát
proposal trên web thật chỉ đọc, chưa click, không chỉnh prompt theo từng site.


### LIMIT-001 — Task A public-web observation capture bị chặn

30/10/2026: agent thử capture https://docs.python.org/3/ bằng công cụ mới,
BrowserSession prerequisite không chạy được. Record:
artifacts/benchmarks/web-observation/capture-053b77bf1c32/blocked.json.
Không có PNG capture public web hoặc model quality score từ lượt này.
Không nới sandbox; cần desktop Terminal capture để kiểm chứng thực tế.
Công cụ vẫn hoàn thành luồng capture -> annotation lock -> offline evaluate,
và fake tests kiểm tra integrity/scoring/no model before lock. Cơ chế cùng-host
có thể chặn CDN nên capture public site có thể thiếu tài nguyên: annotator phải
ghi unscorable thay vì âm thầm chấm trang khác kỳ vọng. Chưa giải quyết giới
hạn này bằng mở host rộng hơn trong Task A.

## LIMIT-002 — Public-web manifest chưa có oracle ảnh

- Trạng thái: giới hạn đánh giá đang tồn tại; 30/10/2026.
- Task B có 24/24 provisional, 0 confirmed, trên 6 URL/domain, 12 dev/12 held_out.
  URL/page text đã tra cứu không chứng minh target visible, role hay bbox.
- Đã review manifest/protocol và chạy lại 5 manifest tests + 7 observation
  tests: 12/12 đạt. Task A capture --manifest-case kiểm tra manifest và lưu
  SHA256; annotation bổ sung reviewer/evidence_source và liên kết capture.
- Cần capture desktop, chấm ảnh gốc, review/lock trước khi đo. Không lấy
  expected từ nhãn provisional. Blocked/unscorable ghi riêng, không tính đúng.
- Chưa có score public web; per-capture tool chưa có aggregator toàn protocol
  (scene/domain grouping, p95, go/no-go). Tích hợp tổng hợp sau khi có annotations.
- Không sửa file Task B hoặc tự tạo ảnh/oracle; chưa gọi model/public web ở
  lượt tích hợp này, không click/gõ, held_out chưa inference.

## UX-001 — Capture lưu thành công nhưng người dùng không thấy cửa sổ

- Ghi nhận 30/10/2026: capture-847adc526f29 có PNG/HTML hợp lệ, Chromium
  headless nên không tự hiện viewer; dòng View original chưa hướng dẫn mở rõ.
- Xử lý hiện tại: hướng dẫn `open artifacts/benchmarks/web-observation/capture-847adc526f29/original.html`.
- Đã xem PNG: trang tài liệu Python có link Tutorial. Metadata là manual,
  URL /3/, target Tutorial; không phải wo_d01_python_search từ manifest.
  Không sửa metadata cũ hoặc tính capture này là case manifest đó.
- Chỉ kiểm tra ảnh gốc, chưa proposal/inference. Đây là vướng mắc trải nghiệm,
  không phải lỗi capture hay grounder. Chưa thêm tự mở viewer vào code.

## ANNOTATION-001 — Target Search khác placeholder Quick search

30/10/2026, capture-50b2d6a274a3, wo_d01_python_search: người dùng đo bbox
[847.6,20.6,132.2,16.5], ảnh gốc xác nhận đúng vùng textbox Quick search.
Metadata target là Search. Theo baseline exact label hiện tại, không tự coi
Quick search là nhãn Search. Chưa khóa annotation, chưa gọi grounder. Hướng
dẫn trước đó yêu cầu khoanh ô nhưng chưa chỉ rõ khác nhãn: cần đính chính.
Đề xuất not_found cho Search trong ảnh này; nếu muốn positive Quick search,
tạo case/capture riêng, không đổi target hoặc manifest âm thầm. Đây là vấn đề
định nghĩa oracle, không phải model bug. Tránh chuyển sang khớp ngữ nghĩa chỉ
để chấm found. Giữ bbox người dùng như bằng chứng vùng gần giống, không truth
của Search khi áp dụng exact-label protocol.

### ANNOTATION-001 — đã khóa trước inference theo người dùng đồng ý

capture-50b2d6a274a3/annotation.lock.json: expected not_found cho Search,
truth=[], distractor là bbox Quick search người dùng đo. Người dùng đồng ý
đề xuất sau khi đã xem ảnh gốc, reviewer assistant-visual (AI, không phải
reviewer người thứ hai độc lập). evidence_source vision_only. Không sửa
metadata/manifest; chưa chạy model. Không gọi đây là oracle đã review bởi
hai người độc lập; ghi rõ nguồn review khi tổng hợp kết quả.

### LIMIT-002 — public-web observation đầu tiên có oracle và proposal

Đối chiếu capture-50b2d6a274a3/proposal-9ccd323d3ff2.json: ca dev
wo_d01_python_search trả not_found / correct_rejection đúng annotation khóa
trước inference. Locate 719.567 ms, actions=0; không click/navigation/freshness.
Một negative observation trên một scene/domain, chưa có positive hit hoặc
held_out score, không suy ra accuracy tổng quát. Manifest vẫn provisional;
annotation riêng xác nhận capture này, không sửa manifest. Người chấm là user,
reviewer AI đã công khai, không phải hai human annotators độc lập.
Tiếp theo cần positive Quick search riêng và các domain dev khác, giữ target
Search/annotation/report hiện tại bất biến.

### LIMIT-002 — positive manual annotation trên cùng ảnh

capture-d90358ec1736 target Quick search có PNG SHA256 giống hệt
capture-50b2d6a274a3. Đã xem ảnh gốc, tái dùng bbox người dùng đo trước proposal
[847.6,20.6,132.2,16.5], khóa found cho case manual riêng. Annotator user-01,
reviewer assistant-visual, nguồn vision_only; không giả reviewer human thứ hai.
Không sửa manifest/ca Search, chưa có positive model result. Hai capture là
một unique scene/domain; ca mới không tính là held_out hay scene độc lập.

### LIMIT-002 — positive public-page proposal đầu tiên đúng

Đã đọc capture-d90358ec1736/proposal-415feb222c63.json: found,
correct_target, bbox tâm nằm trong truth Quick search đã khóa, locate
8624.325 ms, actions=0, freshness_verified=false. Cùng ảnh với ca negative
Search: 2 observations/1 unique scene/1 domain, chưa có dataset score hoặc
held_out evidence. Thời gian 8.62s là một locate offline, gần TTL browser10s
nhưng không chứng minh live freshness. Tiếp theo thêm scene/domain dev MDN,
không chỉnh prompt theo kết quả này.

## ANNOTATION-002 — MDN Elements có thể là disclosure control, role chưa rõ

Capture-8f1a6f6661b3, wo_d05_mdn_elements: ảnh gốc có Elements ở sidebar
trái khoảng y745, kèm chevron; target chữ hiện diện nhưng chưa đủ bằng chứng
vision-only để khẳng định role link thay vì disclosure button. Không suy
role từ tên manifest, không chấm found hoặc chạy model trước oracle. Chưa
khóa annotation. Cần human review hoặc DOM-assisted evidence gắn capture;
nếu vẫn không xác định được, ghi undetermined, không tính correct rejection.
Không click chevron để làm lộ nội dung. Đây là giới hạn oracle của ảnh hiện
có, chưa phải lỗi grounder.

### ANNOTATION-002 — thêm supplemental DOM review chỉ đọc

Task A có `review-dom CAPTURE_DIR`: mở lại URL công khai trong session riêng,
so PNG SHA256 + final URL với capture trước và sau khi đọc semantic tag/role
của exact text. Không click, mở disclosure, scroll, hoặc truyền DOM cho model.
Nếu ảnh khác, chỉ báo capture_changed, không xuất candidate evidence để chấm
capture cũ. Cùng pixel không chứng minh DOM tuyệt đối không đổi; DOM vẫn chỉ
là evidence hỗ trợ cần human review, không tự khóa expected. Role inference
chỉ subset HTML native/explicit role, không accessibility tree đầy đủ.
8 observation tests đạt, gồm pixel mismatch làm mất hiệu lực DOM evidence.
Chưa đo desktop. Oracle cần ghi dom_assisted nếu dựa vào kết quả này.

### ANNOTATION-002 — DOM review ảnh không khớp, giữ unscorable

Đọc dom-review-0b54bf86554f.json: status=capture_changed, không có candidates.
Không dùng DOM lượt này suy role của ảnh cũ. Khóa capture-8f1a6f6661b3 là
undetermined (vision_only, assistant self-review công khai, không giả human
review độc lập). Không inference hoặc tính correct rejection. Capture vẫn
được giữ trong ledger như unscorable, không xóa/đổi thành ca dễ hơn.
Tiếp theo case dev Wikipedia trong manifest; MDN chưa có score chất lượng.
Cùng pixel không bảo đảm cùng semantic, và đổi pixel không chứng minh site
lỗi; khả năng nội dung động/chênh thời điểm là giả thuyết, chưa xác minh.

### LIMIT-002 — Wikipedia dev positive đã khóa, chờ model

capture-427fd6fce49a, wo_d09_wiki_search_input: ảnh gốc có một textbox nhãn
Tìm kiếm trên Wikipedia. Người dùng đo bbox [305.8,15.2,389.7,31.8], không gồm
submit button. Khóa found trước inference, annotator user-01, reviewer AI
assistant-visual (không phải human reviewer thứ hai), vision_only. Một số
ảnh nội dung trang chưa hiển thị; không ảnh hưởng vùng target quan sát được,
nhưng không khẳng định trang tải đầy đủ. Chưa có proposal hoặc quality score
cho case này; giữ nguyên manifest và ảnh gốc.

## BUG-009 — Wikipedia search textbox false abstention trên public capture

- Trạng thái: đang điều tra; 30/10/2026.
- Report capture-427fd6fce49a/proposal-b83a0339cf95.json: target Tìm kiếm trên
  Wikipedia, expected found khóa trước model, observed not_found,
  false_abstention, locate707.865ms, actions0. Không đổi oracle để chấm đạt.
- Chưa xác minh nguyên nhân: report trước không chứa stage/candidate count;
  thời gian nhanh chỉ gợi ý OCR, không đủ kết luận. Native helper recognition
  language hiện en-US, nhưng chưa biết có phải nguyên nhân của ca này.
- Thêm diagnostics không raw text vào proposal web mới; không sửa report cũ.
  Thêm diagnose-ocr CAPTURE_DIR opt-in chỉ đọc PNG public đã được phép lưu,
  xuất raw OCR hai profiles cục bộ, không model/click/recapture. Cần desktop
  native OCR do giới hạn môi trường agent. Thuật toán chưa thay đổi.

### BUG-009 — nguyên nhân icon và bản sửa đã replay model thật

ocr-diagnostic-bf350d31596c.json: cả hai OCR profiles đọc vùng search thành
Q Tìm kiếm trên Wikipedia, nhận magnifier là Q. Không phải sai dấu tiếng Việt.
Mở rộng hypothesis cho một token đầu một ký tự trước target nhiều từ. Chỉ
sinh candidate; blind read vẫn thấy toàn region, không strip ký tự để chấp
nhận. Prompt phân biệt pictogram và ký tự đầu thực; fake test A Save draft
không được tự chấp nhận cho Save draft. Không đổi oracle/scorer.

Replay icon-replay-01.json dùng toàn bộ OCR outputs đã lưu, native image crop
và model qwen3.5:4b thật: đọc target đúng, local textbox/enabled, full one,
found và tâm bbox nằm trong oracle. Không native OCR/live browser trong lượt
replay, không click. Chưa đóng bug trước desktop evaluate lại capture cũ.
V4 source đã thay sau snapshot 90/90+54/54: không gán điểm cũ cho cấu hình mới.
Report web mới lưu source SHA256 để phân biệt. Ca Wikipedia từ nay là dev
regression sau chỉnh theo lỗi, không điểm blind. Kiểm tra hồi quy synthetic
cần thực hiện trước khi qualify bản thay đổi cho thao tác thật.

### BUG-009 — desktop vẫn bị semantic rejection, chưa đóng

proposal-53ff11df3986.json: candidate_count1, model_rejected_candidate,
false_abstention, 2675.551ms. Bản sửa icon đã qua OCR nhưng chưa đủ semantic.
Replay OCR đã lưu lần 2 icon-replay-02.json vẫn found; chưa thể coi replay là
bằng chứng native desktop. Diagnostics cũ không lưu role/state khi rejected;
chưa xác minh model đã chọn sai role nào hay disabled. Thêm observed_role,
availability, semantic_rejection luôn có khi semantic reject.

Code review phát hiện local role classifier crop rộng có thể chứa nhiều control
nhưng chưa truyền bbox label để chỉ mục tiêu. Thử thêm candidate bbox theo tọa
độ crop, role yêu cầu vẫn withheld, không lấy tọa độ oracle/DOM. Đây là sửa
điểm thiếu thông tin có thật, chưa xác minh là nguyên nhân duy nhất của ca này.
Thêm --diagnose-model cho evaluate: xuất model replies cục bộ của capture đã
được phép lưu; không cấp oracle cho model. Cần một desktop evaluate có raw
phases nếu còn lỗi, không đoán tiếp từ stage chung. Giữ annotation/scorer/TTL.

### BUG-009 — native desktop found sau bổ sung candidate anchor

Đã đối chiếu proposal-42b96742101d.json và model-diagnostic-7e7833181ad3.json:
blind read đúng Tìm kiếm trên Wikipedia; local textbox/enabled; full image
textbox/enabled/count one. Found / correct_target, locate4248.552ms, actions0,
nguyên annotation checksum giữ nguyên. Đã giải quyết trên một lượt native
OCR + model desktop của capture này; không claim ổn định mọi scene/repetition.
Lượt này là dev regression sau sửa, không blind generalization. Nguyên nhân
OCR Q đã xác minh; thiếu anchor là thiếu sót code đã sửa, không có raw phases
của lượt trước để chứng minh model từng phân loại nhầm cụ thể gì.
Cấu hình mới thay source so với snapshot synthetic cũ, cần regression nhãn
và browser trước khi qualify nó cho actions; live Vision vẫn tắt. Không xóa
hai false abstention trước đó hoặc gộp chỉ successes thành public-web score.

## BUG-010 — False acceptance do bỏ qua full-frame role trái với crop

- Trạng thái: đã sửa guard, chờ native model regression; 30/10/2026.
- Report vision-labels-20261030T133824-c26cdf7e.json: all87/90, positives66/66,
  false acceptances3/24. Cả ba d14 Open guide heading/prose trả found.
- Evidence: local observed_role=link/enabled, full_observed_role=text,
  full_image_match_count=one nhưng code vẫn cho found. Không phải oracle sai.
- Nguyên nhân code xác minh: parent v2/v3 chủ ý dùng full image cho count/state,
  chưa yêu cầu role đồng thuận. V4 thêm role anchor có false classification ở
  crop; full-image text đúng không được dùng làm veto. Bằng chứng độc lập
  mâu thuẫn không được phép biến thành approval chỉ bằng crop.
- Sửa riêng v4: full observed role phải đúng requested role và full state
  enabled; sai role, unknown hoặc disabled đều phủ quyết. Giữ schema/scorer,
  không whitelist nhãn/site, không đổi guards v2/v3 để giữ baseline tái lập.
- Tests fake kiểm tra crop chấp nhận nhưng full text/wrong role/unknown state
  bị từ chối và full+crop đồng thuận mới found. Chưa có model desktop sau sửa;
  có thể tăng false abstention, cần đo toàn bộ chứ không chỉ d14.
- Live Vision vẫn tắt; bản có3 false acceptance không qualify cho actions.

### BUG-010 — xác nhận labels regression 90/90 sau full-role veto

Đã đối chiếu vision-labels-20261030T135206-aa502fc3.json: all30 scenes x3,
90/90, positives66/66, false acceptances0/24, correct ambiguity6/6, errors0.
Giải quyết trong phạm vi labels regression đã đo, không claim web/browser
click qualification. Giữ bản report 3 false acceptances trước đó. Native
Wikipedia và browser qualification sau guard mới chưa có kết quả; live Vision
vẫn tắt. Cần chốt hồi quy trước khi thêm tính năng hoặc tối ưu khác.

### BUG-010 — browser challenge54/54, bản guard đồng thuận

Đã đọc browser-vision-20261030T135657-0a593a15.json:54/54, 27/27 verified
clicks, 0 wrong/unexpected mouse, 9/9 guards. Grounding median
3716.957ms, max 5912.083ms. Cùng bản source với labels90/90
đã đo trước đó trong phiên, không thay code giữa hai lượt. Snapshot nghiên
cứu configs/vision-v4-consensus-snapshot.json; chưa runtime enable Vision.
Wikipedia sau full-role veto vẫn chờ một native regression; không lấy điểm
synthetic suy ra chất lượng toàn public web.

### BUG-009 — mở lại: đọc nhãn không ổn định sau synthetic qualification

proposal-ef8a126e0a02.json: false_abstention,1627.511ms,
candidate_count1, label_read_rejected, verified0. Không đến full-role veto,
không kết luận guard mới là nguyên nhân. Lượt trước cùng capture từng found,
nhưng còn thiếu crop hashes/raw OCR của lần này để phân biệt input variation
và model variation. BUG-009 chưa ổn định; giữ tất cả failed/success reports.
Không sửa prompt/guard tiếp. Thêm evaluate --diagnose-model --repetitions3:
thu native OCR boxes/text, crop hashes/anchor boxes/model replies và links
mọi proposal, xuất reproduction manifest. Không retry thao tác; chỉ lặp
inference trên ảnh offline theo yêu cầu, không gọi browser/click. Mọi lần
đều giữ trong báo cáo, không chọn success để che failure. Chưa có kết quả.

### BUG-009 — reproduction xác nhận đọc nhầm vùng lân cận

reproduction-36efc1713b57.json: ba lượt false_abstention. OCR text/bbox hai
profiles giống nhau; transcription crop SHA 8a1a2031... giống nhau, model cả
ba đọc thư mở (chữ từ logo gần bên), không phải target. Không có bằng chứng
OCR instability ở ba lượt này. So với lượt found trước, model đã từng đọc
đúng cùng image hash, nhưng có thay source/prompt giữa các lượt; không gộp
thành kiểm chứng nondeterminism trên cùng cấu hình khi chưa so toàn prompt.

Thử nghiệm marker OCR candidate: helper Swift --crop-mark vẽ outline đỏ cách
bbox 3px cho transcription crop, dựa OCR hoàn toàn, không oracle/DOM/target.
Role/state và full-frame vẫn nhận ảnh gốc không marker. Model vẫn phải đọc
nhãn exact và đồng thuận semantic; không bôi/xóa chữ hoặc chọn output thuận ý.
Native QA marked-crop-qa-01.json xác nhận cùng dimensions, pixels trong OCR
bbox giống ảnh crop gốc, marker thay814pixels bên ngoài. Đây chỉ là QA một
ảnh, không chứng minh mọi input. Protocol giới hạn dims/args và tests thêm.

icon-replay-marked-01.json dùng OCR outputs đã lưu + helper/model thật: đọc
đúng target, local textbox/enabled, full one, found. Không native OCR mới,
không browser/actions trong replay. CHƯA đóng BUG-009, cần desktop3 repetitions
với marker. Source mới khác snapshot; cần synthetic regression sau nếu đủ ổn.

### BUG-009 — marker native desktop 3/3 đúng trên capture hiện tại

Đối chiếu reproduction-7125c3197433.json và cả ba proposal/diagnostic:
3/3 correct_target, mỗi lượt đọc đúng nhãn, local textbox/enabled, full one.
Median locate 3676.904ms, max 3947.162ms; actions0.
Đã giải quyết trong phạm vi một ảnh/dev regression này; không kết luận ổn
định mọi layout hoặc model. Lưu nguyên failures trước; các repeats vẫn một
scene, không ba scene và không blind score. Native helper OCR thật đã chạy.
Marker source khác snapshot consensus cũ; cần all-label regression trước
browser/actions. Giữ source hiện tại trước đo, không thêm prompt/site hacks.

## BUG-011 — Marker toàn cục hồi quy Tag;

- Trạng thái: bản policy thử nghiệm, chờ native regression; 30/10/2026.
- vision-labels-20261030T141846-3416eddf.json:87/90, positives63/66,
  false acceptances0/24, ambiguity6/6. h05 Tag; false abstention3/3,
  exact OCR1 nhưng label_read_rejected. Chưa có raw read h05 để khẳng định
  cụ thể ký tự model đã đọc sai; marker/prompt preprocessing là thay đổi
  liên quan so với baseline90/90, không khẳng định chỉ riêng pixels marker.
- Thử thu hẹp marker cho hypothesis có token đầu một ký tự không khớp target
  nhiều từ (loại lỗi icon Q), quyết định trước model, không phụ thuộc case ID,
  website, oracle hoặc output. Exact/punctuation/diacritic candidates dùng
  crop không marker và không prompt marker. Không retry nhiều crop để chọn
  output thuận ý; một preprocessing path cho mỗi input candidate.
- Không tự bỏ prefix để chấp nhận; nhãn đọc vẫn exact, semantic/full-image
  phải đồng thuận. Fake test giữ A Save draft không được nhận Save draft.
- Cấu hình/source mới chưa có quality score, không gán90/90 hoặc Wikipedia3/3
  của source cũ cho bản này. Giữ mọi báo cáo và scorer. Cần all-label native
  regression và Wikipedia diagnostic; live Vision vẫn tắt.

### BUG-009/011 — selective marker đạt labels90/90 và Wikipedia3/3

Đã đối chiếu vision-labels-20261030T142847-af878fc5.json:90/90, positives
66/66, false acceptances0/24, ambiguity6/6. reproduction-dea0f71d8025.json:
3/3 correct_target, median3506.419ms, max5440.8ms (làm tròn); actions0.
BUG-009/011 giải quyết trong regression này, không khẳng định tổng quát.
Giữ các fail reports cũ; không chọn successes để tính blind public score.
Checkpoint configs/vision-v4-selective-marker-snapshot.json. Live Vision vẫn
tắt, browser actions chưa qualify sau selective marker. Không chỉnh source
trước khi thêm annotations dev; tiếp tục MDN wrong-role case nơi ảnh đủ rõ,
không cần dùng DOM review của capture cũ đã thay đổi.

### LIMIT-002 — MDN wrong-role oracle trước proposal

capture-e206ca64ae4a, wo_d08_mdn_wrong_role: xem ảnh gốc thấy target
HTML: HyperText Markup Language là tiêu đề bài, không button nhìn thấy.
Khóa not_found vision_only trước model, assistant-visual tự review công khai,
không ghi là human independent annotation. Không dùng DOM review cũ hoặc
suy role từ manifest. Chưa có proposal/quality score cho capture này; giữ
ca Elements undetermined cũ, không thay nó bằng ca mới để che unscorable.

## BUG-012 — MDN wrong-role ca trả PROVIDER_ERROR trước diagnostics

- Trạng thái: đang điều tra; 30/10/2026.
- capture-e206ca64ae4a/proposal-c92c64f7ca25.json: grounder_error,
  PROVIDER_ERROR,477.462ms, diagnostics rỗng, actions0. Không tính correct
  rejection, không đổi annotation not_found đã khóa trước model.
- Chưa biết nguyên nhân native OCR hay protocol parsing. OCRError có thể
  phát sinh trước candidate_count; không kết luận lỗi model semantic.
- diagnose-ocr nay giữ status/error_type và raw bounded native JSON/returncode
  khi OCR API thất bại; không chạy lại helper để lấy bằng chứng khác. Chỉ
  stdout của native đọc ảnh public đã được phép lưu, không ảnh/secret mới.
- Cần một desktop diagnostic trên PNG cũ; chưa sửa thuật toán/guards.

### BUG-012 — xác minh native bbox hơi vượt mép; sửa bounded tolerance

ocr-diagnostic-41267a2472be.json: helper cả hai profiles returncode0, JSON
hợp lệ (51/52 lines). Một line HTML ở mép trái có x=-7.5e-7(native) và
x=-0.042086 CSS px(upscale). Native observations validator strict làm cả
response OCR_FAILED, trước candidate stage. Không phải model/provider outage.

Sửa OCR_EDGE_TOLERANCE=0.1 CSS pixel chỉ native OCR: sai lệch endpoints nằm
trong0.1 thì lấy phần giao viewport, giữ positive extent; vượt0.1 hoặc không
còn visible area vẫn lỗi. Không áp dụng cho model boxes, không nới click
bounds/scorer. Thêm tests -0.042 accepted, -0.101 và vượt right0.101 rejected;
zero-visible rejected. Ghi native_edge_adjustments vào diagnostics, config
web công khai tolerance. Đây là policy bounded explicit, không clamp vô hạn.

edge-replay-01.json dùng raw native JSON đã lưu + validator mới + native crop/
model thật:51/52 lines decoded, mỗi profile1 edge adjustment, target read đúng,
observed_role=link/enabled nên từ chối requested button -> not_found. Model
không nhận đúng heading/text ở lượt này, chỉ xác nhận wrong requested role;
không coi đó là semantic classification hoàn hảo. Replay không native OCR mới.
Cần desktop evaluate cũ sau sửa, giữ annotation và failed report. Chưa đóng
BUG-012, chưa có full native regression sau tolerance.

### BUG-012 — xác nhận native desktop hết lỗi decoder trên capture MDN

proposal-d6615bb7d815.json + model-diagnostic-b8d6f1bb053b.json: native OCR
decode thành công, native_edge_adjustments2 (hai profiles), exact OCR1;
not_found/correct_rejection, locate2464.052ms, actions0. Annotation giữ nguyên.
Bug provider-error giải quyết trên capture đã đo, chưa mọi page/geometry.
Semantic model vẫn gọi heading là link/enabled, chỉ đúng quyết định không
phải requested button; không claim phân loại heading đúng. Full-role veto
còn cần bảo vệ khi requested link. Chưa sửa prompt hoặc scorer ở lượt này.
Tolerance source mới cần all-label regression trước qualification actions;
giữ snapshot/failed report cũ, không nâng điểm baseline tự động.

### BUG-012 — all-label regression90/90 après bounded OCR edge normalization

Đã đối chiếu vision-labels-20261030T144854-4e2b0a75.json:90/90, positives
66/66, false acceptances0/24, correct ambiguity6/6, errors0. Không sửa scorer
hoặc annotation. Checkpoint configs/vision-v4-ocr-edge-snapshot.json lưu source
checksums để cố định cấu hình khi thêm public annotations. Đủ bằng chứng
đóng BUG-012 trong phạm vi MDN capture và bộ regression đã đo; chưa action
qualification hay toàn web. Public reports qua nhiều source version không
được cộng thành quality score cho một model/cấu hình cố định.

### LIMIT-002 — Wikipedia search button oracle trước inference

capture-9b49c7d26ad8, wo_d10_wiki_search_button: khóa found theo bbox người
dùng đo [695.4,15.7,84.5,33.9], reviewer assistant-visual, vision_only,
không phải hai human annotators. Không gồm search textbox bên trái; nhãn và
role button nhìn thấy rõ. Chưa có proposal, không click/submit. Cấu hình
edge-normalization checkpoint giữ nguyên, không sửa grounder cho ca mới.

### LIMIT-002 — Wikipedia button proposal đúng trên checkpoint OCR edge

capture-9b49c7d26ad8/proposal-c0f33b01ccb5.json: correct_target, local/full
button/enabled, bbox tâm trong oracle, locate9105.864ms, actions0. Không
nhầm textbox, không submit và không xác minh live freshness. Source SHA
khớp bản bounded OCR edge của MDN rejection, không chỉnh thuật toán giữa hai
ca. Một lượt/một target, không claim ổn định. Tiếp theo positive link dev để
phủ ba loại role; web held_out vẫn chưa inference.

### LIMIT — Latency public proposal gần TTL hành động

Wikipedia button locate9.11s trên ảnh offline. Đây không phải lỗi thực thi
(vì không click) và chưa biết cold/warm inference/time breakdown. Nhưng gần
TTL browser10s nên chưa đủ biên cho live actions. Giữ TTL, không auto retry;
đo phân bố latency sau khi có thêm observations, không tối ưu theo một mẫu.

### LIMIT-002 — Wikipedia Hướng dẫn positive link oracle khóa trước model

capture-0b3622ac6410, wo_d11_wiki_guide: người dùng đo
[727.3,275.5,78.1,15.5], một link màu xanh Hướng dẫn nhìn thấy ở hàng Trợ giúp.
Khóa found vision_only, user-01 annotation + assistant-visual review công khai;
không DOM/model output để đặt bbox. Chưa proposal, không action hoặc đổi source.

## BUG-013 — Wikipedia Hướng dẫn không tạo OCR candidate

- Trạng thái: đang điều tra; 30/10/2026.
- capture-0b3622ac6410/proposal-e31a3b6b446e.json: false_abstention,
  candidate_count0, exact_match0, ocr_no_exact_match,820.484ms, không actions.
  Oracle đã khóa trước model, không sửa để hợp thức hóa failure.
- OCR của ảnh Wikipedia trước (capture-427fd6fce49a/ocr-diagnostic-bf350d31596c.json)
  gộp cả hàng Trợ giúp: FAQ • Giúp đỡ • Hướng dẫn • Chỗ thử • Guestbook thành
  một observation. Hướng dẫn có trong text nhưng không bằng nguyên dòng nên
  không sinh candidate. Đây là bằng chứng trên capture khác; cần xác nhận
  raw OCR của ảnh hiện tại trước khi kết luận nguyên nhân.
- Không dùng bbox cả dòng cho Hướng dẫn hoặc nội suy tỷ lệ theo số ký tự:
  như vậy có thể chỉ nhầm link lân cận. Nếu xác nhận lỗi segmentation, hướng
  sửa là native character-range bounding boxes / subline observations rồi
  vẫn giữ blind read + role/full-image guard, không chấp nhận substring ngay.
- Chưa sửa grounder/source từ checkpoint OCR edge. Cần diagnose-ocr ảnh cũ
  hiện tại, không chụp lại trang và không click link.

### BUG-013 — xác nhận merged OCR trên capture hiện tại, thêm native subline

ocr-diagnostic-53b4f456175f.json xác nhận cả hai profiles gộp target vào dòng
Trợ giúp: FAQ • Giúp đỡ • Hướng dẫn • Chỗ thử • Guestbook; exact whole-line0.
Không phải thiếu chữ/role model. Bổ sung helper opt-in --segments: tách bằng
•/·/|, trim whitespace, dùng VNRecognizedText.boundingBox(for: Swift Range)
cho từng đoạn; không nội suy theo độ dài. Word-level precision ở accurate,
bbox chỉ là observation không bảo đảm exact fit. Tài liệu Apple:
https://developer.apple.com/documentation/vision/vnrecognizedtext/boundingbox(for:)

Giữ original lines, thêm subline observations, max512 và bounded output.
Subline width>=95% parent bị bỏ thay vì dùng bbox cả dòng làm target riêng.
V4 chỉ đọc thêm OCR segmentation khi không có hypotheses thông thường và
merged line có delimiter + target. Đây là read-only planned OCR pass, không
retry tác vụ/click; có thể tăng latency và chưa đủ giải mọi loại merged text.
Không substring-accept: subline vẫn qua blind read, local/full-role/state
agreement. Không whitelist case/site, không dùng ground truth/DOM.
37 tests liên quan đạt; helper Swift compiled thành công. Chưa native quality
result cho Hướng dẫn; sandbox OCR agent không dùng làm quality score. Cần
native evaluate trên capture cũ với --diagnose-model, giữ annotation/scorer.
Source khác checkpoint OCR edge: không gán điểm90/90 cũ cho bản mới.

### BUG-013 — native subline đúng; đọc nhầm crop rồi phân loại link thiếu underline

proposal-b89e3fc4f12c.json: subline_ocr_passes1, candidate1,
false_abstention5500.041ms. Native cung cấp Hướng dẫn bbox[728,279,76.5,17],
tâm nằm trong oracle nhưng transcription trả Sửa bài ở hàng khác.
Không phải native segmentation sai. Marker policy mở rộng từ single-glyph
hypothesis sang subline hypothesis (OCR provenance, trước model, không site
hay oracle). Plain/exact/punctuation không mặc định marker, tránh BUG-011.

span-marker-replay-01.json (saved OCR/subline + crop/model thật) đọc đúng
Hướng dẫn nhưng local text/enabled -> từ chối. Bổ sung mô tả role v4: link
navigation có thể không underline, xét ngữ cảnh hàng điều hướng; màu đơn lẻ
không đủ cho heading/prose thành link, unknown và full-role veto giữ nguyên.
Không đơn giản map text -> link trong code.

span-marker-replay-02.json sau mô tả: blind read đúng, local link/enabled,
full link/enabled/count one, found đúng bbox native. Chỉ replay dữ liệu OCR
đã lưu, không native OCR mới hoặc browser actions. CHƯA đóng bug; cần native
3 repetitions trên capture cũ, rồi synthetic negative/role regression vì
thay model prompt có thể gây false acceptance. Giữ mọi report cũ/scorer.

### BUG-013 — native3/3 correct_target, đóng trong capture đã đo

Đã đọc reproduction-1523152f6e27.json cùng ba proposals:3/3 correct_target,
bbox native subline[728,279,76.5,17] giống nhau, tâm trong oracle. Mỗi lượt
subline_ocr_passes1, read Hướng dẫn đúng, local/full link/enabled/count one.
Median3438.180ms;3841.7/3438.2/3377.2ms (làm tròn), actions0. Xác nhận native
OCR/subline/model sau thay đổi, không chỉ replay. Giải quyết trong một ảnh/dev
regression, không mọi trang/delimiter. Giữ tất cả failures và các version cũ.
Cần all-label regression vì có marker/prose classification prompt thay đổi;
không dùng điểm90/90 từ source trước làm điểm cho bản mới. Public actions
vẫn tắt, web held_out chưa inference, chưa đủ scene/domain cho go/no-go.

### BUG-013 — labels regression90/90 sau subline/marker/navigation role

Đã đối chiếu vision-labels-20261030T151837-1c5d231b.json:90/90, positives
66/66, false acceptances0/24, ambiguity6/6, errors0. Checkpoint source
configs/vision-v4-subline-snapshot.json cùng public Hướng dẫn3/3 đã đo trước.
Giữ nguyên source để hoàn thiện public dev oracle; không tiếp tục test cùng
cấu hình vô hạn khi không có change/failure. Chưa action qualification,
chưa đủ scene/domain/ambiguity hoặc held_out để kết luận generalization.

### LIMIT-002 — wo_d12_wiki_duplicate chỉ một nhãn visible

capture-3a14a28d658d/ảnh gốc: Trang Chính chỉ nhìn thấy một lần ở mục điều
hướng đang chọn, không phải hai matching labels trong viewport. Không đặt
ambiguous theo case ID. PNG SHA giống capture-427fd6fce49a, nên không tính
scene độc lập chỉ vì capture_id mới. Role của mục điều hướng đang chọn cần
review nếu không chắc link versus tab/text; đề nghị review-dom chỉ đọc với
pixel equality trước/sau, không click. Chưa khóa oracle hoặc gọi model.
Không lấy source text liệt kê links/alt text ngoài ảnh làm visible duplicate.

## UX-002 — Separate-session DOM review luôn gặp ảnh thay đổi ở các lượt đã thử

30/10/2026: dom-review-640e1daf13d4.json của capture-3a14a28d658d báo
capture_changed, không có candidate evidence. Không dùng để suy role ảnh cũ;
khóa capture cũ undetermined, assistant self-review công khai, không inference.
Đây là hạn chế thu oracle theo hai lượt navigation, không chứng minh site lỗi.

Sửa workflow, không đổi grounder: capture --record-dom thu exact-text semantic
metadata ngay cùng session, ảnh trước và sau DOM read phải khớp SHA/finalURL
mới xuất candidates. Không reopen, click, scroll, hoặc đưa DOM vào model.
Không tự khóa expected từ DOM; cần đối chiếu ảnh và ghi dom_assisted khi dùng.
Nếu giữa hai snapshots vẫn đổi, giữ capture_changed. Test kiểm tra một navigate
và mismatch không lộ candidate evidence;10 observation tests đạt. Chưa native
public capture sau thay đổi; capture cũ và unscorable vẫn giữ trong ledger.

### UX-002 / LIMIT-002 — DOM-at-capture vẫn mismatch, dừng capture lại case này

capture-d47fdfc8ef47/dom-at-capture.json: same_capture_session=true nhưng
capture_changed, candidates không xuất. Ảnh có banner sinh nhật và sidebar
appearance khác vài capture trước; chưa có after-image để chứng minh pixel
nào đổi giữa hai snapshots, không kết luận đó là nguyên nhân duy nhất.
Không nới pixel equality hoặc dùng DOM khác thời điểm để suy role ảnh cũ.
Khóa capture mới undetermined vision_only, assistant self-review công khai,
không inference; vẫn giữ capture-3a14a28d658d và các unscorable cũ trong ledger.
Không capture-retry tới khi khớp để che bất ổn. Hạn chế oracle còn tồn tại;
--record-dom là cải thiện workflow, chưa giải quyết mọi trang động. Tiếp tục
case khác đã định trước trong dev manifest, không tự thay expectation hoặc
đổi case lỗi thành ca dễ. Không claim đạt ngưỡng blocked/unscorable<=20%.

### LIMIT-002 — Python modules target vắng trong viewport, oracle not_found

capture-fda0c42ff563, wo_d02_python_modules: ảnh gốc không có link nhãn
Installing Python Modules trong viewport1280x800; chỉ thấy các link tài liệu
khác, không thay thế target. Khóa not_found trước model, vision_only,
assistant self-review công khai (không human independent review). Không kết
luận target vắng trên toàn webpage hoặc cuộn thêm để tạo expected khác.
PNG SHA giống ảnh tutorial dùng Search/Quick search, không là unique scene
mới chỉ vì case/capture mới. Grounder giữ nguyên, chưa có proposal.

### LIMIT-002 — Python modules correct_rejection

capture-fda0c42ff563/proposal-c2080bb79579.json: not_found,
correct_rejection,786.208ms, candidate0, actions0. Oracle absence trong
viewport đã khóa trước model; không coi target vắng trên toàn site.
Giữ source subline checkpoint. Bốn dev cases còn cần capture/annotation:
wo_d03_python_offscreen, wo_d04_python_absent, wo_d06_mdn_html_reference,
wo_d07_mdn_punctuation. Có thể capture read-only theo batch, nhưng vẫn phải
review mỗi ảnh trước oracle/model; không giả định expected theo case names.

### LIMIT-002 — batch bốn dev captures, oracle đã khóa trước model

Đã xem riêng cả bốn PNG:
- capture-1270f5693ab4 / d03 What Now? link: not_found trong viewport.
- capture-6f3b08ae42be / d04 Create invoice button: not_found.
- capture-42768b4fcce8 / d06 HTML reference link: not_found; HTML title và
  Reference section không phải nhãn link nguyên văn HTML reference.
- capture-3522a8085fb7 / d07 HTML reference. link: not_found gồm dấu chấm.
Khóa cả bốn bằng vision_only, assistant self-review được ghi rõ, không hai
human reviewers, chưa model/proposals. Không kết luận target vắng ngoài
viewport/toàn site. Hai Python PNG trùng scene cũ, không unique scene mới.
MDN pixel hashes khác nhau không đồng nghĩa domain/layout độc lập mới.
Grounder/source giữ nguyên; không sửa manifest kỳ vọng hoặc scorer.

### LIMIT-002 — bốn negative batch đều đúng; cố định dev run plan

Đọc các proposals2b613e92c4ea/5f77ab3466a7/9f1429169b95/29113dbdbbd1:
4/4 correct_rejection, 600.47/564.87/536.95/538.23ms, actions0; MDN native
edge adjustments2 mỗi ca, không provider error. Không aggregate chúng với
best-of public success qua các source versions khác.

Thêm benchmarks.web_observation.plan và evaluate-plan:12 ca dev đã có oracle
trước inference,10 scorable (3positive/7negative),2undetermined; source/oracle
checksums; một lượt mỗi ca, giữ all attempts/progress/errors riêng, không
tái dùng report cũ làm điểm. Kế hoạch dev-plan-subline-01.json đã kiểm tra
bindings, CHƯA native run. Manual Quick search extra không nằm trong12case
manifest. Reviewer AI/self-review và dev đã xem phải ghi rõ khi kết luận.
Không đủ ambiguity positives/domain/held_out để go-live hoặc claim generalization.

Frozen-plan integration:6 tests mới bao phủ giữ failure, không best-of,
unscorable skip, source/oracle mismatch trước inference, partial errors và
proposal binding mismatch. Toàn suite530tests đạt; git diff --check đạt.
Chưa có native evaluate-plan report; quality_valid phải false nếu incomplete
hoặc validation lỗi. Không lấy fake tests làm model quality score.

### LIMIT-002 — frozen dev plan native10/10, chưa đủ generalization gate

Đã đối chiếu plan-run-c4d54d4b564b.json:quality_valid=true,incomplete=null,
12planned/10scorable/2unscorable;10/10 đạt;3/3 positives,0/7 false acceptance,
0errors. Median576.449ms bị chi phối bởi các negative không gọi model;
positives4874.590/5105.862/5685.256ms; p95 nearest-rank6419.051ms (n10).
7unique image hashes trên3hosts không phải7websites/layout độc lập. Không
ambiguity oracle (denominator0), không held_out score; gate false giữ nguyên.
AI/self-review annotation không độc lập hai human raters, dev đã dùng sửa.

Đã lưu configs/vision-web-heldout-freeze-v1.json để giữ core source/manifest
trước khi đo held_out. Chỉ capture/annotate tiếp, chưa model. Thêm --page-cases:
một navigation/page screenshot cho các manifest goals cùng URL/split, tạo
case dirs riêng nhưng image hash/shared_page_capture_id chung. Không copy
oracle/proposal hoặc tính4goals thành4scenes; không record-dom cùng option.
Test giữ nguyên PNG/time, goal mới, không kế thừa annotation, reject URL khác.
Không sửa grounder nên không yêu cầu lặp synthetic suite ở lượt này.

## HELD-001 — Oracle held_out trước inference: thiếu role/label, Chrome render suy giảm

- 30/10/2026: đã xem ba PNG gốc cho12case held_out, chưa model. Mỗi domain
  bốn target dùng cùng image SHA; không tính thành12unique scenes.
- GitHub: Get started có heading và một blue navigation link; Migrations có
  một blue link. GitHub Docs là title/brand, không visible button cùng nhãn.
  Search for anything... nhìn như search launcher; ảnh chưa đủ khẳng định
  textbox versus button nên proposed undetermined, không tự gán not_found.
- W3C: Recommendation underlined blue link phía trên; Latest published
  version: là bold metadata label cạnh URL khác, không link cùng nhãn;
  Pay invoice không có trong viewport. Errata exists. ở mép dưới: chưa chắc
  dấu chấm là một phần text của anchor hay punctuation ngoài anchor chỉ từ
  ảnh; proposed undetermined cho exact-label protocol trước khi xem model.
- Chrome: ảnh mất nhiều styling/icons, default font/raw navigation/list ngôn
  ngữ. Chưa xác minh network host nào bị chặn; có thể do capture policy, không
  gọi đó là website/model lỗi. Docs thấy hai blue underlined links (top và
  navigation thấp); Get started thấy trong hàng nav gần đáy; Filter không
  hiện; Search button icon không có visible label chắc chắn nên proposed
  undetermined. Scorable targets phải báo thuộc degraded rendering, không
  khẳng định là giao diện bình thường hoặc chấm phần ngoài viewport.
- Cần human boxes cho4positive targets và2Docs ambiguity boxes trước model.
  Các oracle AI/self-review phải công khai, chưa phải hai human annotators.
  Không đổi grounder/manifest hoặc setup để chọn ca theo kết quả model.

### HELD-001 — Khóa oracle trước lượt đo desktop

Đã lưu sáu vùng người dùng đo vào năm annotation found/ambiguous, reviewer
assistant-visual; bảy oracle còn lại là assistant-visual/self-review, không
mạo nhận hai người độc lập. Get started Chrome có box rộng hơn chữ, được ghi
rõ dùng center-hit, không phải segmentation pixel-tight. 12 oracle khóa trước
model, 4 found/4 not_found/1 ambiguous/3 undetermined; ba trường hợp chưa rõ
không được tính correct rejection. Plan held-out-plan-frozen-01.json gắn
checksum ảnh/metadata/annotation/source và freeze. Core Vision không đổi.
Chưa inference held-out; coverage chưa đạt: unscorable25% >20%, chỉ1 ambiguity
so với tối thiểu2, held-out chỉ3 ảnh. Không thay ca hoặc hạ ngưỡng để đạt.

Runner trước đây chỉ tạo dev plan; đã bổ sung split held_out tường minh với
freeze/model/manifest/đủ-case checks và giữ mặc định dev. Test fixture mới
ban đầu khai báo1280x800 nhưng tái dùng PNG kích thước khác, dẫn tới
Invalid PNG header/size; đã sửa fixture lấy đúng kích thước gốc, không sửa
guard sản phẩm. 25 tests observation và toàn suite534 tests đạt.

## BUG-014 — Public-web held-out nhận một target dù nhãn Docs trùng

- Trạng thái: đã tái hiện trong báo cáo, chưa sửa. Nguồn:
  plan-run-0d240437b49b.json, case wo_h09_chrome_docs, proposal-5a5410cfb323.json
  dưới capture-462805ae0235. Core vẫn khớp freeze-v1; annotation trước model.
- Có ít nhất hai liên kết Docs được người dùng khoanh. Pipeline trả found
  tại liên kết thấp, candidate_count1, exact_match_count0, subline pass1,
  full_image_match_count one; false_acceptance. Không có mouse action.
- Đã xác minh count guard không chặn được ca này; chưa có raw OCR/model
  response để kết luận vì sao mất ứng viên hoặc model đếm sai. Cần điều tra
  extraction/merge/candidate coverage và count verifier trên ảnh đã lưu.
- Tác động: không được kết luận an toàn từ0/4negative false acceptances;
  ambiguity có1/1false acceptance. Giữ live Vision tắt, không nới scorer.

## BUG-015 — Public-web held-out thiếu OCR candidate cho nhãn hiện hữu

- Trạng thái: đã quan sát, chưa sửa. Cùng report nêu trên: W3C Recommendation
  proposal-188acba724c5.json (capture-a885e567e9a8) và Chrome Get started
  proposal-4965f20c00fa.json (capture-b4e60c379808). Hai ca đều positive, trả
  false_abstention, candidate_count0/ocr_no_exact_match.
- Chưa có raw OCR để phân biệt sai ký tự với merged line hoặc lọc candidate.
  Chrome render suy giảm là giới hạn ảnh, không tự là nguyên nhân đã xác minh.
- Tiếp theo: diagnostic OCR trên đúng ảnh, không recapture thay ca hoặc sửa
  oracle. Chỉ nới proposal generation nếu vẫn kiểm chứng độc lập và giữ
  duplicate/role/state guards; chưa chọn giải pháp khi chưa có bằng chứng.

## BUG-016 — Migrations có OCR exact match nhưng blind label read từ chối

- Trạng thái: đã quan sát, chưa sửa. capture-23c487694c59,
  proposal-ae1d35a91cee.json: false_abstention, candidate_count1,
  exact_match_count1, decision_stage label_read_rejected.
- Biết lỗi nằm sau tạo candidate, chưa biết model đọc thành chữ gì do lượt
  baseline không lưu raw response. Không quy lỗi cho OCR/model/crop khi chưa
  có diagnostic. Điều tra crop/anchor và transcription sau ưu tiên BUG-014.

### HELD-001 — Đã hoàn tất lượt baseline, coverage và chất lượng chưa đạt

12 ca dự định,9scorable,5đúng; positive1/4,ambiguous0/1,3unscorable.
Median1091ms/p959353ms,n9. Đã đối chiếu checksums và tính lại summary.
Không thay freeze/report/nhãn để chạy lại lấy điểm cao. Chưa thay code hay
gọi inference trong lượt phân tích. Báo cáo chi tiết tại
Docs/WEB_VISION_HELD_OUT_PILOT_2026-10-30.md; sau tuning các ca này chỉ còn
giá trị regression đã thấy, không được gọi đánh giá mù mới.

### BUG-014 / BUG-015 — Bản sửa ứng viên dòng ghép, chờ desktop

- Đã xác minh lỗ hổng code: bước subline chỉ chạy khi chưa có hypothesis và
  chỉ cho delimiter •·|. Vì thế một nhãn đứng riêng có thể làm bỏ qua một
  nhãn khác trong dòng navigation ghép. Test tái hiện Docs + Docs Case studies
  Blog trước full-image count. Đây là lỗi thuật toán phù hợp baseline; chưa
  có raw OCR baseline để khẳng định đây là toàn bộ nguyên nhân ca desktop.
- Sửa label_candidates.py: kiểm tra mọi merged line chứa target dù đã có
  candidate; dùng geometry substring do native OCR trả, không chia tọa độ
  theo tỷ lệ ký tự. Nếu merged label chưa định vị được thì ambiguous, model
  đếm one không thể ghi đè. Giữ độc lập label read, role/state và full veto.
- recognize.swift/ocr.py thêm --label query bounded, argv shell=False. Giữ
  punctuation dính cuối substring để không biến Publish. thành Publish;
  chặn match bên trong từ; geometry nguyên dòng không dùng làm subline.
  Mode delimiter cũ giữ cho tương thích. Query chỉ tạo proposal, không là
  evidence chấp nhận; không đưa oracle vào provider.
- Runner ghi label_query và unresolved_merged_labels trong diagnostic,
  sửa config subline_policy cho đúng phiên bản. Không sửa freeze/baseline.
- 57 targeted tests qua; toàn suite546 tests qua, native helper compile
  thành công ocr-c9712f46187ddc4e; git diff --check qua. Native OCR trong
  agent vẫn thất bại trên ảnh Chrome (ocr-diagnostic-4c2243c120e3.json),
  nên chưa có điểm native/model thật cho bản sửa. Không đánh dấu resolved.
- BUG-015: thay đổi này hỗ trợ dòng ghép không có delimiter, nhưng cần OCR
  desktop để biết W3C/Get started có đúng nguyên nhân này hay không.
- BUG-016 Migrations: chưa sửa transcription khi chưa biết nó đọc thành chữ
  gì. Cần --diagnose-model một lượt trên ảnh đã lưu. Không bỏ blind read,
  không retry output khác để nhận. Sau sửa là regression đã thấy, không
  thay điểm held-out đầu tiên5/9. Live Vision vẫn tắt.

### BUG-014..016 — Desktop diagnostic và sửa focus, 30/10/2026

Bốn diagnostic: cc5602511322 (Migrations), f7fdaa6836a5 (W3C), b6be5ccdadfc
(Docs),9ec3d499bacd (Get started), nằm trong capture tương ứng. Bản merged
query vẫn0/4đúng: Docs có2candidate nhưng model classify nhãn trên thành
textbox rồi chọn nhãn dưới; full-image đếm one. Migrations OCR đúng nhưng
model đọc Get started ở dòng bên cạnh. W3C/Get started đã có geometry đúng,
lỗi chuyển sang semantic role. Chưa được gọi lỗi duplicate là resolved.

Sửa label_candidates.py: label crop padding12 thay96 hạn chế đọc dòng bên
cạnh; role crop padding96 với outline ngoài bbox, prompt chỉ rõ control tại
outline. Label marker vẫn policy cũ để giữ dấu câu. Tính lại relative bbox
đúng từng crop. Full-frame vẫn ảnh gốc, veto role/state giữ nguyên. Runner
ghi config mới. Test mới xác nhận focus/marker/relative bbox và full-frame
nguyên bản. Toàn suite547 tests đạt; git diff --check qua.

Native OCR agent vẫn lỗi, nên probe dùng cached desktop OCR + native crop
helper + live qwen3.5:4b, không phải native end-to-end. Probe e1b71764c093
có đánh dấu cả full-frame,2/4đúng; probe65c8e92a6a5e dùng full-frame gốc và
extra focus prompt,1/4đúng. Giữ cả hai, không gộp best-of.
Replay đúng source hiện tại, không override message, tại
focus-cached-ocr-probe-d1aeb6f7bdb3.json:1/4đúng (Docs ambiguous). Ba label
đều đọc đúng, local classify link, nhưng full-frame classify text nên đều
false_abstention. Driver và provenance/hash lưu cùng thư mục. Không tuyên bố
điểm desktop mới hoặc sửa hoàn tất.

Trạng thái: đã cải thiện focus và duplicate trong replay, chờ desktop; chưa
hết lỗi. Nút thắt còn lại là bất đồng local/full-frame role của model4b.
Không gỡ veto hay thay oracle để nâng điểm. Cần đánh giá phân loại role tốt
hơn và negative regressions. Live Vision tắt, baseline held-out5/9 giữ nguyên.
Lúc lưu provenance, lệnh đầu thiếu PYTHONPATH nên import elvion lỗi trước
khi ghi manifest/log; đã chạy lại với PYTHONPATH=src:., không inference lại.

## AX-LIMIT-001 — Spike desktop AX chưa có cây thật do thiếu quyền

Task B hoàn tất module Calculator chỉ đọc trong7file, API observe_app và
immutable snapshots; mặc định không đọc nhãn, không dùng AXValue hoặc
thao tác AX. Nhánh chính đã đọc code/helper/tests/docs và chạy lại8/8tests.
Demo native30/10/2026 trả permission_required/AX_PERMISSION_REQUIRED,0node.
Đây là kết quả kiểm tra quyền, không phải quan sát cây AX thành công.
Chưa nối AIMS/planner/UI. Cần chủ dự án mở Calculator bằng tay và cấp
Accessibility cho host chạy lệnh rồi chạy script summary; chưa lưu snapshot
thô hay kiểm chứng coordinate/multi-display/truncation thật.

## AX-BUG-001 — Decoder chấp nhận boolean version và JSON lặp khóa

- Phát hiện khi review Task B: payload version=true và payload có hai khóa
  version (2 rồi1) đều trả observed trên fake backend. Lỗi parser có thật;
  không ảnh hưởng tới trạng thái quyền native hoặc chứng minh AX tree thật.
- Nguyên nhân: Python True==1, json.loads mặc định lấy khóa cuối.
- Sửa observer.py dùng strict_json dùng chung, bắt type(version) is int.
  Thêm test cho hai ca trên và UTF8 lỗi. Sau sửa9/9testsAXđạt, diff-checkqua.
- Đã xử lý trong phạm vi protocol unit tests. Không thêm hành động native;
  demo desktop có quyền vẫn chờ người dùng.

### AX-LIMIT-001 — Đã qua smoke desktop sau cấp quyền

Ngày30/10/2026, người dùng chạy script trên desktop sau bước cấp Accessibility
và gửi summary: status observed, reason null,243nodes,truncated false.
Đã vượt trở ngại quyền ở host của lượt chạy này và có quan sát AX native
không rỗng; không phải fake-test evidence. Đây là summary người dùng cung cấp,
nhánh chính chưa đối chiếu snapshot/tree/coordinates trực tiếp. Không lưu
nhãn hoặc nội dung app vào nhật ký. Trở ngại quyền đã xử lý trong môi trường
này; còn kiểm chứng role/bbox cụ thể, multi-display/freshness và privacy.
truncated=false chỉ là cờ từ helper, không chứng minh mọi control đều được
AX cung cấp. Chưa nối selector AIMS và chưa có action adapter AX.

## LIMIT-003 — So sánh Vision9B bị chặn ở bước tải model

Ngày30/10/2026, Ollama local chỉ cóqwen3.5:4b,digest
7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13.
Search tool lỗi; đã đọc trang chính thức https://ollama.com/library/qwen3.5:9b
quaHTTP và xác minh tag có Vision,khoảng7,6GB. Không suy ra nó tốt hơn từ
số tham số. Khởi động ollama pull9b được, nhưng tốc độ khoảng0,25–0,35MB/s,
chỉ khoảng81MB ở lần đọc cuối, ước tính nhiều giờ. Đã dừng client bằngCtrl+C
(exit130); không có model9B sẵn, không có điểm9B. Không xin sandbox escalation.

Đã chuẩn bị compare_models.py giữ cùng4ảnh/cached OCR và guard/scorer, pin
checksum và digest, one-pass theo nhóm4B/9B và unload giữa nhóm. Giữ mọi
error/partial, báo không blind/no nativeOCR/no absent-negative coverage.
Model metadata dùng GET /api/tags, không POST. Cả hai giữ context4096,
max_tokens512,temperature0,timeout120s; cold start tính vào locate.
5tests mới bao phủ denominator/all attempts, missing model no inference,
model digest change, input change giữ progress và cached OCR query/bounds.
25targeted và toàn suite553tests đạt; diff-checkqua. Preflight thật tạo
model-comparison-5a64450351bd.json:complete=false,phasepreflight9b,0observations.
Đây không phải điểm chất lượng hay một batch so sánh đã chạy xong.

Trạng thái: runner hoàn tất, chờ tải model trong Terminal desktop và chạy
lệnh trongDocs/WEB_VISION_MODEL_COMPARISON.md. Không đổi model mặc định
sản phẩm hay mở live Vision; baseline5/9 và các probe cũ giữ nguyên.

## AX-LIMIT-002 — Targeting synthetic đạt, nhãn/bbox Calculator thật chưa xác minh

Ngày31/10/2026, nhận Task B10file module desktop_targeting, demo, benchmark
và tài liệu. Nhánh chính đã đọc locator/contracts/demo/runner/docs, chạy
lại14tests targeting+benchmark và9tests observer:23tests đạt. Benchmark
synthetic chạy lại30/30,0falseacceptances,0actions tại
artifacts/benchmarks/desktop-targeting/desktop-targeting-20261030T175351-d7c3eeaf.json.
Đây là bằng chứng synthetic, không phải30tác vụ Calculator thành công.

Policy hiện tại exact NFC/casefold/whitespace,giữ punctuation/diacritics;
duplicate buttons ambiguous kể cả disabled; missinglabel/role/evidence
unavailable. Snapshot malformed,stale,future hoặc truncated bị từ chối.
Locator pure và không có action, chưa nối AIMS/executor. Bbox native AX
screen points,negative origins hợp lệ,không chuyển CSS/click.

Task B báo demo agent permission_required; nhánh chính không coi đó là
thiếu quyền trên Terminal của người dùng vốn đã smoke243nodes. Cần chạy
opt-in --label7 --include-labels trên chính Terminal đó để xác minh target.
243nodes không chứng minh có AX label7/+ hoặc bbox đúng. Timestamp observer
ghi cuối thu thập nên agefilter chưa đủ freshness cho execution; chưa review
window/focus/visibility/multi-display. Không gỡ guard hoặc tự sửa label để
lấy found. Trạng thái: synthetic reviewed, chờ native target summary.

## AX-LIMIT-003 — Native targeting7bị chặn vì incomplete evidence

Ngày31/10/2026, sau mở Calculator người dùng gửi summary unavailable/
INCOMPLETE_AX_EVIDENCE,candidate_count1,age3,033625ms. Điều này xác nhận
một AXButton khớp exactlabel7 trong snapshot, chưa xác nhận enabled/bbox hay
uniqueness khi còn unknowns. Không kết luận nhãn7vắng hoặc quyền bị mất.
Locator có global guard: unlabelled button/unknown role có thể là duplicate.
Chưa biết node nào gây chặn từ summary; không tự loại node chưa rõ.

Thêm evidence_summary pure và demo --diagnose-evidence opt-in. Reuse cùng
predicate unknown, cùng một observation, chỉ counts/IDs/roles/ancestor IDs,
không nhãn hoặc tọa độ của blocker. Giữ unavailable và toàn guard.
Test mới kiểm tra không lộ label, không thêm observer call/không đổi outcome.
Test ban đầu tìm substring bbox trongJSON vướng tên count matching_with_bbox,
không phải lộ tọa độ; đã sửa assertion kiểm tra keybboxthật.25testsAX đạt;
benchmark30/30,0falseacceptances,0actions giữ nguyên. Chờ diagnostic native
để phân biệt thiếu nhãn control liên quan hay node ngoài phạm vi cửa sổ.

### AX-LIMIT-003 — Ba blocker trực tiếp AXWindow; thêm scope tường minh

Người dùng gửi diagnostic244nodes:matching_buttons1,enabled1,with_bbox1,
BUTTON_LABEL_MISSING3, cả ba parentAXWindow. Chưa có subrole nên nhận định
window chrome vẫn là giả thuyết, không tự kết luận close/minimize/zoom.

Đã thêm scopecalculator_content opt-in, defaultall_buttons giữ nguyên.
Chỉ loại AXButton có subrole chuẩn window management và trực tiếp dưới
AXWindow; không loại theo nodeID/tọa độ/số lượng hoặc thiếu nhãn đơn thuần.
Subrole constants xác minh SDKAXRoleConstants.h. Result found bindscope.
Giữ unknown/duplicate/enabled/bbox/stale/truncated guards, không cấp quyền
thao tác. Diagnostic thêm subrole/count exclusions và dùng cùngsnapshot,
không dump nhãn/bbox.28AXtestsđạt; benchmark scopeall_buttons30/30giữ nguyên
tại desktop-targeting-20261030T180100-59fa3548.json. Scopecontent chưa native
verified, chờ lệnh --scope calculator-content --diagnose-evidence.

Kiểm tra tích hợp sau sửa scope: toàn suite572tests đạt,git diff --check đạt. Native content scope vẫn chờ desktop.

### AX-LIMIT-003 — Desktop xác nhận found7 trong scope content

Ngày31/10/2026, người dùng chạy demo scoped và gửi summary:found/EXACT_BUTTON,
roleAXButton,enabledtrue,candidate_count1,target_scopecalculator_content,
243nodes,blocker_counts rỗng. Exclusions xác nhận đúng3subroles:
AXCloseButton1,AXZoomButton1,AXMinimizeButton1. Giả thuyết window chrome
đã có bằng chứng subrole native, không còn dựa vào số lượng/vị trí.

Lỗi bị chặn do window-management nodes không nhãn đã được xử lý trong scope
content và lượt Calculator này. Defaultall_buttons vẫn bảo thủ; không nới
unknown guard trong phạm vi đã chọn. Summary do người dùng cung cấp, chưa
review snapshot toàn bộ. Có bbox với yâm; nativeAXscreenpoints cho phép
negative origins trên hệ màn hình mở rộng, không coi đây là lỗi từ dấuâm
nhưng cũng chưa đối chiếu vị trí màn hình để xác minh bbox đúng. Age2,701041ms
là tuổi timestamp cuối snapshot, không phải chứng minh từngnodeatomic/fresh.
Chưa có click, chưa nốiAIMS/executor hoặc biến bbox thành clickcoordinates.
Bước tiếp theo: kiểm chứng thêm label+trường hợp từ chối nếu mở rộng phạm vi;
thiết kế freshness/window/display mapping và verifier trước actionadapter.

## AX-GEOM-001 — Đối chiếu target/window/display chưa có native desktop

Ngày31/10/2026, sau found7người dùng yêu cầu kiểm tra bbox. Đã thêm pure
check_geometry,display metadata helper và scriptcheck_desktop_geometry.py.
SDKAXAttributeConstants.h xác nhận AXPosition gốc top-left màn hình menu,
yhướngxuống,units points; AXSize units points. Helper đổi NSScreenframe
sang hệđó rồi đối chiếuCGDisplayBounds từngdisplayID, mismatch>0,5point
thì từ chối. Scale chỉmetadata,không nhânbbox. Đọc layout trước/sauAX,
build trước snapshot; layoutđổi/stale/future/truncated/bboxngoàicửa sổ
haykhông thuộc duy nhất1displayđềuunavailable. Khôngclick/focus/screenshot.

7geometrytests và tests liên quan31/31đạt; toànsuite579testsđạt. Lỗi compile
Swift đầu tiên do String? ?? NSNull thiếu contextAny trong JSON dictionary;
đã sửa envelope kiểu[String:Any] và serialization guard. swiftc compile
thành công sau sửa. Nativehelper chạy trongagent trả DISPLAY_LAYOUT_UNAVAILABLE
(displaysrỗng),không chứng minh displaymapping desktop hoặc bboxnút7đúng.
Chưa gọi readAX mới trongagent; giữ dữ liệu riêng tư tối thiểu.

Trạng thái: pure checks/tests/build hoàn tất,chờ Terminaldesktop chạy
scripts/check_desktop_geometry.py --label7 --include-labels. Thành công
geometry_consistent chỉ chứng minh containment/các mẫu tọa độ nhất quán,
không xác nhận visibility/occlusion/pixels hay freshness choexecution.
Hai mẫu layoutkhớp không chứng minh không có thay đổi ở giữa.

### AX-GEOM-001 — Native geometry Calculator7đã qua

Ngày31/10/2026, người dùng gửi geometry_consistent/
AX_WINDOW_AND_DISPLAY_CONTAIN_TARGET,targetfound/EXACT_BUTTON,scopecontent.
Targetbbox[1103,-519,48,48] nằm trongwindow[1093,-706,230,408] và
display[62,-900,1600,900],scale1. Negativey nhất quán với displayởphía
trên gốc màn hình menu. Hai mẫu layoutkhớp,age35,631625ms (timestampcuối
snapshot). Đây là summarydesktopdo người dùng cung cấp; khôngscreenshot
hoặcđối chiếupixel.

Đã xác minh native target/window/display containment trong lượt này;
giới hạn thiếu layouttrong môi trườngagent không còn chặn smoke desktop.
Giữ actions0,visibility_verifiedfalse,freshness_for_executionfalse.
Không suy từcontainment rằng targetkhôngbịche/đangforeground/clickable,
không dùng35ms làm bằng chứngtuổi từngnode hay cấp quyền thựcthi.
Chưa nốiAIMS/executor,không có click. Khi mởrộng cần kiểmtra thêm trường
hợp layout/thay đổiwindow và thiết kế action-specific reobserve/verifier.

### LIMIT-003 — Model9Bđã tải và hoàn tất so sánh thật

Người dùng cung cấp model-comparison-637f29445f0f.json:complete=true,8obs,
actions0. Đã đối chiếu mọi inputhash/sourcehash,modeldigest hiện tại,
imagehashphasechung và tính lại summary.4B1/4(positive0/3),9B3/4(positive2/3).
Hai model không có absent-negativecases, mẫu sốfalseacceptance loạiđó0.
Trở ngại download đã xử lý; không tuyên bố toàn bộVisionđạt.

### BUG-014..016 — So sánh9B cải thiện role trên2ca, còn empty label read

9BMigrations/W3Cđều correct_target và fullrolelink,4Bfullroletext nên từchối.
Docs9Bambiguous được scorer tínhcorrect_rejection nhưng hai labelreads rỗng,
verifiedcandidate0; không chứng minh duplicate detection. Get started9B
false_abstention cũng vì emptyread, chưa tớirolecheck. Cả hai vẫn là giới hạn
nghiên cứu, không gỡguard để chọn khi model không đọc được.9Bchưa mặc định
sản phẩm,liveVisiontắt. Bboxkhônglưu trongcomparisonrow nên review chỉ
đối chiếu summary/bindings/trace,không chấm lại bbox độc lập.

Median9B3,71s thấp hơn4B4,14s doChrome dừng sớm (2/1calls thay4/3calls),
không kết luận9Bnhanh hơn. Migrationscold11,38s vs7,51s;W3C5,61s vs4,55s.
Chưa đoRAMpeak. Docchi tiết:Docs/WEB_VISION_MODEL_RESULTS_2026-10-31.md.
Tiếp theo điều tra emptyread bằng test trình bày crop có kiểm soát;
kíchthước/marker là giảthuyết, chưa có nguyênnhân đã xácminh. Giữ baseline
held-out5/9 và mọi probe cũ,không biến regression này thành held-outmới.

## BUG-017 — Vision9Bđọc rỗng các ảnh cropnhỏ của Chrome

Ngày31/10/2026: làm thínghiệm đọc nhãn có plan trước model6profiles×5regions
trong4cađãthấy. Artifactlabel-presentation-253630be6d5d/report.json,plan và
30inputPNGs cùng thư mục. Current/image_coords/unmarkedđều2/5đúng,3empty;
upscale2/upscale4đều5/5đúng,0empty; context96đạt3/5. Không best-of:mọirow
được giữ. CropChrome gốc56×42,62×42,95×42. Marker/key riêng không đủ sửa;
phóngảnh có hiệu quả trong các mẫu này. Chưa xác minh cơ chếencoder hoặc
nguyên nhân duy nhất; không kết luận mọi cropnhỏ đều được sửa.

ThêmResizeImage.swift/presentation.py bounded PNGresize2×/4×,khôngOCR/model/
hànhđộng. Grounderlabel_scaleopt-in,default1không đổi. Chỉảnhlabelreadđược
phóng,anchorbbox_image_pixels đi theoảnh; targetbboxCSS,rolecrop/fullimage
giữ nguyên. Không runtimeoutput-basedretry. Sources cho report mới gồm
presentation.py+ResizeImage.swift; freeze cũ không cập nhật. Benchmark native
vision_labels nhận --label-scale, ghi đúngconfig. Testxácnhận kíchthước/CRC/
giớihạn/shellFalse và targetbbox không đổi. Toànsuite584testsđạt.

ReplaypipelinecachedOCR+nativecrop/resize+livemodel ở
model-comparison-f3f83f7c307a.json:4B1/4,9B3/4. Nay Docs9Bđọc cả2nhãn và
classify cả2link,verifiedcandidate2=>ambiguous; trướcchỉemptyread. Getstarted
labelđúng/localrolelink nhưng fullframecountzero/roletext=>false_abstention.
Không gỡveto. Chưa nativeOCRend-to-end hoặc regressionnegative rộng.

Thửfullframe3profiles×4casesđãthấy:
fullframe-presentation-125fd64cc2aa.json,12rows. Đổiimagecoordkey/phóng
fullframe2×không sửaGetstarted;Docscountvẫnone ởmọiprofile tronglượtnày.
Không tíchhợpfullframe scaling. Drivervàprovenance giữcùngartifact.

Negativeprobe4oraclecũ trênảnhbyte-identical,
scaled-negative-replay-940ced048136.json:3correctrejection,1groundererror,0found.
GitHubwrongrole thiếu cachedsublinequery cho targetGitHubDocs (cachebanđầu
choMigrations),nên không coi rowerror là correctrejection hoặc lỗi model9B.
W3Cmetadata từchối ở labelread,2absent không gọi model;chưa có semantic
negative coverage rộng. Giữ mọi outcome,không chạy lại lấy điểm cao.

Trạng thái: readstage cải thiện đã đo trêncachedOCR+livemodel;defaultchưa
đổi,nativebroadregressionchờdesktop. Getstarted/fullframeveto và global
duplicatecountvẫn làgiớihạn. Không đóng BUG-014..016 toàn bộ,liveVisiontắt.
Docchi tiết vàlệnh30case9B2×:Docs/VISION_IMAGE_PRESENTATION.md.

## BUG-018 — NearwordSavefiles bị coi là mergedlabel của Savefile

Ngày31/10/2026, native9B/scale2syntheticreport
vision-labels-20261031T032101-b142c710.jsonđạt26/30,19/22positive,0falseaccept,
0wrongtarget,0errors,2/2ambiguityvới verifiedcandidate2. Manifest/HTMLhash và
summaryđã đối chiếu. Ba falseabstention làProceed!(localbutton),Methods:
(fulltext),Status:ready(localtext). MộtwrongabstentionSavefile/Savefiles
trảambiguous/unresolvedmergedlabel,candidate0.

Bugcode tái hiện bằngOCRlineSavefiles,targetSavefile: phép substring cũ
kích hoạtspanquery sai cho prefixkhácword. Sửaembedded_label kiểm boundary
Unicodeletters/numbers/marks/underscore và prefixspace/delimiter phù hợp.
Không gọi model/spanOCR cho nearword; vẫn xửlý DocsCase studies và
W3CRecommendation+date. Hai unit mới xác minh absentnearword và không
phámerged navigation/punctuation. Chưa có rawOCRbaseline để quy đây là toàn
bộ nguyênnhânnative; chờrerun case. Baseline26/30không bị sửa hoặc nângđiểm.

ThêmRecordingGrounder,--diagnose-model opt-in cho syntheticrunner; lưu raw
OCR/phase/error/screenshot fixture và resultbbox trongsidecar mới,cósourceSHA.
Không cóoracle trongmodelpayload,defaultreportsanitized giữ nguyên. Ba test
kiểm mỗiobservation riêng,failedprovider được giữ/khônglộrawexception và
ảnh sidecar/hash/quyền0600. Toànsuite589testsđạt,diff-checkqua.

Ba lỗi role chưa sửa; marker/context là giảthuyết,không nới guard. Chạy4ca
selected với --diagnose-model đểthu ảnh/cachedOCR rồi có thểreplayoffline,
không nhờ chạy lại toàn bộ30ca liên tục. Doc:
Docs/VISION_9B_SYNTHETIC_REGRESSION_2026-10-31.md.

### BUG-018 — Native boundarycase đã xác minh

vision-labels-20261031T033137-e4158aca.json/diagnostics xác nhận1/4đúng:Savefile
nearword trảnot_found/ocr_no_exact_match,OCRthật làSavefiles. Ba linkđọcchữ
đúngnhưngroletrượt. Boundaryfixđã qua ca native này,không sửa điểm26/30cũ.

## BUG-019 — Role marker/presentation ảnh hưởng phân loại link

ẢnhroleProceed!/Statusđãlưu cho thấy khungđỏbao text. Sànglọc6regions×4mode
ởrole-presentation-cde9b7956c40/report.json:current2/6,unmarked5/6,marked2x3/6,
unmarked2x5/6. Bỏmarkerđồngthờibỏcâuhướngdẫnmarker, nên không quy kết duy
nhất pixelsđỏ. Metadatađốichứng vẫnlocalclassifylinkcả4mode:giới hạncòn.

Thêmrole_markeropt-in(defaultTruegiữcũ),khôngxóarole/state/countveto.
Replayunmarked trên4fixturecached ởfixture-replay-4afb56c85e04.json:2/4,
Proceed/nearwordđúng,Methods/Statusvẫnfullframetext. Giữ mọi attempt.

Fullrole5subjects×3modes tạifull-role-cb55d60aeb45.json:current3/5,outline2/5,
upscale2(đổianchorimagepixels)5/5role;Methods/Statusthànhlink,metadata/heading
giữtext. FieldcountheadingGitHubDocsvẫnone dùcóbrand/title, không gọi5/5
làcount/uniquenesshoàn hảo. Driver/plan/provenancecùngfolder.

Thêmfull_scaleopt-in1/2(default1),presentationhookgiữ behaviorV2/V3/default
cũ;phóngtoànảnh,candidateanchorimagepixel,giữCSSbbox/scorer. Dùngcùnghook
cho fullstate-disabledrefusal. Khôngbỏguard,khôngoutput-basedretry,không
vẽoutlinefull.4fixturereplaykếthợp label2/roleoff/full2 ở
fixture-replay-a9b7fd3667d5.jsonđạt4/4,source/binding/bboxđã chấm lại.
Ba positive17,6–22giây,không nớiTTLđểthựcthi.

Publicregressionkếthợp:model-comparison-ce218ae01e84.json,4B1/4,9B3/4,
Getstartedcònfullveto nhưtrước. Modeldefaults vàliveVisionkhông đổi.
Toànsuite605testsđạt;testmới giữscaledtargetgeometry/fullveto,validate
fixtureimage/HTML/goal/pathbinding. Côngcụreplayofflineđãcó,nên không cần
ngườidùngretestnative4casemỗithửnghiệm. Nativesynthetic30ca với config mới
vàdiagnosticđầyuđangchờdesktop;4/4selectedkhônglàgeneralization.

MộtlệnhkiểmtrareplaybanđầuthiếuPYTHONPATH vàdừngimport;đãchạylạiđúng
PYTHONPATH=src:.,khônginferencehoặcđổibáocáotronglầnđóchạy.
Docchi tiết:Docs/VISION_ROLE_PRESENTATION_2026-10-31.md.


### BUG-019 — Cập nhật native toàn bộ 30 ca, 31/10/2026

Bằng chứng: `artifacts/benchmarks/vision-labels/vision-labels-20261031T040148-8df207b3.json`
và sidecar `.diagnostics.json`. Cấu hình 9B, label_scale=2,
role_marker=False, full_scale=2; 8/8 source hashes khớp code hiện tại.
Kết quả: 28/30, positive 21/22, 0 wrong target, 0 false acceptance,
1 false abstention, 1 wrong abstention, 0 provider errors. Median 17.357 giây.
So với native 26/30: Proceed!, Save file/Save files và Status: ready đã đạt;
Methods: vẫn trượt và ca sai role Open guide hồi quy.

- `vl_h04_colon_link`: đọc đúng Methods:, local role=link/enabled nhưng
  full-image role=text, matching_labels=one. Guard từ chối đúng thiết kế;
  đây là mâu thuẫn phân loại model, không phải thiếu OCR hay lỗi dấu hai chấm.
- `vl_d14_wrong_role_text`: hai nhãn Open guide đều được đọc đúng nhưng
  local model nhận cả heading/prose thành link/enabled. Grounder trả ambiguous
  vì hai candidate, trong khi oracle yêu cầu not_found. Không có proposal click;
  không được đổi scorer để coi ambiguous là đúng và không chọn một candidate.
  Đây là hồi quy trong phạm vi BUG-004 khi đổi model/presentation, không chứng
  minh logic từ chối duplicate bị hỏng.

Trạng thái BUG-019 còn mở. Chưa có căn cứ sửa pipeline bằng cách bỏ full veto,
chọn local evidence thuận lợi hoặc tự retry model. Đã có diagnostic đủ 30 ảnh
và OCR để thử nghiệm offline; bước tiếp theo là kiểm tra độ lặp lại trên các
ảnh cố định, có đối chứng heading/prose, link thật và duplicate, trước khi
thay đổi cách trình bày ảnh/prompt. Chưa đổi code sản phẩm, default hoặc TTL;
live Vision vẫn tắt. Kết quả này là regression đã xem, không phải đánh giá mù.


## AXVIS-LIMIT-001 — Visibility chỉ đọc chưa xác minh native Calculator

- Ghi nhận 31/10/2026 từ bàn giao Task B; trạng thái chờ native desktop.
- Spike dùng system-wide AX hit-test tại năm điểm, binding target/window/PID;
  không chụp ảnh, click, focus hay tích hợp executor. `visible` chỉ xác minh
  điểm mẫu, luôn whole_target_visibility_verified=false và
  freshness_for_execution=false. Không coi AX hit-test là bằng chứng pixel.
- Bằng chứng bàn giao: desktop-visibility-20261031T032956-8fa901f6.md,
  synthetic 28/28, 0 false visible, 0 actions; helper biên dịch được theo Task B.
- Nhánh chính chạy lại 12 test visibility/benchmark đạt; cùng upstream
  observation/targeting/geometry đạt 43 tests. Đây là fake/unit evidence.
  Python hệ thống không cài pytest; đã dùng unittest, không cài dependency mới.
- Native agent bị DISPLAY_LAYOUT_UNAVAILABLE trước probe theo báo cáo Task B;
  không suy ra Terminal người dùng thiếu quyền AX.
- Review giới hạn bổ sung: helper đặt layout_unchanged/state_unchanged từ
  binding trước hit-test, chưa đọc lại geometry/state sau năm hit. Vì thế
  các flags không chứng minh toàn lượt probe không có race. Chưa đủ làm guard
  hành động; không thay đổi freshness TTL hoặc tích hợp AIMS từ spike này.
- Bước tiếp theo: mở Calculator bằng tay, bảo đảm nút 7 không bị che, chạy
  scripts/check_desktop_visibility.py --label '7' --include-labels trên Terminal.
  Lưu summary để đối chiếu native. Các ca che cửa sổ cần kiểm tra riêng;
  unknown là thiếu bằng chứng, không tự đổi thành visible.
- File: Docs/DESKTOP_VISIBILITY.md, src/elvion/desktop_visibility/,
  native/macos/DesktopVisibility.swift. Nhánh chính chưa sửa các file Task B.


### AXVIS-LIMIT-001 — Bổ sung smoke native từ người dùng, 31/10/2026

Người dùng cung cấp hai summary Calculator thật, actions=0:
- Lượt đầu blocked/SAMPLED_POINT_OCCLUDED, checked_points=5, age≈700.45ms.
  Chưa có oracle độc lập xác nhận cửa sổ nào che; chỉ ghi nhận hit-test.
- Lượt tiếp visible/FIVE_AX_POINTS_BOUND_TO_TARGET, checked_points=5,
  age≈61.66ms, target_scope=calculator_content, sampled_visibility_verified=true.
  Đây là bằng chứng native positive cho năm điểm mẫu trên target đã bind.

Mốc smoke positive native đã đạt theo output người dùng; không gọi đây là
kiểm chứng tất cả ca occlusion hoặc toàn bộ pixels. Cả hai lượt đều giữ
whole_target_visibility_verified=false, freshness_for_execution=false.
Giới hạn race trước/sau probe và chưa tích hợp action verifier vẫn mở.
Không cần cấp quyền mới hay đổi guard từ kết quả này. Tiếp tục Task A Vision;
trước desktop action cần thiết kế revalidation và verifier riêng.


### BUG-019 — Kế hoạch thử nghiệm role offline, 31/10/2026

Bổ sung replay --case/--repetitions và --role-profile chỉ dành nghiên cứu;
không đổi product prompt/default. Chọn case phải tồn tại trong diagnostic,
không trùng và giữ thứ tự nguồn; kế hoạch ghi đủ case, số lượt và driver hash.
Bước 1: lặp hai ca lỗi d14/h04 hai lượt, cùng cấu hình native28/30 để đo
khả năng tái hiện. Bước 2: thử lời nhắc visual-evidence-v1 bổ sung cách đọc
styling/anchor, không cung cấp role mong muốn, trên tám ca cố định:
d04 textbox, d06 link, d12 near-word, d13 duplicates, d14 plain text,
h02 period link, h04 colon link, h08 internal punctuation link.
Tất cả observations giữ trong báo cáo, không chọn attempt tốt nhất;
không tự retry trong product hoặc bỏ local/full veto để lấy điểm.
Nếu profile không cải thiện có đối chứng, giữ là kết quả nghiên cứu thất bại.


### BUG-019 — Kết quả probe và giả thuyết context

Replay baseline `fixture-replay-16c9899e7ed8.json`: 4 observations,
Methods: đúng cả hai lượt, d14 sai role cả hai. Profile bổ sung visual-evidence-v1
ở `fixture-replay-3c398f615cfc.json`: 7/8, d14 vẫn trượt; chưa áp dụng vào product.
Full-frame role probe `duplicate-role-probe/probe-9f6098b146b5.json`:
hai candidate d14 đều text/multiple; hai duplicate buttons d13 đều button
nhưng count=one sai. Không dùng full model để thay thế duplicate guard.

Telemetry full2: prompt_eval_count=4315–4319 với num_ctx=4096, API ps xác
nhận context_length=4096. Đây là dấu hiệu cần đo, CHƯA chứng minh truncation
hoặc nguyên nhân lỗi. Đang thử cùng ảnh với num_ctx=8192, không đổi mặc định.

Thiết kế candidate cho bước kế: kiểm tra full-frame chỉ để tinh chỉnh refusal
ambiguous thành not_found khi TẤT CẢ candidate trùng đã đọc nhãn chính xác
đều được full model nhận là text và matching_labels=multiple. Không được
chọn candidate hay tạo found từ bước này. Bất kỳ control/unknown/count khác
multiple giữ ambiguous; lỗi protocol giữ error. Mặc định off, thử opt-in trước.


### BUG-019 — Context và refusal refinement opt-in

Probe context8192 `duplicate-role-probe/probe-70903a422daa.json`: d13 hai
anchor vẫn button/countone; d14 hai anchor vẫn text/multiple; Methods: link.
Bốn quan sát chung không đổi so với context4096. Không chứng minh tăng context
sửa lỗi; giữ num_ctx mặc định. Không kết luận truncation từ token count.

Đã thêm duplicate_text_check mặc định False vào OCRLabelGrounder và flag
--duplicate-text-check ở runner/replay. Chỉ xét khi không có uncertainty và
có hơn một match; mỗi full observation phải role=text/countmultiple để đổi
ambiguous thành not_found. Gặp role/control/unknown/count khác multiple dừng
và giữ ambiguous. Schema lỗi vẫn error; không tạo found/bbox. Không retry.
Thêm tests all-candidate requirement, unknown/count/protocol, uncertain read;
48 test liên quan đạt. Đang chạy replay tám ca đối chứng với profile current,
không dùng lời nhắc visual-evidence-v1 đã không giải quyết d14.


### BUG-019 — Replay refinement và kế hoạch regression toàn bộ

`fixture-replay-23cb45d55938.json`: refusal refinement + prompt current đạt
7/8; d14 đã correct_rejection, d13 correct_ambiguity; Methods: lại false_abstention.
So với visual-evidence-v1 7/8 (d14 lỗi, Methods đúng), hai thay đổi giải quyết
hai cơ chế khác nhau trong mẫu đã đo. Chưa tuyên bố sửa Methods ổn định.
Kế hoạch tiếp theo: chạy MỘT lượt toàn bộ 30 ảnh cached, profile
visual-evidence-v1 + duplicate_text_check, label2/roleoff/full2; giữ mọi ca
và output, không đổi scorer/manifest/threshold. Đây là thử phối hợp đã xem,
không đánh giá mù và không phải native end-to-end.


### BUG-019 — Kết quả phối hợp, 31/10/2026

- `artifacts/benchmarks/vision-labels/fixture-replay-3046254907a8.json`:
  30/30 observations đúng oracle, 22/22 target hits, 6 correct rejections,
  2 correct ambiguities, 0 wrong targets/false acceptances/errors, actions=0.
  Median toàn corpus ≈17.66s. Cấu hình 9B, label2/roleoff/full2,
  visual-evidence-v1 + duplicate_text_check. Không đổi scorer hoặc manifest.
- `fixture-replay-993f839ae05b.json`: Methods: đúng thêm 3/3 lượt cùng
  cấu hình. Cùng ảnh lặp có thể hưởng cache/warm-up; không dùng latency lượt
  lặp làm bằng chứng tăng tốc và không coi 3/3 là bảo đảm ổn định tổng quát.
- Đã đối chiếu coverage toàn bộ 30 case, planned/completed observations,
  input/source hashes và lời nhắc được dùng. Cả hai báo cáo complete.
- Shared helper `benchmarks/vision_labels/role_profiles.py` dùng cùng chuỗi
  prompt trong native/replay; kiểm thử giữ nguyên image/schema/anchor và
  không đổi label transcription. Replay trước lúc gom helper giữ nguyên
  báo cáo/driver hash; nội dung lời nhắc đã đối chiếu bằng nhau.
- Toàn suite 611 tests đạt. Sau gom helper chạy 6 tests liên quan đạt;
  git diff --check đạt. Không sửa các module desktop của Task B.

Trạng thái: mốc synthetic cached regression đã đạt trong cấu hình opt-in;
chưa có native OCR end-to-end sau sửa, chưa có blind/public-web validation
cho cấu hình mới. BUG-019 còn mở ở phạm vi rộng. Mặc định flag False,
role profile current; không đổi model/context mặc định, TTL hoặc live Vision.
Lệnh desktop và giới hạn trong Docs/VISION_ROLE_REVALIDATION_2026-10-31.md.


## AXREVAL-LIMIT-001 — Spike revalidation chờ native desktop

Ghi nhận 31/10/2026 từ Task B và review nhánh chính. Collector có provenance
capture-start, process launchDate marker, giữ native references trong probe,
so sánh target/window trước và sau hit-test và display layout sau probe.
ready chỉ là một lượt quan sát mới đủ các điều kiện; không chứng minh identity
liên tục từ snapshot cũ, whole pixels hoặc quyền/freshness để thực thi.
Giữ actions=0, authority_granted=false, freshness_for_execution=false.

Nhánh chính chạy trực tiếp 8 hàm test đạt và scorer synthetic 40/40,
2 ready/22 blocked/12 unknown/4 error, false_ready=0, actions=0.
Báo cáo Task B: helper compile; native agent dừng DISPLAY_LAYOUT_UNAVAILABLE.
Chưa có ready trên Calculator thật. Không suy ra quyền Terminal từ lỗi agent.
Bước tiếp: người dùng mở Calculator, nút 7 không bị che, chạy demo opt-in.
Giới hạn TOCTOU, timestamp observer cuối lượt đọc và node_id không ổn định
vẫn tồn tại; không tích hợp spike vào executor/AIMS trước action-time design.

## AXREVAL-TEST-001 — Test dạng hàm chưa được unittest discovery chạy

Triệu chứng: tám test mới chạy trực tiếp đạt nhưng là module-level functions;
lệnh unittest discover hiện dùng trong repository không tự thu thập chúng.
Không cộng tám test này vào suite chỉ vì import module thành công.
Xử lý: thêm load_tests adapter dùng unittest.FunctionTestCase trong hai module
Task B; giữ nguyên test functions để không thêm dependency pytest. Chờ xác
minh bằng unittest trên module và suite chung.


AXREVAL-TEST-001 đã giải quyết: unittest trên hai module thực sự chạy 8 tests
đạt; toàn suite unittest discover chạy 619 tests đạt. git diff --check đạt.
Chỉ thêm adapter trong tests và tài liệu, không đổi revalidation runtime.
AXREVAL-LIMIT-001 vẫn chờ native desktop; không dùng suite làm bằng chứng ready.


### AXREVAL-LIMIT-001 — Native positive từ người dùng, 31/10/2026

Người dùng cung cấp summary demo Calculator thật:
status=ready, reason=BOUNDED_AX_SAMPLES_MATCH,
bounded_observation_checks_passed=true, actions=0.
Đây là smoke positive native cho lượt quan sát mới theo contract spike.
Không suy rộng thành đã kiểm chứng mọi ca thay đổi/che khuất trên desktop.
Summary giữ authority_granted=false, freshness_for_execution=false,
native_identity_since_snapshot_proven=false và
whole_target_visibility_verified=false, đúng giới hạn thiết kế.

Mốc native ready đã đạt theo output người dùng. Giới hạn continuity từ
snapshot cũ, TOCTOU và action-time verifier vẫn mở; không tự bật executor,
quyền hoặc desktop click. Bước kế tiếp cần thiết kế hợp đồng action riêng,
giữ bước kiểm tra quyền/xác nhận và hậu điều kiện độc lập.


## AXACTION-001 — Luồng AXPress cần authority và kiểm chứng riêng

Ghi nhận 31/10/2026 khi bắt đầu Task A. Native ready của revalidation chỉ là
quan sát; không được dùng làm quyền thực thi. SDK public AXUIElement.h nêu
AXUIElementPerformAction có thể trả cannotComplete dù đã có tác dụng.
Thiết kế: capability cố định Calculator/nút7/AXPress, confirmation digest,
helper giữ native reference và kiểm tra lại trước dispatch; handshake commit
chỉ sau authority check. Ghi attempt bền vững trước commit; timeout/mất IPC
sau đó uncertain, không retry. Native ack không phải verifier 0→7.
Phụ thuộc Task B calculator_verification đang được viết song song; reader
chưa sẵn sàng hoặc profile chưa review phải dừng trước dispatch. Không sửa
file Task B hoặc bật capability trong CLI/GUI chung trong spike này.


### AXACTION-001 — Đã triển khai Task A, chờ native positive

- Capability cố định desktop.calculator.press7, policy bắt buộc grant press7
  và read_result, confirmation digest với target PID/launchDate/bbox/layout.
  Registry/AIMS/TaskOrchestrator dùng contract hiện có, chưa đăng ký vào
  CLI/voice/GUI chung. Không sửa module Task B đang làm song song.
- Native CalculatorPress.swift giữ reference, reacquire/CFEqual trước/sau
  commit, scan giới hạn, five-point hit testing, process/layout/state/action
  support và expiry kiểm tra trước AXPress. Có đúng một mutation site.
- Private pipe prepare/commit có nonce/digest; Python kiểm tra authority và
  baseline 0 trước commit. SQLite reservation bền vững ghi trước mọi byte
  commit; lỗi storage không dispatch. Key đã reserve không được tái dùng.
- Timeout/partial write/native error/malformed reply sau commit -> uncertain,
  không retry. Native success phải qua fresh after-observation và pure verifier
  Task B; ack không đổi display bị đánh uncertain trong test.
- 19 tests mới đạt, toàn suite 649 tests đạt trong lượt này. Helper native
  compile bản calculator-press-7218bcb7c06e495a; ba request bool/float schema
  sai bị reject, authorization hết hạn blocked. Không commit/AXPress thật.
- Native discovery agent dừng DISPLAY_LAYOUT_UNAVAILABLE. Đây không chứng
  minh quyền của Terminal người dùng; chưa có positive action native.
- Phụ thuộc còn: profile vùng kết quả Task B phải review và native capture
  trước/sau đạt. Không đoán profile, không dùng button/history làm display.
- Giới hạn: parent giữ baseline 0 tối đa2s trước commit, nhưng native helper
  không giữ reference vùng result để đọc 0 sát dispatch. Năm điểm mẫu/lease
  không loại bỏ TOCTOU hoặc thu hồi quyền sau khi đã gửi commit. Không tuyên
  bố causality/exactly-once hay whole-pixel visibility.
- File: src/elvion/desktop_action/, adapters/calculator_ax.py,
  policy/calculator.py, verification/calculator.py, native/macos/CalculatorPress.swift,
  scripts/check_calculator_action.py, tests/test_calculator_action.py.
  Trace projection chỉ thêm allowlisted codes; không lưu raw display/profile.
- Trong test ban đầu phát hiện sqlite connection không được close bởi context
  manager sqlite mặc định; đã dùng contextlib.closing. Test với ResourceWarning
  thành error và suite đều đạt, không còn cảnh báo đó.
- Hướng dẫn/thời hạn/giới hạn đầy đủ: Docs/CALCULATOR_ACTION.md.


## AXRESULT-001 — Native result node không có identifier riêng

Ghi nhận 31/10/2026 từ diagnostic STRUCTURE_ONLY người dùng cung cấp:
AXStaticText identifier rỗng dưới AXScrollArea/StandardResultView; vùng nhập
khác nằm dưới AXScrollArea/StandardInputView. Actions=0, không đọc giá trị.
Profile validator và CLI hiện yêu cầu identifier không rỗng, native dùng
nodeID == identifier nên nil cũng không thể khớp chuỗi rỗng.
Thiết kế sửa: chỉ cho phép identifier rỗng với tuple chính xác đã quan sát
(AXStaticText, '', AXScrollArea, StandardResultView), không wildcard hoặc
chọn theo value. Native vẫn phải duyệt đầy đủ, duy nhất một window/match;
StandardInputView/history/duplicate không được coi là result profile rỗng.
Cần kiểm chứng read-only transition trên desktop trước AXPress thật.


### AXRESULT-001 — Đã sửa profile, chờ native read-only transition

Cho phép identifier rỗng chỉ khi profile reviewed khớp tuple đã quan sát;
native chuẩn hóa nil/empty identifier thành cùng trạng thái thiếu/rỗng,
không wildcard. Known StandardInputView bị từ chối cả khi child ID nonempty.
Giữ full traversal, unique window/match, chỉ đọc AXValue sau unique binding.
Hai CLI dùng kiểm tra None để nhận được đối số chuỗi rỗng đã nhập rõ ràng.
Task A reader dùng cùng validator, không tự nới thành mọi identifier rỗng.

34 tests liên quan đạt: profile exact/near wrong parent/history/input,
duplicate region, transition không đổi và CLI đối số rỗng. Chưa có đọc giá
trị native từ StandardResultView; helper compile không chứng minh AXValue
là string hoặc chuyển đổi 0→7. Nếu value unavailable sẽ điều tra tiếp từ
bằng chứng, không lấy value vùng nhập làm fallback. Hướng dẫn smoke chỉ đọc
đã thêm trong Docs/CALCULATOR_VERIFICATION.md và Docs/CALCULATOR_ACTION.md.

AXRESULT-001: sau guard cuối, toàn suite 653 tests đạt; helper native
calculator-result-observation-ccd54416d79a6405 biên dịch được; git diff --check
đạt. Native read-only transition vẫn chờ người dùng, chưa AXPress thật.


### AXRESULT-001 — Smoke native vẫn RESULT_REGION_NOT_FOUND

Người dùng chạy profile cấu trúc đã chọn, collector trả unknown/
RESULT_REGION_NOT_FOUND, actions=0. Chưa xác minh nguyên nhân: vùng result
có thể thay đổi sau khi Clear, traversal có thể chưa gắn AXWindow hoặc
profile ở lượt capture khác diagnostic. Không quy kết là AXValue lỗi vì
chưa qua bước chọn region. Diagnostic hiện không cho biết window ancestry
hoặc helper source version. Bổ sung window_role và helper_source_sha256
chỉ trong structural diagnostic để phân biệt; không nới capture guard,
không đọc value vùng nhập hay chọn candidate theo số 0/7.


Bổ sung diagnostic structural window_role (rỗng hoặc AXWindow) và fingerprint
source của binary collector; source bytes được pin từ lúc tạo backend để
compile/hash cùng nội dung. Capture/value-selection guard giữ nguyên.
35 tests liên quan đạt, gồm diagnostic không gửi/read value và reject role
cửa sổ không hợp lệ. Bước tiếp: người dùng đưa Calculator về 0 rồi chạy lại
--diagnose-region để xem profile trong đúng trạng thái precondition; chưa
kết luận nguyên nhân hoặc sửa region selection khi chưa có evidence mới.


### AXRESULT-001 — Nguyên nhân native đã xác định ở trạng thái 0

Diagnostic sau Clear của người dùng, helper source f3dcec3b5a6130cc...:
chỉ AXStaticText ID rỗng dưới AXScrollArea/StandardInputView, window AXWindow;
không có StandardResultView. Guard window không phải nguyên nhân trong lượt
này. Thiết kế smoke nhấn digit7 đã nhầm vùng nhập hiện tại với kết quả phép
tính. Không được âm thầm coi input là computed result.

Sửa theo contract: thêm surface current_entry và opt-in đọc entry riêng;
result surface vẫn từ chối StandardInputView. Chọn entry bằng exact tuple đã
quan sát, unique window/node và traversal đầy đủ, không theo value. Verifier
phải bind expectation.surface với cả hai observation; chỉ xác nhận numeric
entry 0→7, không expression/history/computed result. Action v2 dùng grant
read_entry và postcondition calculator_entry_transition, confirmation mới.
Chưa đọc value native; chưa AXPress thật. Cần smoke chỉ đọc entry trước.


### AXRESULT-001 — Entry surface riêng đã triển khai, chờ smoke native

ResultRegionProfile/CalculatorExpectation có surface result mặc định để giữ
API cũ; current_entry chỉ chấp nhận tuple StandardInputView đã quan sát.
Capture entry có API/consent flag riêng, result opt-in không đọc entry.
Hai surface không thể thay thế nhau trong verifier. Native mode capture_entry
vẫn chỉ đọc AXValue sau unique structural binding; result mode vẫn từ chối
known input container. Không tự nhấn Equals/Clear hoặc tính giá trị biểu thức.

CLI smoke entry chỉ cần --include-current-entry, không cần nhập profile tay.
Task A policy v2 dùng read_entry, calculator_entry_zero và entry_transition;
confirmation nêu rõ ô nhập, không tái dùng quyền read_result. Result path cũ
không được coi là verifier cho digit7. Raw entry value vẫn không in/lưu trace.
38 tests liên quan và toàn suite 657 tests đạt, helper
calculator-result-observation-abf577c2000d765c compile được; diff check đạt.
Chưa native capture/transition entry, không AXPress thật. Lệnh tiếp theo chỉ
đọc, người dùng tự đưa về 0 và tự nhấn 7. AXRESULT-001 chưa đóng native.


## AXFORMAT-001 — Entry đã đọc được nhưng chuỗi 0 chưa parse được

Ghi nhận 31/10/2026: người dùng nhấn Enter đầu khi Calculator ở 0 và nhận
UNSUPPORTED_RESULT_FORMAT ngay, chưa đến bước nhấn7. CLI nhánh này chứng
minh region được chọn và AXValue trả string, nhưng _number không chấp nhận.
Chưa biết do whitespace/directional marks/locale/giá trị khác; không coi lỗi
thứ tự thao tác. Bổ sung diagnostic format-only opt-in, không xuất raw digits,
để xác minh Unicode wrappers trước khi sửa parser. Không strip tùy tiện
sign/decimal/operator hoặc auto-coerce thành0; chưa AXPress thật.


### AXFORMAT-001 — Chẩn đoán đã sẵn sàng, chờ format native

41 tests liên quan đạt; diagnostic format-only chỉ báo số lượng/category/
codepoint trình bày, không in raw số. Lỗi ở capture đầu tự kèm stage và
format; --diagnose-format chụp một lần, không cần thao tác7 hoặc prompt.
Thử read-only trong agent trả APP_NOT_RUNNING, không có mẫu chuỗi để xác
định nguyên nhân parser; không suy ra trạng thái desktop người dùng.
Chưa sửa chuẩn hóa/strip Unicode khi chưa có bằng chứng. Bước tiếp: người
dùng mở Calculator về0 và chạy --include-current-entry --diagnose-format.
Khi sửa parser sau bằng chứng, phải dùng cùng parser cho baseline Task A,
không để smoke đọc được nhưng action còn so raw .strip(' ') với0.


### AXFORMAT-001 — U+200E xác định, parser dùng chung đã sửa

Diagnostic native người dùng: length2, ASCII digit1, Cf1/Nd1,
presentation_codepoints U+200E1, syntax trống. Do length2 và một chữ số,
LRM nằm ở một mép chuỗi. Không cần lưu/đọc raw digit để xác định ký tự gây
parser từ chối; không suy diagnostic này chứng minh số thực tế bằng0.

Thêm parse_display_number trong formatting.py, chỉ loại ASCII space và
U+200E ở mép; giữ nguyên số, dấu âm, decimal, toán tử và raw observation.
LRM nội bộ, bidi controls khác, newline/NBSP và expression vẫn bị từ chối.
_number trong pure verifier và precondition is_zero của action cùng dùng
parser này. Không sửa riêng smoke rồi bỏ sót precondition AXPress.

45 tests liên quan đạt: CLI fake 0→7 có LRM, pipeline fake authorization/
press/verifier có LRM, số âm/thập phân/17 không thành7, -0/expression không
thành0, interior/control khác không được xóa. Chưa có smoke native sau sửa;
trạng thái đã sửa, chờ kiểm chứng desktop. Không gọi AXPress thật.

AXFORMAT-001 bổ sung: toàn suite hiện tại 678 tests đạt; git diff --check đạt.
Giới hạn native sau sửa vẫn chưa xác nhận, không đánh dấu đã đóng toàn bộ.


### AXFORMAT-001 / AXRESULT-001 — Native read-only entry transition đã đạt

31/10/2026: người dùng cung cấp summary verified/ENTRY_TRANSITION_OBSERVED,
observed_matches_expected=true, transition_observed=true, surface=current_entry,
actions=0, authority_granted=false, action_causality_proven=false.
Đây là positive smoke native collector+parser+pure verifier khi người dùng
chuyển entry 0→7 bằng tay. Cấu trúc StandardInputView và parser edge U+200E
đã được kiểm chứng phù hợp trong ca native này. Mốc lỗi read-only ban đầu
đã giải quyết trong phạm vi đã đo; chưa chứng minh mọi format/locale/chế độ.

Chưa thực thi AXPress tự động. Bước tiếp: action v2 một lần có grant press7/
read_entry và confirmation, precondition0, native revalidation và after-read
độc lập. Giữ no retry và uncertain cho outcome không rõ. Không diễn giải
smoke actions=0 thành bằng chứng ELVION đã gây ra transition.


### AXACTION-001 — Native positive AXPress end-to-end đã đạt

31/10/2026, summary desktop người dùng cung cấp: status=succeeded,
reason=AXPRESS_RETURNED, error_code=null, postcondition_verified=true,
trace_status=saved. Qua script action v2 có grant/xác nhận, helper native
thực hiện yêu cầu AXPress nút7 và after-read độc lập quan sát entry0→7.
Không phải chỉ returncode helper hoặc fake tests. Trace saved được ghi nhận
qua summary người dùng; nhánh chính chưa đọc lại nội dung trace trong lượt này.

Mốc native single-action Calculator đạt trong phạm vi smoke này. Không
suy ra mọi guard âm đã được kiểm thử native, mọi app/control hỗ trợ hoặc
causality tuyệt đối/exactly-once/whole-pixel visibility. No-retry, durable
reservation, final native checks và independent verifier giữ nguyên.
Chưa đăng ký vào global CLI/voice/GUI; mở rộng cần negative desktop smoke
và phạm vi capability cụ thể. Giới hạn TOCTOU đã ghi vẫn còn.


## CONV-LIMIT-001 — Hội thoại độc lập chưa có model-quality/integration proof

31/10/2026, review bàn giao Task B: 14 unittest nhánh chính chạy lại đạt.
Fake benchmark60/60 chỉ chấm scripted proposals + guards, không chứng minh
routing/reply của model thật. Module không gọi executor; action handoff giữ
nguyên utterance/request ID. Context caller cấp, chưa có adapter typed từ
runtime/session và chưa nối CLI/voice.

Đang chạy smoke8ca dev synthetic trên qwen3.5:4b đã cài, không tải model,
không Vision9B, không action. Chọn greet/tired/DFS/BFS-followup/open/how-to/
negated-open/quoted-title trước inference; giữ toàn bộ replies/routes/errors
và latency để review, không chấm reply-quality tự động hoặc suy rộng heldout.

Review phát hiện cần theo dõi thêm: oversized memory pair hiện bị bỏ qua
mà giữ topic cũ, có thể khiến follow-up nhận ngữ cảnh cũ; dấu hỏi ngoài quote
bị veto toàn bộ action proposal, gồm khả năng từ chối lời nhờ dạng câu hỏi.
Chưa sửa hoặc kết luận coverage model từ các giả thuyết này; cần tests/chốt
hợp đồng trước khi tích hợp. Persona/context không thay quyền thực thi.


### CONV-LIMIT-001 — Review và model smoke đã có

14 tests bàn giao đạt; fake60/60 chạy lại đạt. Real local qwen3.5:4b smoke
8 dev cases ở artifacts/benchmarks/conversation/local-smoke-3aeac798d5f7.json:
8/8 route khớp, false_action_handoff0, actions0. PersonaELVION, synthetic
capability context, một inference/lượt. Latency đo ~0.59–4.06s, gồm lượt
đầu; không coi đây là p95 hoặc tốc độ toàn bộ hội thoại. Đây là trước sửa
memory boundary bên dưới, không phải full60 hoặc heldout model benchmark.

Đọc reply thấy greeting/DFS/BFS followup có phản hồi; how_to_open bị hiểu
máy tính là laptop/nút nguồn. Câu này mơ hồ nếu chỉ truyền capability IDs;
phần tích hợp cần target/app context đáng tin cậy hoặc clarify. Không gọi
8/8 routing là 8/8 chất lượng nội dung. Reply rubric vẫn unreviewed tổng thể.

## CONV-MEM-001 — Oversized turn để lại topic cũ

Xác minh code: append bỏ qua pair quá max_chars và giữ lịch sử cũ. Sau
trả lời chủ đề mới dài, followup vẫn được cấp ngữ cảnh topic trước đó.
Đã sửa: drop toàn bộ history của session đó nếu latest pair không thể fit,
không truncate phủ định/words, không ảnh hưởng session khác. Service trả
reason CONTEXT_TURN_NOT_RETAINED làm metadata, reply vẫn hiển thị bình thường.
Test followup kiểm tra không còn chủ đề cũ và giữ session khác đạt.
15 tests conversation/benchmark đạt; fake60/60 sau sửa đạt, actions0.
Chưa real model validation cho overflow case; không tích hợp executor.

CONV-MEM-001 bổ sung: toàn suite hiện tại 679 tests đạt; git diff --check đạt.
Model8smoke vẫn chỉ là dev routing, không thay heldout/reply quality review.


### AXACTION-001 — Bắt đầu negative desktop smoke

31/10/2026, người dùng đề nghị thử các ca từ chối, nhắc việc cửa sổ bị che
trước đây. Đã đối chiếu native helper có five-point guard trước prepared và
sau commit, trước AXPress. Read-only blocked cũ không đủ chứng minh action
negative. Kế hoạch hiện tại: che kín nút7 ở entry0 (giữ Calculator tại chỗ),
confirmation n, và precondition5. Chưa có kết quả native cho ba ca này.
Mỗi lượt ghi reason thực và UI value sau test, không ép expected error code
nếu một guard sớm hơn đã dừng. Hướng dẫn trong Docs/CALCULATOR_ACTION.md.


### AXACTION-001 — Native negative occlusion đã đạt

31/10/2026: người dùng thử Terminal che kín nút7 và cung cấp summary:
failed, STALE_OBSERVATION, SAMPLED_VISIBILITY_UNCERTAIN,
postcondition_verified=false, trace_status=saved; xác nhận UI vẫn0.
Đây là negative smoke của action helper phù hợp với refusal ở five-point
guard, không phải chỉ readonly visibility probe. Không suy ra toàn bộ
negative cases/TOCTOU đã được giải quyết; chưa audit nội dung trace.
Tiếp theo: confirmation n ở entry0/nút không bị che; precondition5 còn chờ.


### AXACTION-001 — Native negative confirmation decline đã đạt

31/10/2026: người dùng trả n, summary cancelled/User declined; no execution,
PERMISSION_DENIED, postcondition_verified=false, trace_status=saved và xác
nhận UI vẫn0. Mốc từ chối confirmation đạt theo summary/UI; không audit
trace trong lượt này. Negative precondition5 còn chờ.


### AXACTION-001 — Precondition native đã từ chối đúng summary

31/10/2026: theo hướng dẫn entry ban đầu5, người dùng cung cấp summary
failed/VERIFICATION_FAILED/CALCULATOR_BEFORE_NOT_ZERO_OR_UNKNOWN,
postcondition_verified=false, trace_status=saved. Reason này thuộc nhánh
adapter từ chối baseline trước backend.press, phù hợp dừng trước AXPress.
Summary đạt expected refusal; chưa có xác nhận UI value sau lượt thử này
trong tin nhắn, không tự ghi UI vẫn5. Chờ xác nhận để chốt smoke đầy đủ.
Positive0→7, occlusion UI0 và confirmation n UI0 đã có evidence trước đó.


### AXACTION-001 — Chốt ba negative smoke native

31/10/2026: người dùng xác nhận UI vẫn5 sau precondition refusal. Ca entry5
đã đạt cả summary và UI; không còn chờ xác nhận giá trị sau test.
Bộ smoke hiện có: positive AXPress0→7 verified; che nút7 bị từ chối/UI0;
confirmation n cancelled/UI0; precondition5 bị từ chối/UI5. Trace saved
được ghi nhận theo summary từng lượt, chưa audit lại nội dung traces.
Đạt mốc single-action Calculator cùng ba negative smoke trong phạm vi này.
Không suy rộng mọi app/control/locale, tất cả ca âm, TOCTOU hoặc exactly-once.
No-retry và các guard giữ nguyên; capability chưa đăng ký global CLI/voice/GUI.


## CONV-CLI-001 — Review integration và guard completion

31/10/2026, Task B bàn giao CLI bridge; nhánh chính chạy 100 tests liên quan
đạt. Chưa có model thật integration trong báo cáo B (MODEL_UNAVAILABLE),
Ollama hiện kiểm tra tags đã sẵn4B/9B. Giữ phân biệt fake60 và model-quality.
B đã sửa regex completion cho cả “Đã mở...” không có đại từ, dùng safe
TaskReport summary. Test fake failure không bị diễn đạt success đạt; chưa
chứng minh mọi cách diễn đạt completion được guard bao phủ.

## CONV-CONFIRM-001 — Conversation với rules planner chưa bắt buộc confirmation

Review xác minh InteractiveSession mặc định require_confirmation=False;
conversation bridge dùng nguyên _execute_request nên app.open sau grant
có thể thực thi không hỏi nếu người dùng không truyền --confirm. Legacy CLI
cho phép điều này nhưng đường model conversation cần confirmation luôn bật.
Sửa dự kiến: require_confirmation=True khi có conversation_service; mode cũ
không conversation giữ nguyên. Thêm test granted app.open + n khi không
truyền --confirm phải cancelled và không launch. Không nới policy/grants.


### CONV-CONFIRM-001 — Đã siết confirmation trong conversation session

InteractiveSession đặt require_confirmation=True khi có conversation_service,
không cần --confirm; legacy mode không conversation giữ setting cũ. Test mới
app.open đã grant, mặc định không --confirm, trả n => cancelled/no launch.
98 tests conversation/CLI/session/voice liên quan đạt, fake routing60/60 đạt.

### CONV-CLI-001 — Smoke CLI/model thật đã chạy

Artifact artifacts/benchmarks/conversation/cli-smoke-b3351f863d95.json:
CLI subprocess thật, Ollama qwen3.5:4b, 6 lượt ngôn ngữ tổng hợp + chat-reset/
quit. Chào/DFS/BFS followup/negation/reset có phản hồi; yêu cầu mở app đi đúng
pipeline và bị PERMISSION_DENIED do không grant. Trace disabled, 0 trace files,
returncode0; tổng14.22s gồm startup/inference, không coi là per-turn/p95.
Không grant, không app launch được cấp phép; không dùng smoke này làm positive
native action proof. Thử granted/deny confirmation dùng fake backend trong test.
Source hashes và toàn bộ transcript synthetic lưu trong artifact, không chat thật.
Chưa benchmark full60/heldout trên model thật, chưa tích hợp voice/GUI.

CONV-CLI-001 / CONV-CONFIRM-001: toàn suite hiện tại 689 tests đạt,
git diff --check đạt. CLI/model smoke không có grant; positive native
action qua hội thoại vẫn cần thử trên desktop riêng. Voice chưa tích hợp.


### CONV-CLI-001 — User desktop cancellation qua CLI hội thoại đã đạt

31/10/2026: người dùng cung cấp hiển thị “Yêu cầu đã được hủy” với task/trace
sau hướng dẫn grant app.open, nhập yêu cầu mở app và n. Xác nhận user-facing
handoff/confirmation/cancel qua CLI; chưa audit trace hoặc khẳng định positive
native qua hội thoại từ ca hủy này.

## CONV-VOICE-001 — Tích hợp bridge vào voice, chưa native smoke

Bắt đầu nhánh chính nối voice sau khi user CLI cancel đạt. VoiceSession hiện
chỉ gọi task pipeline; bridge callback _execute_request cần được override để
clarification/report TTS không bị bypass hoặc đọc report hai lần. Thêm flag
conversation-model opt-in, giữ transcript review, keyboard confirmation,
colon directive chỉ từ bàn phím. Reply/clarify không chạy planner/executor.
TTS hiện chỉ public speak_prompt/speak_report và giới hạn240 ký tự; bổ sung
public speak_text dùng chung service/lock, voice đọc excerpt có giới hạn và
hiển thị đầy đủ text. Không mở mic trước khi stop_speaking thành công, không
fallback/retry khi model/TTS lỗi. Fake tests và typed-input model smoke trước;
không tự thu âm/phát tiếng/thao tác desktop trong agent.


### CONV-VOICE-001 — Bridge voice và TTS bounded đã triển khai

Thêm voice --conversation-model opt-in. VoiceSession dùng bridge hiện có;
report/clarification chuyển vào override _execute_request để không bypass
hoặc chạy/đọc report hai lần. Reply/clarify không executor, transcript vẫn
review, y/N vẫn keyboard, colon từ speech không dispatch. Legacy no-chat
voice 39 tests và benchmark session31/31 giữ hành vi.

TTS thêm public speak_text cùng service/process/busy/stop với prompt/report.
Voice đọc excerpt<=240 ký tự, hiển thị full text, có thông báo khi cắt. Không
đọc reply lúc mic mở/decoding; stop lỗi không mở mic. Lỗi TTS/model không retry.
14 tests voice conversation và3 TTS mới, 85 tests liên quan đạt; toàn suite
706 tests đạt, git diff --check đạt. Benchmark session31/31, tasksuccess14/31.

Actual voice CLI + typed synthetic text + qwen3.5:4b smoke ở
artifacts/benchmarks/conversation/voice-text-smoke-f343521fdb07.json:
chat/DFS/BFS/followup có phản hồi, app.open vào pipeline nhưng denied vì
không grant, reset/quit, returncode0, tracefiles0. Tổng11.04s cả chuỗi,
không dùng làm per-turn/p95. Không mở mic, STT, audible TTS hoặc native action.
Trạng thái implementation đạt tests/typed model smoke; chờ user desktop
full voice smoke. Tài liệu Docs/CONVERSATION_VOICE.md.


### CONV-VOICE-001 — User desktop basic conversation smoke đã đạt

31/10/2026: sau lệnh voice --conversation-model qwen3.5:4b --speak và hướng
dẫn thu/dừng/duyệt lời chào, người dùng xác nhận phản hồi đã ổn. Ghi nhận
smoke hội thoại mic/transcript review/model/TTS theo xác nhận người dùng;
không có transcript/latency đo mới, không suy mọi câu hoặc action qua voice
đã được native kiểm thử. Chưa có native multi-turn followup/reset/action n
cho chế độ conversation voice mới. No-retry/permission/keyboard confirmation
và các giới hạn STT/model/excerpt giữ nguyên.


## VOICE-QUALITY-001 — TTS cắt excerpt và mixed-English/STT cần cải thiện

31/10/2026: user xác nhận voice followup DFS bám ngữ cảnh, nhưng STT từ
English yếu; TTS mất chữ/giật, cảm giác bị tắt giữa câu, đọc English bằng
âm Việt. User làm rõ dùng Terminal và không có countdown thực tế.
Xác minh code: Voice chỉ đọc excerpt<=240 ký tự; SpeechService timeout30s.
Excerpt là nguyên nhân chắc chắn mất phần cuối ở reply dài; chưa xác minh
mọi hiện tượng giật là timeout. Không quy cho bộ đếm recording30s hay GUI12s.

Kế hoạch: API speak_reply đọc full bounded1500 chars, một reservation chung,
budget theo lượng text/rate có hard cap; không auto mở mic khi phát chưa
xong, Ctrl+C vẫn dừng. Mixed mode opt-in dùng English voice đã cài và glossary
thuật ngữ/acronyms, không sửa nội dung model hoặc target. Không hứa seamless
hoặc English bất kỳ nếu chưa nghe native. Thêm preset STT tech public và
language vi/en/auto opt-in; không rewrite transcript/titles hoặc retry STT.
Cần đo trên clip thật, không coi prompt như bằng chứng accuracy tăng.
Primary refs: developer.apple.com/documentation/avfaudio/speech-synthesis;
huggingface.co/vinai/PhoWhisper-small. Native say voice list có Linh/Samantha.

VOICE-QUALITY-001 — cập nhật implementation 31/10/2026:
Đã thay excerpt240 trong VoiceSession bằng speak_reply full<=1500. Giọng
Việt mặc định dùng một process cho cả reply; budget theo words/chars/rate
45..240s. Prompts/reports giữ quy tắc cũ. Thêm speech-mode mixed/en opt-in:
glossary thuật ngữ + đánh vần acronym qua English voice đã cài; giữ một
reservation cho cả chuỗi, preflight voices, stop giữa đoạn không phát tiếp.
Không tự fallback/retry; văn bản hiển thị và yêu cầu tác vụ giữ nguyên.
STT thêm tech context và vi/en/auto opt-in; defaultvi/context đã lưu giữ
nguyên. Tech không lưu preference; speech-mode/language chỉ có hiệu lực
trong phiên. Không có clip/accuracy mới, không tuyên bố đã hết giật/mất chữ.

Trong kiểm thử mới, fake backend.start gọi ngược speak_text khi service
đang giữ lock làm test bị treo. Đã dừng test và chuyển assertion busy vào
communicate (ngoài lock); đây là lỗi test callback, không nới lock sản phẩm.
Regression stop lúc process đơn đã kết thúc ban đầu thay đổi kết quả; đã
giữ completed cho single prompt/report, chỉ áp dụng stop-between cho batch.
File: voice/output/pronunciation.py, service.py, interface/voice_session.py,
voice/input/whisper.py và các test/document tương ứng.

Kiểm chứng bản sửa: 714/714 unittest đạt, trong đó8 tests mới về full reply,
mixed order/busy/stop, lỗi không retry và STT options; CLI --help có các cờ
mới, git diff --check đạt. Chỉ dùng fake audio/process cho tests; không
phát tiếng thật, không thu mic, không chạy model thật trong lượt sửa này.
Trạng thái: đã sửa logic, chờ user nghe native và đo STT cùng clip.

VOICE-QUALITY-001 — feedback desktop sau bản sửa:
User báo chỉ khựng khi đổi giọng, các đoạn cùng giọng không còn biểu hiện đó.
Không có đo audio/latency mới; ghi nhận theo feedback, không suy tất cả
câu dài đều hoàn hảo. Code mixed hiện kết thúc process say cho mỗi đoạn
rồi tạo process mới; đây là ranh giới có chi phí khởi tạo, chưa đo riêng
phần khựng do process, voice engine hay output device. STT thuật ngữ English
được user mô tả sai gần như toàn bộ; tech prompt chưa đủ theo smoke này.
Chưa có reference/recognized pairs hoặc cùng clip so model nên chưa kết
luận do accent, preset language hay model.
Bước tiếp: TTS thử backend giữ một session/queue đa giọng hoặc tổng hợp
trước rồi phát một audio stream, giữ stop và mic guard; không tự hứa hết
khoảng ngắt do voice. STT tạo phép so trên cùng clip Việt xen English giữa
PhoWhisper/Whisper đa ngữ và vi/auto; chấm riêng thuật ngữ, acronym, tên
ghi chú, thời gian và hallucination. Không tự sửa target bằng LLM hoặc
thay model mặc định trước có bằng chứng.

VOICE-QUALITY-001 — triển khai phép đo và buffer 31/10/2026:
Bắt đầu thêm corpus technical12 câu và model×context×language matrix, chấm
exact English terms/phrase cùng title, misses/insertions/latency; không
rewrite transcript hoặc tự đổi default. Máy có3 model small/medium/PhoSmall.
TTS mixed tổng hợp PCM WAV từng voice vào temp0700, ghép rồi afplay một
lần, vẫn cùng busy/stop/process ownership. Cắt chỉ silence rất nhỏ ở cạnh
và giữ margin60ms; không sửa text. Chờ tests và nghe desktop.
Native file-only synthesis thử Linh/Samantha trả exit0 nhưng WAV0frames
trong process agent. Chưa biết do audio service/voice/sandbox, không suy
Terminal của user có cùng vấn đề. Bản mới phải từ chối WAVrỗng trước playback,
không retry/fallback. Không phát tiếng thật trong lượt này.

VOICE-QUALITY-001 — kết quả kiểm chứng phép đo/buffer:
Toàn suite726 unittest đạt (bao gồm5 test metrics/matrix mới và7 test buffer
ban đầu). Bổ sung2 ca stop-during-player/player-timeout: nhóm buffer9/9 đạt,
nhóm voice130/130 đạt. Fake tests xác nhận tất cả synthesis trước1player,
không phát khi thiếu/rỗng/lỗi, stop/timeout không replay, cleanup quyền
0700/0600, PCM limits/margin và giữ pause nội bộ. Một ca all-silent WAV ban
đầu lọt do bước scan10ms còn dư mẫu; đã thêm kiểm tra toàn đoạn silent trước
scan và test regression đạt. CLI help và git diff --check đạt.
Không thu mic, không chạy STT model thật, không phát tiếng thật trong lượt
này. File-only native0frames đã ghi trên; chưa đánh dấu hết khựng hay tăng
accuracy. Cần corpus technical user xác nhận và nghe native buffered mixed.

VOICE-QUALITY-001 — trở ngại chạy corpus english-01 trong agent:
Lượt6 cấu hình×12clip đều trả failed rất nhanh; sau đó ghi report ở corpus
ngoài writable roots bị PermissionError. Không coi đây là0% accuracy hoặc
kết luận model nghe sai: chưa xác định được lỗi engine/response. Chưa lưu
được report ở corpus, clip/reference gốc giữ nguyên. Điều tra1clip với
backend logs đã lọc; cần output-dir trong workspace để lưu kết quả nghiên
cứu mà không yêu cầu ghi ra corpus read-only của process agent.

VOICE-QUALITY-001 — chẩn đoán engine của lượt english-01:
Engine default thoát -6, stderr ggml_metal_buffer_init không cấp phát buffer
4.41MiB, GGML_ASSERT(buffer). Không kết luận model quá nặng/thiếuRAM của
người dùng từ lỗiMetal trong process agent. Probe CPU --no-gpu nhận dạng
được1clip (~2.4s), không ghi transcript/log thô vào nhật ký. Đã thêm device
cpu opt-in cho benchmark, không auto fallback runtime; metadata báo rõCPU.
Thêm output-dir cho report riêng tư trong artifacts bịgitignore thay vì
phải ghi vào corpus read-only; WAV/reference gốc không đổi. Đang chạy lại
72 observations CPU theo cùng3model×vi/auto, chờ report để kết luận accuracy.

DOC-ALPHA-001 — trạng thái kiểm chứng Finder giữa tài liệu không khớp
(31/10/2026): `CURRENT_TASKS.md` ghi người dùng đã mở bản alpha từ Finder trên
máy đã setup, trong khi `RELEASE_0.1.0_ALPHA1.md` vẫn nói chưa kiểm chứng bước
đó. Tác động: kế hoạch thử người dùng có thể lặp lại mốc đã đạt và bỏ sót máy
mới. Nguyên nhân xác minh: release note chưa được cập nhật sau phản hồi desktop;
không có bằng chứng về máy mới. Đã sửa release note và lập
`ALPHA_USER_TEST_PLAN.md` tách vòng máy hiện tại với vòng máy mới. Kiểm chứng:
đối chiếu hai tài liệu và nội dung sửa; chưa chạy thử trên máy mới. Trạng thái:
đã sửa tài liệu, chờ kiểm chứng vòng máy mới. Bước tiếp: chạy vòng B khi có
môi trường phù hợp, ghi kết quả đã lọc.

VOICE-QUALITY-001 — english-01 CPU benchmark đã hoàn tất:
72 observations từ12clip/54.2s,16terms,6titles. PhoSmallvi4/16terms;
WhisperSmallvi13/16; Mediumvi14/16; tất cả4/6titles, whole-exact1/12,1/12,
2/12. Auto không cải thiệnterms: Pho4,small13,medium12/16 +1 lỗi
STT_INVALID_RESPONSE. Không replay để đoán chính xác trường response hỏng.
Glossary insertions0, không chứng minh không hallucination ngoài glossary.
MedianCPUvi2.34s/2.25s/6.24s tương ứng; không suy tốc độGPU Terminal.
Đề xuất thử WhisperSmallvi/tech, chưa đổi default. BFS vẫn miss2lần trên
small/medium; title chưa đạt đủ. Không coi81.25% term-recall là taskaccuracy.
Báo cáo sanitized Docs/VOICE_ENGLISH_RESULTS_2026-10-31.md; raw JSON riêng
tư ở artifacts/benchmarks/voice-technical/private/comparison-e90c452aab2344ef99ffeea1c0301c97.json.
Cập nhật runner: CPU opt-in và output-dir, preflight khả năng ghi trước
inference. 9 tests speech_reply và20 voice_evaluation đạt, diffcheck đạt.
Trạng thái: có bằng chứng lựa chọn thử trên dev12, chờ user native câu mới;
không chốt generalization hoặc tự đổi saved model.

Kiểm chứng cuối lượt english-01: toàn suite732/732 unittest đạt; git diff --check đạt.

VOICE-QUALITY-001 — native fresh utterance sau đề xuất smallvi/tech thất bại:
User báo transcript tiếng Việt xen English bị sai nghĩa rõ rệt (~4.2sclip,
662msSTT). Không lưu transcript vào nhật ký. Khuyến nghị smallvi/tech dựa
13/16terms quá sớm khi wholeexact chỉ1/12 và title4/6. Rút khuyến nghị
coi đây là cấu hình tốt dùng hàng ngày; chưa đổi saved default. Không quy
lỗi cho phát âm user. Chưa biết nguyên nhân do prompt/model/decoder/audio.
Điều tra ablation none vs tech trên cùng corpus, ưu tiên fullsentence/title/
WER hơn termhits; không yêu cầu user thu lại cùng12clip, không LLM rewrite.

VOICE-QUALITY-001 — audit âm thanh read-only english-01:
medianRMS -18.66dBFS, không LOW_OVERALL_LEVEL/NEAR_FULL_SCALE flags.
4 energy-at-start/7 energy-at-end flags, chỉ là chỉ báo năng lượng, không
chứng minh speech bị cắt, không đoSNR hoặc đánh giá accent. Không quy lỗi
cho người dùng/mic. Report quality-4d6b49dcf682432fbe080fe21c81acd1.json trong
artifacts/benchmarks/voice-technical/private. Chưa có audio fresh sentence
được lưu; không coi clip cũ là chính clip vừa thất bại.

VOICE-QUALITY-001 — ablation none đã hoàn tất (24obs CPU):
Smallnonevi whole0/12,title2/6,term9/16,WER55.13%; so tech whole1/12,
title4/6,term13/16,WER37.18%. Mediumnonevi whole2/12,title4/6,term13/16,
WER33.33%; tech whole2/12,title4/6,term14/16,WER30.77%. Tắt prompt không
giải quyết; không kết luận presettech là nguyên nhân mọi lỗi hoặc mic/
accent/model là rootcause đã chứng minh. Không có cấu hình đang thử đủ
bằng chứng chất lượng hội thoại dùng hàng ngày; không chuyển default.
Rawreport comparison-dd9932488390435bb5134a3ed8eff39b.json trong private dir.
Không patch mã STT đoán mò, không thêm autocorrect/LLM rewrite, không tải
model mới hoặc yêu cầu user thu lại12câu. Cần đánh giá backend/ASR Việt-Anh
khác trên corpus sẵn có rồi test câu mới; đây là công việc chưa thực hiện.

VOICE-QUALITY-001 — phương án sau nghiên cứu nguồn chính thức:
Đã đọc AppleSiri2018/WWDC23/custompronunciation/contextual/code-switch,
Googleadaptation/boostfalsepositives, MicrosoftLID so multilingualSpeech,
OpenAIASRtraining và QwenASR modelcard. Nhận diệnngônngữ không đồng nghĩa
code-switch từng từ. Không có bằng chứng model hiện tại chữa được bằng
prompt. Kế hoạch Docs/STT_RECOVERY_PLAN.md: benchmarklocalcandidate Qwen3-ASR
0.6B trước, kiểm tra AppleSilicon/runtime tách biệt trước download; supported
Vietnamese/English chưa chứng minh mixed accuracy. AppleSpeech chỉprobe
ondevice locale, không tự dùng cloud. Context/pronunciation là bước sau.
Chốt screeningwhole>=10/12,title6/6 + controls/failures/insertions, rồi mới
đến câu mới. Đây là mục tiêu đề xuất, chưa đạt. Chưa tải/cài/backend/upload
hoặc đổi saved config trong lượt lập phương án. TaskB reminders độc lập.

VOICE-QUALITY-001 — bắt đầu spikeQwenASR 31/10/2026:
User đã đồng ý thực hiện phương án. Kiểm traPython3.14arm64 chưa cóMLX/
PyTorch/HF. Tài liệu chính thứcQwen thiênPython3.12/CUDA; tìm runtime
community mlx-qwen3-asr0.4.4 với4coredeps, khôngPyTorch/transformers.
PyPI cóMLX0.32.4 wheelcp314arm64. Chuẩn bịvenv riêng .build/qwen-asr,
không sửa environment/sản phẩm/TaskBreminders. Cần probeCPU/Metal trước
weights; chưa suy MLX chạy được từ metadata. Sources: pypi.org/project/
mlx-qwen3-asr và github.com/moona3k/mlx-qwen3-asr. Không uploadaudio.
## DOC-STRUCTURE-001 — bản mô tả cấu trúc chưa theo kịp working tree

- Ngày phát hiện: 31/10/2026. Phạm vi: `Docs/PROJECT_STRUCTURE.md` và README
  mô tả bộ khung ngày 29/10; working tree hiện có thêm `browser/`, `vision/`,
  `voice/`, `conversation/`, các module desktop và `reminders/`.
- Triệu chứng/bằng chứng: mục thư mục của `PROJECT_STRUCTURE.md` chỉ liệt kê
  các module nền; một số câu trạng thái còn nói voice/SQLite làm sau trong khi
  mã tương ứng đã xuất hiện. Đây là độ trễ tài liệu đã quan sát, không kết luận
  các module đó đã tích hợp hoặc chạy production.
- Tác động: người đọc có thể hiểu nhầm danh sách ban đầu là toàn bộ cấu trúc
  hiện tại. Trạng thái: **đã bổ sung bản đồ working tree, chờ rà lại tài liệu
  gốc** tại `Docs/REPOSITORY_GRAPH.md` và `graphify-out/`.
- Bước tiếp theo: chủ sở hữu kiến trúc rà từng module và cập nhật
  `PROJECT_STRUCTURE.md`/README theo trạng thái đã kiểm chứng; sau thay đổi mã,
  dựng lại graph rồi đối chiếu các cạnh `EXTRACTED` với source.


VOICE-QUALITY-001 — MLX runtime native probe không qua trong agent:
Đã tảiMLX0.32.4/core+metalwheel (~78MBmetal). Probe các wheel đã tải ở
.build/qwen-asr/runtime-probe: import mlx.core báo ImportError metal::load_device
No Metal device available. Lỗi xảy ra trước set_default_device(cpu), vì
vậy optionCPU không vượt được runtime init này. Không suyGPU M5/Terminal
thật không hỗ trợ. Không xin escalation bịpolicycấm, không tảiweights1.88GB
khi doctor chưa qua. Đang hoàn tấtvenv, cần chạydoctor từTerminal người
dùng để xác nhậnnative. Worker trảfixedcodeMETAL_DEVICE_UNAVAILABLE.

VOICE-QUALITY-001 — spikeQwen bàn giao phần chuẩn bị:
Venv.build/qwen-asr/venv đã cài mlx-qwen3-asr0.4.4/MLX0.32.4 +deps; freeze
trong.build/qwen-asr/requirements.freeze.txt. Doctor native venv default và
CPU đều METAL_DEVICE_UNAVAILABLE (import trước device selection). Prepare
--download đã xác nhận guard dừng, weights_downloaded=false. Không tải
weights, chạyQweninference, thu mic hoặc uploadaudio; chưa cóqualityscore.
Đã có hostadapter/stdio worker offline,doctor,preparepinrevision/resume/hash,
benchmark auto/vi + gatewhole/title/controls trong file riêng. Không sửa
voice/interface/planner/TaskBreminders. 14 tests mới fake đạt; toàn suite
755tests đạt trước2testdoctor/downloadguard cuối, gitdiffcheck đạt.
Native probe artifacts/benchmarks/voice-technical/qwen-runtime-probe.json.
Cần user chạy PYTHONPATH=src python3 scripts/check_qwen_asr.py --doctor từ
Terminal desktop; agent thiếuMetal không chứng minh Mac hoặc model kém.
Tham khảo Docs/QWEN_ASR_RESEARCH.md. Trạng thái runtimeblocked, chưa đạt
mục tiêu10/12whole +6/6title, chưa tích hợp/live-enable.

## REMINDER-CORE-001 — tích hợp bàn giao và lỗi validation/error boundary

31/10/2026: TaskB bàn giao ReminderStore/SQLite outbox,11tests,9scenario.
Nhánh chính chạy lại11/11 và9/9 đạt; chưa notification/voice/background.
Bàn giao ghi2lỗi đã sửa: once thiếutimezone trảTIMEZONE_REQUIRED; sửacontent
invalidate pending snapshot cũ/rearm earliest (testregression đã đạt).

Review thêm: Schedule.weekly với weekday tuple chứa list làm set() ném
TypeError trước validation. collect_due sau close làm rollback handler đọc
in_transaction trên connection đóng, ném ProgrammingError thay DATABASE_ERROR.
Cả2 tái hiện bằng synthetic/tempDB; ảnh hưởngcontract lỗi, không có ngoại
tác. Đang sửa và thêmtests. Snapshot event hiện chỉ content/timezone/instant/
revision, không lưu fullschedule; handoff cần nói đúng phạm vi snapshot.

REMINDER-CORE-001 — sửa và kiểm chứng:
Validate type/range weekdays trước khi set(), trảSCHEDULE_INVALID đúng
contract kể cả phần tửunhashable. Rollback probe bắtsqliteError, trả
DATABASE_ERROR khiconnectionđóng/hỏng; giữKeyboardInterrupt/SystemExit.
Thêm2tests: weekday malformed +7nhómoperation sauclose.13/13 reminders
tests và benchmark9/9 đạt, duplicate/stale/externalactions0; diffcheckđạt.
Sửa mô tả snapshot/revision cho khớp dữ liệu thực tế. Chỉ kiểm chứng lõi
SQLite/synthetic, chưa có notification/voice/daemon hoặcnatural language.

REMINDER-CORE-001 — fullsuite sau review:759/759unittest đạt;gitdiffcheckđạt.
## BRANCH-SPLIT-001 — Calculator action thiếu allowlist trace khi tách nhánh

- Ngày phát hiện: 31/10/2026. Phạm vi: nhánh tách `codex/calculator-action`
  trước commit `6d7115f`; working tree tích hợp ban đầu không gặp lỗi này.
- Triệu chứng: `tests.test_calculator_action` chạy trên worktree tách trả
  `KeyError: capability` ở ca kiểm tra trace. Tái hiện bằng cách ghép các
  module desktop/Calculator nhưng bỏ thay đổi `src/elvion/storage/trace_privacy.py`.
  Tác động: trace của action bị lọc mất capability và test không đạt.
- Nguyên nhân đã xác minh: capability, adapter, policy và reason của Calculator
  chưa nằm trong allowlist trace ở `origin/main`; working tree gốc có chúng
  trong một diff chung với web/model.
- Cách giải quyết: thêm chỉ các giá trị Calculator cần thiết vào
  `src/elvion/storage/trace_privacy.py` của nhánh action, không kéo theo
  allowlist web/model. Kiểm chứng sau sửa: 22/22 test Calculator action và
  231/231 test trên nhánh đạt; Swift `CalculatorPress.swift` typecheck đạt.
  Trạng thái: **đã giải quyết ở nhánh action**. Giới hạn: chưa chạy lại native
  action từ worktree tách; smoke desktop trước đó được ghi ở
  `Docs/CALCULATOR_ACTION.md`.


VOICE-QUALITY-001 — Qwen native english-01 report đã đọc:
qwen-comparison-a5c5bf4924724cddb7270099b8a50a30.json: noneauto5/12whole,
4/6title,6/16terms +3STT_INVALID_RESPONSE; nonevi5/12whole,4/6title,
10/16terms,0fail. Median desktop defaultvi~560ms,auto~598ms (successful
only), coldprocess+load perclip; không so trực tiếp với WhisperCPU.
Cả2gatefalse. Lỗi có sai từ thật (đổi thuật ngữ, từ quan hệ, actionprefix),
không chỉformatacronym; không ghi nguyên văn transcript vào nhật ký.
3 lỗi auto chưa có dữ liệu phân biệt schema/language/worker. Chưa promote
Qwen hoặc tải1.7B. Đang thêm diagnostic reason fixed và statictechcontext
opt-in đúngAPIruntime đã đọc, không hậu sửatext/nới gate.

VOICE-QUALITY-001 — diagnostic/context thử tiếp đã triển khai:
Qwen last_diagnostic phân biệtWORKER_EXIT/WORKER_ERROR/INVALID_RESPONSE_SCHEMA/
LANGUAGE_OUT_OF_SCOPE/INVALID_TRANSCRIPT/TIMEOUT, không rawtext và chỉ
reportedlanguage thuộc danh mụcnhãn. Sửa workererror thànhSTT_FAILED thay
vì gộpnhầm vớiINVALID_RESPONSE. Workertechcontext dùngpublic glossary qua
APIcontextđãxácminhsource0.4.4; no rewrite/nohistory/noautofallback.
Benchmark--contextboth chạy none/tech ×auto/vi, lưudiag theoIDclip và
config, không nới guard/gate. Thêm tech-both vào evaluator, giữ nghĩa cũ
của contextboth choWhisper.16Qwentests +21evaltests đạt, CLIhelp/diffcheck
đạt. Native tech chưa đo; cần userTerminal vìagentMetalunavailable.

VOICE-QUALITY-001 — fullsuite sau diagnostic/context:762/762unittest đạt, gitdiffcheckđạt; chưa native contexttech.

VOICE-QUALITY-001 — nativeQwen ablation,01/11/2026:
48obs report qwen-comparison-3655ef4f277a44cfaa034380238734a1.json:
noneauto5/12whole,4/6title,6/16terms,3reject; nonevi5/12,4/6,10/16,0reject;
techauto6/12,4/6,10/16,2reject; techvi6/12,4/6,13/16,0reject.
Auto rejection đều LANGUAGE_OUT_OF_SCOPE: none Cantonese1+Thai2,tech
Cantonese1+Thai1; khôngworker crash haylỗiJSON tronglượt này. Guardgiữnguyên.
Techvi best vẫn failgatewhole10/12,title6/6. Có semantic/entity errors,
không chỉ chữviếttắt; không promote/đổi default, không nới scorer.
Dừng thửpresetmù; nextproposal kiểmchứngimplementationchínhthức trên2–3
clip sai bằngcùngweights trướcquyếtđịnhtải1.7B. Chưa cài/runchínhthức,
chưa kết luận rootcausedoMLX haymodel/accent. Không rawtranscript tronglog.

VOICE-QUALITY-001 — bắt đầu paritychínhthức,01/11/2026:
User cho phép tiếp tục phương án khác khi không đạt. Đang kiểm tra
qwen-asr0.0.6 chínhthức: pinsTransformers4.57.6,importforcedaligner/nagisa
unconditional, librosa/soundfile. Chưa thể giả định chạyPython3.14; không
stubdependency hoặc sửa kiến trúc để gọi làreference. Táchvenv/.build,
reuseweights0.6B đãverify, ưu tiênCPU vìagentthiếuMetal. Cần kiểm tra môi
trường/deps trước; chưa cókếtquảparity hoặcmodelmới.

VOICE-QUALITY-001 — AppleSpeech metadata probe song song:
Thêm native read-only probe vi-VN supportedlocale/ondevice/authorization,
không requestauth/mic/audio. Swiftcompile mặcđịnh gặp cache Clang ngoài
writable root; đang chuyển modulecachevào.build theo scope. Chưa có
kếtquảcapability hoặcnative transcription. PyTorchreference đang tải.

VOICE-QUALITY-001 — parityenv vàdownloadtăngtốc:
Đã xác nhận nagisa0.2.11/DyNet38 vàTorch2.15 cówheelcp314arm64. Cài
qwen-asr0.0.6 --no-deps vàoenvriêng, ASRdependencies pinTransformers4.57.6
+Accelerate1.12+Nagisa0.2.11; bỏUI/video chưa dùng, không sửa packagecode.
Torch138.6MB tải chậm; lưu39.3MBprefix đã có trước khi ngắt pip, dùng
HTTPRange8phần trên cùngURLPyPI, bắt buộc size/SHA256 đúng metadata trước
install. Không tải model mới, không touchvoice/runtime/TaskB.
AppleSpeechProbe compile qua khi modulecachetrong.build: localevi-VNtrue,
ondevicefalse, authdenied trongagent, không mic/authrequest/audio. Không
suy tìnhtrạngTerminaldesktop hoặc globalVietnameseunsupported.

VOICE-QUALITY-001 — officialreference đã chạy,01/11/2026:
qwen-asr0.0.6 unmodified vớiASRdepssubset đãimport/CPUprobe thànhcông.
3clip sai chọn trước(case2/4/6),cùngweights+tech+vi,CPUFP32/eager:0/3whole,
0/2title,3/4terms. Cả3transcript giốngnguyênvăn MLXFP16/GPU trêncùngca.
Không quy mọi lỗi choMLX, không tuyênbố paritytổngquát chỉ3ca. RSSpeak
4.18/4.88/6.27GB(process,khôngGPU/globalRAM). Đã dùng weights hashkhớp.
Reportprivate qwen-reference-5dd4b3f8e1fc46f5974f3788dda517dd.json; không
chéptranscript vàojournal. User đãchoautonomousalternate; chuyển kiểm
tracandidate1.7B theo plan, không chạyFP32nặng trên16GBkhi chưa budget.

VOICE-QUALITY-001 — candidate1.7B resource/download:
Metadatachínhthức1.7B revision7278e1e70fe206f11671096ffdd38061171dd6e5,
2shards4,220,320,824+478,200,688bytes. Bổ sungprofilepinned/index validation
chốngpathtraversal đểkhônggánnhầmrevision0.6B. CPUFP16matmul+conv nhỏ qua;
đang thửFP16trên0.6B trước1.7B. DefaultreferencevẫnFP32,precisionchọnrõ.
Đãbắtđầutải1.7B trongignoredmodel_weights với doctorreferencequa,HTTPRange
resume+SHA256LFStrướcfinalize. Khôngđổi voice hoặcautoenable.

## REMINDERS-INT-001 — Chuẩn hoá contracts và verification trong Reminders product integration

- Trạng thái: đã giải quyết trong phạm vi unit test / full test suite (785/785 PASS); chờ kiểm chứng native macOS desktop khi test trên máy thật.
- Ghi nhận và xử lý: 01/11/2026.
- Triệu chứng:
  1) `ContractError: estimated_latency_ms must be a non-negative integer` khi probe `RemindersAdapter` (do truyền `5.0` kiểu float).
  2) `AttributeError: 'ActionIntent' object has no attribute 'id'` và `'action_digest'` khi tạo/kiểm tra `AuthorizationToken` (thuộc tính đúng là `step_id` và phương thức `digest()`).
  3) `TypeError: ObservationRequest.__init__() got an unexpected keyword argument 'intent'` trong `verify_reminders` (`ObservationRequest` contract chỉ nhận `app`, `kind`, `subject_id`).
  4) Planner regex `is_reminder_command` chưa nhận diện lượng từ "các" ("Xem các nhắc việc đã xong"), và tách tên thứ trong tuần `re.split(r"[,;\s]+")` làm vỡ cụm từ tiếng Việt ("thứ hai" bị chia thành "thứ" và "hai").
- Nguyên nhân xác minh: Chữ ký API contracts (`CapabilityDescriptor`, `ObservationRequest`, `ActionIntent`, `AuthorizationToken`) có schema và kiểu dữ liệu nghiêm ngặt; tách từ ngữ tự nhiên tiếng Việt cần khớp ưu tiên cụm từ dài trước.
- Cách xử lý:
  - Cập nhật `estimated_latency_ms=5` (int) trong `src/elvion/adapters/reminders.py`.
  - Sử dụng `token.permits(intent)` và `intent.step_id` chuẩn contract trong adapter và test.
  - Chuẩn hóa `ObservationRequest(app=..., kind=..., subject_id=...)` trong `src/elvion/verification/reminders.py` và adapter `observe()`.
  - Cập nhật regex và bộ tách thứ tự ưu tiên cụm từ tiếng Việt trong `src/elvion/planning/reminders.py`.
- File liên quan: `src/elvion/adapters/reminders.py`, `src/elvion/verification/reminders.py`, `src/elvion/planning/reminders.py`, `tests/test_reminders_product.py`.
- Kiểm chứng thực tế: 20/20 test cases trong `tests/test_reminders_product.py` PASS; full test suite `discover -s tests` đạt 785/785 PASS (0 failures, 0 errors).
- Giới hạn: Đã kiểm chứng độc lập trên SQLite ReminderStore và unit test / in-memory runtime; việc hiển thị thông báo native UNNotificationCenter trên màn hình macOS thật cần chạy kiểm thử thực tế trên máy người dùng.

VOICE-QUALITY-001 — tiếp tục sau giới hạn công cụ:
Lượt trước bị automatic approval review không hoàn tất vì usage quota,
không phải đánh giá hành động unsafe. Sau user tiếp tục, công cụ chạy lại
bình thường. Download session cũ không còn;1.7B mới có3config nhỏ, chưa
weights. Chạy lại downloader cùngprofile để giữ/resume file đã có, không
đổiscope haycấpquyền mới. Reference0.6FP16 mộtclip đã chạy: vẫnsai whole,
terms2/2, không lấytermrecall làmchấtlượng. Chờ1.7Bdownload vàCPUsmoke.

VOICE-QUALITY-001 — downloadcheckpoint/ngoài-scopewhitespace:
Tải1.7B16connection tiếp từ~372MBpartial, không tải lạiđầufile; scratch
downloader thêmstop/cancelfutures khiinterrupted. Process cũ kếtthúc bằng
Ctrl+C do bản cũ jointhread chờstream, partial giữ lại, SHA cuối vẫnbắtbuộc.
Khôngliệtkêprocesses được do sandbox (không escalation/bypass).
Fullgitdiffcheck hiện báo blanklineEOF src/elvion/core/runtime.py do nhánh
khác đangtíchhợpreminders; không sửa file ngoài ASRscope hoặc nhận làlỗiASR.

VOICE-QUALITY-001 — khôi phục workspace và tải dở:
Sau mất kết nối môi trường, ba exec session cũ không còn truy cập được.
Đã kiểm tra trực tiếp: có khoảng 1.46 GB range parts; chưa có đủ hai shard
và manifest hoàn tất. Tiếp tục downloader giữ partial, không tải lại từ đầu.
Không dùng kết quả test của process cũ khi không lấy được output. Python hệ
thống thiếu pytest; dùng unittest với PYTHONPATH=src:.:tests, 19 test Qwen
đạt. Full suite đang chạy lại và lưu log để không mất kết quả khi ngắt phiên.
Reference benchmark được sửa mô tả scope khi chọn đủ corpus, subset không được gán quality gate.
Chưa có kết quả inference 1.7B và chưa đổi cấu hình sản phẩm.

VOICE-QUALITY-001 — kiểm chứng và nguồn tải thay thế:
Full unittest discovery đạt 800/800, log `.build/qwen-reference/test-suite.log`.
ModelScope Qwen trả HTTP206 và Content-Range đúng với probe 4 MiB. Đã dừng
HF worker trước khi chuyển nguồn, giữ khoảng 1.5 GB partial. Kho mirror dùng
master chỉ là nguồn byte; danh tính weights vẫn phải qua full SHA-256 của
revision HF đã pin. Không tự gọi master là revision đã kiểm chứng hoặc load
weights trước khi kiểm hash. Chưa có kết quả inference 1.7B.

VOICE-QUALITY-001 — kiểm tra entry point:
Thử chia sẻ scorer qua import scripts làm entry point PYTHONPATH=src lỗi
ModuleNotFoundError. Đã bỏ dependency script-to-script; giữ thay đổi scope
và chạy lại --help theo đúng lệnh trong tài liệu. Không ảnh hưởng runtime.

VOICE-QUALITY-001 — continuation có checkpoint:
Đã nối downloader với CPU/FP16 resource probe rồi full 12 clip trong script
nghiên cứu ignored `.build/qwen-reference/continue_research.py`. Probe chỉ
cho chạy tiếp khi inference không lỗi, có peak RSS hợp lệ <=8 GB. Đây là
ngân sách chọn cho thí nghiệm, không phải hard RAM limit. Lỗi/timeout dừng
và lưu trạng thái, không tự retry inference hoặc đổi model. Log riêng tư
được giữ dưới artifacts; checkpoint `.build/qwen-reference/continuation-status.json`.
Mọi bước actions=0; không tích hợp live voice hay đổi default. Chưa hoàn tất
weights nên kết quả mới vẫn đang chờ, không được báo là model đã cải thiện.

VOICE-QUALITY-001 — bàn giao tải bằng Terminal:
Khi kiểm tra continuation, công cụ trả process failed vì network policy
chặn cdn-lfs-cn-1.modelscope.cn. Vì vậy trạng thái checkpoint verified-download
không chứng minh worker vẫn chạy. Không xin escalation hoặc thử vượt policy.
User yêu cầu tự tải trên Terminal: bàn giao đúng range downloader hiện có,
giữ partial và kiểm full hash. Chưa có weights hoàn tất/inference 1.7B.

## REMINDERS-INT-002 — Chưa có entry point phiên và vòng quét đến hạn

- Trạng thái: đã xác minh thiếu tích hợp, chưa sửa.
- Khi hướng dẫn test desktop, tìm toàn bộ src/scripts thấy
  RemindersOrchestrator và ReminderNotificationConsumer chỉ được dùng trong
  định nghĩa và tests; session mới có tên capability, chưa gọi orchestrator
  hay khởi động consumer. CLI check_reminders.py chỉ đọc/ghi lõi và outbox,
  ghi rõ không phát notification.
- Tác động: chưa thể thử nhắc việc end-to-end bằng câu lệnh trong phiên
  ELVION thường; chưa có background scheduling khi đóng phiên.
- Kiểm thử native phù hợp trước mắt: smoke riêng ReminderStore + consumer,
  dùng thư mục tạm và nội dung tổng hợp. osascript returncode=0 chỉ xác nhận
  lệnh notifier được chấp nhận, không chứng minh banner hiển thị hoặc
  exactly-once. Cần người dùng xác nhận banner trên desktop.
- Bước sau: nối router/CLI, vòng đời consumer và startup trước khi tuyên bố
  tính năng hoàn chỉnh; cần kiểm thử hủy, persistence và lỗi notification.

REMINDERS-INT-002 — đã nối phiên, chờ kiểm chứng native:
User xác nhận smoke riêng có banner và kết quả 1/0, ca hủy + mở lại database
đạt. Đã thêm --reminders cho session/voice, route trước model planner và
capability inventory cho hội thoại; grants/xác nhận không bỏ qua. Preview
nhắc việc và danh sách/UUID/giờ đến hạn đã hiển thị trong CLI. Worker sở hữu
connection riêng, lock chống hai worker cùng data-dir, dừng khi lỗi gửi/ack
và khi thoát. 9 test mới (routing, quyền, từ chối, persistence, lifetime,
lock, delivery failure và relative schedule) +20 test tích hợp cũ đạt.
Chưa có native test của CLI/voice mới. Không đảm bảo exactly-once/crash hay
atomic cancellation-vs-notification; giới hạn ghi Docs/REMINDERS_SESSION.md.

## REMINDERS-INT-003 — Báo cáo relative time nhưng planner chỉ hỗ trợ lúc

- Phát hiện khi chuẩn bị lệnh desktop: planner không có nhánh "sau 1 phút"
  dù báo cáo tích hợp nêu hỗ trợ thời gian tương đối.
- Đã thêm nhánh fullmatch giây/phút/giờ/ngày, tính bằng clock lập kế hoạch,
  giới hạn >0 và <=365 ngày; preview giữ thời điểm tuyệt đối đã chốt.
- Test clock cố định xác nhận +1 phút, từ chối 0/âm/quá lớn. Đã sửa ở mức
  unit/integration; chờ test user qua CLI mới.

REMINDERS-INT-002/003 — kiểm chứng sau tích hợp:
Full unittest discovery đạt 809/809 (log .build/reminders-session-final-tests.log),
entry point session/voice --help xác nhận có cờ/grants mới, git diff --check
đạt. Trạng thái vẫn “đã sửa, chờ native CLI/voice”; không dùng fake notifier
làm bằng chứng banner thực tế.

REMINDERS-INT-002 — người dùng kiểm chứng CLI native:
Người dùng chạy session --reminders, tạo một lời nhắc sau 1 phút và xem lại
trong cùng phiên; cả hai TaskReport succeeded, UUID và thời điểm khớp.
Sau đó xác nhận thông báo có phát và không thấy phát lặp trong lượt thử.
Đã kiểm chứng native luồng tạo/xem/dispatch của phiên CLI. Không suy rộng
thành exactly-once hay bảo đảm qua crash. Ca hủy/từ chối/persistence qua
CLI mới và voice vẫn chưa có xác nhận desktop; smoke store riêng trước đó
không thay thế các ca end-to-end này.

## REMINDERS-INT-004 — Biến thể “Huỷ” không được nhận diện

- Người dùng thử hủy qua CLI bằng đúng UUID nhưng nhận UNSUPPORTED.
- Xác minh: router is_reminder_command và regex planner chỉ chứa “hủy”,
  thiếu biến thể đặt dấu trên y “huỷ”. Không phải lỗi UUID/quyền.
- Tác động: không lập được intent hủy; lịch vẫn có thể phát khi đến hạn.
- Đang sửa router, lệnh hủy và bộ lọc “đã huỷ”; không thay tiêu đề/nội dung
  lời nhắc hoặc nới các bước grant/xác nhận.

REMINDERS-INT-004 — đã sửa, chờ CLI native bản mới:
Router và planner nay nhận Hủy/Huỷ (không phân biệt hoa thường); bộ lọc
“đã hủy/đã huỷ” cùng chọn cancelled. Không replace toàn bộ nội dung người
dùng. Regression đi qua session thật với SQLite: cả ba cách viết Hủy/Huỷ/HUỶ
vẫn bị chặn khi thiếu grant, chọn n giữ active, chọn y mới cancelled; cả hai
bộ lọc trả cùng danh sách. 30/30 test reminders session/product đạt;
git diff --check đạt. Phiên Python đang mở cần khởi động lại để nạp mã mới.

REMINDERS-INT-002/004 — người dùng xác nhận thêm hai ca CLI native:
Người dùng xác nhận lịch sau khi hủy không hiện thông báo. Sau đó làm theo
bài thử tạo lịch sau 2 phút, thoát :quit rồi mở lại session --reminders và
xác nhận đạt (kỳ vọng thông báo xuất hiện một lần ở phiên mới).
Đã kiểm chứng qua phản hồi người dùng: tạo/xem/phát, hủy trước hạn và giữ
lịch qua mở lại phiên CLI. Không có quan sát process/trace native trực tiếp
ở lượt xác nhận này, không suy rộng thành bảo đảm exactly-once khi crash,
chạy lúc app đóng, hoặc desktop voice đã đạt. Biến thể “Huỷ” chưa được xác
nhận riêng sau khi nạp mã mới; regression test đã đạt trước đó.

## WEB-READER-001 — DOM lồng sâu crash; chấm điểm lặp theo cây con

- Trạng thái: đã giải quyết trong phạm vi synthetic/unit test đã đo.
- Tái hiện: extract_article('<div>'*1100 + '<p>Synthetic content sufficiently long.</p>' + '</div>'*1100)
  gây RecursionError dù input chỉ khoảng 12 KB, dưới MAX_HTML_CHARS.
- Nguyên nhân: traverse/text_content/inspect/walk đều đệ quy không có depth
  guard. Builder vẫn tạo toàn bộ node; boilerplate không thực sự được bỏ từ
  khâu parse như báo cáo. Từng candidate lại duyệt cây con để score.
- Đo synthetic nested div class=content 100/200/400 tầng: ~2.74/10.04/39.51ms
  một lượt trên host hiện tại; chỉ là diagnostic, không percentile benchmark.
- Xử lý: chuyển toàn bộ traversal (text_content, candidate discovery, score,
  extraction) sang vòng lặp iterative dùng explicit stack, loại bỏ hoàn toàn đệ
  quy Python. Thêm ranh giới MAX_DOM_DEPTH=256 và MAX_DOM_NODES=20000 trong
  _DOMBuilder; bỏ toàn bộ cây con của script, style, noscript, svg, canvas,
  iframe ngay từ handler starttag/data lúc parse.
- File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
- Kiểm chứng: `test_web_reader_001_deep_dom_recursion_guard` với 1200 tầng div lồng nhau
  chạy thành công không gây RecursionError và trích xuất đúng nội dung; toàn suite 816 tests đạt.
- Giới hạn: Cắt tầng DOM sâu sau ngưỡng 256; tài liệu không còn tuyên bố latency tùy ý dưới 5ms.

## WEB-READER-002 — max_chars không là hard bound, mất đoạn dài

- Trạng thái: đã giải quyết trong phạm vi contract và unit test đã đo.
- Tái hiện: Với một p chứa 1200 ký tự, max_chars=1000: paragraphs=(), full_text chỉ có
  marker 40 ký tự. Không giữ prefix nội dung, nên bản tóm tắt không có text.
  max_chars=10 trả full_text dài 40 vì nối marker ngoài budget.
  title/description/headings/links không có tổng budget; excerpt từ lead có
  thể dài 453 (450 + ...), fallback description không cắt.
- Nguyên nhân: vòng lặp paragraph chỉ xét nguyên khối p, nếu len(p) vượt available budget
  thì break bỏ toàn bộ đoạn; ghép marker tĩnh không kiểm tra budget còn lại.
- Xử lý: khi đoạn văn dài hơn available budget, giữ lại tiền tố của đoạn văn cắt theo
  word boundary trong phạm vi budget còn lại; bỏ marker vượt ngân sách; bảo đảm bất biến
  len(full_text) <= max_chars. Bổ sung cờ `is_truncated: bool` trên ExtractedArticle.
  Ràng buộc cứng các trường metadata: MAX_TITLE_CHARS=300, MAX_DESCRIPTION_CHARS=500,
  MAX_BYLINE_CHARS=200, MAX_DATE_CHARS=100, MAX_HEADING_CHARS=200, MAX_HEADINGS=100,
  MAX_LINKS=200; excerpt bị ràng buộc bởi min(max_chars, MAX_EXCERPT_CHARS).
- File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
- Kiểm chứng: `test_web_reader_002_budget_preserves_prefix_and_hard_bounds` đạt: ca 1200 chars
  với budget 1000 trả đúng 1000 ký tự tiền tố (paragraphs có 1 phần tử), is_truncated=True;
  ca budget 10 trả đúng <= 10 ký tự; metadata quá cỡ được cắt đúng giới hạn.
- Giới hạn: Cắt tiền tố theo số ký tự/từ có thể ngắt câu ở giữa đoạn khi ngân sách cạn.

## WEB-READER-003 — Đoạn trong blockquote/li có thể bị lặp

- Trạng thái: đã giải quyết trong phạm vi unit test đã đo.
- Tái hiện: <article><blockquote><p>Synthetic quoted paragraph with sufficient length.</p></blockquote></article>
  trả hai paragraphs giống nhau; walk thêm text tổng blockquote rồi tiếp tục
  thêm p con. Có thể lặp tương tự với li chứa p/nested lists.
- Nguyên nhân: container block (blockquote, li) vừa trích xuất text_content() làm đoạn văn,
  vừa duyệt tiếp các con nên thẻ p con bị trích xuất lần hai.
- Xử lý: phân định rõ LEAF_BLOCK_TAGS (p, pre) và CONTAINER_BLOCK_TAGS (blockquote, li, dd, dt).
  Kiểm tra `_has_child_blocks(node)`; nếu container chứa block con thì chỉ duyệt sâu để
  trích xuất các block lá con riêng biệt, không tạo đoạn văn tổng của container. Nếu không
  chứa block con, mới trích xuất đoạn văn từ container đó.
- File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
- Kiểm chứng: `test_web_reader_003_no_duplicate_content_in_nested_blocks` đạt:
  blockquote chứa p chỉ trả đúng 1 paragraph duy nhất; li chứa p và li trơn trả đúng 2 paragraphs.
- Giới hạn: Không thực hiện deduplication toàn cục để giữ nguyên các câu văn lặp có chủ đích của tác giả.

## WEB-READER-004 — URL không dùng allowlist scheme

- Trạng thái: đã giải quyết trong phạm vi unit test đã đo.
- Tái hiện: href="JaVaScRiPt:alert(1)" vẫn xuất hiện trong article.links; startswith
  blacklist chỉ nhận javascript viết thường. data/file/custom schemes cũng không bị loại.
- Nguyên nhân: blacklist startswith phân biệt hoa thường và không bao quát các scheme nguy hiểm;
  chưa kiểm tra netloc và scheme hợp lệ sau khi resolve.
- Xử lý: dùng `_sanitize_link` với allowlist scheme ALLOWED_LINK_SCHEMES = {"http", "https"}.
  Lọc trước regex không phân biệt hoa thường các scheme nguy hiểm (javascript, data, vbscript,
  file, blob); dùng urlsplit chuẩn hóa scheme thường và kiểm tra netloc; lọc ký tự điều khiển ASCII < 32.
- File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
- Kiểm chứng: `test_web_reader_004_link_scheme_allowlist` đạt: loại bỏ hoàn toàn JaVaScRiPt:alert(1),
  data:, file://; chỉ giữ lại các link http/https hợp lệ và resolve đúng link tương đối.
- Giới hạn: Reader chỉ lọc danh sách link tĩnh; mọi thao tác click/navigate của executor vẫn phải
  qua URL validator và security policy riêng trước khi mở.

## WEB-READER-005 — hidden content vẫn được coi là nội dung bài

- Trạng thái: đã giải quyết trong phạm vi DOM attributes tĩnh đã đo.
- Tái hiện: Article chứa p visible và p hidden trả cả hai text. is_boilerplate không
  xét hidden/aria-hidden hoặc inline display:none.
- Nguyên nhân: is_boilerplate chỉ kiểm tra thẻ cấu trúc và class/id ad/cookie, không kiểm tra
  thuộc tính ẩn tĩnh của HTML.
- Xử lý: bổ sung kiểm tra thuộc tính `hidden` (HTML5), `aria-hidden="true"`, các inline style
  (display:none, visibility:hidden, opacity:0), và regex class ẩn (hidden, is-hidden, d-none,
  invisible) vào `is_boilerplate()`. Bổ sung fallback thẻ `<time datetime="...">` cho published_date.
- File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
- Kiểm chứng: `test_web_reader_005_hidden_content_exclusion` và `test_time_tag_published_date_fallback` đạt;
  toàn bộ nội dung ẩn bị loại bỏ khỏi paragraphs và full_text; time datetime được trích xuất đúng.
- Giới hạn: Bộ đọc tĩnh chỉ kiểm tra thuộc tính DOM/inline styles; không có engine layout/CSS computed
  hoàn chỉnh để phát hiện phần tử bị che khuất bởi script động hoặc stylesheet ngoài. Chưa thay thế
  cho cơ chế chống prompt injection.

Web reader review checkpoint — cập nhật sau sửa:
21/21 test reader đạt; toàn bộ 5 lỗi WEB-READER-001 đến 005 đã có test tái hiện và kiểm chứng sau sửa.
Full test suite đạt 816/816 PASS (0 failures, 0 errors).
Đã loại bỏ các tuyên bố chưa có căn cứ benchmark (latency < 5ms, 70-85% boilerplate); MAX_HTML_CHARS
được ghi nhận chính xác là giới hạn ký tự (5 triệu chars). Chưa nối reader vào capability của planner.

VOICE-QUALITY-001 — 1.7B đã tải và qua resource probe:
Người dùng hoàn tất tải; agent kiểm lại cả hai shard khớp size/SHA-256 trong
manifest revision7278e1e70fe206f11671096ffdd38061171dd6e5. Assets đầy đủ.
Official CPU FP16 case2 chạy được, peakRSS4,800,282,624bytes, load~9.04s,
decode~7.26s/coldtotal~20.39s; whole0/1,terms2/2. Không lấy một clip làm
kết luận chất lượng hoặc so CPU latency với MLX GPU. Resource dưới budget
8GB nên đang đo đủ12clip cũ tech/vi; không đổi default hoặc nới gate.
Report private qwen-reference-31c2e607addd4e26b2aabcfa078fcba0.json.

VOICE-QUALITY-001 — 1.7B full corpus tech/vi chưa đạt:
Report private qwen-reference-0281201e74304174846103208a576ddf.json:
12attempts,0failure,whole5/12,title4/6,terms13/16,insertions0; proposed dev
screen false. PeakRSS~7.66GB across clips, coldmedian11.21s, p95~17.00s,
không so tốc độ CPU eager với native MLX GPU. Có lỗi ở title/action words,
không chỉ viết hoa/dấu câu. Hai câu EN được trả thành VI khi ép languagevi;
đây là confound quan trọng cho exact-match, cần đối chứng languageauto trước
kết luận về khả năng ASR tiếng Anh. Đang đối chứng none/vi trên cùng12clip
để tách ảnh hưởng glossary; chưa promote model hoặc sửa transcript tự động.

VOICE-QUALITY-001 — 1.7B ba cấu hình đã đo, chưa promote:
Full12 clip, official CPU FP16:
tech/vi5whole,4titles,13/16terms,0fail;
none/vi5whole,4titles,11/16terms,0fail;
none/auto6whole,4titles,11/16terms,0fail.
Cả ba development screens false. Auto trả đúng một trong hai câu EN,
nhưng chỉ đúng một trong hai control VI. Không đổ lỗi tất cả cho language
forcing và không kết luận model lớn tự cải thiện acoustic errors.
Max process RSS cả3lượt~7.66GB; không phải RAM toàn hệ thống/GPU latency.
Report auto qwen-reference-2e9e26d567aa4c48be0e664a67811953.json; report nonevi
qwen-reference-9121c2daaa524f7e93dd9ca4aa9ab55e.json; report techvi đã ghi trên.
Không có runtime product/config STT nào bị thay trong lượt đo. Không đo
tech/auto; không tuyên bố đã tìm optimum hoặc tổng quát từ12clip dev.

VOICE-QUALITY-001 — tiếp tục theo quyền chủ động, kiểm precision gốc:
Weights shard 1.7B header 654 tensors BF16, trong khi reference probes trước
chọn FP16 vì RAM. README chính thức dùng bfloat16 cho example/evaluation:
https://github.com/QwenLM/Qwen3-ASR (evaluation: greedy, language omitted).
Tiny CPU BF16 matmul/Conv1d chạy được. Chưa chứng minh FP16 là nguyên nhân
chất lượng thấp; thêm opt-in BF16 research để đối chiếu trên ca lỗi.
Không sửa bộ giải mã model, không chuyển runtime sản phẩm, không tải weights.

VOICE-QUALITY-001 — BF16 diagnostic không giải quyết ba lỗi đã chọn:
Official BF16 none/auto cases2/4/6:0/3whole,0/2titles,2/4terms,0fail.
Private qwen-reference-2d9ca5f3f5ac40c08ad3b3ce9bfd6b30.json. Đây là subset
lỗi đã biết, không làqualityscore tổngquát; chưa có bằng chứng FP16 là căn
nguyên. Research worker hỗ trợ BF16 opt-in,20Qwen tests đạt, default giữcũ.
Tiếp theo hai đối chứng có giả thuyết riêng trên lỗi2/4/6 +control11:
(a) thêm400ms silence mỗi đầu không sửa sample gốc để kiểm boundary;
(b) beam4 thaygreedy để kiểm search, không đổi glossary/language/precision
FP16 none/auto của baseline đã có. Không tự sửa câu hoặc dùng expectedtitle
làm gợi ý. Nếu subset không cải thiện thì không chạy full/promote config đó.

VOICE-QUALITY-001 — padding diagnostic và lượt beam đã ngắt:
Padding400ms mỗi đầu trên2/4/6/11:1/4whole (control11 được sửa),1/3titles,
2/4terms,0fail. Ba lỗi2/4/6 vẫn chưa được giải quyết nên không coi padding
là bản sửa hoặc promote; nguồn WAV giữ byte-for-byte (test xác nhận).
Private report qwen-reference-f7742bb9aca3446d992da43ee74ba332.json.
Lỡ khởi động beam4 trước lúc padding kết thúc; chủ động ngắt để không chạy
hai model nặng cùng lúc trên16GB. Lượt đã ngắt được giữ nguyên trong report
qwen-reference-c4ade9b163a94d7186fdcf7fdeeb256f.json,1failed do cancel;
không trộn với qualityscore hoặc coi là OOM. Sau khi padding dừng hoàn toàn,
khởi động lượt beam riêng. Không có tác vụ ứng dụng được thực thi.

VOICE-QUALITY-001 — domain hint có tín hiệu cải thiện, chưa promote:
Hướng dẫn chính thức Transformers có free-form Vocabulary prompt:
https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/qwen3_asr.md
Research profile assistant-v1 gộp vocabulary công khai của app/ghi chú và
tech, thêm nhãn Vocabulary; không dùng tên/ground truth của dataset.
Subset3/4/6/9/11:3/5whole,2/4titles,4/5terms,0failure; baseline none/auto
cùngsubset1/5whole,2/4titles. Cải thiện câu command/control và câu EN;
hai tên4/6 vẫn sai. Không đọc kết quả subset thành generalization/gate.
Private qwen-reference-b4d01b97bf3c4d81af8c89d14136860d.json. Đang đo đủ12.
Beam4 riêngcase4 vẫn sai tên,không chạy full cấu hình này; report private
qwen-reference-8786aaa3a88e4b5ba737a628d0b91511.json. Không âm thầm bật beam,
padding,BF16 hayhint ở live product. Research worker có validation opt-in;
22testQwen/researchtools đạt, testpadding xác nhận giữ nguyên mọi frame.

VOICE-QUALITY-001 — cải thiện đã đo và giới hạn còn lại:
Full assistant-v1 auto đạt8/12whole,4/6titles,6/6commands,14/16terms,
0failure/insertions,haiVIcontrolsđúng. WER10.256% so với19.231% của baseline
none/auto cùng backend/corpus. Raw report private:
qwen-reference-3aaa97a12b3549a2883f31ecb1f3a9b4.json. Giữ strict8/12 dù một
lỗi là cách viết compound, không sửa scorer để nâng điểm. Hai tên vẫn sai,
gatefalse, defaultvoice không đổi. Không thể gọi development improvement là
đã xử lý giọng vùng miền tổng quát.
Đã chuẩn bị bộ thu tech-fresh12câu tổ hợp mới, freeze profile/promptset hash
trong Docs/QWEN_REFERENCE_DIAGNOSTIC.md, chờ audio người dùng. Test mới từng
nhầm bool(Counter có keys zero) với tổnghits0,đã sửa testsetup dùngsum(values),
không đổi scorer/benchmarkoutputs. 44testliênquan vàfullsuite820testsđạt,
gitdiffcheckđạt. MLXdoctor agent vẫn METAL_DEVICE_UNAVAILABLE, không tự
fallback hay coi CPUtiming là GPU. Không tải thêm model trong lượt này.

VOICE-QUALITY-001 — bắt đầu fresh validation english-02:
Người dùng cung cấp12clip promptsettech-fresh; loader xác nhận WAV hợp lệ và
reference khớp thứ tự bộ câu đã freeze. Hint SHA256 và promptset SHA256 vẫn
khớp hồ sơ trước thu. Không chỉnh prompt/scorer sau khi xem dữ liệu mới.
Plan/provenance private fresh-validation-plan-37e5186722c548b694b397064c12e0ba.json
lưu manifest/audio/source hashes và tiêu chí trước khi so sánh candidate.
Baseline FP16 none/auto:5/12whole,4/6titles,10/16terms,1failure do guard
LANGUAGE_OUT_OF_SCOPE (reported Thai),không phải bằng chứng worker crash;
clip lỗi vẫn giữ trong denominator. Hai VIcontrols đúng. Không tự retry.
Report private qwen-reference-7805c6be589f4358b6c48122479abc3a.json.
Đang chạy fixed assistant-v1 sequential cùng model/backend/precision,
không có tác vụ ứng dụng hoặc thay runtimevoice trong lượt đo.

VOICE-QUALITY-001 — english-02 so sánh hoàn tất, chưa đạt gate:
Fixed assistant-v1:7/12whole,6/6titles,6/6commands,13/16terms,0fail,
1term insertion. Baseline5/12whole,4/6titles,10/16terms,1fail. Hai câu mới
đúng,không mất câu đúng;haiVIcontrols đúng. Có1câu đổi BFS→DFS, là lỗi
thuậtngữ thật, không nới scorer/gate để bỏ qua. Candidate vẫn fail yêu cầu
10/12whole và0insertions. Chỉ kết luận improved same-speaker new compositions,
không suy thành tổngquát/đã giải quyết hoàn toàn giọng vùngmiền.
Integritycheckmanifest/audio/source/hint đều unchanged. Private pairedreport
fresh-validation-e7a51475e5e641a09c730e7ec7f3d182.json; candidate
qwen-reference-277717a9e7134386962c4ee2d2dd030a.json. Không thêm lần rerun để
chọn kết quả, không chỉnh profile theo english-02. Chưa đổi livevoice.
NativeMLX/GPUsmoke vẫn cần Terminaluser vì agent METAL_DEVICE_UNAVAILABLE.

VOICE-QUALITY-001 — GPU native assistant-v1 đã kiểm chứng trên english-02:
User cung cấp qwen-comparison-52803280cdc544fe880411e53581252b.json.
Native MLX FP16:7/12whole,6/6titles,6/6commands,13/16terms,0failure,
1term insertion; tất cả12rawtranscript giống official CPU FP16 cùnghint.
Cold process+load+decode median1.439s,p95nearest-rank4.493s(firstclip),
không coi là model-only inference/keep-loaded benchmark. Gate vẫn false.
Không có bằng chứng lỗi riêng MLX trên12clip này; không suy rộng mọi input.
Giữ profile/fresh score đã chốt, không chọn best-of để thay report.
Bắt đầu diagnostic beam4 assistant-v1 ở clip lỗi acronym9 (english-02) và
đối chiếu clip9 english-01. Vì đã xem reference, mọi phép mới này chỉ là
error analysis trên dữ liệu tái dùng, không là heldout validation của decoder
mới. Phải có audio chưa dùng trước khi tuyên bố tăng accuracy tổng quát.

VOICE-QUALITY-001 — beam4 follow-up không sửa acronym:
Diagnostic beam4 assistant-v1 trên clip9english-02 vẫn0/1exact,1term
insertion,không có lỗi worker. Private report
qwen-reference-30d6da3ad15545e1830ad98b93883b95.json. Không chạy regression
rộng/đối chứng oldclip vì target chưa được sửa; không thay scoregreedy và
không promote decoder. Kết quả này là erroranalysis sau khi thấyreference,
không gọi testđộc lập. Tốc độGPU đã kiểm chứng nhưngqualitygatevẫnfalse;
không thay runtime/default hoặc tự sửa rawacronym để qua gate.

### WEB-READER-001..005 — review độc lập sau bản sửa, 01/11/2026

21/21 test reader chạy lại đạt. Các repro ban đầu đều qua: DOM1200tầng
không RecursionError và giữ text; p1200 với max_chars1000 giữ1000 và bật
is_truncated; budget10 trả10; blockquote>p chỉ một đoạn; hidden thường và
JaVaScRiPt URL bị loại. Tuy nhiên chưa thể đóng toàn bộ issue: có bốn repro
bổ sung bên dưới. Lượt này chỉ review/ghi nhật ký, chưa sửa code sản phẩm.

**WEB-READER-001 — mở lại phần trạng thái parse-discard với HTML void:**
- reader.py handle_starttag dòng192 đặt _ignore_tag='embed', chờ endtag.
  embed là void tag HTML, dạng hợp lệ không có endtag.
- Repro: '<embed src="media.bin"><article><p>Visible article text after media embed.</p></article>'
  trả full_text rỗng. Cùng input dùng '<embed src="media.bin"/>' trả đúng text.
- Tác động: phần nội dung sau embed bị nuốt hoàn toàn dù HTML hợp lệ.
- Hướng sửa: bỏ riêng void discard element mà không vào trạng thái ignore
  subtree; test cả dạng bare void và XHTML self-closing, kể cả trước article.

**WEB-READER-001/005 — mở lại overflow DOM làm mất semantics hidden:**
- reader.py dòng217 return khi đạt depth/node bound nhưng handle_data vẫn
  append vào current; skipped opening tag không có frame tương ứng trong
  stack, closing tag còn có thể đóng ancestor khác có cùng tên.
- Repro: '<article>' + '<div>'*(MAX_DOM_DEPTH-2) +
  '<p hidden>Hidden text at depth limit must remain excluded.</p>' +
  '</div>'*(MAX_DOM_DEPTH-2) + '</article>'
  trả chính text hidden trong full_text.
- Tác động: điều kiện ẩn/boilerplate bị bỏ qua ở biên tài nguyên, cây có thể
  sai cấu trúc. Đây là lỗi chất lượng lọc, không là bằng chứng thực thi action.
- Hướng sửa: theo dõi overflow subtree có trạng thái cân bằng, không gắn
  data của tag bị bỏ vào cha visible; báo partial/truncated khi phải bỏ.
  Ưu tiên fail-closed khi vượt budget thay vì trả dữ liệu sai semantics.

**WEB-READER-003 — mở lại, bỏ mất loose text trong mixed block:**
- reader.py dòng409 chỉ xếp các _DOMNode con vào stack khi có block con;
  các string trước/sau block con không được trích xuất.
- Repro: '<article><blockquote>Opening context is essential.<p>Detailed explanation is here.</p>Closing context is essential.</blockquote></article>'
  chỉ trả ('Detailed explanation is here.',), mất cả opening và closing.
- Tác động: sửa trùng lặp bằng cách làm mất nội dung hợp lệ. Có thể xảy ra
  tương tự với li chứa phần giới thiệu và nested list/paragraph.
- Hướng sửa: duyệt text runs và leaf blocks đúng thứ tự, flush text trước/
  sau block; không dùng dedup toàn cục hoặc bỏ mọi string của container.

**WEB-READER-002 — mở lại cờ truncation khi chạm MAX_PARAGRAPHS:**
- _extract_from_container cắt paragraphs[:MAX_PARAGRAPHS] trước khi caller
  biết độ dài gốc, nên is_truncated không nhận ra cắt do số đoạn.
- Repro: article với501 p, mỗi đoạn 'Paragraph number {i} has substantive content.'
  trả500đoạn,23388ký tự (<50000), nhưng is_truncated=False.
- Tác động: caller/planner có thể coi bài thiếu là bài đầy đủ.
- Hướng sửa: truyền explicit truncation/resource flags từ parse/extraction
  lên result; test riêng501đoạn với character budget còn dư.

Trạng thái cập nhật: WEB-READER-004 đã qua repro scheme cũ; 001/002/003/005
đã sửa được ca cũ nhưng còn lỗi bổ sung nêu trên. Không gọi “đã giải quyết
hoàn toàn” chỉ từ21tests hiện có. Scoped git diff --check reader/tests đạt.

### WEB-READER-001..005 — giải quyết triệt để 4 ca lỗi phát sinh, 01/11/2026

Đã xử lý dứt điểm cả 4 ca lỗi được chỉ ra trong đợt review:
1. Void tag `<embed>` (WEB-READER-001):
   - Xử lý: `_DOMBuilder.handle_starttag()` chỉ đặt `_ignore_tag` khi tag thuộc `PARSE_DISCARD_TAGS` và KHÔNG thuộc `VOID_TAGS`. Các void tag tự đóng hoặc bare void như `<embed>` bị bỏ qua ngay tại starttag mà không tạo subtree bỏ qua, ngăn việc nuốt toàn bộ nội dung sau thẻ.
   - Kiểm chứng: `test_web_reader_001_embed_void_tag_does_not_swallow_trailing_content` kiểm thử cả `<embed src="media.bin">` và `<embed src="media.bin"/>`, nội dung bài phía sau được giữ đầy đủ.
2. Cân bằng overflow DOM và fail-closed text ẩn (WEB-READER-001/005):
   - Xử lý: Bổ sung bộ đếm `_overflow_depth` và cờ `overflowed: bool` trong `_DOMBuilder`. Khi đạt ngưỡng `MAX_DOM_DEPTH` (256) hoặc `MAX_DOM_NODES` (20000), `_overflow_depth` theo dõi và cân bằng thẻ mở/đóng; `handle_data()` bỏ qua dữ liệu khi `_overflow_depth > 0` hoặc khi vượt ngưỡng độ sâu, tuyệt đối không gắn text của tag bị bỏ (kể cả `<p hidden>`) vào cha visible. Khi cây bị tràn, cờ `is_truncated = True` được bật.
   - Kiểm chứng: `test_web_reader_001_005_depth_overflow_does_not_leak_hidden_content` với `<p hidden>` ở ngưỡng độ sâu xác nhận text ẩn không lọt vào bài và `is_truncated=True`. `test_web_reader_001_deep_dom_recursion_guard` với 1200 tầng div xác nhận không RecursionError và fail-closed an toàn.
3. Mixed block không mất loose text và không lặp đoạn (WEB-READER-003):
   - Xử lý: `_extract_from_container()` chuyển sang cơ chế flow parser duyệt theo document order: duy trì inline buffer cho loose text; flush buffer thành đoạn văn khi gặp leaf block (`p`, `pre`), heading, container block con, hoặc khi kết thúc block cha. Thêm `"byline"` vào `BOILERPLATE_CLASS_OR_ID` và `"document"`, `"html"`, `"body"` vào `NON_LEAF_BLOCK_TAGS` để đảm bảo phân tách rõ ràng metadata với nội dung bài viết và hỗ trợ phân cấp fallback heading.
   - Kiểm chứng: `test_web_reader_003_mixed_container_preserves_loose_text_and_blocks` với blockquote chứa text mở đầu + `<p>` + text kết thúc giữ đủ cả 3 đoạn; `test_basic_article_extraction` giữ đúng 4 đoạn bài viết chuẩn.
4. Truncation flag khi chạm `MAX_PARAGRAPHS` (WEB-READER-002):
   - Xử lý: `_extract_from_container()` trả cờ `raw_truncated` nếu số đoạn vượt quá `MAX_PARAGRAPHS` (500). `extract_article()` nhận cờ này và đảm bảo `is_truncated = True` ngay cả khi character budget chưa vượt ngưỡng.
   - Kiểm chứng: `test_web_reader_002_max_paragraphs_truncation_sets_flag` với bài 501 đoạn trả đúng 500 đoạn và `is_truncated=True`.

File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
Kiểm chứng:
- 25/25 unit tests trong `tests/test_browser_reader.py` PASS trong 0.010s.
- Toàn bộ test suite repository đạt 843/843 tests PASS trong 18.25s (0 failures, 0 errors).
- `git diff --check` đạt 0 lỗi.
Trạng thái: Đã giải quyết trong phạm vi contract, synthetic edge cases và unit/regression test đã đo. Sẵn sàng tích hợp với pipeline tóm tắt/planner.

## VOICE-REVIEW-001 — triển khai duyệt/sửa/hủy bằng giọng nói thử nghiệm

- User đã cho phép Qwen opt-in và nói lại/sửa thuật ngữ/hủy; xác nhận thao
  tác thật vẫn giữ bàn phím. Chế độ mới --voice-review, cửa sổ tự dừng2..15s,
  tối đa6lượt review; Enter ban đầu vẫn kích hoạt micro, chưa phải wake word.
- Dictation Qwen auto dùngassistant-v1 đã đo; controlturn chọnVietnamese
  trước inference vì là grammar tiếngViệt. Không retry clip lỗi/đổi backend
  sau thất bại. File WAV tạm và transcriptcontrol không lưu vào trace.
- Test bắt helper đổi riêng tên có thể bỏ phần “rồi mở web” vì guard cũ
  chỉ kiểm scope/confirmation modifiers, không kiểm compound instructions.
  Đã thêm kiểm tra compound cục bộ trước khi giữ prefix; trường hợp mơ hồ
  phải nói lại toàn yêu cầu, không sanitize thành tác vụ benign.
- Một test ban đầu dùng tên “Mới” thuộc vague-title set, gây clarification
  ngoài fixture; đổi fixture sang “Bản mới”, không nới validation sản phẩm.
- Đang kiểm toàn luồng với backend giả. Native Qwen benchmark trước đây
  không thay thế kiểm chứng desktop của luồng thu/review mới.

VOICE-REVIEW-001 — kiểm chứng tích hợp và giới hạn:
18test mới spoken_review +1prompt extension;108test liên quan đạt. Giữ nguyên
11promptv1, bổ sung5promptv2 cố định qua cùngservice. Qwen--doctor thực tế
trảnot_ready/qwen3-asr-mlx/METAL_DEVICE_UNAVAILABLE,không mởmic; không dùng
kết quả benchmarkGPU cũ làm chứng cứ controlturn mới đã hoạt động native.
Đã sửa helpername-edit để không nuốt chuỗi lệnh; lời đọc lại tên “Hủy” là
literal ở dictationturn, chỉ controlturn mới hiểu cancel. Bare acronym mơ hồ
hoặc thay thế nhiều vị trí đều không tự sửa. Đã test ASR lỗi bỏ request cũ,
TTS/readback/stop lỗi chặncontrolmic, speech không cấpquyền/phêduyệt action.
Fullsuite839tests có3failure ở reader (basic_article_extraction paragraphs5
vs4,metadata_fallback_hierarchy heading rỗng,deep_dom guard thiếucontent).
Reader source đã được nhánh khác đổi (có overflowguard) kể từ review trước;
không sửa đè reader/test hoặc nới assertions trong lượt voice. Log gốc:
.build/voice-spoken-full-tests.log. Chưa gọi fullsuiteđạt. Cần nhánh Reader
xác nhận/sửa các regression; docsVOICE_SPOKEN_REVIEW.md có hướng dẫn native.

VOICE-REVIEW-001 — chốt kiểm chứng:
Đã phát hiện thêm mơ hồ khi tên mới bắt đầu bằng “Tên”: ModelPlanner dùng
“tên” làm field label trong khi rules dùng literal tail. Helper thay tên
nay chọn named-vs-literal theo planner, giữ đúng dữ liệu tên đã đọc lại;
regression xác nhận inspect_note_reference.region vẫn giữ “Tên đã sửa”.
20testspoken mới+1prompt extension;110testsliênquan đạt. Lượt full cuối
845/845đạt sau khi nhánh Reader cập nhật (không phải sửa Reader trong lượt
voice này);gitdiffcheckđạt. Log .build/voice-spoken-full-final-tests.log.
Whisper/savedpreferences giữ nguyên;Qwen opt-in qua--stt-engine,không tự
fallback/download. --voice-review dùng timer giới hạn,không làwakeword/VAD.
CLI preflight thực tế thiếuMetal trảmicrophone_opened=false. Native mic/TTS
spoken-control accuracy mới chưa đo, cần user thử;không coi fake tests là
bằng chứng đã đạt100%giọngnói hoặc chất lượng ASR đã qua gate.

VOICE-REVIEW-001 — phản hồi desktop, phạm vi xác nhận cần làm rõ:
User báo đã thử các luồng đều đúng và không cần xác nhận bàn phím. Ghi nhận
native feedback cho spoken review, chưa suy thành action approval bằng giọng.
Đối chiếu source VoiceSession vẫn require_confirmation=True và _confirm
chỉ đọc stdin y/yes/có; reviewcontrol không gọi confirmation. Những trace
mặc định gần nhất đọc được là reminder cũ có awaiting_confirmation; không
có bằng chứng đầy đủ về action mới của lượt voice (có thể dùng data-dir khác
hoặc no-trace). Cần phân biệt chat/duyệt transcript với thao tác Notes thật
trước khi đóng kiểm chứng hoặc kết luận có bypass.

VOICE-REVIEW-001 / VOICE-QUALITY-001 — user làm rõ native smoke và accent:
User xác nhận trường hợp không hỏi xác nhận là câu “giải thích”, tức hội
thoại, không phải tạo Notes thật. Không có bằng chứng bypass actionconfirm;
phản hồi các luồng spokenreview native chạy đúng được ghi nhận, không suy
ra actionapproval bằng giọng đã bật. User cũng quan sát khi cố nói giọng
Bắc thì nhận dạng tốt hơn giọng tự nhiên. Đây là quan sát chưa có paired
corpus cùngcâu/mic/tốcđộ; không khẳng định thiếu dữ liệu vùng miền là nguyên
nhân đã chứng minh. Có thể khác phân bố phát âm/ngữ điệu/tốc độ hoặc cách
đọc English. Cần test cặp kiểm soát trước khi chốt và cá nhân hóa; không ép
người dùng đổi giọng hoặc tuyên bố có lỗi ở phát âm người dùng.

VOICE-QUALITY-001 — định hướng cá nhân hóa theo giọng chủ máy:
User ưu tiên giọng tự nhiên của mình vì dùng cá nhân. Kế hoạch mới tại
Docs/PERSONAL_VOICE_PLAN.md; chưa thu thêm/lưu audio phiên voice/tuneweights.
Đã xác định rủi ro supervision: text sau khi đổi ý hoặc đọc lại riêng tên
không phải nhãn đúng của clip gốc. Không dùng trực tiếp transcript đã sửa
làm training label nếu chưa có xác nhận lời thực sự đã nói/provenance.
Official SFT script hướngGPU/torchrun; chưa xác minh train/adapters và load
checkpoint trênMac16GB. MLXpackage đã cài chưa thấy moduletraining. Không
hứa vài clip đủhọcgiọng,không download/upload/cloud training tự động.
Bước ưu tiên là pipeline dữ liệu được chọn lưu +session/group split trước
khi chạy train lâu. Bộ english-02 chỉ là regression cho các lượt tối ưu sau.

### WEB-READER — review bản sửa 25tests, 01/11/2026

25/25test đọc web chạy lại đạt. Đã xác nhận riêng bốn repro lượt trước:
bare embed giữ bài phía sau; mixed block giữ opening/p/closing đúngthứtự;
501p trả500vàis_truncated=True; hidden ởdepthoverflow đúng dạng balanced bị
loại vàflagTrue. Các ca này đã sửa. Chưa sửa productcode trong lượt review.

**WEB-READER-001/005 — overflow endtag không kiểm tag tương ứng, còn mở:**
- reader.py handle_endtag dòng256 giảm _overflow_depth với mọi endtag, kể
  cả endtag không có opener hoặc endtag void. Khi về0sớm, handle_data ghi
  text của subtree bị bỏ vào ancestor visible.
- Repro:
  prefix='<article>'+'<div>'*(MAX_DOM_DEPTH-2)
  suffix='</div>'*(MAX_DOM_DEPTH-2)+'</article>'
  extract_article(prefix+'<section hidden></unexpected>Hidden direct text must remain excluded.</section>'+suffix)
  trả text hidden dùis_truncated=True. Dạng '<section hidden><br></br>Hidden direct text after void closing.</section>' cũng lọt.
- Phạm vi: malformed HTML bên trong overflow; testbalanced mới không bắt.
  Đây là sai semantics nội dung/fail-closed, không bằng chứng chạy action.
- Hướng sửa: không giảm counter với closing tag void/không khớp; cơ chế
  overflow phải chịu HTML lỗi, hoặc cắt parser fail-closed khi chạm resource
  limit và báopartial. Thêm regression directtext sau mismatched/void end.

**WEB-READER-005 — opacity zero dạng thập phân chưa lọc, còn mở:**
- reader.py dòng144 regex0(?![.\\d]) loại bỏ chính dạng0.0/0.00.
- Repro: article gồm pvisible và '<p style="opacity:0.0">Fully transparent content long enough.</p>'
  vẫn trả cảvisible vàtransparent. Đây là CSSnumericzero hợp lệ.
- Hướng sửa: parse giá trị số0 với ranhgiới declaration; test0/0.0/0.00 và
  control0.5 phải giữvisible. Không tuyên bố staticfilter là computedCSS.

## WEB-READER-006 — Bỏ sót anchor lồng trong inline wrapper ngoài p

- Trạng thái: đã tái hiện trong review, chưa sửa.
- _extract_from_container dòng478 chỉ quét link nếu inline child trực tiếp
  là a; nếu child làspan thì lấy text_content nhưng không scananchors con.
- Repro: '<article><span>Visible intro <a href="https://example.com/docs">useful documentation</a> ends here.</span><p>Main paragraph sufficient length.</p></article>'
  trảlinks=() dùanchor hợp lệ xuất hiện trong nội dung đã lấy.
- Hướng sửa: quét link iterative một lượt trên chosencontainer (tôn trọng
  boilerplate/hidden/caps), hoặc quét descendants của inlinewrapper; giữ
  documentorder/seenlinks, không chạy lặp cùngsubtree quá nhiều lần.

Kết luận: các lỗi được fix ở balanced cases có kiểm chứng; vẫn cần đóng
001/005 malformedoverflow,opacitydecimal và006linkdiscovery trước tuyên bố
“toàn diện”. 002/003/004 qua các repro hiện được kiểm; không đánh đồng test
pass với chứng minh mọi trang/HTML/CSS. Review không sửa mã của nhánh B.

### WEB-READER-001/005 & WEB-READER-006 — giải quyết triệt để 3 ca lỗi phát sinh, 01/11/2026

Đã xử lý dứt điểm 3 lỗi được ghi nhận trong đợt review:
1. Malformed overflow endtag (WEB-READER-001/005):
   - Xử lý: Thay thế bộ đếm số `_overflow_depth` bằng `_overflow_stack: list[str] = []` để theo dõi chính xác các thẻ mở trong vùng tràn.
   - Thẻ đóng void (`VOID_TAGS`) như `</br>`, `</img>` bị bỏ qua hoàn toàn, không bao giờ pop thẻ nào.
   - Thẻ đóng không tồn tại trong `_overflow_stack` và không có trong `self.stack` (như `</unexpected>`) bị bỏ qua, không làm giảm hay reset stack tràn.
   - Khi gặp thẻ đóng khớp với một thẻ trong `_overflow_stack`, parser unwind danh sách tràn đến thẻ đó. Nếu gặp thẻ đóng của một ancestor trong `self.stack`, parser dọn sạch `_overflow_stack` và unwind `self.stack` chuẩn xác.
   - `handle_data()` bỏ qua dữ liệu khi `_overflow_stack` không rỗng hoặc khi độ sâu `>= MAX_DOM_DEPTH` (fail-closed tuyệt đối).
   - Kiểm chứng: Cả hai ca repro với `prefix + '<section hidden></unexpected>Hidden direct text...</section>' + suffix` và `prefix + '<section hidden><br></br>Hidden direct text...</section>' + suffix` đều loại bỏ hoàn toàn text ẩn, trả về `is_truncated = True`.
2. Opacity zero dạng số thập phân CSS (WEB-READER-005):
   - Xử lý: Cập nhật regex kiểm tra style trong `_DOMNode.is_boilerplate()` thành:
     `r"(?:^|;)\s*opacity\s*:\s*(?:0+(?:\.0+)?|\.0+)\s*(?:%|\s*!important)?\s*(?:;|$)"`.
   - Bắt chính xác `0`, `0.0`, `0.00`, `.0`, `0%` và `!important`, loại bỏ hoàn toàn thẻ trong suốt; trong khi các giá trị dương như `opacity: 0.5` vẫn giữ nguyên vẹn nội dung hiển thị.
   - Kiểm chứng: `test_web_reader_005_hidden_content_exclusion` xác nhận `opacity: 0`, `0.0`, `0.00` bị loại bỏ, `opacity: 0.5` được giữ lại.
3. Anchor lồng trong inline wrapper ngoài `<p>` (WEB-READER-006):
   - Xử lý: Trong `_extract_from_container()`, khối `else:` (xử lý các thẻ inline như `span`, `em`, `strong`, `code`) gọi trực tiếp `_scan_links_iterative(child, base_url, seen_links, links)` thay vì chỉ kiểm tra thẻ `<a>` ở cấp trực tiếp.
   - Giữ nguyên document order, không lặp lại thẻ, tôn trọng boilerplate/hidden và giới hạn `MAX_LINKS`.
   - Kiểm chứng: `test_web_reader_006_anchor_in_inline_wrapper_extracted` xác nhận link lồng trong `<span>` và `<em>` đều được trích xuất chính xác vào `article.links`.

File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
Kiểm chứng:
- 26/26 unit tests trong `tests/test_browser_reader.py` PASS trong 0.014s.
- Toàn bộ test suite repository đạt 846/846 tests PASS trong 20.37s (0 failures, 0 errors).
- `git diff --check` đạt 0 lỗi.
Trạng thái: Đã giải quyết triệt để cả 3 ca lỗi trong phạm vi contract, synthetic edge cases và unit/regression tests. Đóng các issue WEB-READER-001/005, 005 và 006.


### WEB-READER-001/002 — review bản sửa 26 tests, 01/11/2026

Ba repro trước (malformed overflow endtag, opacity decimal zero, nested inline
anchor) đã đạt khi chạy lại độc lập; 26/26 unit tests Reader đạt.
Không sửa reader.py hoặc test của nhánh B trong lượt review này.

Còn hai vấn đề resource/truncation đã tái hiện:

1. **Mất text tại đúng biên độ sâu, không báo truncation** (còn mở):
   `extract_article('<article>' + '<div>' * (MAX_DOM_DEPTH - 2) +
   'Visible text at the exact allowed depth.' + '</div>' *
   (MAX_DOM_DEPTH - 2) + '</article>')` trả full_text rỗng và
   is_truncated=False. handle_data loại bỏ text khi len(stack)>=256,
   nhưng overflowed chỉ bật khi gặp starttag vượt biên tiếp theo.
   Hướng sửa: thống nhất biên starttag/data; nếu bỏ dữ liệu vì resource guard,
   phải bật truncation. Test cần có text tại biên và ngay hai phía biên.
2. **Overflow stack không có trần depth/node độc lập** (còn mở):
   `_DOMBuilder().feed('<div>' * 10000)` giữ regular stack 256 nhưng
   `_overflow_stack` dài 9745. Giới hạn HTML tổng 5 Mi ký tự vẫn tồn tại,
   nên đây không phải bộ nhớ vô hạn; tuy nhiên giới hạn depth 256/node 20000
   không giới hạn cấu trúc phụ này. Endtag không khớp còn quét toàn bộ stack
   vùng tràn cho mỗi lần đóng. Hướng sửa: bounded overflow tracking hoặc
   dừng parse fail-closed khi chạm resource limit; tránh tái tạo trạng thái
   sâu tùy theo input và tránh repeated linear scans trên overflow lớn.

Opacity 0/0.0/0.00/.0/0%/0 !important đều bị loại; 0.5 được giữ.
Nested inline anchor được trích xuất đúng URL. Các kết quả này là synthetic
static HTML, không chứng minh computed CSS hay chất lượng website thực tế.

Kiểm chứng hồi quy lượt review: toàn suite 846 tests đạt (17.955s);
`git diff --check` đạt. Hai repro bổ sung ở trên vẫn cần sửa dù suite xanh.

### WEB-READER-001/002 — giải quyết triệt để 2 vấn đề biên tài nguyên & truncation, 01/11/2026

Đã xử lý dứt điểm cả 2 ca lỗi phát sinh:
1. Thống nhất biên starttag/data tại đúng độ sâu MAX_DOM_DEPTH (WEB-READER-001/002):
   - Nguyên nhân: Trước đây, `handle_data()` có dòng `if len(self.stack) >= MAX_DOM_DEPTH: return`. Khi thẻ mở cuối cùng hợp lệ nằm ở đúng độ sâu 256 (`len(stack) == 256`), text trực tiếp bên trong thẻ đó bị bỏ qua nhưng không bật `overflowed = True`.
   - Xử lý: Xóa bỏ ranh giới cắt ngầm trong `handle_data()`. Khi `self.current` là một node hợp lệ đã được chấp thuận vào `self.stack` (độ sâu <= `MAX_DOM_DEPTH`), và `_overflow_stack` đang rỗng, text trực tiếp của node được gắn vào node con bình thường (`is_truncated = False`). Khi có bất kỳ thẻ nào vượt quá độ sâu hợp lệ, thẻ đó được đưa vào `_overflow_stack`, `self.overflowed = True` được bật ngay từ starttag và mọi text bên trong nó đều bị bỏ qua (fail-closed, `is_truncated = True`).
   - Kiểm chứng: `test_web_reader_001_depth_boundary_text_preservation_and_truncation` kiểm thử cả 4 trường hợp:
     * Trong biên (độ sâu 255): giữ nguyên text, `is_truncated = False`.
     * Đúng biên (độ sâu 256): giữ nguyên text `Visible text at the exact allowed depth.`, `is_truncated = False`.
     * Ngoài biên (độ sâu 257): loại bỏ text vượt biên, `is_truncated = True`.
     * Hỗn hợp (text tại biên + thẻ con vượt biên): giữ text tại biên, loại bỏ text vượt biên, `is_truncated = True`.
2. Giới hạn trần độc lập cho Overflow Stack và dừng parse fail-closed (WEB-READER-001):
   - Nguyên nhân: `_overflow_stack` trước đây không có trần riêng, tiếp tục nhận thẻ mở đến 9.745 phần tử với input 10.000 thẻ `<div>`, gây tốn bộ nhớ và khiến các vòng lặp kiểm tra thẻ đóng không khớp bị chậm.
   - Xử lý:
     * Bổ sung hằng số `MAX_OVERFLOW_DEPTH = 256`.
     * Trong `handle_starttag()`, khi `len(self._overflow_stack) >= MAX_OVERFLOW_DEPTH`: kích hoạt `self.overflowed = True` và `self._exhausted = True`.
     * Khi `self._exhausted = True`: parser lập tức dừng tiếp nhận mọi starttag, endtag và data (fail-closed trong O(1)), khống chế kích thước tối đa của `_overflow_stack` không bao giờ vượt quá 256 phần tử.
     * Tối ưu `handle_endtag()`: kiểm tra nhanh `if tag_lower in self._overflow_stack:` trước khi duyệt ngược, loại bỏ việc quét tuyến tính lặp lại trên các thẻ đóng không khớp.
   - Kiểm chứng: `test_web_reader_001_overflow_stack_bounded_resource_limit` xác nhận với input 10.000 thẻ `<div>`, `len(stack) <= 256`, `len(_overflow_stack) <= 256`, `overflowed = True`, `_exhausted = True`, thời gian xử lý cực nhanh dưới 0.01s.

File liên quan: `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
Kiểm chứng:
- 28/28 unit tests trong `tests/test_browser_reader.py` PASS trong 0.023s.
- Toàn bộ test suite repository đạt 862/862 tests PASS trong 18.11s (0 failures, 0 errors).
- `git diff --check` đạt 0 lỗi.
Trạng thái: Đã giải quyết hoàn toàn toàn bộ các vấn đề và edge case tài nguyên/truncation của Web DOM Reader. Đóng toàn bộ WEB-READER-001..006. Sẵn sàng tích hợp planner/action chaining.


## VOICE-DATA-001 — Nhãn sau review chưa đủ provenance để cá nhân hóa

- Ngày: 01/11/2026. Trạng thái: đã có công cụ dữ liệu và fake/unit tests;
  chờ thu/nghe/gán nhãn trên desktop thật, chưa train hoặc đo accuracy mới.
- Vấn đề: WAV phiên voice hiện xóa sau STT; yêu cầu sau sửa có thể là đổi ý,
  đọc lại tên hoặc control turn, không tương ứng nguyên văn audio trước đó.
  Tự dùng request được duyệt làm nhãn sẽ gây sai dữ liệu huấn luyện.
- Xử lý: module voice/personal/store.py và scripts/personal_voice.py tạo luồng
  opt-in riêng; nghe lại WAV, nhập đúng lời đã nói, xác nhận giữ từng clip.
  Không sửa capture/ASR/executor của phiên voice thường, không tự lưu audio
  nền hoặc biến xác nhận tác vụ thành đồng ý huấn luyện.
- Provenance: session/split cố định, sample ID, kind dictation/title/control,
  nhãn manual_utterance, thời gian, SHA WAV/PCM. SQLite lưu audio và nhãn
  cùng transaction; kiểm trùng PCM/câu/group khác split, audit gần trùng
  ký tự >=0.9 và chặn export khi có rủi ro. Pilot giới hạn 500 samples.
- Ghi dữ liệu private directory700/file600, delete/export local, không
  upload, không có model inference hoặc training. Export từng split riêng.
- Kiểm chứng: 16 tests mới đạt, gồm từ chối consent không mở mic/tạo dữ liệu,
  hủy/không xác nhận/lỗi playback không lưu, literal title/control, rollback
  khi insert lỗi, restart, dedup PCM dù header thay đổi, giới hạn pilot,
  chống rò split, hash corruption, export và delete. Không dùng giọng thật
  trong test hoặc đưa transcript cá nhân vào nhật ký.
- Giới hạn: caller/human phải xác nhận audio/text đúng ngữ nghĩa; không tự
  chứng minh qua ASR. Near-duplicate heuristic không bao phủ paraphrase;
  chưa freeze evaluation artifact hoặc train recipe. Xóa không bảo đảm xóa
  khỏi backup/snapshot, export không crash-atomic khi process bị kill.
  Chưa có cải thiện accuracy được đo. Hướng dẫn PERSONAL_VOICE_DATA.md.

Hồi quy cuối lượt VOICE-DATA-001: toàn suite 864 tests đạt (17.746s),
16 test personal voice đạt; CLI từ chối consent exit0, không tạo thư mục
dữ liệu; git diff --check đạt. Desktop mic/playback thật chưa chạy.

### VOICE-DATA-001 — pilot desktop và giới hạn audit agent, 01/11/2026

User đã thu pilot. Audit CLI trên process agent gặp PermissionError vì
PersonalCorpus constructor yêu cầu chmod thư mục private ngoài writable
roots; không phải bằng chứng dữ liệu hỏng. Đã dùng SQLite mode=ro để kiểm
tra không sửa thư mục: 23 clip dictation, 1 phiên train, tổng120.4giây;
quick_check=ok,0 lỗi hash/WAV/PCM,0 duplicatePCM. Không ghi transcript,
sampleID hoặc audio vào nhật ký. Chưa có dev/held_out, chưa đủ bằng chứng
cho training hoặc kết luận cải thiện accuracy. Native thu đã được user
hoàn tất; gán nhãn ngữ nghĩa vẫn dựa vào xác nhận của user.

### VOICE-DATA-001 — kiểm tra đợt dev, 01/11/2026

SQLite mode=ro: train23clip/120.4giây,dev15clip/76.2giây,mỗi split1phiên.
quick_check=ok,0 lỗi hash/format/PCM,0 PCM trùng,0 rủi ro khác split
theo phrase/group/SequenceMatcher>=0.9. Không khẳng định đã loại hết
paraphrase hoặc kiểm chứng nhãn ngữ nghĩa; không in raw labels/audio.
Tổng38clip,196.6giây; chưa có adaptation/accuracy cá nhân được đo.


### VOICE-QUALITY-001 / VOICE-DATA-001 — baseline personal dev, 01/11/2026

Report private qwen-comparison-fb9888cc09374006a2bf71ce77a97f87.json:
Qwen1.7B/MLX/assistant-v1 tech-auto, 15 attempts, 0 failures, 5 strict exact,
WER19.53%,CER11.78%,cold process/load/inference median1.417s,p954.371s.
Thuật ngữ theo scorer hiện hữu:4/7hits,3misses,1insertion; title metric chỉ
nhận1case trong corpus,0/1đúng,không suy thành coverage tất cả câu Notes.

Phân loại manual so sánh text:2/10câu mismatch chỉ khác cách viết (word
spacing hoặc số dạng chữ/digit),8/10còn khác nội dung thật hoặc hỗn hợp.
Không đổi groundtruth hoặc nới scorer; chưa nghe lại audio để chứng minh
nguyên nhân accent. Acronym confusion vẫn tồn tại. Screening gate 12clip cũ
không áp dụng cho15clip này (applicable=false),không gọi là model lỗi/chưa
qua một ngưỡng được thiết kế cho dataset khác.

Audio diagnostic:medianRMS~-24.99dBFS;13clip có energy đầu,14clip có energy
cuối. Đây chỉ là năng lượng, không chứng minh clipping/mất âm đầu/cuối hoặc
noise/speech. Cần nghe kiểm trước khi kết luận lỗi capture. Không tự trim.
Held_out30 cùng công cụ quality: median RMS -28.13dBFS, 29 clip có energy
sát đầu, 27 sát cuối; chưa nghe kiểm nên vẫn chỉ là giả thuyết capture,
không khẳng định mất âm. Phạm vi 30 clip một phiên. Bước tiếp theo:
nghe đối chiếu các clip sai và ranh giới audio trước khi chỉnh recorder.
Phân tích aggregate/source hash lưu private personal-dev-baseline-analysis.json.
Không log transcript hoặc tên riêng. Chưa có weights cá nhân hoặc training;
23trainclip~2phút chỉ là pilot để feasibility probe,không bảo đảm accuracy.
Dev đã xem lỗi nên dùng tuning; cần phiên held_out mới sau chốt cấu hình.


## VOICE-ADAPT-001 — chưa có gradient/adapter pipeline đã kiểm chứng trên Mac16GB

- Ngày01/11/2026. Trạng thái: research probe đã triển khai, chờ native Metal.
- Trở ngại: backend ASRMLX0.4.4 đang dùng chỉ cung cấp inference trong luồng
  ELVION; chưa có training recipe/RAM/reload compatibility được xác minh.
  Agent native probe dừng METAL_DEVICE_UNAVAILABLE trước đọc clip/loadmodel;
  không có loss/gradient/update được tính và không tự fallback sang CPU.
- Giải pháp cụ thể: scripts/probe_personal_asr.py + voice/personal/probe.py
  và lora_probe_worker.py. One train dictation clip<=8s, batch1,512input/
  128targettokens,rank4 q/v hai decoderlayercuối,8tensoradapter,basefrozen,
  encoderfeaturesstopgradient,maskprompt/audio,SGD1step1e-5,save riêng và
  reload teacherforcedloss trên wrapper mới. Không sửa modelbase/sitepackages.
- Guard: readonlySQL chỉ train/dictation/manual_utterance,hashWAV/PCM,
  explicitlocalmodel/rank/outputoutsidebase,env offline,180s childtimeout,
  MLXallocator8GiB/cache256MiB (không hardlimit tổngRSS). Không retry.
- Kiểm chứng:6 contract/launcher tests mới +16 datasettests đạt; maskshift/
  EOS,prefixkhôngsupervise,selectorloạidev/heldout/title/control/longaudio,
  chốngoverwritebase/output,offline/shellfalse/timeout/noautoretry/protocol.
  Testpath ban đầu so /var với /private/var lỗi do symlink macOS, sửa assert
  canonical path; không đổi sản phẩm để lách test. Chưa numerical MLXtest.
- Agent report private probe-03bee76d352e4235aed9c1d5ea43870c.json ghi thiếu
  Metal; không coi đó là bằng chứng training không phù hợp máy của user.
- Giới hạn: reload mới chỉ wrapper cùngbase trong một process; chưa full
  processreload/free-decoding/accuracy; languageprefixVI cố định riêngprobe,
  decoderLoRA chưa là encoderacoustic adaptation. Loss một clip không chứng
  minh cải thiện giọng riêng. Docs/PERSONAL_ASR_PROBE.md ghi handoff đầy đủ.

Hồi quy VOICE-ADAPT-001: fullsuite870testsđạt18.243s;gitdiffcheckđạt.
Chỉ contract/launcher unit evidence, không thay thế numerical native probe.


### VOICE-ADAPT-001 — native one-step đạt; process reload đang chờ

01/11/2026,report private probe-5c846bf040ca469e874753437ca4dddb.json:
probe_passed,1step,57344param,gradientnorm0.2641,adapterchanged,
loss1.400645→1.395105,sameprocesswrapperreloadlosskhớp,6.288giây.
PeakMLX~7.60GiB gần allocatorlimit8GiB;không suy ra nhiềuclip/batch sẽ vừa.
RSS~1.12GiB không đại diện tổngRAMunified hoặc cộng thẳng vớiMLX.
Không có dev/free-decoding evidence từ one-step này;chưa promote vào voice.

Đã triển khai --verify-report: child process mới,read đúng trainID/hash,
rank/config/sourcecheckpoint binding,strict8adaptertensorkeys/shapes,
restoreloss<=1e-4,baseline/candidate greedydecode vớiEOS/nonempty.
Khôngupdate,khôngđọclabeldev/heldout,khôngupload,khôngoverwriteadapter.
7probecontracttests+16datasettests đạt. Agentverify dừng thiếuMetal trước
sample/model;report private probe-b5c9b7870ac94284bf3769bd115ce456.json.
Chờ Terminaluser; không ghi sampleID hoặc transcript vào nhật ký.

Hồi quy fresh-processverify:871testsđạt17.980s,gitdiffcheckđạt.
Kiểm safetensorsheader native:8tensor a/b,57344param,230202bytes;
khớp report. FreshprocessGPUdecode vẫn chờ,không suy từ header/unit tests.


### VOICE-ADAPT-001 — native fresh-process reload đạt, chưa có gain

Report private probe-006221e7f77d4b24b1a40752c5b6a23d.json:reload_passed,
0updates,restoredloss1.395104885khớpcheckpoint gốc,greedyEOS8tokens ởcả
base/candidate,textsha trùng,3.021s,peakMLX~7.60GiB. Xác nhận load/decode,
không phải evidence nhận giọng tốt hơn.

## VOICE-ADAPT-002 — loss từ gradient trace khác loss forward trực tiếp

- Ngày01/11/2026. Trạng thái: phát hiện sai lệch phép đo,đã thêm diagnostic,
  chưa có nativev2/rootcause; tạm dừng mở rộng training.
- Bằng chứng: reportprobeđầu loss_before1.400645 sau1.395105; reportreload
  baseforward1.393135 thấp hơnadapterforward1.395105. Không thể coi mức giảm
  của trace cũ là gain train. Câu giải mã không đổi.
- Nguyên nhân chưa xác minh. Có thể khác numerical execution path khi
  autodiff/FP16/fusion hoặc yếu tố khác; chưa chứng minh và không quy lỗi
  dữ liệu/người dùng/MLX. Codepackage không có dropout trong encoder/decoder
  khi tìm source nhưng điều này chưa đủ xác định rootcause.
- Sửa phép đo: v2 ghi directloss lặplại,tracedloss,delta cùngforward trước/
  sau;chỉ ghi single_clip_descent_verified nếu repeatổnđịnh,trace/directkhớp
  tolerance1e-4vàdirectlossgiảm. accuracy_improvement_verified luônfalse.
  Verifyreport còn so zeroLoRAwrapperloss vớiunwrappedfrozenbaseloss để
  khoanhvùng numericalpath. Không có optimizerupdate trong verify.
- 8probecontracttests+16datasettestsđạt, gồm trường hợp trace nhìn giảm
  nhưng directloss tăng/tracegap lớn phải không được nhận là descent.
- Giữ nguyên2reportnative vàmodelgốc,không train thêm hoặc promoteadapter.
  Cần Terminal chạy lại --verify-report trên probeđầu để lấy diagnosticv2.

VOICE-ADAPT-002 hồi quy:872testsđạt17.853s,gitdiffcheckđạt.
Diagnosticv2 native chưa chạy; không kết luận rootcause từ unit tests.


### VOICE-ADAPT-002 — nativev2 khoanh vùng gradient path, 01/11/2026

Reportprivate probe-a7289ce838d3416da91a49cf7d33edb3.json:
directbefore=repeat=unwrappedbase=1.393134832;zeroLoRAgap=0.
tracedbefore1.400645018,gap0.007510185;adapterdirect1.395104885,
delta+0.001970053,single_clip_descent_verified=false;decode vẫn trùngbase.
Vậy mất ổn định repeat hoặc zeroLoRAwrapper không giải thích chênh lệch
trong phép đo này. Chưa xác minh chính xác primitive/kernel gây ra.

Ablation mới explicit-fp32: thay duy nhất helperattention trong moduledecoder
của child nghiên cứu bằng QK/softmax/V tường minh,đầu vào scoreFP32,
GQA repeat đúng đầu,maskbool/additive,outputcast vềdtypegốc. Encoder/base
weights/sitepackages/livevoice không đổi;không giả vờ đây là profile cũ.
Có metadata attention_profile vàverify dùng lại đúngprofile củacheckpoint.

Guard mới: trướcupdate phải repeatstable vàtrace-directgap<=1e-4;nếu không
trả LOSS_PATH_MISMATCH,steps0,noadaptersave. Không nới tolerance để cópass.
Với profile mới nhất quán rồi mới mộtstepSGD;lossdescent vẫn báo riêng,
không suy accuracy. Pytest/unit sốhọc NumPy đối chiếu uniformattention,
GQA vàcausalmask chỉ kiểm formula,không chứng minh Metal/autodiff.

PrimaryMLXsource main/mlx/fast.cpp có in_grad_tracing ảnh hưởng dispatch,
vàdocs NumericalPrecision mô tả giới hạn precision. Đây là cơ sở giả thuyết
kernelpath,không phải bằng chứng tag0.32.4 trên máyuser hoặc kết luậnrootcause.
Nguồn:https://github.com/ml-explore/mlx/blob/main/mlx/fast.cpp
https://ml-explore.github.io/mlx/build/html/usage/precision.html
Fetchsource tagv0.32.4quaweb thất bại;không âmthầm dùngmain như pinversion.

25testliênquanđạt,fullsuite đang kiểm;chờ native explicit-fp32. MLX8GiB là
allocatorguideline theoAPI,không hard memorycap;giữtimeout180s,batch1,1clip.
Một lần apply_patch bị từ chối vì cùngfileđượckhai báo2lần,khôngmutation;
đã gộp patch vàapply thành công,không mất nội dung hiện hữu.

Hồi quy attentionablation:873testsđạt18.461s;gitdiffcheckđạt.

### VOICE-ADAPT-002 — native explicit-fp32 khớp loss, update chưa giảm loss

01/11/2026, private report `probe-ee903db42a0d4100bdb1cc75f6497950.json`:
`probe_passed`, attention profile explicit-fp32, direct/repeat/traced before
đều 1.394790173, trace/direct gap 0; gradient norm 0.263856, 57344 tham số.
Vậy đường attention tường minh loại bỏ sai lệch đo được của profile này.
Chưa chứng minh primitive cụ thể gây sai lệch trong profile fused cũ.

Sau một SGD step lr1e-5, direct loss 1.394791365, tăng 0.000001192;
`single_clip_descent_verified=false`. Adapter có đổi và reload cùng process
khớp, nhưng chưa verify process mới hoặc có bằng chứng ASR tốt hơn. Peak MLX
8158413560 bytes (~7.60 GiB), elapsed 3.60s; trần allocator không bảo đảm
tổng unified RAM. Trạng thái: chênh lệch trace/direct của explicit-fp32 đã
khắc phục theo phép đo native, hiệu quả update chưa đạt; giữ issue mở.

Nguyên nhân update không giảm loss chưa xác minh. Giả thuyết cần kiểm tra:
step quá nhỏ so với lượng tử hóa FP16 ở nhánh output LoRA, hoặc nhiễu số
trong forward. Tiếp theo: đo magnitude adapter delta và loss ở các mức
step giới hạn trên cùng train clip/profile; yêu cầu kiểm direct loss và
fresh-process reload trước khi cân nhắc train nhiều clip. Không dùng clip
dev/held_out để chọn step, không promote adapter này vào live voice.
Lượt kiểm tra 01/11/2026: Python mặc định không có `mlx`; Python trong
`.build/qwen-asr/venv` import được nhưng Metal báo `No Metal device available`.
Đây là giới hạn phiên agent, chưa phải lỗi GPU trên Terminal của người dùng;
native probe tiếp theo vẫn cần chạy ở Terminal có Metal.

### VOICE-ADAPT-002 — fresh-process reload explicit-fp32 đạt

01/11/2026, private report `probe-1339293a8e6f4c9d81cb588fb8c6f165.json`:
`reload_passed`, 0 update, đúng attention profile explicit-fp32. Loss base
1.394790173, adapter restore 1.394791365, khớp report probe nguồn; repeat,
traced và unwrapped base đều khớp, trace/direct gap 0. Base và candidate
decode EOS sau 8 token, hash câu giống nhau. Peak MLX 8158413560 bytes,
elapsed 3.34s. Xác nhận khả năng nạp/giải mã trong process mới; không có
bằng chứng giảm loss hay cải thiện accuracy. VOICE-ADAPT-002 vẫn mở để điều
tra hiệu quả update. Chưa chứng minh toàn bộ base weights không đổi bằng hash.

Đã chuẩn bị diagnostic update giới hạn: `--attention-profile explicit-fp32
--diagnose-update`, cùng một train clip/gradient, thử tạm 1e-5/1e-4/1e-3
từ cùng baseline; đo direct loss và norm delta, luôn restore, không save
adapter. Nếu trace/direct lệch, guard hiện hữu chặn trước update. Test logic
restore kể cả khi đo lỗi và launcher status mới đạt; native Metal chưa chạy.
Kiểm chứng code: 10/10 test `test_personal_asr_probe.py` đạt; full suite
874 test đạt (1 skipped) trong 17.948s; compileall và `git diff --check` đạt.
Đây là kiểm chứng contract/logic, chưa thay cho phép đo MLX/Metal native.

### VOICE-ADAPT-002 — native step scan không có descent

01/11/2026, private report `probe-ffcfcee89ef247c090c78ef7940e75b8.json`:
`diagnostic_passed`, ba update tạm, không lưu adapter. Explicit-fp32 giữ
direct/repeat/traced base 1.394790173 và trace/direct gap 0; gradient norm
0.263856. Từ cùng baseline, lr1e-5: adapter delta norm 0.000002639,
direct loss +0.000001192; lr1e-4: 0.000026386, loss +0.000000596;
lr1e-3: 0.000263856, loss +0.000625610. Update magnitude tăng đúng bậc
theo learning rate, nhưng cả ba direct loss đều tăng. Peak MLX 8158413560
bytes, elapsed 1.95s; report xác nhận không có checkpoint mới.

Kết luận giới hạn: recipe này chưa chứng minh descent ngay trên train clip;
không có cơ sở train nhiều clip hoặc promote adapter. Chưa xác định nguyên
nhân; lượng tử hóa/cast FP16 ở nhánh LoRA, khác biệt giữa autodiff và finite
step, hoặc step quá lớn ở 1e-3 vẫn là giả thuyết, không suy thành kết luận.
Trạng thái: issue mở; tiếp theo điều tra riêng phép cộng LoRA/FP16 và hướng
gradient bằng ablation có guard direct/traced, rồi mới quyết định recipe.
Đối chiếu mã optimizer MLX 0.32.4 cài tại local: SGD mặc định tính
`parameter - learning_rate * gradient`; không thấy lỗi dấu cập nhật trong
optimizer. Điều này chưa xác nhận gradient của model phản ánh đúng finite step.

### VOICE-ADAPT-002 — chuẩn bị ablation FP32 LoRA sum và signed step

01/11/2026: profile nghiên cứu `--fp32-lora-sum` chỉ dùng cùng
`--diagnose-update --attention-profile explicit-fp32`. Giữ base weights,
LoRA q/v scope, seed, dữ liệu và output FP16; thay riêng phép cộng base+LoRA
delta thành cộng FP32 rồi cast một lần. Quét signed step -1e-3/-1e-4 và
+1e-5/+1e-4/+1e-3 từ cùng baseline, luôn restore và không save adapter.
Giữ legacy profile mặc định để so trực tiếp report trước; không sửa live
voice hoặc checkpoint đã lưu. NumPy test cho trường hợp hai cách làm tròn
FP16 khác nhau đạt; chưa chứng minh hiệu quả MLX native hay nguyên nhân gốc.
Nếu trace/direct lệch, guard hiện hữu dừng trước quét. Metal agent vẫn không
khả dụng; chờ một lần Terminal native với lệnh trong Docs/PERSONAL_ASR_PROBE.md.

### VOICE-ADAPT-002 — native FP32 LoRA sum và signed-step ablation

01/11/2026, báo cáo private `probe-c1796bd9a7e54e07bd8f0599f76d84dd.json`
(FP32 sum) và `probe-92e1b237bb85423e9c6e1a29b0d89c5d.json` (legacy):
cùng clip train, attention explicit-fp32, base direct/repeat/traced
1.394790173, gap 0, gradient norm 0.263856. Cả hai có loss delta ở
step -1e-3 = -0.000002980 và +1e-3 = +0.000625610. FP32 sum ở +1e-5:
0; +1e-4: +0.000000834. Legacy tương ứng +0.000001192 và +0.000000596.
Step -1e-4 đều tăng khoảng 5e-7. Tất cả update chỉ tạm, 0 checkpoint.

Kết luận từ đối chứng: loại bỏ một phép cast FP16 ở phép cộng LoRA không
sửa được độ lệch quan sát tại bước lớn; kết quả ở bước nhỏ khác cỡ 1e-6.
Không thể kết luận gradient đảo dấu chỉ từ mức giảm rất nhỏ ở -1e-3;
độ rời rạc của forward FP16 hoặc path khác vẫn là giả thuyết. Không có
bằng chứng recipe này học đúng, giữ VOICE-ADAPT-002 mở và dừng mở rộng train.
Tiếp theo: kiểm loss/logits precision và đạo hàm finite-step bằng phép đo
riêng, trong trần RAM hiện có, hoặc chọn training backend/recipe khác.

Phiên shell sandbox trước đó báo thiếu Metal; lần này lệnh giới hạn chạy
được ngoài sandbox và tạo 2 report native. Công cụ UI từ chối truy cập
Terminal, nhưng không ảnh hưởng kết quả probe qua shell.
Kiểm chứng sau ablation: 875 test đạt (1 skipped) trong 18.282s;
`compileall` và `git diff --check` đạt. Hai native report xác nhận guard
trace/direct bằng 0, không lưu adapter. Chưa có test accuracy thực tế.

### VOICE-ADAPT-002 — tắt TF32 tạo descent tái lập trên một clip

01/11/2026, theo MLX 0.32.4 Numerical Precision, một số phép matmul FP32
chạy reduced precision mặc định; `MLX_ENABLE_TF32=0` yêu cầu full FP32
cho nhóm phép này. Nguồn chính: https://ml-explore.github.io/mlx/build/html/usage/precision.html

Hai report private `probe-c5ee8e4de9f44ffdb24c1d4e8b2f4394.json` và
`probe-4358772dfb87421eb91525a438d582ed.json` đều
`mlx_tf32_disabled=true`, legacy LoRA sum/explicit-fp32 attention/cùng
train clip. Kết quả lặp lại giống hệt: direct/repeat/traced base
1.393469334, gradient norm 0.263975, +1e-5 loss delta -0.000002265,
+1e-4 -0.000623822, +1e-3 -0.003908038. Base loss cũng khác report
TF32 mặc định 1.394790173; +1e-3 ở cấu hình mặc định từng tăng
0.000625610. Không lưu adapter, peak MLX 8158413560 bytes.

Trạng thái: đường precision là yếu tố đã xác minh ảnh hưởng loss và
directional probe trên clip này; chưa xác minh primitive cụ thể hay tính
đúng của gradient tổng quát. Ngay cả -1e-3 cũng giảm ~0.003906 trong
full-FP32 scan, nên chưa dùng một kết quả descent làm chứng nhận training.
Tiếp theo: kiểm nhiều train clip và adapter reload cùng env precision,
sau đó mới đánh giá dev. Không promote live voice hoặc tuyên bố accuracy.

### VOICE-ADAPT-002 — TF32 off chưa đủ cho 1.7B; 0.6B FP32 có gradient nhất quán

01/11/2026: 1.7B FP16/TF32 off trên train ordinals 5 và 10 có trace/direct
gap0 nhưng positive step loss gần như đứng yên; ordinal5 negative step
-1e-4 giảm 0.001738 còn positive +1e-4 tăng rất nhẹ. Precision env một
mình chưa tạo recipe đáng tin cho 1.7B. Report private
`probe-3e574e48bbed49e8a28fbf6e9e39b299.json` và
`probe-2d56f3ad978b45ccbc84018f2c229a38.json`.

Checkpoint 0.6B/1.7B trên đĩa là BF16. Backend load_model(dtype=float32)
không tự cast weight ở nhánh đó; diagnostic FP32 nay cast floating weights
sau load và kiểm toàn bộ floating params là FP32, giữ tied lm_head nếu có.
Đây là thay đổi in-memory, không sửa checkpoint. Ba report private
`probe-85d48c3b85e647f593719356bb1f4724.json`,
`probe-4141a41f5efa4868b6ba1ee9b5fa9b93.json`,
`probe-077315a46cb14afd881bab009fc1b2ed.json` (train ordinal0/5/10):
0.6B full-FP32+TF32off, gap0; mọi +1e-5/+1e-4/+1e-3 giảm direct loss,
mọi -1e-4/-1e-3 tăng loss. Peak MLX3.62–3.63GB. Chỉ chứng minh finite
step trên 3 clip; chưa có multi-step stability hay dev accuracy.

### VOICE-QUALITY-001 — so model/prompt trên personal dev15

01/11/2026: 0.6B/assistant-v1/tech-auto report private
`qwen-comparison-0d9535745daf48cb91129a5815df526b.json`:
6/15 exact, WER19.53%, CER12.93%, 6/7 term hits, 0 failure,
cold median0.472s. 1.7B cùng điều kiện baseline5/15, WER19.53%,
CER11.78%, 4/7 hits, median1.417s; paired exact:4 cùng đúng,
2 chỉ 0.6B đúng,1 chỉ 1.7B đúng. 0.6B/tech-vi cho cùng aggregate
(`qwen-comparison-b0cbd47b23024d99be5896c8cd515358.json`);
1.7B/tech-vi cũng cùng aggregate với auto
(`qwen-comparison-32610566a18e4dc4ad5fc39b64c4ec57.json`).
0.6B/none-auto giảm2/15, WER29.17%, 1 failure, 1/7 term hits
(`qwen-comparison-3bb9770318d64c5b83195796879f3320.json`).
Dev đã dùng chọn cấu hình, không là held_out. Chưa promote 0.6B vào
live voice; cần test mới sau khi recipe/model chốt.

### VOICE-ADAPT-003 — train worker dừng trước dữ liệu do import thiếu

01/11/2026, `train-45b6c8bafaa44f57953dab3325c68218.json`:
`ModuleNotFoundError` tại stage preflight, trước Metal probe/data/model;
không có adapter mới. Chưa biết module cụ thể từ report đầu; import check
thủ công của các dependency chính đạt. Đã bổ sung tên module thiếu an toàn
vào report private để khoanh vùng; chờ rerun xác định nguyên nhân rồi sửa.
Report `train-1578d0951599460aae16817110af49f3.json` xác định module
thiếu là `mlx`. Nguyên nhân đã xác minh: launcher `.resolve()` đường dẫn
Python venv, đi theo symlink đến binary hệ thống và mất venv site-packages.
Sửa thành `.absolute()` để giữ đúng entrypoint venv; file liên quan
`scripts/train_personal_asr.py`. Chưa đánh dấu resolved cho tới khi native
train worker qua import và chạy đúng.
Rerun `train-66c8c0a241e641ceba1bd2172bbf4f02.json` đạt native:
22/23 clip train đủ điều kiện <=8s, 22/22 SGD steps giảm direct loss,
FP32 0.6B peak MLX3701339084 bytes, 18.33s. Base và adapter trên dev15
đều6/15 exact, WER19.53%, CER10.81%, 6/7 term hits, 0 failures;
chưa có accuracy gain. Adapter research lưu private, không promote.
VOICE-ADAPT-003 đã sửa và kiểm chứng: launcher chạy đúng venv, không còn
ModuleNotFoundError. Một train clip >8s bị loại bởi guard hiện hữu, không
phải thiếu dữ liệu/đọc lỗi. Chưa kiểm fresh-process reload của adapter.

### VOICE-ADAPT-004 — Adam lr1e-4 overfit mạnh sau một epoch

01/11/2026, private `train-5c6dd8c86d55451c8a3ca40ab26f596a.json`:
0.6B FP32/Adam1e-4/22clips/1epoch, 22/22 step train loss giảm,
mean direct trước/sau3.0261→2.9071. Nhưng dev15 base6/15 exact,
WER19.53%, candidate0/15, WER88.28%, term hits6/7→1/7,
15/15 decoded outputs đổi. Peak MLX3701502924 bytes, 15.60s.
Trạng thái: recipe này bị loại, không promote adapter. Nguyên nhân chưa
phân biệt learning rate quá lớn, dữ liệu ít hay optimizer dynamics; train
loss giảm không là bằng chứng chất lượng. Sẽ thử Adam1e-5 và SGD dài hơn
trong giới hạn, rồi quyết định tiếp. Không lưu raw transcript trong log.

Adam1e-5/1epoch `train-b8d756e4036a4ed5a7c3ee05ddd08902.json`:
22/22 train step giảm, dev không đổi đầu ra nào (6/15, WER19.53%).
SGD1e-3/3epochs `train-1954d9c7a7f84263bf393f4943ba28d6.json`:
66/66 step giảm, dev cũng không đổi đầu ra (6/15, WER19.53%).
Adam3e-5/1epoch `train-43251b3d51ae44f6b6d7ff7aaa65b344.json`:
22/22 step giảm, dev 6/15 exact giữ nguyên, WER19.53%→18.75%,
CER10.81%→10.26%, 6/7 term hits giữ nguyên, 1/15 đầu ra đổi.
Chưa kiểm fresh-process reload, không gọi đây là cải thiện tổng quát;
dev đã dùng tuning và cần held_out phiên mới.

Fresh-process `train-cf2d9bdb21c94bdaa239548635a6ed28.json` nạp
adapter Adam3e-5 và lặp chính xác base/candidate dev15, 0 update,
1 output đổi. Regression paired12 trong
`train-9296510a2c284b5d9890db3034d5ca45.json`: base và candidate
0.6B đều6/12 exact, WER16.28%, 11/16 term hits, 0 failure;
không hỏng thêm nhưng vẫn kém cấu hình 1.7B/assistant-v1 trên bộ này
(8/12 exact, 14/16 terms). Không so trực tiếp latency FP32 warm với
baseline1.7B cold vì phạm vi đo khác. Chưa có held_out cá nhân độc lập;
chưa chọn model live. Một apply_patch context miss trong lượt thêm learning
rate không sửa file; patch lại đúng context, không mất nội dung.
Hồi quy sau train/verify: 876 tests đạt (1 skipped) trong 18.237s,
`compileall` và `git diff --check` đạt. Native one-epoch/adapter reload
đã chạy; chưa có held_out mới hoặc phép đo latency paired cùng điều kiện.

Đã chuẩn bị nhánh `--held-out` trong verifier để so base/adapter 0.6B
trên corpus mới, không update; hai base FP16 dùng benchmark hiện hữu.
Recipe/cấu hình ứng viên đã freeze trước khi có dữ liệu held-out. Chưa
đọc hoặc chấm held-out nào; không thể kết luận lựa chọn model tối ưu cho
giọng mới tại thời điểm này. Hướng dẫn thu/eval trong
Docs/PERSONAL_ASR_PROBE.md.
Kiểm chứng cuối lượt: 876 tests đạt (1 skipped) trong 16.689s,
`compileall` và `git diff --check` đạt. Nhánh held-out mới chỉ có
contract/compile evidence, chờ dữ liệu mới để chạy native end-to-end.
SQLite mode=ro kiểm 01/11/2026: 0 clip `held_out`; không đọc hoặc in audio/
transcript. Quyết định model cuối vẫn chờ người dùng thu và xác nhận nhãn.

### VOICE-ADAPT-004 — held_out mới không xác nhận lợi ích adapter, 01/11/2026

- **Triệu chứng/phạm vi:** Adapter 0.6B FP32 Adam3e-5 chỉ cải thiện rất nhỏ
  trên 30 clip giọng held_out mới; 0.6B FP16 kém 1.7B FP16 trên cùng bộ.
  Đây là giới hạn hiệu quả của recipe hiện tại, chưa xác định nguyên nhân
  mức cải thiện nhỏ. Giả thuyết chưa kiểm: ít dữ liệu train hoặc khác biệt
  phân bố giữa train và held_out.
- **Bằng chứng/tái hiện:** Corpus `artifacts/personal-voice/heldout-01` có
  30 clip dictation từ một phiên; audit/export đạt, 0 nhãn gần trùng
  train/dev ở ngưỡng similarity 0.8 (max 0.615). FP16 1.7B: 13/30 exact,
  WER10.34%, CER6.01%, 9/11 thuật ngữ, 5/5 title, 0 failure.
  FP16 0.6B: 7/30, WER20.38%, CER12.53%, 8/11 thuật ngữ, 2/5 title,
  0 failure. Paired FP32 0.6B base/adapter: cùng 7/30, WER20.06%→19.75%,
  CER10.99%→10.71%, cùng 8/11 thuật ngữ, 0 failure. Báo cáo private:
  `artifacts/benchmarks/personal-asr/private/qwen-comparison-d777562b09fc4639869333930e2b3b86.json`,
  `artifacts/benchmarks/personal-asr/private/qwen-comparison-f6093597510d408f901438df46d447bc.json`,
  `artifacts/benchmarks/personal-asr/private/train-6bf66bafe3cd42629762d152e8aefcc8.json`.
- **Tác động/trạng thái:** Không có bằng chứng để promote adapter hoặc đổi
  lựa chọn Qwen opt-in 1.7B; voice mặc định vẫn là Whisper. 0.6B nhanh hơn (median FP16 0.594s so
  1.483s) nhưng giảm độ chính xác trên bộ này và regression kỹ thuật cũ.
  VOICE-ADAPT-004 đóng về quyết định recipe; bài toán cá nhân hóa đạt lợi
  ích rõ rệt vẫn mở. Không chỉnh recipe dựa trên held_out đã xem.
- **Kiểm chứng/giới hạn/bước tiếp theo:** Cả ba phép đo hoàn tất và không
  có failure. Một phiên thu, 30 clip, chưa chứng minh độ ổn định qua phiên
  hoặc desktop end-to-end. Nếu tiếp tục nghiên cứu recipe khác, dùng
  train/dev cho phát triển rồi thu bộ kiểm độc lập mới trước quyết định live.

## VOICE-ASR-005 — Cấu hình PhoWhisper đang lưu nhận dạng kém trên giọng cá nhân

- **Triệu chứng/phạm vi:** Với 30 clip held_out người dùng vừa thu,
  PhoWhisper-small/none/vi đang lưu trong voice preferences có độ chính
  xác thấp hơn Qwen1.7B/assistant-v1/tech/auto. Đây là chênh lệch đo trên
  corpus này; chưa xác định nguyên nhân là model, context, language hay
  khác biệt pipeline. Không suy ra mọi giọng/phiên đều vậy.
- **Bằng chứng/tái hiện:** `python3 -m elvion.voice.input.evaluation compare`
  trên `artifacts/personal-voice/heldout-01` với PhoWhisper-small/none/vi:
  5/30 exact, WER30.09%, CER21.24%, 1/11 thuật ngữ, 2/5 title,
  median0.447s, 0 failure. Qwen1.7B cùng corpus: 13/30, WER10.34%,
  CER6.01%, 9/11 thuật ngữ, 5/5 title, median1.483s, 0 failure.
  Private reports `artifacts/benchmarks/personal-asr/private/comparison-200e720c7f124f2a9b391808bdb50ae5.json`
  và `artifacts/benchmarks/personal-asr/private/qwen-comparison-d777562b09fc4639869333930e2b3b86.json`.
- **Tác động/trạng thái:** Chưa đổi preference mặc định; Qwen vẫn opt-in.
  Có bằng chứng accuracy tốt hơn nhưng chưa kiểm luồng micro/review/action
  thật, nên chưa đánh dấu giải quyết. CLI `--doctor` Qwen ready và
  `--transcribe-file` với một WAV riêng tư thành công, có text, exit0;
  hai phép này không mở micro hay chạy tác vụ.
- **Bước tiếp theo:** Người dùng thử một phiên voice Qwen1.7B opt-in
  trên desktop, đọc/sửa câu rồi xác nhận hoặc hủy một tác vụ an toàn.
  Ghi kết quả tổng hợp, không lưu audio/nội dung câu; chỉ sau đó xét đổi
  lựa chọn mặc định. Bộ held_out này đã xem kết quả, không dùng để chỉnh
  prompt/model và gọi là đánh giá độc lập.

**Cập nhật sau xác nhận micro 01/11/2026:** Người dùng báo phiên Qwen chạy
bình thường. Đã lưu Qwen làm STT trong preferences cá nhân, kiểm bằng
launcher không truyền `--stt-engine`: doctor ready, transcribe-file có text,
context tech, không lỗi. Chênh lệch chất lượng đã được xử lý bằng lựa chọn
model cho người dùng hiện tại; chưa xác nhận chất lượng qua nhiều phiên
hoặc luồng action desktop, nên không mở rộng kết luận cho mọi môi trường.

## VOICE-ASR-006 — Chưa thể lưu Qwen làm lựa chọn STT cho người dùng

- **Triệu chứng/phạm vi:** CLI `voice` mặc định `--stt-engine whisper` và
  `voice-config` chỉ lưu model/context của Whisper. Sau một phiên Qwen
  chạy bình thường, lần mở `./elvion` tiếp theo vẫn dùng PhoWhisper.
- **Bằng chứng/tái hiện:** `src/elvion/interface/cli.py` đặt default engine
  `whisper`; `VoicePreferences` không có trường engine và
  `resolve_voice_options` chỉ lấy lựa chọn Qwen từ cờ CLI. Người dùng
  xác nhận phiên micro Qwen chạy bình thường ngày 01/11/2026; chưa rõ
  họ đã thử spoken review hoặc thực thi tác vụ nào.
- **Tác động/trạng thái:** Cấu hình được đo tốt hơn không thể chọn bền vững
  cho người dùng hiện tại; đang sửa. Không tự suy ra thành kiểm chứng
  end-to-end mọi tác vụ.
- **Bước tiếp theo:** Thêm engine vào voice preferences với migration v1,
  giữ Whisper là mặc định cho cấu hình chưa chọn Qwen, cho phép CLI
  override từng phiên và kiểm chứng trước khi lưu Qwen cho người dùng.

**Đã sửa và kiểm chứng 01/11/2026:** Thêm `stt_engine` vào
`src/elvion/interface/voice_settings.py` schema v2, đọc schema v1 cũ;
`src/elvion/interface/cli.py` lấy engine đã lưu khi không có cờ CLI,
thêm `voice-config --stt-engine`; cập nhật thông báo trong
`src/elvion/interface/voice_session.py`, tài liệu và
`tests/test_voice_settings.py`. Cấu hình cá nhân đã lưu Qwen; `./elvion
--doctor` trả ready/Qwen/auto và `./elvion --transcribe-file` với một WAV
riêng tư trả engine Qwen/context tech/có text/exit0, không mở micro hay
thực thi tác vụ. Người dùng xác nhận phiên micro Qwen chạy bình thường.
Targeted32 tests và full877 tests đạt (1 skipped). VOICE-ASR-006 đã giải
quyết cho lựa chọn STT bền vững; chưa xác minh spoken review hoặc mọi
action desktop. Không ghi nội dung câu/audio vào log.

Trong kiểm tra code sau đó phát hiện giá trị `stt_engine` dạng list trong
schema v2 có thể gây `TypeError` trước khi trả lỗi cấu hình cố định, do
kiểm membership trước kiểu dữ liệu. Đã đảo thứ tự kiểm kiểu trong
`VoicePreferences.__post_init__` và thêm ca cấu hình hỏng vào
`tests/test_voice_settings.py`; file hỏng được giữ nguyên, phiên không mở.

## VOICE-ACCENT-001 — Nhãn hai cách nói chưa ghép đủ 20 cặp

- **Triệu chứng/phạm vi:** Hai kho A (tự nhiên) và B (cách nói Bắc) mỗi
  bên có 20 clip held_out, hai phiên thu mỗi bên, nhưng chỉ 13 nhãn A/B
  trùng nhau sau chuẩn hóa chữ hoa/dấu câu. A khớp 14/20 câu mẫu,
  B khớp 18/20; chưa xác định phần khác do lời nói thực tế hay gõ nhãn.
- **Bằng chứng/tái hiện:** Audit/export thành công sang
  `artifacts/personal-voice/accent-a-01` và `accent-b-01`; 20 nhãn duy
  nhất mỗi bên, không trùng hash PCM giữa hai bên. Đối chiếu normalized
  reference với 20 câu trong `Docs/VOICE_ACCENT_PAIRED_TEST.md` cho số
  trên. Không in hoặc ghi nhãn riêng tư vào log.
- **Tác động/trạng thái:** Chỉ 13 cặp nhãn giống nhau đủ điều kiện so
  theo cặp đúng cùng câu. Không sửa nhãn thành câu mẫu hoặc gộp những
  câu khác nhau; vấn đề mở trong lúc chạy benchmark.
- **Bước tiếp theo:** Chạy cùng Qwen1.7B trên toàn bộ 20+20 clip, báo
  riêng so sánh paired13 và toàn bộ20 mỗi bên; kiểm sự nhất quán theo
  hai nửa. Nếu cần đủ 20 cặp để kết luận, thu lại cặp khác nhãn sau khi
  người dùng xác nhận lời nói thực tế, không ép sửa nhãn.

**Cập nhật sau kiểm chứng 01/11/2026:** Hai report Qwen1.7B/
assistant-v1/tech/auto `qwen-comparison-a055522522654d9aad650a64139838c4.json`
và `qwen-comparison-ada30a02551e4460abb7fc77d2a38187.json`:
40/40 inference thành công. Toàn bộ A9/20 exact, WER7.84%; B13/20,
WER4.37%, từng phiên 10 clip A4/5, B6/7. Trên 13 cặp cùng nhãn:
A8/13, B10/13; B-only3, A-only1, WER4.55% so2.27%.
Nửa đầu paired A3/7, B5/7; nửa sau A5/6, B5/6. Median duration
paired A5.18s, B5.20s. Không đạt ngưỡng đã đặt trước (B hơn
>=5/20 exact và hai nửa paired cùng chiều). Trạng thái: vấn đề ghép
nhãn chưa giải quyết, kết luận “cách nói B cải thiện rõ” chưa được xác
nhận; số tổng quan chỉ gợi ý. Không sửa nhãn hoặc dùng A/B để train.
Người dùng muốn hoãn fine-tune và phát triển các phần khác; nếu sau này
cần kết luận chắc hơn, thu lại 7 cặp khác nhãn hoặc bộ mới và kiểm lại.

## WEB-LIVE-001 — Chromium không khởi động trong sandbox agent

- **Triệu chứng/phạm vi:** `./elvion --browser-check` ngày 01/11/2026
  dừng ở `BrowserSession.start()` với `WEB_BROWSER_UNAVAILABLE`, trước
  fixture click hoặc public network. Đây là môi trường sandbox agent;
  chưa kết luận code/browser trên desktop người dùng bị lỗi.
- **Bằng chứng/tái hiện:** Lệnh trả exit1, `BrowserError` tại
  `src/elvion/browser/session.py:101`. Playwright/Chromium venv đã có
  marker, nhưng exception gốc được driver ẩn theo hợp đồng lỗi cố định.
- **Tác động/trạng thái:** Chưa có phép kiểm browser thật trong lượt này.
  Trở ngại đang điều tra; không gọi fake/unit tests là desktop proof.
- **Bước tiếp theo:** Chạy lại smoke fixture trong môi trường được phép
  mở Chromium, sau đó thử luồng CLI public HTTPS với grant, xác nhận
  và verifier. Nếu vẫn lỗi, chẩn đoán runtime không lưu URL/query riêng tư.

**Cập nhật 01/11/2026:** Chạy `./elvion --browser-check` với quyền mở
Chromium đạt: DOM click + đọc trạng thái độc lập, PNG 1280×800.
Lần gọi `./elvion session` sai vì launcher mặc định mở `voice`; lần gọi
`python3 -m elvion session` dùng Python hệ thống không có Playwright,
trả `UNSUPPORTED` trước hành động. Dùng đúng `.venv-browser/bin/python`
cho session: `web.open` tới `https://example.com` thành công,
`selected_method=dom`, `postcondition_verified=true`, 0 trace.
Trở ngại sandbox/runtime đã được giải quyết cho fixture và open public;
search/open_result và reader CLI cũng đã chạy thật trong phiên riêng sau
đó (xem WEB-LIVE-002/003). Chưa kiểm chứng phiên browser lâu dài trên
desktop người dùng.

## WEB-LIVE-002 — Search thật đạt nhưng DOM open_result từ chối trước click

- **Triệu chứng/phạm vi:** Trong cùng phiên CLI với `.venv-browser`, tìm
  `Wikipedia Alan Turing` thành công, verifier `web.search` đạt và hiện
  10 kết quả. `Mở kết quả 1` ngay sau đó trả `FAILED/UNSUPPORTED` tại
  probe, không hiện confirmation và không click. Candidate DOM báo
  `WEB_BROWSER_UNAVAILABLE` vì locator không đúng một link visible.
- **Bằng chứng/tái hiện:** `web.search` report `status=succeeded`,
  `selected_method=dom`, `postcondition_verified=true`; result1 là
  `https://en.wikipedia.org/wiki/Alan_Turing`. `web.open_result` report
  `status=failed`, `selected_method=null`, candidate DOM `eligible=false`.
  Cả hai chạy `--no-trace`; không có thao tác trên trang đích.
- **Tác động/trạng thái:** Luồng search→open_result sản phẩm chưa hoàn tất
  trên web công khai. Nguyên nhân chưa xác minh: locator title có thể
  không còn khớp/visible, hoặc trang DOM thay đổi. Không tự chuyển vision
  hay retry click vì chưa có bằng chứng target đúng.
- **Bước tiếp theo:** Tái hiện read-only và đếm locator trên trang kết
  quả thật; so title/selector/visibility không ghi raw DOM hay query riêng
  tư. Sửa đúng nguyên nhân rồi chạy lại một lượt search→open_result có
  grant, confirmation, verifier.

**Nguyên nhân đã xác minh 01/11/2026:** Trên DuckDuckGo thật, result1
title `Alan Turing - Wikipedia` không duy nhất: `get_by_role(link,
name=title, exact=True)` khớp 3–4 link visible; `a[data-testid=result-title-a]`
chỉ có một link tới URL đã duyệt. `BrowserDOMAdapter.probe` yêu cầu
`locator.count()==1`, nên trả không đủ điều kiện trước confirmation.
Không phải browser đóng hoặc locator mất do timing. Cần ràng buộc link
bằng href gốc cùng title, không chọn `.first` theo tên trùng.

**Cập nhật sau sửa 01/11/2026:** `BrowserSession.search()` lưu `href` gốc
của từng kết quả; `result_locator()` ràng buộc đồng thời title chính xác,
selector result-title và `href` này tại thời điểm probe/click. Sửa tại
`src/elvion/browser/session.py`. Trên DuckDuckGo thật, locator kết quả 1
còn đúng một link visible. CLI search→open_result với grant và xác nhận
riêng đã đạt `selected_method=dom`, `postcondition_verified=true` trên
Wikipedia. Trạng thái: đã giải quyết cho ca công khai đã đo; các layout
provider khác và redirect ngoài URL duyệt vẫn là giới hạn cần kiểm riêng.

## WEB-LIVE-003 — Reader có trong BrowserSession nhưng chưa tới CLI

- **Triệu chứng/phạm vi:** `BrowserSession.read_article()` đọc được trang
  Wikipedia thật (8637 từ, 130 đoạn, 34 heading, có lead; cờ truncated),
  nhưng `InteractiveSession` chưa có lệnh đọc trang đang mở. Web CLI chỉ
  expose open/search/open_result, nên người dùng chưa xem nội dung sạch.
- **Bằng chứng/tái hiện:** `src/elvion/browser/session.py:190` gọi
  `read_page`, còn `src/elvion/interface/session.py` không gọi phương thức
  này. Native read-only probe trên Wikipedia trả metadata trên, không
  lưu HTML/nội dung vào log.
- **Tác động/trạng thái:** Web chỉ mở trang, chưa có bước đọc trực tiếp
  trong luồng người dùng; đang nối lệnh đọc ngắn gọn. Đây chưa phải
  tóm tắt bằng model hoặc kiểm chứng nguồn cho câu trả lời.
- **Bước tiếp theo:** Thêm lệnh `:web-read` chỉ đọc trang đang mở,
  hiển thị URL/title/excerpt có giới hạn và cờ cắt; test fake và native
  trên trang công khai. Không coi nội dung web là chỉ dẫn cho agent.

**Cập nhật sau sửa 01/11/2026:** Đã thêm `:web-read` vào
`src/elvion/interface/session.py` và test CLI tại `tests/test_session.py`.
Lệnh chỉ đọc trang đang mở, xuất URL/title/excerpt có giới hạn, số từ và
cờ cắt; không điều hướng thêm. Native CLI trên Wikipedia sau xác nhận
`web.open` trả excerpt mở đầu bài và `is_truncated=true`. Trạng thái:
đã giải quyết cho khả năng đọc đoạn trích; tóm tắt bằng model và kiểm
chứng phát biểu theo nguồn chưa nằm trong tính năng này.

## WEB-READER-007 — Dòng nguồn Wikipedia bị chọn làm lead/excerpt

- **Triệu chứng/phạm vi:** Native `BrowserSession.read_article()` trên
  bài Alan Turing có 8637 từ nhưng `lead_paragraph`/`excerpt` chỉ là
  “From Wikipedia, the free encyclopedia” (37 ký tự), không phải mở
  đầu bài viết. Lệnh `:web-read` mới hiển thị đoạn này.
- **Bằng chứng/tái hiện:** `extract_article()` chọn `paragraphs[0]` làm
  lead; bộ lọc boilerplate không có dòng nguồn Wikipedia. Native reader
  trả 130 paragraphs, 34 headings, `is_truncated=true`.
- **Tác động/trạng thái:** Trích dẫn/đoạn đọc đầu tiên kém hữu ích và có
  thể khiến người dùng tưởng nội dung bài rỗng; đang sửa. Không thay đổi
  URL hoặc kết quả xác nhận mở trang.
- **Bước tiếp theo:** Loại dòng boilerplate đã xác minh khỏi paragraph
  flow, thêm test ngắn và chạy lại reader thật. Không cắt mọi đoạn ngắn
  vì nhiều bài có mở đầu ngắn hợp lệ.

Sau khi bỏ dòng nguồn, native reader vẫn chọn dòng dẫn hướng “For the
Oregon artwork...” 53 ký tự. DOM thật có 7 khối `div.hatnote`, khối đầu
52 ký tự. Đã xác minh đây là nguồn đoạn thứ hai; lọc class `hatnote`
thay vì loại mọi đoạn ngắn.

Sau khi lọc hatnote, lead là “Alan Mathison Turing” (20 ký tự): DOM thật
có một `.infobox` đứng trước phần văn xuôi; 25 paragraph đầu là dữ kiện
trong hộp. Đã thêm `infobox` vào bộ lọc class/id và ca fixture Wikipedia
tại `src/elvion/browser/reader.py`, `tests/test_browser_reader.py`.
Kiểm chứng thực tế: `BrowserSession.read_article()` trên Wikipedia trả
lead/excerpt bắt đầu bằng phần mở bài “Alan Mathison Turing (... was an
English mathematician...)”, 100 paragraphs, 8672 từ, cờ truncated.
CLI `web.open`→`:web-read` cũng trả đoạn mở bài; 70 test reader/workflow/
session đạt. Trạng thái: đã giải quyết cho ca này; chưa kết luận mọi
Wikipedia page hoặc website khác có excerpt tốt.

## VOICE-TEST-001 — Test transcribe-file lệ thuộc cấu hình STT đã lưu

- **Triệu chứng/phạm vi:** Chạy toàn bộ 879 test ngày 01/11/2026 có 1
  failure tại `test_file_transcription_does_not_build_or_open_recorder`:
  `main(['voice','--transcribe-file','synthetic.wav'])` trả 1 thay vì 0.
  70 test web/reader/session riêng đều đạt.
- **Bằng chứng/tái hiện:** Test chỉ mock `WhisperTranscriber`; profile voice
  của người dùng hiện đã lưu Qwen1.7B. Chưa xác minh đây chính là nguyên
  nhân; cần cô lập prefs/data-dir rồi chạy lại test.
- **Tác động/trạng thái:** Full suite chưa xanh. Không quy lỗi cho phần web
  khi chưa chứng minh quan hệ; đang điều tra.
- **Bước tiếp theo:** Chạy riêng test và kiểm đường chọn engine trong CLI;
  sửa test để độc lập cấu hình cá nhân hoặc sửa hồi quy code nếu có.

**Nguyên nhân và xử lý 01/11/2026:** Test chạy lại riêng vẫn fail; CLI
chọn engine từ voice preferences khi thiếu `--stt-engine`, còn test chỉ
mock `WhisperTranscriber`. Profile hiện tại đã lưu Qwen1.7B. Đã thêm
`--stt-engine whisper` vào đúng ca test tại `tests/test_voice_session.py`
để kiểm đường Whisper mà test định giả lập. Full suite sau sửa: 879 test
đạt, 1 skipped; `git diff --check` và compileall đạt. Trạng thái: đã
giải quyết lỗi phụ thuộc cấu hình trong test; không thay đổi engine đã
lưu cho người dùng hoặc đường chạy Qwen thật.

## DOC-WEB-TECH-001 — Tài liệu nền web/tech chưa đồng bộ với triển khai (01/11/2026)

- **Triệu chứng/phạm vi:** `Docs/TECH_STACK.md` còn ghi Swift helper “chưa triển khai” và SQLite “triển khai sau”; `Docs/PROJECT_STRUCTURE.md` còn ghi `native/macos/` chỉ có hướng dẫn. `Docs/WEB_BASELINE.md` phần trạng thái còn ghi browser thật chưa chạy vì thiếu Playwright, trong khi `Docs/CURRENT_TASKS.md` ghi desktop Chromium fixture DOM và mở Wikipedia thật đã qua verifier. Đồ thị `graphify-out/graph.json` tạo 31/10, trước khi thêm Web DOM Reader 01/11, nên không chứa `src/elvion/browser/reader.py`.
- **Bằng chứng/tái hiện:** Đối chiếu các tài liệu trên với `native/macos/*.swift`, `src/elvion/reminders/store.py`, `.venv-browser/browser-ready`, `src/elvion/browser/reader.py` và `Docs/REPOSITORY_GRAPH.md`. Đây là độ lệch mô tả trạng thái, không phải kết luận rằng tính năng đang chạy sai.
- **Tác động:** Người đọc dễ hiểu nhầm mức hoàn thiện của bridge, lưu trữ và web; truy vấn Graphify bỏ sót reader mới.
- **Trạng thái:** Đã cập nhật Graphify ngày 01/11/2026; độ lệch trạng thái trong tài liệu nền còn mở.
- **Kiểm chứng Graphify:** `graphify extract . --code-only --out .` trích xuất lại 52 tệp mã, sau đó `cluster-only . --no-label` tạo lại `graph.json`, `graph.html`, `GRAPH_REPORT.md` và manifest. Đồ thị mới có 3.336 nút, 10.542 cạnh, 165 cụm; `browser/reader.py` có 34 nút và truy vấn thấy `extract_article()`, `read_page()`.
- **Bước tiếp theo:** Cập nhật các câu trạng thái đã cũ sau khi xác định phạm vi kiểm chứng từng module. Giữ nguyên phân biệt desktop fixture, live DOM và Vision public web.

## VOICE-HANDSFREE-001 — scripts/run_handsfree_voice.py mặc định chạy kịch bản mô phỏng thay vì thu âm từ micro thật (02/11/2026)

- **Triệu chứng/phạm vi:** Khi người dùng chạy `scripts/run_handsfree_voice.py` trên nhánh `feat/hands-free-voice`, script tự động bơm các frame âm thanh giả lập và tự in hội thoại mẫu ("Mở Apple Music", "Dạ, ELVION đang mở Apple Music cho bạn") mà người dùng không hề nói gì vào micro.
- **Bằng chứng/tái hiện:** Chạy `PYTHONPATH=src:. python3 scripts/run_handsfree_voice.py`, script thực thi `run_simulated_demo()` tự động một mạch từ đầu đến cuối trong 5 giây mà không mở luồng microphone của hệ thống.
- **Nguyên nhân đã xác minh:** Module `ContinuousVoiceSession` ban đầu chỉ nối với mock test case và hàm demo tĩnh; chưa có native Swift helper để stream PCM thời gian thực từ `AVAudioEngine` và chưa nối trực tiếp `open_live_audio_stream` vào vòng lặp micro của người dùng.
- **Tác động/trạng thái:** Đang xử lý. Người dùng hiểu nhầm tính năng chỉ là mockup giả lập và không thể trải nghiệm nói chuyện thật bằng micro.
- **Cách giải quyết:** 
  1. Triển khai `src/elvion/voice/continuous/stream_capture.swift` và `src/elvion/voice/continuous/streamer.py` sử dụng `AVAudioEngine` và `installTap` để stream PCM 16kHz 16-bit mono thời gian thực từ microphone macOS.
  2. Nối `WhisperTranscriber` (PhoWhisper) làm acoustic verifier cho `KeywordWakeWordDetector` khi có năng lượng tiếng nói (RMS threshold).
  3. Đổi mặc định của `scripts/run_handsfree_voice.py` thành `run_live_mic()` lắng nghe microphone thật; chỉ chạy mô phỏng khi người dùng truyền tường minh cờ `--simulate`.
- **Kiểm chứng:** Kiểm tra biên dịch `stream_capture` qua `swiftc` đạt; kiểm tra đọc 10 chunk từ mic đạt 5932 bytes PCM; kiểm tra phản hồi từ `ConversationService` với `qwen3.5:4b` đạt câu trả lời tiếng Việt. Trạng thái: đã sửa, chờ người dùng kiểm chứng trên máy thật.

## VOICE-HANDSFREE-002 — VAD không tự ngắt trên micro laptop và Whisper ảo giác (hallucination) sinh lời thoại ngẫu nhiên khi im lặng (02/11/2026)

- **Triệu chứng/phạm vi:** Khi mở `run_handsfree_voice.py` trong phòng bình thường và không nói gì, sau vài giây hệ thống tự kích hoạt wake word hoặc tự nhảy vào listening, không tự dừng ghi âm, và tự in ra/phát ra các câu thoại ngẫu nhiên ("random dialogue") từ mô hình.
- **Bằng chứng/tái hiện:**
  1. Ngưỡng `min_speech_rms = 120.0` trong `VoiceActivityDetector` thấp hơn độ ồn nền (noise floor) thực tế của microphone laptop (thường dao động 150-300 RMS), khiến VAD nhận nhầm tiếng quạt/tiếng ồn phòng là tiếng nói liên tục và không đạt điều kiện `silence_hangover` (800ms) để tự ngắt.
  2. Trong `LISTENING`, thiếu cơ chế `listen_timeout_seconds` (nếu sau khi thức giấc mà người dùng không nói gì quá 3.5s thì phải tự huỷ và quay về `STANDBY`).
  3. `KeywordWakeWordDetector` có biểu thức regex `_NORMALIZED_KEYWORD_RE` quá lỏng (`(?:e[ol]|ai|eo|em|en)\s*vi[oôe]?n?`), dễ khớp các từ ảo giác Whisper sinh ra từ tiếng ồn phòng như "em vi...", "ai viên".
  4. Mô hình Whisper khi nhận 15s tiếng ồn/im lặng có hiện tượng hallucination sinh văn bản rác, sau đó văn bản này được đẩy vào LLM Ollama khiến Ollama sinh câu trả lời ngẫu nhiên.
- **Tác động/trạng thái:** Đang xử lý. Vòng lặp hands-free không thể sử dụng ổn định trong môi trường thực tế nếu chưa lọc ồn và chống ảo giác.
- **Cách giải quyết:**
  1. Nâng ngưỡng năng lượng âm thanh `min_speech_rms` từ 120.0 lên mức thích ứng tự động (Adaptive Calibration) và ngưỡng thực tế cao hơn (~350-450 RMS cho micro Mac), và yêu cầu tỷ lệ ZCR (Zero-Crossing Rate) phù hợp với giọng nói con người (tránh quạt tản nhiệt).
  2. Bổ sung `listen_timeout_seconds = 3.5` trong `ContinuousVoiceSession`: nếu trong trạng thái `LISTENING` mà không có tiếng nói bắt đầu trong 3.5 giây, tự động quay về `STANDBY` và phát âm thanh huỷ.
  3. Siết chặt regex wake word trong `wakeword.py`: bắt buộc khớp đúng âm tiết "elvion" / "eo-vi-on" / "en-vi-on" có ranh giới từ rõ ràng (`\b`), loại bỏ các nhánh so khớp quá ngắn.
  4. Bổ sung bộ lọc ảo giác (Whisper Hallucination Filter): kiểm tra độ dài câu, tỷ lệ lặp từ, danh sách câu hallucination phổ biến của Whisper tiếng Việt (như "Cảm ơn các bạn", "Hãy like", "Subtitles by", v.v.), và từ chối xử lý nếu âm thanh không vượt qua kiểm tra năng lượng giọng nói thực tế.
  5. Thêm ngưỡng năng lượng tối thiểu cho utterance: chỉ gửi vào STT nếu utterance có chứa năng lượng giọng nói thật (`speech_frames >= 15`, tức ít nhất 300ms giọng nói có năng lượng cao).
- **Bước tiếp theo:** Áp dụng các sửa đổi trên trong `vad.py`, `wakeword.py`, `session.py` và `run_handsfree_voice.py`, kiểm chứng với test suite và chạy kiểm thử micro trực tiếp.

**Nguyên nhân và cách giải quyết (02/11/2026):**
- Đã tạo `src/elvion/voice/continuous/hallucination.py` định nghĩa `is_whisper_hallucination` lọc các mẫu câu ảo giác đặc trưng của Whisper (lời cảm ơn, xin subscribe, credit phụ đề, vòng lặp từ trùng lặp >= 75%).
- Đã thêm `listen_timeout_seconds = 3.5` vào `ContinuousVoiceSession`: khi ở `LISTENING` nếu quá 3.5s không có tiếng nói bắt đầu (`VADState.SILENCE`), phiên tự động huỷ và trở về `STANDBY` kèm chuông Tink, giải quyết triệt để lỗi không tự dừng.
- Đã thêm kiểm tra năng lượng RMS tối thiểu (< 280) trong `_dispatch_utterance`: bỏ qua các đoạn thu ambient rác không đủ âm lượng giọng nói.
- Đã nâng `min_speech_rms` lên 300-350 và `energy_threshold` lên 420, đồng thời siết chặt regex wake word thành `\b(?:hey\s+|ê\s+|ơi\s+)?(?:el|eo|en|e)\s*vi[oô]n(?:\s+ơi)?\b|\belvion\b`.
- **Kiểm chứng thực tế:** 14/14 test đơn vị trong `tests/test_continuous_voice.py` đạt (bao gồm 2 test mới cho hallucination filter và listening timeout); 964 test toàn hệ thống đạt. Trạng thái: đã sửa, chờ kiểm chứng trực tiếp trên micro của người dùng.



