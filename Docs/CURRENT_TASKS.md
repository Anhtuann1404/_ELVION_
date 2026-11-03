# Công việc hiện tại

- Hands-free đã nối lệnh chỉ đọc “Xem nhắc việc hôm nay”. Chạy
  `scripts/run_handsfree_voice.py --acoustic-wake --reminder-list`.
  Đọc nhắc việc đang chờ đến hạn hôm nay theo giờ Việt Nam, tối đa năm
  mục mỗi lượt. Chờ thử mic thật trước khi nối tạo nhắc việc có xác nhận.

- Người dùng xác nhận pilot `--acoustic-wake` hoạt động ổn trên mic thật.
  Có thể dùng chế độ này cho các phiên cá nhân. Số liệu độ ổn định dài
  hạn và quyết định bật mặc định vẫn chưa chốt.

- Pilot dò câu gọi cá nhân `scripts/run_handsfree_voice.py --acoustic-wake`.
  Replay 7/9 mẫu gọi, 0/5 đối chứng kích hoạt. Chờ kiểm mic thật và thời
  gian chờ có hội thoại nền trước khi cân nhắc dùng mặc định.

- 04/11/2026, so wake offline trên 9 mẫu gọi và 5 đối chứng độc lập.
  MFCC/DTW nhận 5/9, Qwen0.6B khớp chữ 0/9, cả hai kích hoạt 0/5 đối
  chứng. Tiếp theo đo trên cửa sổ cuộn và cải thiện tỷ lệ nhận câu gọi.

- 04/11/2026, prototype dò mẫu MFCC/DTW nhận 5/9 mẫu gọi held-out.
  Có 18 mẫu gọi và 11 đối chứng train. Chờ đối chứng held-out để đo
  thức nhầm. Xem HANDSFREE-ENROLL-006.

- 04/11/2026, thu mẫu wake cá nhân bằng `scripts/personal_voice.py --wake`.
  Kho `wake-voice` riêng có mẫu dương, mẫu âm và tập kiểm độc lập.
  17 test đạt. Tiếp theo người dùng thu mẫu, rồi thử bộ phân loại và so
  tỷ lệ bỏ lỡ, thức nhầm, độ trễ với luồng hiện tại.

- 04/11/2026, `HANDSFREE-NOISE-004`: thêm gate so với nền trong chế độ
  chờ. 24 test hands-free đạt. Chờ kiểm mic thật bằng `--debug-wake`,
  im lặng 10 giây rồi gọi tên một lần.

## Wake STANDBY không phản ứng: có diagnostics, lỗi chất lượng vẫn mở — 02/11/2026

- **Trạng thái mới nhất:** File đang bị sửa đồng thời trong lúc kiểm:
  alias/hint/threshold được thêm ngoài patch lượt này. Targeted mới nhất
  23 test fail2, không dùng kết quả suite OK trước đó cho source hiện tại.
  Đang hỏi người dùng có chat khác cùng sửa không; giữ nguyên sửa ngoài
  lượt, chưa chốt bản hoạt động. Các bullet dưới mô tả điều tra/candidate.
- Người dùng xác nhận gọi không phản ứng khi STANDBY. Đo audio tổng hợp
  bằng Qwen thật tái hiện nhận Elvion thành E Leon/Elrion không khớp.
- Hint assistant-v1 giúp mẫu positive nhưng gây prompt echo/false wake
  trên âm đơn cả0.6B và1.7B, đã loại candidate khỏi runner. Không đổi
  model/context lưu hoặc thêm alias chưa đo.
- Thêm `--debug-wake` hiển thị RMS, STT error, keyword mismatch và text
  tại terminal, mặc định tắt và không ghi log. Detector chờ đủ .25s trước
  STT. Hướng dẫn hiện hành đầu `Docs/HANDS_FREE_VOICE.md`.
- HANDSFREE-WAKE-003 vẫn mở: cần diagnostics từ giọng thật để xác minh
  nguyên nhân riêng; chưa tuyên bố đã sửa được wake. Không thu mic người
  dùng trong các phép đo synth lượt này.

## Hands-free: mic native đã đọc được ngoài môi trường hạn chế — 02/11/2026

- Người dùng xác nhận đã cấp quyền. Cùng helper trả permission denied
  trong môi trường hạn chế nhưng nhận5/5 frame640 byte khi chạy ngoài
  môi trường đó. Stream đã đóng; không lưu/gửi audio.
- Blocker capture đã khoanh vùng theo cách chạy; không cần bật lại quyền.
  Chưa đo wake word/model/hội thoại thật. Chi tiết bổ sung tại
  HANDSFREE-NATIVE-002, giữ lịch sử các lượt từ chối trước đó.

## Hands-free 899f212: regression đạt, chờ quyền mic native — 02/11/2026

- 20/20 continuous tests và toàn suite970 test OK (1 skipped).
  5 fixture độc lập xác nhận deadline/framing/keyword, Qwen sanitize,
  stop không bị verifier chặn và worker cũ không đi vào phiên mới.
- Native runner qua STT preflight nhưng helper trả MIC_PERMISSION_DENIED;
  chưa nhận audio thật, chưa kiểm chất lượng gọi tên/echo/độ trễ.
- Chi tiết HANDSFREE-NATIVE-002 trong BUG_LOG; report
  `artifacts/benchmarks/handsfree-voice/verify-899f212-20261102.json`.
  Tiếp theo cấp đúng quyền mic cho môi trường chạy và thử runner thật;
  không coi lỗi quyền là lỗi nhận dạng hoặc khẳng định native đã đạt.

## Kiểm lại hands-free 49efa80 — 02/11/2026

- Deadline, boundary, câu dịch và ghép short read đã qua fixture kiểm lại;
  17 test continuous OK, toàn suite967 test OK (1 skipped).
- Vẫn còn hai P1: wake STT giữ lock/chặn đọc mic và stop; Qwen nhận
  context elvion từ preferences hợp lệ gây crash trước preflight.
- Phát hiện P2 worker cũ trả lời/đổi state sau stop→start; tài liệu còn
  claim stop<0,1ms và số test không thống nhất. Chưa sửa production.
- Chi tiết trong BUG_LOG, mục HANDSFREE-REVIEW-001 bổ sung49efa80;
  report `artifacts/benchmarks/handsfree-voice/recheck-49efa80-20261102.json`.
  Chưa mở mic/model thật; sửa các lỗi này trước khi chốt native readiness.

## Review hands-free voice — 02/11/2026

- Đã đọc nhánh `feat/hands-free-voice`, HEAD `ce096bd`, code continuous,
  runner và `Docs/HANDS_FREE_VOICE.md`. Chưa sửa production.
- 14 test continuous đạt; toàn suite964 test OK (1 skipped); Swift
  typecheck đạt, chưa mở mic/model/TTS thật trong lượt review.
- 7 fixture bổ sung xác nhận lỗi deadline wake chậm, stop bị chặn, WAV
  lúc STANDBY, framing read ngắn, cấu hình STT mặc định, keyword substring
  và lọc câu hợp lệ; runner còn che route error/action bằng câu xác nhận.
- Chi tiết, ưu tiên và giới hạn trong BUG_LOG mục HANDSFREE-REVIEW-001;
  report `artifacts/benchmarks/handsfree-voice/review-ce096bd-20261102.json`.
  Bước tiếp: sửa deadline/thu audio độc lập và hợp đồng RAM-only, sau đó
  regression runner/streamer và native mic smoke. Chưa coi suite xanh là
  bằng chứng chất lượng wake word hoặc các số CPU/latency trong tài liệu.

## Music catalog: chọn bài, phát và tạm dừng đã kiểm chứng native — 02/11/2026

- CLI đã nối thêm `music.catalog.play` và `music.catalog.pause`, mỗi bước
  có grant và xác nhận riêng. Sau mở nghệ sĩ, danh sách bài có số để chọn
  bằng `Phát bài nhạc <số>`; `Tạm dừng nhạc` kiểm lại player paused.
- Policy `music-catalog-v3`: tra metadata công khai theo ID qua Apple
  Lookup (VN), đối chiếu title/artist/album/duration với native player,
  chốt persistentID trong RAM; volume phải giữ nguyên. Đây là kiểm chứng
  metadata, chưa phải storeID do player cung cấp trực tiếp.
- Report `artifacts/benchmarks/agent-desktop/catalog-play-cli-bcd3882a23ff4c7c851efd42c43d9aae.json`:
  cả4 action succeeded/verified, simulated=false,4 xác nhận; cuối paused,
  volume không đổi, không cần cleanup pause. Source hashes có trong report.
- 28 test catalog đạt; toàn suite chạy950 test, OK (1 skipped). Hướng dẫn
  chạy đủ4 grants trong `Docs/MUSIC_CATALOG_CLI.md`; cần mở lại phiên cũ.
- Giới hạn: đóng panel Queue trước thử, storefront khác chưa đo, metadata
  trùng hoàn toàn không phân biệt được release; vẫn có race focus khi
  người dùng thao tác song song. Chưa nối tìm bài trực tiếp hoặc voice.
  Nhánh YouTube vẫn cần nền browser/Vision được đóng gói riêng.

## Người dùng xác nhận Music catalog CLI chạy ổn — 02/11/2026

- Sau khi được hướng dẫn mở phiên CLI với music-catalog, grants và
  physical-input, người dùng báo “chạy ổn r”. Ghi nhận kiểm chứng thủ
  công của người dùng cho luồng vừa hướng dẫn tìm/mở nghệ sĩ.
- Không có report mới từ người dùng; chưa suy ra mọi truy vấn, playback
  hoặc voice đã được kiểm chứng. Native report của agent giữ nguyên.

## Music catalog đã nối CLI, submit bằng phím thật có guard — 02/11/2026

- Thêm driver `adapters/music_catalog.py`, composition/policy/planner/
  verifier tại `core/music_catalog.py`. CLI opt-in `--music-catalog`,
  `--allow-physical-input`, path agent-desktop; capability search/open_artist
  tách riêng, mỗi bước bắt buộc xác nhận. Không nối playback hoặc voice.
- Submit dùng Return không gắn --app sau kiểm foreground Music, window ID,
  query/mode và textfield focused. Đã kiểm native cơ chế CGEventPost;
  không cần ảnh, tọa độ hoặc click dropdown. Card/header giữ artist type
  và catalog ID, handle trong RAM có TTL300s, refresh ref trước hành động.
- Native CLI Latin và Unicode đều search→open_artist đạt. Report chốt
  `artifacts/benchmarks/agent-desktop/catalog-cli-146061fbbcc84ee0a43934847f30223e.json`:
  2 confirmation, 2 succeeded, verifier đạt, current track/volume không đổi,
  player paused trước/sau. Query/name/AX tree không lưu vào trace.
- 935 tests OK (1 skipped);13 test catalog phủ focus race, token hết quyền,
  hủy/thiếu grant, hết TTL/context đổi, ID sai, timeout và trace privacy.
  Compileall và diff check đạt. Hướng dẫn `Docs/MUSIC_CATALOG_CLI.md`.
- Giới hạn: mới thử Music tiếng Việt/agent-desktop1.0.2, foreground guard
  chưa khóa được input con người; không có artist card thì báo chưa kiểm
  chứng sau timeout. Còn cần đóng gói dependency/nền Git cho nhánh YouTube.

## agent-desktop: chọn kết quả và xác minh artist ID đạt — 02/11/2026

- Mở thẻ nghệ sĩ Beethoven, đọc header mới xác minh cùng catalog ID1130028.
  Ca Unicode nhập Trịnh Công Sơn đúng; phân biệt album và nghệ sĩ cùng tên,
  chọn thẻ artist320152275 và xác minh header sau mở khớp ID.
- Đã đo4 cell cùng nhãn/3ID khác nhau, vì vậy cần giữ entity_type+catalog_id
  thay vì chỉ tên. Không dùng decimal catalog ID làm16hex persistentID JXA.
- Report sanitized `artifacts/benchmarks/agent-desktop/music-selection-daa62d6bf7c54a51bab1a23d968199fb.json`.
  Không chọn/phát bài, player cuối paused. Chưa thành adapter ELVION tự động.
- Vướng còn lại: submit truy vấn qua dropdown vẫn cần click theo ảnh;
  menu surface probe không đọc được dropdown. Cần driver submit đáng tin
  hoặc Vision có frame binding/kiểm chứng. Chuột người dùng và input thật
  có thể tranh chấp; đọc lại trạng thái trước mỗi bước, không click lại mù.

## agent-desktop: thử tìm catalog Music bằng AX + input thật đạt — 02/11/2026

- Có phép người dùng dùng chuột/phím thật trong Music, chỉ tìm kiếm.
  Headed sidebar click mở textfield; set-value Beethoven và snapshot
  xác nhận đúng giá trị. Radio Apple Music checked.
- Icon search và AXConfirm chưa mở trang kết quả; đã xác minh bằng ảnh.
  Click theo ảnh đúng dòng gợi ý truy vấn mở trang catalog; AX đọc được
  cell kết quả liên quan. Đây là một ca thử có người giám sát, gồm bước
  chọn tọa độ bằng ảnh; chưa phải adapter tự động hoặc Vision local đạt.
- Player cuối paused, không chọn/phát bài. Báo cáo không có metadata
  cá nhân: `artifacts/benchmarks/agent-desktop/music-search-c914fe1122fc4766b78a7d24f267b9b1.json`.
  AD-PROBE-005 còn mở về confirm/popover; không dùng tọa độ test làm hằng số.

## agent-desktop: thử điều hướng Search gặp giới hạn semantic — 02/11/2026

- Find exact toàn cây chạm locator_budget_limit; lấy ref mới bằng
  snapshot skeleton sidebar thay vì dùng dữ liệu query chưa hoàn tất.
- Semantic click Tìm kiếm trả delivered_verified nhưng chỉ chọn hàng.
  Snapshot và wait-for5s chưa có textfield; ảnh xác nhận chưa đổi view.
  AD-PROBE-003/004 ghi BUG_LOG. Chưa gửi truy vấn hoặc phát nhạc.
- Đã hỏi người dùng cho phép thử physical input trong riêng Music theo
  quy tắc --headed; đang chờ, chưa chuyển sang chuột/phím thật.

## agent-desktop: đọc UI Apple Music thật đạt — 02/11/2026

- Accessibility granted sau người dùng cấp quyền. Tên app từ list-apps
  là `Nhạc` (bundle com.apple.Music); `--app Music` trả APP_NOT_FOUND,
  đổi đúng display name thì snapshot được.
- Skeleton60 nodes/53 refs; interactive depth16 có158 nodes/148 refs.
  Nhận diện Tìm kiếm, Thư viện, Phát/Tạm dừng/Tiếp theo qua Accessibility.
  Đã có bằng chứng backend đọc được UI mà không tự viết helper AX mới.
- Snapshot complete=false, view đã đọc chưa có text input. Chưa test
  click/type/search catalog/playback; chưa thay adapter hiện có. Bước
  tiếp theo là thử điều hướng mục Tìm kiếm bằng ref mới và verify lại.
- Report sanitized: `artifacts/benchmarks/agent-desktop/music-interactive-5741222ec3e34583ad906d837dc1eca2.json`.
  AD-PROBE-001/002 đã giải quyết trong phạm vi quyền và app lookup đã đo.

## agent-desktop: đã cài thử, chờ quyền macOS — 02/11/2026

- Cài npm agent-desktop@1.0.2 bằng prefix riêng
  `/private/tmp/elvion-agent-desktop-probe`, ignore-scripts; không sửa
  dependency ELVION. Binary macOS arm64; JSON envelope v2.5.
- Đã đọc tài liệu nhúng desktop/platform. `status` và `permissions`
  chạy được; Accessibility denied, Screen Recording granted.
- Snapshot Music trả PERM_DENIED/not_delivered. `permissions --guide`
  trả guide=started; đang chờ người dùng bật quyền theo System Settings.
  AD-PROBE-001 đã ghi BUG_LOG. Chưa có bằng chứng đọc cây UI của Music,
  chưa quyết định thay helper cũ, không click hoặc phát nhạc.

## Apple Music: native read-only sau review đạt — 02/11/2026

- Sửa parser lỗi native và unknown state, thêm 3 test biên subprocess;
  32 test Music đạt, full suite 922 test OK (1 skipped).
- Read-only trên máy thật 6/6 đạt: AppKit, player state mặc định3s,
  search chuỗi test có dấu, search ngoặc kép/backslash, tra ID không tồn
  tại và Swift probe. Không phát nhạc, không lưu track metadata.
  Report `artifacts/benchmarks/apple-music/readonly-b71bbbe9b54e4191a263c8a93f5e0523.json`.
- Native player từng timeout3s ở lượt đầu, sau đó timeout15s đạt0,237s,
  mặc định3s đạt0,193s. AM-NATIVE-003 còn điều tra nguyên nhân ban đầu.
- Chưa có proof playback thật hoặc tích hợp CLI search→chọn→play.
  Tìm chuỗi synthetic chỉ chứng minh transport/response, chưa chứng minh
  tìm trúng bài có tên đặc biệt trong thư viện người dùng.

## YouTube: xác nhận blocker commit nền — 01/11/2026

- `feat/youtube-vision` tại `2ff695d` chỉ có 2 tài liệu kế hoạch/issues,
  chưa có implementation hoặc phép đo native. Worktree sạch.
- Browser/Vision đã kiểm chứng ở checkout chung vẫn chưa commit; checkout
  chung hiện ở `codex/apple-music`. YT-BLOCK-001 đã ghi trong BUG_LOG.
- Ưu tiên tích hợp: tạo nhánh nền `feat/*` với dependency đầy đủ và kiểm
  trên cây sạch để YouTube lấy về. Chưa sửa/rebase/push nhánh YouTube trong
  lượt kiểm tra này.

## Web summary: bản chọn ID qua ca cũ và trang mới — 01/11/2026

- Xác minh lỗi cũ: clean duplicate paragraph; Wikipedia/Example Domain
  quote mismatch. Đã đổi sang model chọn ID của span cắt sẵn; code lấy
  quote trực tiếp từ nguồn. Nhiều span cùng paragraph được phép; có
  abstain khi không có nội dung phù hợp.
- Hai lượt sau sửa đều synthetic 8/8, native 5/5. Native gồm Python
  Tutorial, Wikipedia, Example Domain, MDN Introduction và Python Data
  Structures. Các ca injection Việt/paraphrase, instruction-only đạt;
  tutorial hợp lệ không bị bỏ nhầm. Report chốt:
  `artifacts/benchmarks/web-summary/summary-d7ca5210de624c16a3db4d4d0f2a1a3a.json`.
- 890 test toàn dự án đạt (1 skipped); 35 test liên quan đạt sau khi chốt
  phép đối chiếu quote độc lập; compileall/diff check đạt. WEB-SUMMARY-001/
  002 đóng trong phạm vi ca đã đo. Không dùng số này làm semantic accuracy
  hay bảo đảm chống mọi injection. Bước kế tiếp: hợp đồng hỏi đáp có
  nguồn, bộ ca có đáp án/thiếu đáp án/mâu thuẫn trước khi nối voice.

## Web summary: đã có benchmark, phát hiện giới hạn model thật — 01/11/2026

- Thêm `benchmarks/web_summary/runner.py`, hướng dẫn
  `Docs/WEB_SUMMARY_CHECKS.md`, và test cách chấm. 31 test liên quan đạt;
  compileall và diff check đạt.
- Phép đo qwen3.5:4b đầu tiên: synthetic 2 pass/2 fail; native 1 pass/2
  fail. Python Tutorial đạt; Wikipedia, Example Domain và ca clean
  synthetic bị validator từ chối. Ca injection chọn chỉ dẫn giả làm ý
  chính dù quote khớp. Report:
  `artifacts/benchmarks/web-summary/summary-007345525a8947d28f851c7bb6c0bd17.json`.
- Giữ nguyên mọi failure và không gọi đây là held-out/semantic accuracy.
  WEB-SUMMARY-001/002 trong BUG_LOG còn mở. Tiếp theo cần diagnostics mã
  vi phạm và cải thiện chọn đoạn trước khi nối hỏi đáp hoặc voice.

## Web thật: DOM open/search/open_result và đọc đoạn trích — 01/11/2026

- Đã thêm `:web-summary`: model Ollama local chọn tối đa ba câu/đoạn ngắn
  nguyên văn trong 30 paragraph đầu (tối đa 7.000 ký tự); mỗi quote phải
  khớp đúng paragraph trước khi hiển thị cùng URL. Native CLI
  `web.open`→`:web-summary` trên Python Tutorial đạt với qwen3.5:4b,
  3/3 trích dẫn khớp nguồn. Full suite 883 test đạt (1 skipped),
  `git diff --check` và compileall đạt. Đây là tóm tắt trích xuất, không phải kiểm
  chứng mọi suy luận hoặc trả lời câu hỏi tự do.
- Chromium fixture DOM click + verifier đạt. Trên web công khai, CLI
  `web.open` tới example.com/Wikipedia, `web.search` trên DuckDuckGo và
  `web.open_result` tới Wikipedia đã chạy thật với grant, xác nhận riêng,
  DOM và `postcondition_verified=true`. Lỗi locator title trùng trên
  DuckDuckGo đã sửa bằng title + `href` gốc của result.
- Đã nối `:web-read` vào phiên CLI: đọc trang đang mở, trả URL/title,
  excerpt giới hạn, số từ và cờ cắt. Native Wikipedia trả mở đầu bài sau
  khi lọc dòng nguồn, hatnote và infobox khỏi reader. Native Python
  Tutorial cũng trả đoạn mở bài đúng trên layout thứ hai. `:web-read`
  chỉ trích xuất nội dung; `:web-summary` chọn điểm chính có dẫn nguồn.
  CLI phải dùng `.venv-browser/bin/python -m elvion session`; launcher
  `./elvion` mặc định mở voice.
- Còn cần kiểm thêm site/layout công khai, trang có redirect/cookie wall,
  và luồng tóm tắt/đọc bằng voice. Vision live tiếp tục tắt vì chưa đạt
  chuẩn chất lượng trước đó; các thành công DOM không thay đổi kết luận
  về Vision.

## Voice: A/B nghiêng về cách nói B, chưa xác nhận khác biệt rõ — 01/11/2026

- Đã thu 20 clip A (tự nhiên) và 20 clip B (cách nói người dùng gọi là
  “giọng Bắc chuẩn”), mỗi bên hai phiên 10+10. Freeze Qwen1.7B/
  assistant-v1/tech/auto; cả40 inference đạt, 0 failure. Toàn bộ A9/20
  exact, WER7.84%; B13/20, WER4.37%. B dẫn cả hai khối 01–10
  (6 so4 exact) và 11–20 (7 so5), nhưng 7 cặp nhãn khác nhau.
- Chỉ13 cặp có cùng lời sau chuẩn hóa: A8/13, B10/13 exact, B-only3,
  A-only1; WER4.55% so2.27%. Khối đầu B5/7 so A3/7; khối sau
  hòa5/6. Không đạt tiêu chí định trước B hơn ít nhất5/20 exact
  và cả hai nửa paired cùng chiều. Đây là tín hiệu gợi ý, không xác nhận
  chắc cách nói B làm ASR tốt hơn. Report private:
  `qwen-comparison-a055522522654d9aad650a64139838c4.json` và
  `qwen-comparison-ada30a02551e4460abb7fc77d2a38187.json`.
- Giữ Qwen1.7B đang dùng; hoãn fine-tune theo ưu tiên người dùng để phát
  triển các phần khác của ELVION. Về sau gom nhu cầu và thử cloud một
  lượt với train nhiều phiên và bộ kiểm mới. Không train trên corpus A/B
  này hoặc thuê/upload dữ liệu trong giai đoạn này.

## ASR cá nhân: Qwen1.7B đã lưu làm STT cho người dùng — 01/11/2026

- Đã xuất 30 clip dictation từ một phiên thu sang `artifacts/personal-voice/heldout-01`.
  Audit/export đạt; kiểm tra nhãn so với train/dev: 0 cặp gần trùng ở
  ngưỡng similarity 0.8 (cao nhất 0.615). Không in/lưu nhãn ở tài liệu.
- Cùng assistant-v1/tech/auto trên 30 clip: 1.7B FP16 đạt 13/30 exact,
  WER10.34%, CER6.01%, 9/11 thuật ngữ, 5/5 title, median1.483s;
  0.6B FP16 đạt 7/30, WER20.38%, CER12.53%, 8/11 thuật ngữ,
  2/5 title, median0.594s. Cả hai 0 failure. Báo cáo private:
  `qwen-comparison-d777562b09fc4639869333930e2b3b86.json` và
  `qwen-comparison-f6093597510d408f901438df46d447bc.json`.
- Adapter 0.6B FP32 Adam3e-5: paired FP32 base/candidate đều 7/30 exact,
  WER20.06%→19.75%, CER10.99%→10.71%, 8/11 thuật ngữ, 0 failure.
  Báo cáo `train-6bf66bafe3cd42629762d152e8aefcc8.json`. Mức cải thiện
  nhỏ, không đủ bù chênh lệch với 1.7B; không promote adapter. 0.6B nhanh hơn
  nhưng kém rõ trên held_out và hồi quy kỹ thuật cũ.
- Giới hạn: 30 clip trong một phiên, nhãn do người dùng xác nhận; chưa đo
  desktop end-to-end hay độ ổn định qua phiên/môi trường khác. Bộ held_out
  này đã xem kết quả, không dùng để chỉnh hyperparameter rồi gọi là kiểm độc lập.
- Đã đo thêm cấu hình voice đang lưu (PhoWhisper-small/none/vi) trên đúng
  30 clip: 5/30 exact, WER30.09%, CER21.24%, 1/11 thuật ngữ,
  2/5 title, median0.447s, 0 failure. Private report
  `comparison-200e720c7f124f2a9b391808bdb50ae5.json`. Qwen 1.7B
  tốt hơn rõ rệt về accuracy nhưng chậm hơn. Voice CLI Qwen doctor ready;
  `--transcribe-file` với một WAV held_out thành công, có text và không
  mở mic/chạy tác vụ. Người dùng xác nhận phiên micro Qwen chạy bình thường;
  chưa xác nhận spoken review hoặc mọi loại tác vụ.
- Đã thêm `stt_engine` vào voice preferences schema v2, đọc được schema v1;
  chưa có lựa chọn thì vẫn Whisper. Đã lưu Qwen cho cấu hình người dùng
  hiện tại. `./elvion --doctor` trả `ready`/`qwen3-asr-mlx`/`auto`;
  `./elvion --transcribe-file` không cần cờ engine thành công với context
  `tech`. 877 tests đạt, 1 skipped. Có thể ghi đè một phiên bằng
  `./elvion --stt-engine whisper`; `./elvion --setup` chọn lại PhoWhisper.
  Chưa gọi đây là kiểm chứng toàn bộ luồng action desktop.
- Hướng cải thiện tiếp: không train thêm trên 22 clip hiện có. Kiểm tra
  nghe âm đầu/cuối ở các clip sai trước; energy diagnostic held_out30 báo
  29 clip có energy sát đầu, 27 sát cuối, nhưng không chứng minh mất âm.
  Nếu lỗi chủ yếu tên/thuật ngữ, thử glossary cá nhân opt-in trên dev
  và kiểm false insertions. Nếu vẫn là lỗi âm học, thu train mới qua
  nhiều phiên/điều kiện rồi mới nghiên cứu adaptation 1.7B; cần bộ
  kiểm độc lập mới trước quyết định model.

## ASR cá nhân: ứng viên tốt nhất hiện có, chờ held_out mới — 01/11/2026

- 0.6B/assistant-v1/tech-auto: dev15 6/15 exact, WER19.53%, 6/7 term hits,
  median0.472s; 1.7B cùng profile 5/15, WER19.53%, 4/7 hits,
  median1.417s. Nhưng 12 clip kỹ thuật cũ với 0.6B FP32 chỉ6/12,
  11/16 term hits; 1.7B/assistant-v1 từng8/12,14/16. Chưa đổi live model.
- LoRA 0.6B FP32/Adam3e-5/1epoch là ứng viên nghiên cứu tốt nhất trong
  4 recipe đã đo: dev WER19.53→18.75%, CER10.81→10.26%, 6/15 exact và
  6/7 term hits giữ nguyên; chỉ1/15 đầu ra đổi. Fresh-process reload
  lặp đúng. Regression12 không đổi so với base0.6B.
- Adam1e-4 gây hỏng dev0/15; Adam1e-5 và SGD1e-3 1/3epoch không đổi
  output dev. Không promote adapter. Cần held_out giọng mới, khác phiên/
  câu train+dev và có cả câu kỹ thuật/negative controls, trước khi chọn
  0.6B/adapter hay giữ 1.7B. Đã chuẩn bị `--held-out` và ba lệnh đánh giá
  trong Docs/PERSONAL_ASR_PROBE.md; chờ người dùng thu giọng mới.

## ASR cá nhân: 0.6B FP32 là ứng viên train/eval tiếp — 01/11/2026

- Dev15 clip: Qwen0.6B/assistant-v1/tech-auto 6/15 exact, WER19.53%,
  6/7 term hits, median0.472s; 1.7B cùng profile 5/15, WER19.53%,
  4/7 hits, median1.417s. 0.6B/tech-vi cho cùng output; none-auto chỉ
  2/15, WER29.17%, 1 failure. Chưa có held_out mới.
- Model weights 0.6B lưu BF16; diagnostic phải cast thật lên FP32. Native
  3 train clip (ordinal0/5/10), TF32 tắt, explicit FP32 attention:
  trace/direct gap0; mọi step SGD dương giảm loss, step âm tăng loss;
  peak MLX3.62–3.63GB. Chưa save adapter hoặc chứng minh accuracy gain.
- Tiếp theo: train giới hạn trên train23clip và so base/candidate trên
  dev15 bằng free decoding; chỉ sau đó mới yêu cầu held_out mới.

## ASR cá nhân: tắt TF32 tái lập loss descent một clip — 01/11/2026

- Hai native scan `probe-c5ee8e4de9f44ffdb24c1d4e8b2f4394.json` và
  `probe-4358772dfb87421eb91525a438d582ed.json` với
  `MLX_ENABLE_TF32=0`, legacy LoRA sum, attention explicit-fp32 cho kết quả
  giống hệt: base loss 1.393469334, +1e-4 giảm 0.000623822,
  +1e-3 giảm 0.003908038 trên một train clip.
- Đây là bằng chứng precision path ảnh hưởng mạnh và một clip có descent;
  chưa đủ để kết luận gradient đúng nói chung hoặc ASR tốt hơn. Không save
  adapter. Tiếp theo kiểm trên nhiều train clip và fresh-process adapter
  với cùng precision config trước khi xét train nhiều bước/dev.

## ASR cá nhân: ablation FP32 LoRA sum hoàn tất, recipe vẫn chưa đạt — 01/11/2026

- Hai native diagnostic cùng clip/seed/attention explicit-fp32, 5 signed
  step: `probe-c1796bd9a7e54e07bd8f0599f76d84dd.json` (FP32 sum) và
  `probe-92e1b237bb85423e9c6e1a29b0d89c5d.json` (legacy sum).
- Cả hai cho +1e-3 delta loss +0.000625610 và -1e-3 delta loss
  -0.000002980; ba step dương không có descent có ý nghĩa. Profile cộng
  FP32 chỉ khác ở các delta cỡ 1e-6, không giải quyết vấn đề.
- Chưa có chứng cứ gradient phù hợp finite step ở path FP16. Dừng recipe
  train này, không lưu/promote adapter; điều tra path logits/precision hoặc
  recipe training khác trước khi đánh giá dev. Xem VOICE-ADAPT-002.

## ASR cá nhân: chuẩn bị ablation cộng LoRA FP32 và hướng gradient — 01/11/2026

- Thêm `--fp32-lora-sum` chỉ cho `--diagnose-update` với attention
  explicit-fp32: cộng base output và LoRA delta trong FP32 rồi cast một lần.
- Quét cả hai hướng gradient ở bước ±1e-4/±1e-3, cùng bước +1e-5; mỗi
  điểm bắt đầu từ baseline, không save adapter. Profile cũ và live voice
  giữ nguyên. Chờ native Metal; xem VOICE-ADAPT-002 và
  Docs/PERSONAL_ASR_PROBE.md.

## ASR cá nhân: step scan không giảm loss; dừng mở rộng recipe LoRA — 01/11/2026

- Native `probe-ffcfcee89ef247c090c78ef7940e75b8.json` với
  explicit-fp32: direct/repeat/traced base đều 1.394790173, gap 0.
- Ba update tạm từ cùng baseline: lr1e-5 delta loss +0.000001192;
  lr1e-4 +0.000000596; lr1e-3 +0.000625610. Norm adapter delta tăng
  tỷ lệ ~10 lần mỗi mức; không có mức nào giảm direct loss.
- Không lưu adapter, không train nhiều clip hay dùng trong live voice.
  Chưa xác định nguyên nhân; cần điều tra đường LoRA FP16/gradient bằng
  ablation tách biệt trước khi chọn recipe khác. Xem VOICE-ADAPT-002.

## ASR training diagnostic: fresh-process reload đạt, cần đo update — 01/11/2026

- Native `probe-1339293a8e6f4c9d81cb588fb8c6f165.json`: adapter
  explicit-fp32 nạp lại đúng loss 1.394791365; base 1.394790173.
- Base/candidate đều EOS sau 8 token, hash câu giống nhau. Không có descent
  hoặc accuracy gain; không dùng adapter trong live voice.
- Đã thêm `--diagnose-update` để đo magnitude và direct loss tại ba step
  tạm thời từ cùng baseline, không lưu adapter. Chờ native Metal; xem
  Docs/PERSONAL_ASR_PROBE.md và VOICE-ADAPT-002.

## ASR training diagnostic: explicit-fp32 khớp loss, chưa có descent — 01/11/2026

- Native report `probe-ee903db42a0d4100bdb1cc75f6497950.json`: direct/repeat/
  traced cùng 1.394790173, trace/direct gap 0; gradient norm 0.263856,
  57344 tham số, một update, adapter save/reload cùng process khớp.
- Direct loss sau update 1.394791365 (tăng 0.000001192), nên
  `single_clip_descent_verified=false`; không có bằng chứng accuracy gain.
- Peak MLX 8158413560 bytes (~7.60 GiB), 3.60 giây. Chưa verify adapter
  này bằng process mới. Tiếp theo: `--verify-report` cho adapter này, rồi
  điều tra kích thước update/độ nhạy FP16 bằng probe giới hạn trước khi
  train nhiều clip; không promote adapter.
- Chi tiết VOICE-ADAPT-002 và Docs/PERSONAL_ASR_PROBE.md.

## ASR training diagnostic: thử attention path tường minh — 01/11/2026

- Nativev2:repeatdirect/basezeroLoRA đều1.393135,traced1.400645,
  adapter1.395105. Reload/decodeđạt nhưng không có descent/gain.
- Thêm --attention-profile explicit-fp32 cho one-step riêng;
  chặnupdate khi trace/directkhôngkhớp (không nới tolerance).
- 25testliênquanđạt,chờnativeGPU;modelvoice/basecheckpointgiữnguyên.
- Chi tiếtVOICE-ADAPT-002,Docs/PERSONAL_ASR_PROBE.md.


## ASR adapter: reload/decode đạt, điều tra loss trước training tiếp — 01/11/2026

- Nativefreshprocessrestorelosskhớp,EOSdecode8tokens,trùngbase,~3s.
- Baseforwardloss1.3931<adapter1.3951;tracedbeforecũ1.4006 không cùng phép
  so sánh. Chưa có bằng chứng descent/accuracy gain.
- Thêm diagnosticv2:repeatdirect/traced/zeroLoRA-vs-base;24testliênquanđạt.
- Tạm dừng mở rộng train,chờnative --verify-report v2. VOICE-ADAPT-002.


## Personal ASR: native LoRA một bước đạt, chờ fresh-process reload — 01/11/2026

- Native probe:57344param,gradienthữuhạn,loss1.4006→1.3951,6.3s,
  peakMLX7.60GiB. Chưa accuracy claim hoặc rollout voice.
- Đã thêm --verify-report: loadadapter ởchildmới,kiểmloss và greedyEOSdecode
  cùngtrainclip,0update. 23testliênquanđạt;agent thiếuMetal nên cần Terminal.
- Lệnh trong Docs/PERSONAL_ASR_PROBE.md. Chưa cần model/gói/dữ liệu mới.


## Cá nhân hóa ASR: one-step LoRA probe chờ native — 01/11/2026

- Đã có scripts/probe_personal_asr.py, chỉ1trainclip/1update,basefreeze,
  rank4 q/v cuối decoder,loss target-only,adapter save/reload riêng.
- 22testliênquan đạt. Native agent thiếuMetal,dừng trướcdata/model load.
- Cần Terminaluser chạy lệnh trong Docs/PERSONAL_ASR_PROBE.md để đo
  finitegradient/update/RAM/reload. Chưa training thành công/accuracy claim.
- Không tải model/gói mới,không thay modelvoice,không đụng reader của B.


## Personal ASR: đã đo baseline 15 clip dev — 01/11/2026

- Qwen1.7B/assistant-v1: strict5/15,WER19.53%,0fail,coldmedian1.417s.
- 2 mismatches chỉ hình thức;8câu còn lỗi nội dung/hỗn hợp. Không sửa scorer.
- Chưa train. Bước kế tiếp: bounded adaptation feasibility/resource probe
  trên train riêng; dev dùng tuning, held_out mới giữ cho kiểm cuối.
- Private report/analysis và giới hạn metric/energy trong BUG_LOG.


## Cá nhân hóa giọng: công cụ dữ liệu opt-in đã triển khai — 01/11/2026

- scripts/personal_voice.py: record/audit/delete/export; thu và nghe lại,
  chọn từng clip, nhãn đúng lời nói. Không inference/train/điều khiển app.
- SQLite private audio+label atomic, provenance session/kind/hash/split,
  chống duplicate PCM và rò câu/group giữa split; audit heuristic gần trùng.
- 16 test mới đạt; chờ người dùng thu pilot giọng tự nhiên. Không đổi model
  hoặc tự giữ clip của phiên voice bình thường. Chưa cần model mới.
- Hướng dẫn Docs/PERSONAL_VOICE_DATA.md; bước sau freeze split, đánh giá lỗi
  rồi spike adaptation/RAM trước khi train. Xem VOICE-DATA-001 trong BUG_LOG.


## Web DOM Reader: hoàn tất xử lý 2 vấn đề biên tài nguyên & truncation cuối cùng — 01/11/2026

Đã xử lý dứt điểm 2 điểm phát sinh từ đợt review 26 tests:
1. Thống nhất biên starttag/data tại độ sâu 256: Giữ nguyên văn bản trực tiếp tại đúng độ sâu tối đa (`is_truncated = False`), chỉ loại bỏ văn bản khi có thẻ con vượt ngưỡng và luôn bật `is_truncated = True`.
2. Đặt trần độc lập cho Overflow Stack: Thêm `MAX_OVERFLOW_DEPTH = 256`, kích hoạt `_exhausted = True` để ngắt parse fail-closed trong O(1) khi input bệnh lý có 10.000 thẻ lồng nhau, khống chế độ dài `_overflow_stack <= 256` và loại bỏ quét tuyến tính lặp lại trên thẻ đóng không khớp.

Kiểm chứng:
- 28/28 unit tests trong `tests/test_browser_reader.py` PASS trong 0.023s.
- Toàn bộ suite dự án đạt 862/862 tests PASS trong 18.11s (0 failures, 0 errors).
- `git diff --check` đạt 0 lỗi.
Đã đóng hoàn toàn toàn bộ chuỗi issue WEB-READER-001..006. Sẵn sàng tích hợp planner/action chaining.


## Web DOM Reader: hoàn tất xử lý 3 ca lỗi biên và đóng toàn bộ WEB-READER-001..006 — 01/11/2026

Đã xử lý dứt điểm cả 3 ca lỗi biên được ghi nhận trong lượt review:
1. Malformed overflow endtag (WEB-READER-001/005): Dùng `_overflow_stack` theo dõi chính xác các thẻ mở trong vùng tràn; bỏ qua thẻ đóng void (`</br>`) và thẻ đóng không khớp (`</unexpected>`); fail-closed tuyệt đối khi gặp HTML lỗi, không rò rỉ text ẩn (`<p hidden>`) và báo `is_truncated = True`.
2. Opacity dạng thập phân CSS (WEB-READER-005): Cập nhật regex kiểm tra style nhận diện chính xác `opacity: 0`, `0.0`, `0.00`, `.0`, `0%` và `!important`, loại bỏ nội dung trong suốt nhưng giữ nguyên nội dung hiển thị khi `opacity: 0.5`.
3. Link trong inline wrapper (WEB-READER-006): Quét link đệ quy iterative trên mọi inline wrapper (`span`, `em`, `strong`), trích xuất chính xác vào `article.links` theo đúng document order.

Kiểm chứng:
- 26/26 unit tests trong `tests/test_browser_reader.py` PASS trong 0.014s.
- Toàn bộ suite dự án đạt 846/846 tests PASS trong 20.37s (0 failures, 0 errors).
- `git diff --check` đạt 0 lỗi.
Sẵn sàng hoàn toàn để ghép Web DOM Reader vào pipeline tóm tắt / action planner.


## ASR cá nhân: ưu tiên dữ liệu giọng tự nhiên và nhãn đúng lời nói

User muốn ELVION ưu tiên giọng riêng. Đã viết kế hoạch
Docs/PERSONAL_VOICE_PLAN.md: opt-in capture/review/provenance → split theo
phiên/câu → thử cá nhân hóa có đo RAM → kiểm trên audio chưa dùng tối ưu.
Chưa triển khai tự lưu audio/tự học hoặc trainweights. Câu sau khi đổi ý hay
đọc lại tên không được gán cho clip cũ. english-02 giữ regression; cần bộ
mới chưa tuning cho validation sau adaptation. OfficialSFT GPU/torchrun chưa
chứng minh phù hợpMac16GB; chưa tải model hoặc chạy tác vụ dài.


## Voice: Qwen opt-in và spoken review đã triển khai, chờ desktop smoke

--stt-engine qwen chọnMLX1.7B/assistant-v1 cho phiên;không sửa preference
Whisper hoặc tự fallback. --voice-review cho nói dùng câu này/nói lại/nói
lại tên/đổi thuật ngữ/hủy; đọc lại sau mỗi sửa. Timer2..15s(default6),tối
đa6reviewturn,Enter kích hoạt ban đầu;chưa wakeword/VAD. Action confirmation
vẫn bànphím riêng,grants vẫn qua directive bànphím. Controlturn chọnVI
trước capture/inference,dictationQwenauto choVI–EN,không retry lỗi.

Giữ prefix tạo/tìm khi đọc lại tên chỉ với yêu cầu rõ,không bỏ modifier hay
compound. Giữ tên bắt đầu bằng “Tên” đúng cảmodel/rules grammar. TTS/stop
lỗi chặn mic/review;hủy/STT lỗi bỏ request cũ;no trace controlraw/audio.
20testspoken mới+1prompt extension,110test liênquan đạt;full845/845đạt sau
cập nhậtReader song song;gitdiffcheckđạt. Agent thiếuMetal nên chưa test
mic thật của luồng mới. Hướng dẫn: Docs/VOICE_SPOKEN_REVIEW.md.


## Web DOM Reader: hoàn tất xử lý 4 ca lỗi phát sinh và đóng WEB-READER-001..005 — 01/11/2026

Đã xử lý dứt điểm cả 4 lỗi phát sinh từ đợt review độc lập:
1. Void tag `<embed>`: Không kích hoạt chế độ ignore subtree khi gặp void tag trong `PARSE_DISCARD_TAGS`, tránh nuốt nội dung phía sau thẻ.
2. Cân bằng overflow DOM và fail-closed: Thêm `_overflow_depth` và cờ `overflowed: bool` cân bằng cấu trúc thẻ khi vượt `MAX_DOM_DEPTH` (256); không gắn dữ liệu bỏ qua vào phần tử cha; text ẩn (`<p hidden>`) không bị lọt vào bài và bật `is_truncated = True`.
3. Mixed block (`<blockquote>`, `<li>`): Áp dụng flow traversal duyệt theo document order và inline text buffer, giữ trọn vẹn loose text trước và sau leaf block mà không nhân đôi đoạn văn; thêm `"byline"` vào boilerplate và `"document"`, `"html"`, `"body"` vào non-leaf blocks.
4. Truncation flag khi chạm `MAX_PARAGRAPHS`: Trả cờ `raw_truncated` khi vượt quá 500 đoạn, đảm bảo `is_truncated = True` dù character budget chưa cạn.

Kiểm chứng:
- 25/25 unit tests trong `tests/test_browser_reader.py` PASS trong 0.010s.
- Toàn bộ suite dự án đạt 843/843 tests PASS trong 18.25s (0 failures, 0 errors).
- `git diff --check` đạt 0 lỗi.
Sẵn sàng ghép luồng đọc web vào action chaining / planner tóm tắt (Item 3 & 4, Nhóm 2).


## ASR: native MLX 1.7B assistant-v1 đã đo, chất lượng vẫn chưa qua gate

Report GPU qwen-comparison-52803280cdc544fe880411e53581252b.json:
7/12whole,6/6title,6/6command,13/16term,0fail,1insertion; cả12rawtext
trùngCPU. Coldmedian1.439s,p954.493s,không đo GPU RAM/keep-loaded latency.
BFS→DFS vẫn là lỗi thật. Diagnostic beam4 sau khi thấyreference ởclip9
english-02 cũng chưa sửa; không gọi đây là heldout evidence mới.
Không promote/defaultchange,không nới gate hoặc rewriteacronym. Chi tiết
và private reportpaths: Docs/QWEN_REFERENCE_DIAGNOSTIC.md.


## ASR english-02: title6/6 nhưng strict7/12 và lỗiacronym, chưa promote

Đã đo cố định assistant-v1 trên12clip mới so với none/auto cùngCPUFP16.
Baseline5/12whole,4/6titles,1fail(reportedThai); candidate7/12whole,
6/6titles,6/6commands,13/16terms,0fail,1insertion(BFS→DFS). HaiVIcontrols
đúng;paired+2whole,+2titles,0lostexact. Manifest/audio/source/hint hash
unchanged. Chưa đạtgate10/12 và0insertion,không đổi voice default hoặc tune
trên english-02 rồi gọi testđộc lập. NativeMLX/GPUsmoke cần Terminaluser vì
agent thiếuMetal. Report/provenancepaths ở Docs/QWEN_REFERENCE_DIAGNOSTIC.md.


## ASR: assistant-v1 cải thiện dev lên8/12, chờ giọng mới để kiểm chứng

Đã kiểm precisionBF16, padding400ms và beam4 trên subset; không sửa hai
lỗi tên. Public combined Vietnamese-command + English vocabulary profile
assistant-v1 (research opt-in) đạt8/12whole,4/6titles,6/6commands,14/16terms,
0fail/insertions,haiVIcontrolđúng; baseline cùngbackend none/auto6/12,
WER19.23%→10.26%. Không nới gate/đổi default: title4/6 vẫn chưa đủ.

Đã freeze profile và tạo promptset tech-fresh12câu mới. Cần người dùng thu
âm, không thay bằng TTS hoặc tự gán lại groundtruth. Chưa có fresh score.
Fullsuite820testsđạt;44testQwen/evalđạt;gitdiffcheckđạt. Agent không cóMetal,
MLX profile mới chưa kiểm trênGPU. Hướng dẫn/reportpaths/hashes:
Docs/QWEN_REFERENCE_DIAGNOSTIC.md. Không tải thêm weights.


## ASR 1.7B: tải/kiểm hash và ba lượt đánh giá đã hoàn tất, chưa đạt gate

Hai shard đã khớp size/SHA-256. Official CPU FP16 full12clip:
tech/vi5/12whole,4/6titles,13/16terms;
none/vi5/12whole,4/6titles,11/16terms;
none/auto6/12whole,4/6titles,11/16terms. Cả3không lỗi inference nhưng đều
fail gate; auto chỉ sửa được1/2câu EN và1/2control VI đúng. Peak processRSS
max~7.66GB; coldCPUmedian~11s không đại diện latency GPU/keep-loaded.
Không đổi model mặc định củaELVION. Không tiếp tục tải/chỉnhpreset mù;
next: phân tích lỗi theo action/title/English và kiểm trên câu mới có người
dùng xác nhận. Docs/QWEN_REFERENCE_DIAGNOSTIC.md có bảng/reportpaths.


## Web DOM Reader: đã sửa xong 5 lỗi review (WEB-READER-001..005) — 01/11/2026

Đã xử lý triệt để 5 vấn đề được phát hiện trong lượt review:
- WEB-READER-001: Khử đệ quy toàn bộ (iterative stack traversal), chặn RecursionError khi DOM lồng sâu (đã test 1200 tầng div); thêm MAX_DOM_DEPTH=256, MAX_DOM_NODES=20000; loại bỏ cây con script/style/svg ngay lúc parse.
- WEB-READER-002: max_chars trở thành hard bound bất biến `len(full_text) <= max_chars`; giữ lại tiền tố đoạn văn dài thay vì bỏ trắng nội dung; bổ sung cờ `is_truncated: bool`; giới hạn cứng metadata (title 300, desc 500, byline 200, links 200, excerpt <= min(max_chars, 450)).
- WEB-READER-003: Phân định block lá (p, pre) và block container (blockquote, li, dd, dt); container chứa block con không trích xuất đoạn văn tổng, loại bỏ hoàn toàn lỗi lặp đoạn văn.
- WEB-READER-004: Áp dụng _sanitize_link với allowlist scheme {"http", "https"}, lọc regex case-insensitive các scheme nguy hiểm (javascript, data, vbscript, file), chuẩn hóa scheme thường và kiểm tra netloc.
- WEB-READER-005: Loại bỏ text ẩn (HTML5 hidden, aria-hidden="true", display:none, visibility:hidden, opacity:0, class ẩn); bổ sung fallback thẻ <time datetime="..."> cho ngày đăng.
Kiểm chứng: 21/21 tests trong `tests/test_browser_reader.py` đạt (100%); toàn suite dự án đạt 816/816 tests PASS (0 failures, 0 errors). Đã cập nhật chi tiết vào BUG_LOG.md. Sẵn sàng để nối vào multi-step planner.


## Nhắc việc: các ca CLI desktop chính đã được người dùng xác nhận

Người dùng xác nhận đạt tạo/xem/phát không thấy lặp, hủy trước hạn không
phát và tạo lịch rồi thoát/mở lại session --reminders vẫn thông báo đúng
kỳ vọng. Worker chỉ chạy khi có phiên mở; chưa kiểm chứng voice native,
crash recovery hay exactly-once. Lỗi chính tả Hủy/Huỷ đã sửa và có regression;
chưa có xác nhận riêng biến thể Huỷ sau khi nạp mã mới.


## Nhắc việc: sửa biến thể “Huỷ” trong router/planner

Lỗi UNSUPPORTED của lệnh hủy do parser chỉ nhận “Hủy”, không phải UUID.
Đã hỗ trợ cả “Hủy/Huỷ” và bộ lọc “đã huỷ”, giữ grant/xác nhận; 30/30 test
session/product đạt. Cần mở lại phiên để thử mã mới trên desktop. Lịch của
lệnh hủy thất bại vẫn có thể phát đến hạn; không suy ra đã hủy thành công.


## Nhắc việc: CLI native tạo/xem/thông báo đã được người dùng xác nhận

Trong phiên `session --reminders`, tạo lịch sau 1 phút và xem lại đều thành
công; người dùng xác nhận thông báo có phát, không thấy phát lặp trong lượt
thử. Chưa suy rộng thành exactly-once. Tiếp theo kiểm tra hủy trước hạn,
từ chối xác nhận và mở lại phiên CLI; voice chưa kiểm chứng desktop.


## Nhắc việc: đã nối phiên CLI/voice, chờ desktop smoke

Bật `--reminders` để route vào RemindersOrchestrator trước model planner
và chạy worker quét mỗi 2 giây khi phiên còn mở. Mỗi action vẫn cần grant
và xác nhận bàn phím. Thread có SQLite connection riêng; lock một worker
mỗi data-dir, dừng khi lỗi gửi/ack và đóng khi thoát. Không có service chạy
sau khi đóng ELVION. Có preview, danh sách, UUID và mốc đến hạn trong CLI;
TTS có câu kết quả cố định cho 4 capability.

Đã bổ sung relative schedule “sau 1 phút”, kiểm bằng clock cố định. 9 test
phiên/worker mới +20 test product đạt; toàn suite 809/809 đạt;
`git diff --check` đạt. Chưa thử CLI/voice mới với notifier thật; smoke riêng
store/consumer desktop người dùng đã xác nhận đạt trước lượt tích hợp này.
Hướng dẫn: `Docs/REMINDERS_SESSION.md`. Lệnh bắt đầu:
`PYTHONPATH=src python3 -m elvion session --reminders`.
Giới hạn race hủy/gửi, crash giữa gửi/ack và hiển thị banner được ghi rõ;
không tuyên bố exactly-once.


## STT: tiếp tục tải 1.7B, chưa có inference mới

Đã khôi phục sau mất kết nối: range parts còn khoảng 1.5 GB, chưa đủ
weights. Đang thử tải tiếp qua kho Qwen ModelScope; chỉ nhận model khi cả
hai shard khớp size/SHA-256 của revision Hugging Face đã chốt. Không thay
model sản phẩm. 19 test Qwen và full suite unittest 800/800 đạt trong lượt
này; log ở `.build/qwen-reference/test-suite.log`. Reference benchmark đã
phân biệt subset diagnostic với đánh giá trên toàn corpus cũ.


## Web DOM Reader: hoàn thành bộ trích xuất nội dung bài viết sạch — 01/11/2026

Đã triển khai bộ đọc DOM và trích xuất nội dung bài viết sạch local-first cho web:
- Bộ đọc bài viết: `src/elvion/browser/reader.py` (`extract_article`, `read_page`, `ExtractedArticle`).
- Lọc bỏ boilerplate/rác: loại bỏ tự động thẻ kịch bản (`script`, `style`, `noscript`), quảng cáo, thanh menu (`nav`, `header`, `footer`), cookie consent, mạng xã hội, popup, comment.
- Thuật toán chọn vùng nội dung: ưu tiên `<article>`, `<main>` hoặc tính điểm mật độ văn bản/đoạn văn của các container `div`/`section`, phạt vùng có link density cao.
- Trích xuất metadata và cấu trúc: tiêu đề (og:title, twitter:title, title), tác giả, ngày đăng, mô tả tóm tắt, danh sách tiêu đề phụ (h1-h6), đoạn văn (`paragraphs`), liên kết nội dung (`links` được chuẩn hóa URL tuyệt đối qua base URL).
- Giới hạn an toàn: chống quá tải bộ nhớ (tối đa 5MB HTML đầu vào, tối đa 50.000 ký tự văn bản trích xuất, 500 đoạn văn), an toàn trước HTML lỗi/thiếu thẻ đóng.
- Tích hợp `BrowserSession`: phương thức `read_article()` cho phép đọc trực tiếp trang web đang mở trong Chromium.
- Kiểm chứng: 15/15 tests trong `tests/test_browser_reader.py` đạt (100%); toàn bộ test suite dự án đạt 800/800 tests PASS (100%). Không chạm vào `src/elvion/voice/` hay `src/elvion/reminders/`.


## STT: official0.6B xácnhận cùng3lỗi;đangtải1.7B

User cho phép tiếp tục phương án khác khi chưa đạt. OfficialCPUFP32 cùng
3transcript sai nhưMLX;0/3whole,0/2title,không làqualityscoretổngquát.
0.6BFP16CPU qua1clip,peakRSS2.78GB,vẫnsai. Đangresumetải1.7B4.70GB
2shards,pinnedrevision/hash. Tiếp theoCPUFP16smoke resource rồi mới
fullcorpus/gate. Không đổivoice default. Docs/QWEN_REFERENCE_DIAGNOSTIC.md.

## Qwen0.6B ablation chưa đạt — 01/11/2026

Besttechvi6/12whole,4/6titles,13/16terms,0reject. Nonevi5/12whole.
Auto báo nhầmThai/Cantonese nên languageguard từchối2–3clips, khôngcrash.
Tất cảgatefalse, chưa đổivoice default. Không tiếp tục chỉnhpresetmù.
Nextproposal: officialimplementation parity trên2–3clipcũ/cùngweights
trước quyết định tải1.7B. Chưa triểnkhai parity, chưa biết nguyênnhâncuối.
Docs/QWEN_ASR_RESEARCH.md chứa metrics; report raw giữprivate artifacts.

## Qwen native chạy được, quality5/12 chưa qua cổng

None auto/vi đều5/12whole và4/6titles;auto3invalidresponses,vi0. Không
promote hoặc tải1.7B. Đã thêmdiagfixed +publictechcontextopt-in. Lệnh
benchmark_qwen_asr.py --corpus <english-01> --context both so4configs trên
clip cũ và ghi nguyênnhân phản hồi bị từ chối; khôngrewrite/nới gate.
16Qwen+21evaltests đạt. Cần chạyTerminaluser;agentvẫnthiếuMetal.

## TaskB reminders: hoàn thành tích hợp sản phẩm độc lập (Option 1) — 01/11/2026

Đã kết nối hoàn chỉnh từ lõi ReminderStore vào hệ thống runtime của ELVION:
- Core Contracts & Validators: `src/elvion/core/reminders.py` (`reminder.create`, `reminder.list`, `reminder.complete`, `reminder.cancel`).
- Policy bảo mật: `src/elvion/policy/reminders.py` (`version="reminders-v1"`, kiểm tra grants, argument types, confirmation bắt buộc khi hủy).
- Bộ phân tích ngôn ngữ tự nhiên: `src/elvion/planning/reminders.py` (lệnh tiếng Việt một lần, hàng ngày, hàng tuần, xem danh sách, hoàn thành, hủy).
- Native Adapter & Verifier: `src/elvion/adapters/reminders.py`, `src/elvion/verification/reminders.py` (xác thực token 64-char SHA256, kiểm chứng hậu điều kiện độc lập qua `ObservationRequest`).
- Consumer & Notification: `src/elvion/reminders/consumer.py` (`ReminderNotificationConsumer` kiểm tra status/revision trước khi dispatch native notification và ack).
- Runtime Orchestrator: `RemindersOrchestrator` trong `src/elvion/core/runtime.py`, đã đăng ký allowlist trong `src/elvion/storage/trace_privacy.py`.
- Kiểm chứng: 20/20 test cases trong `tests/test_reminders_product.py` đạt; full test suite đạt 785/785 tests PASS. Không chạm vào `src/elvion/voice/`.

## SpikeQwenASR: môi trường đã cài, chờ native Metal doctor

Đã chuẩn bị adapter/worker/doctor/resumable verified download/benchmark
độc lập; venv.build/qwen-asr/venv cài xong. Agent doctor default/CPU đều
METAL_DEVICE_UNAVAILABLE ngayimport; chưa tải1.88GBweights/chạyinference.
Cần chạy Terminal: PYTHONPATH=src python3 scripts/check_qwen_asr.py --doctor
14 fake tests mới đạt, fullsuite755 đạt trước2testcuối. Không đổi default
hoặc runtime sản phẩm; TaskBreminders độc lập. Docs/QWEN_ASR_RESEARCH.md.

## Phương án STT mới sau nghiên cứu chính thức — chưa triển khai

Docs/STT_RECOVERY_PLAN.md chốt hướng ASR local candidate mới -> context/
pronunciation -> calibrated clarification -> dữ liệu/fine-tune sau.
Ưu tiên spike Qwen3-ASR0.6B, kiểm tra runtimeAppleSilicon và dependency riêng
trước download; chưa hứa quality/RAM/latency. Cổng đo cảcâu/title, không chỉ
terms. Không cloud upload hoặc defaultchange. TaskB reminders độc lập.

## STT Việt-Anh chưa đạt: dừng khuyến nghị các preset hiện tại

Fresh native câu mới sai nghĩa; smalltech1/12whole chỉ13/16terms không đủ.
Ablation CPU none: small0/12whole,title2/6,term9/16; medium2/12whole,
title4/6,term13/16. Tắt prompt không chữa. Không cấu hình nào được chốt
dùng hàng ngày, saved default chưa đổi. Cần đánh giá ASR Việt-Anh khác
trên corpus sẵn có và test câu mới sau khi đạt whole/title; chưa làm phần
backend mới, không tải model hoặc bắt user thu lại corpus.

## Native English fresh sentence chưa đạt — rút đề xuất smallvi/tech

User thử câu mới và transcript sai nghĩa nặng. Không dùng13/16term như
bằng chứng chất lượng hội thoại; wholeexact1/12/title4/6 đã quá thấp.
Đang so none vs tech trên corpus cũ, ưu tiên full sentence/title/WER.
Không yêu cầu thu lại12clip, không tự đổi model/default hay LLM rewrite.
Audio audit: medianRMS -18.66dBFS, không lowlevel/clipping flags;4onset và
7offset energy flags không chứng minh mất âm hoặc mic kém. XemBUGLOG.

## english-01 có kết quả: ưu tiên thử Whisper-small vi/tech

CPU benchmark72obs: terms PhoSmall4/16,small13/16,medium14/16 (vi);
auto không giúp. Cả3 chỉ4/6titles, wholeexact1..2/12; chưa đủ coi STT ổn.
Đề xuất smallvi/tech cho thử hội thoại English, chưa đổi preference.
MedianCPU2.25s so medium6.24s, không suy GPU. BFS còn sai; cần câu mới và
nghe native mixed buffer. Xem Docs/VOICE_ENGLISH_RESULTS_2026-10-31.md.

## Technical STT comparison và mixed TTS buffer — 31/10/2026

Đã thêm bộ12 câu Việt/Anh/control, matrix model/context/language và metrics
thuật ngữ/title/failures/latency. compare_technical_stt.py so3 model đã cài
với vi/auto (6 cấu hình), không đổi default, không chạy tác vụ. Cần user
thu corpus technical mới trước khi đo accuracy; chưa có cấu hình thắng.
Mixed say hiện tổng hợp PCM riêng tư rồi afplay một lần; busy/stop/mic
guard giữ nguyên, lỗi không replay. Có thể chậm lúc bắt đầu; cần user nghe
desktop. Native agent file-only synthesis trả0frames, không suy desktop.
Docs/VOICE_EVALUATION.md có lệnh thu/so; Docs/VOICE_OUTPUT.md mô tả buffer.

## Voice quality: đã sửa logic, chờ nghe native

Terminal không có countdown thực tế. Đã bỏ excerpt240, speak_reply full<=1500
với budget45..240s. Mixed/en voices và tech STT context + language vi/en/auto
là opt-in; không đổi transcript, grants hay keyboard confirmation. 714 tests
đạt, git diff --check đạt; chưa phát tiếng/thu mic/model thật ở lượt sửa.
User đã xác nhận native followup DFS giữ ngữ cảnh trước bản sửa này.
Lệnh: PYTHONPATH=src python3 -m elvion voice --conversation-model qwen3.5:4b --speak --speech-mode mixed --stt-context tech
Gõ câu DFS/BFS để tách kiểm tra TTS, sau đó nói cùng câu để thử STT.
Mixed có thể ngắt giữa giọng; tech/auto chưa có bằng chứng accuracy tăng.
Xem VOICE-QUALITY-001 và Docs/CONVERSATION_VOICE.md.

## Hội thoại voice: basic native smoke được người dùng xác nhận

Người dùng chạy voice conversation4B + speak, thử theo hướng dẫn lời chào
và xác nhận đã ổn. Mốc thu/dừng/duyệt transcript, model reply và TTS cơ bản
đạt theo user feedback; không có latency mới hoặc transcript artifact.
Chưa xác nhận native multi-turn, reset và action decline qua chế độ mới.
Có thể thử DFS→followup, :chat-reset rồi action app.open + n. Không tự mở
rộng action/capability từ smoke chat. Xem CONV-VOICE-001.

## Voice hội thoại đã nối bridge, chờ native mic/TTS smoke

Command: PYTHONPATH=src python3 -m elvion voice --conversation-model qwen3.5:4b --speak
Giữ transcript review, keyboard confirmation, no-retry. Reply/clarify dùng
speak_text chung service; câu dài đọc excerpt<=240, full text hiển thị.
85 tests liên quan, toàn suite706 đạt; sessionbenchmark31/31.
Real4B typed-input voice CLI smoke đã đạt, không mic/STT/TTS thật hoặc grant;
artifact voice-text-smoke-f343521fdb07.json. Cần user nói lời chào/DFS/followup
và nghe phản hồi, rồi test action n; không suy native từ fake/typed smoke.
CLI chat user cancel trước đó đã nhận “Yêu cầu đã được hủy”.
Xem CONV-VOICE-001, Docs/CONVERSATION_VOICE.md.

## CLI hội thoại đã review và smoke model thật

Bridge giữ nguyên raw handoff/taskID, callback pipeline một lần, context
capabilities/grants cập nhật từng lượt, outcome fixed summary. Đã buộc
confirmation cho mọi conversation session, kể cả rules planner/no --confirm;
legacy CLI giữ setting cũ. 98 tests liên quan + fake60/60 đạt.
Actual CLI + local4B synthetic smoke: chat/DFS/BFS/negation/reset được;
app.open handoff đúng nhưng không grant nên denied, trace files0. Artifact
cli-smoke-b3351f863d95.json; tổng14.22s không là per-turn latency.
User command: python3 -m elvion session --conversation-model qwen3.5:4b
với PYTHONPATH=src. Voice/GUI chưa tích hợp; cần dùng bridge sau khi review.
Xem CONV-CLI-001/CONV-CONFIRM-001, Docs/CONVERSATION_CLI.md.

## Calculator single-action: positive và ba negative native đã đạt

User xác nhận ca precondition refusal UI vẫn5. Đã đủ smoke: AXPress0→7
verified; che nút bị từ chối/UI0; confirmation n cancelled/UI0;
precondition5 bị từ chối/UI5. Trace saved theo summary, chưa audit trace.
Chốt mốc Calculator trong phạm vi này, không mở rộng app/action tự động.
Task B đang tích hợp hội thoại vào CLI; nhánh chính chờ contract bridge để
review và nối voice, giữ capability/confirmation hiện có.
Xem AXACTION-001 và Docs/CALCULATOR_ACTION.md.

## Calculator negative: precondition refusal đúng, chờ UI sau test

Summary ca entry5: failed/VERIFICATION_FAILED/
CALCULATOR_BEFORE_NOT_ZERO_OR_UNKNOWN, postcondition=false, trace saved.
Reason phù hợp nhánh dừng trước AXPress; chưa có xác nhận số UI sau test.
Ca che nút và n đã đạt kèm UI0. Positive0→7 đã đạt. Không mở rộng capability
hoặc tự lặp action từ kết quả này. Xem AXACTION-001.

## Calculator negative: occlusion và confirmation n đã đạt

Ca n: cancelled/PERMISSION_DENIED, postcondition=false, trace saved, UI vẫn0.
Ca che nút trước đó: failed/SAMPLED_VISIBILITY_UNCERTAIN, UI vẫn0.
Còn thử entry ban đầu5 để xác nhận precondition không bị bỏ qua. AXACTION-001.

## Calculator native negative: che nút7 đã đạt

User summary failed/STALE_OBSERVATION/SAMPLED_VISIBILITY_UNCERTAIN,
postcondition=false, trace saved; UI vẫn0. Mốc occlusion action smoke đạt.
Còn confirmation n và entry ban đầu5 cần thử trên desktop. Không retry mù,
không thay guard để né occlusion. Xem AXACTION-001.

## Task B conversation đã review, demo local4B dùng được

15 tests sau sửa memory boundary và fake60/60 đạt. Real4B smoke8dev đạt
8/8 route, actions0; chưa full60/heldout/qualityreview. Artifact
local-smoke-3aeac798d5f7.json, trước sửa overflow memory. Câu hỏi máy tính
có thể bị hiểu là laptop; cần context app khi tích hợp. Chưa nối executor.
Demo: scripts/check_conversation.py --model qwen3.5:4b.
Memory oversized latest turn không còn để topic cũ làm ngữ cảnh tiếp theo;
reason CONTEXT_TURN_NOT_RETAINED. Xem CONV-LIMIT-001/CONV-MEM-001.
Task A native Calculator positive đã đạt; negative desktop smoke còn lại.

## Native Calculator AXPress end-to-end đã đạt

Summary desktop người dùng: succeeded, AXPRESS_RETURNED, postcondition_verified
true, error_code null, trace saved. Đây là single-action nút7 qua grant/
confirmation/revalidation/AXPress/independent after-read quan sát entry0→7.
Native trace saved theo summary, chưa được nhánh chính đọc lại trong lượt này.
AXACTION-001 đạt mốc positive, không suy rộng negative guards hoặc app khác.
Chưa bật global CLI/voice/GUI. Bước tiếp: negative desktop smoke có kiểm soát
(deny, precondition khác0, target bị che), rồi review tích hợp capability.
Task B conversation độc lập, chưa mặc định nối vào action pipeline.

## Calculator: native read-only entry 0→7 đã verified

Người dùng xác nhận verified/ENTRY_TRANSITION_OBSERVED, current_entry,
actions=0, authority=false, causality=false. Collector/profile/parser LRM
và verifier đã đạt mốc smoke desktop. AXRESULT-001/AXFORMAT-001 đã giải quyết
trong phạm vi ca này, không suy rộng mọi locale/mode.
Tiếp theo: check_calculator_action.py --grant-press7 --include-current-entry,
Calculator về0, nút7 không bị che, xác nhận y/N. Chưa AXPress tự động thật.
Không bật global CLI/voice/GUI; no retry giữ nguyên.

## AXFORMAT-001: đã sửa edge U+200E, chờ smoke desktop

Native format diagnostic xác nhận một LRM và một ASCII digit. Parser dùng
chung chỉ bỏ edge U+200E/ASCII space, không xóa sign/decimal/operator hoặc
LRM ở giữa. Verifier và action precondition cùng dùng parser; raw obs giữ
nguyên. 45 tests liên quan đạt. Cần chạy read-only --include-current-entry,
Enter đầu ở0 rồi tự nhấn7 và Enter cuối. Chưa AXPress thật sau sửa.

## AXFORMAT-001: chờ format native của entry 0

Region đã đọc được, lỗi xảy ra ở parser trước bước nhấn7. Đã có diagnostic
một lần --include-current-entry --diagnose-format, không prompt/không action.
41 tests liên quan đạt. Agent trả APP_NOT_RUNNING, chưa có format native.
Không đoán/bỏ dấu âm hay decimal để nhận0. Cần JSON format từ desktop;
sau đó sửa parser dùng chung với baseline adapter. Task B conversation độc lập.

## Calculator: sửa đúng surface cho digit7, chờ smoke entry

Native diagnostic về 0 chỉ có StandardInputView trong AXWindow, không có
StandardResultView. Đã tách current_entry khỏi computed result; opt-in/API/
expectation và action grant riêng. Smoke: scripts/check_calculator_verification.py
--include-current-entry (người dùng tự 0→7). Không nhập profile, không AXPress.
38 tests liên quan, toàn suite 657 tests đạt; Swift helper compile. Chưa có
native value/transition proof. Action v2 dùng read_entry, chưa bấm thật.
Lịch sử sai giả định result và các lần NOT_FOUND nằm ở AXRESULT-001.

## Calculator result: native NOT_FOUND, chờ diagnostic sau Clear

Smoke profile StandardResultView trả RESULT_REGION_NOT_FOUND, actions=0.
Chưa biết profile thay đổi ở trạng thái 0 hay traversal thiếu window binding.
Đã thêm window_role và helper_source_sha256 vào --diagnose-region, không
đọc result/input value, không nới capture guard. 35 tests liên quan đạt.
Cần diagnostic khi Calculator đã về 0; xem AXRESULT-001. Chưa AXPress thật.

## Calculator result: đã nối profile native, chờ smoke chỉ đọc

Diagnostic người dùng xác định AXStaticText ID rỗng dưới
AXScrollArea/StandardResultView, khác StandardInputView. Đã sửa validator,
collector native và hai CLI để nhận đúng tuple rỗng này, không wildcard;
known input container bị từ chối, duplicate vẫn unknown. 34 tests liên quan
đạt. Cần chạy read-only demo 0→7 bằng tay với --result-identifier '' trước
AXPress thật. Chưa có bằng chứng AXValue/transition native. AXRESULT-001.
Lệnh cụ thể trong Docs/CALCULATOR_VERIFICATION.md.

## Task A Calculator AXPress: code và fake pipeline đã đạt

Đã có desktop.calculator.press7 qua policy/confirmation/registry/orchestrator,
helper prepare/commit một lần, revalidation native trong cùng process,
reservation SQLite và verifier độc lập Task B. Không tự retry; không nối vào
CLI/voice/GUI chung. 19 tests mới và toàn suite 649 tests đạt; Swift compile,
reject-only native protocol đạt, không gửi commit/AXPress thật.
Agent discovery dừng DISPLAY_LAYOUT_UNAVAILABLE. Native positive còn chờ
Terminal người dùng và profile vùng kết quả đã review/kiểm chứng Task B.
Bước tiếp: --diagnose-region chỉ đọc để review profile, smoke collector 0→7
bằng tay, rồi script check_calculator_action.py có hai grant flags + y/N.
Không đoán profile hoặc bỏ verifier để thử action. Xem Docs/CALCULATOR_ACTION.md
và AXACTION-001. Nhánh chính không sửa các file Task B.

## Desktop revalidation: native ready đã đạt

Người dùng đã chạy Calculator thật: ready/BOUNDED_AX_SAMPLES_MATCH,
bounded_observation_checks_passed=true, actions=0. Mốc smoke positive native
đã đạt, không còn chờ lượt ready đầu tiên. Authority, execution freshness,
identity liên tục từ snapshot cũ và whole-target pixel visibility vẫn false.
Không bật desktop click hoặc tích hợp executor tự động. AXREVAL-LIMIT-001
vẫn mở cho giới hạn action-time/TOCTOU; cần hợp đồng thao tác và verifier riêng.
Vision Task A đã đạt cached regression 30/30, chưa native/public validation
cho cấu hình mới. Nhật ký giữ riêng evidence synthetic và native.

## Task B revalidation đã review, chờ native ready

Spike chỉ đọc đạt 40/40 synthetic, false_ready=0, actions=0. Nhánh chính
chạy lại tám hàm test đạt và thêm load_tests adapter để unittest discovery
thực sự thu thập chúng; xem AXREVAL-TEST-001. Không sửa evaluator/backend.
ready là reacquired target có provenance/clock/process marker và pre/post
samples phù hợp, không là authority hoặc continuity từ snapshot cũ.
Cần người dùng chạy scripts/check_desktop_revalidation.py --label '7'
--include-labels sau khi mở Calculator và để nút không bị che.
Native agent chỉ có DISPLAY_LAYOUT_UNAVAILABLE theo Task B; chưa có ready
trên desktop thật. Giới hạn AXREVAL-LIMIT-001 vẫn mở, chưa nối executor/AIMS.

## Task A Vision: replay 30/30, Methods lặp thêm 3/3

Hai thay đổi opt-in: visual-evidence-v1 (chỉ runner nghiên cứu) và kiểm tra
full-frame để tinh chỉnh refusal của các candidate trùng thành not_found
khi tất cả được xác nhận là text/multiple. Không tạo found từ bước này.
Report fixture-replay-3046254907a8.json: 30/30, target hit 22/22,
0 false acceptances/wrong targets; Methods thêm 3/3 ở 993f839ae05b.
611 tests đạt. Median toàn corpus ≈17.66s; chưa đạt execution freshness.
Đã đủ cached regression, chưa native end-to-end/public/blind cho config mới.
Chưa đổi defaults/live Vision. Hướng dẫn và lệnh native:
Docs/VISION_ROLE_REVALIDATION_2026-10-31.md; lịch sử BUG-019.
Task B desktop revalidation độc lập, nhánh chính không sửa file Task B.

## Visibility: smoke native năm điểm mẫu đã đạt

Người dùng đã chạy Calculator thật: blocked/occluded ở một lượt, sau đó
visible/FIVE_AX_POINTS_BOUND_TO_TARGET, 5 điểm, age≈61.66ms, actions=0.
Đã có positive native; lượt blocked chưa có oracle che khuất độc lập.
Chỉ xác nhận sampled AX visibility, chưa whole pixels hay execution freshness.
Giới hạn race/revalidation AXVIS-LIMIT-001 vẫn mở. Task A Vision tiếp tục;
chưa tích hợp desktop action vào AIMS/executor.

## Task B visibility đã review, chờ smoke native

Spike chỉ đọc hoàn tất; nhánh chính chạy 12 test visibility/benchmark và 43
khi gồm upstream đều đạt. Synthetic bàn giao 28/28, chưa chứng minh native.
Calculator thật cần thử nút 7 trên Terminal với --include-labels.
Giới hạn AXVIS-LIMIT-001: năm điểm AX khác whole-pixel visibility;
layout/state chỉ bind trước hit-test, chưa đủ execution freshness.
Không tích hợp AIMS/executor; Task A Vision tiếp tục độc lập.

## Native 9B toàn bộ 30 ca: 28/30, còn mâu thuẫn role

Report `vision-labels-20261031T040148-8df207b3.json`: positive 21/22,
0 false acceptances, 0 wrong targets; source hashes 8/8 khớp. Methods: bị
full-image nhận thành text dù local là link. Open guide heading/prose bị
local nhận thành hai link, trả ambiguous thay vì not_found. Median 17.357s.
Đã cập nhật BUG-019 và liên hệ hồi quy BUG-004; chưa sửa guard hay scorer.
Có đủ 30 frame/OCR để nghiên cứu offline với đối chứng, không cần thu lại.
Live Vision vẫn tắt; Task B visibility tiếp tục độc lập.

## Visionrolepresentation — selectedreplay4/4,chờnative30

Boundarynearwordđãnativepass ởe4158aca(1/4tổng,còn3role). Offline6-region
roleexperiment:unmarked5/6vscurrent2/6;metadata controlcònlocalrolewrong.
Fullrole2×5/5rolecontrol,vẫncócountmisskhônggọiquniquenessproof.
Combinedlabel2/roleoff/full2:fixture-replay-a9b7fd3667d5.json4/4,re-scored
bbox/sourcebindings. Defaults/guardkhôngđổi,605testsđạt. Positive17,6–22s
chưaphùhợpexecutionfreshness. Publiccached4case9Bvẫn3/4,Getstartedcònveto.
Cầnnative30ca1lượt --label-scale2 --role-marker off --full-scale2 với
--diagnose-modelđểcachedtoànbộdatasetchochẩnđoántiếp. Khôngclick/liveVision.
XemDocs/VISION_ROLE_PRESENTATION_2026-10-31.md,BUG-019. TaskBvisibility
độc lập,khôngthayAXmodulestronglượtnày.


## Native9B/scale2synthetic26/30 — sửa boundary,chờ4ca diagnostic

Reportvision-labels-20261031T032101-b142c710.jsonđã đối chiếumanifest/HTML/
summary:positive19/22,0falseaccept,2/2duplicateverified2. Ba falseabstentions
Proceed!/Methods:/Status:ready ởrolecheck,1wrongabstentionSavefile/Savefiles.
Đã sửa substringprefix bằng Unicodewordboundaries,không nới guard/scorer.
589testsđạt. Thêm --diagnose-model lưusyntheticframes/OCR/replies/bbox riêng
đểreplayoffline;chờ4cachọnlọc1lượt desktop,không yêu cầu cả30ca nữa.
XemDocs/VISION_9B_SYNTHETIC_REGRESSION_2026-10-31.md vàBUG-018.
TaskBvisibilitychỉ đọc vẫn độc lập,liveVisiontắt.


## Bàn giao TaskBvisibilitydesktop chỉ đọc

Promptchi tiết:Docs/TASK_B_DESKTOP_VISIBILITY.md. Phạmvi filemới package
desktop_visibility/helper/demo/benchmark/tests/docs,không sửaVision hoặc
AXmoduleshiệncó. Yêu cầudesignbằngchứngtrướcimplementation,visible/blocked/
unknown/error,sampledvisibility khácwholepixelvisibility;khôngauthority
hoặcexecutionfreshness. Tối thiểu24syntheticcases,khôngclick/focus/screenshot.
Promptđã sẵn đểgiao phiênB,nhánhchính chưa khởichạy agent hoặc implement
TaskBnày. TaskAVisionlabelscale2nativebenchmark30ca vẫn độc lập.


## Visionlabel2× — đọcnhãn5/5, pipeline9Bvẫn3/4

Đã đo6profiles×5regions,cóplantrướcmodel. Ảnhgốc2/5,upscale2/4đều5/5;
marker/keyriêngkhôngđủ. Thêm boundednativePNGresizevàlabel_scaleopt-in,
default1. TargetbboxCSS/rolecrop/fullveto giữnguyên;584testsđạt.
Modelcomparison-f3f83f7c307a.json:9B3/4,Docsverified2linkđúngcơchếduplicate;
Getstartedđọclabelđúngnhưngfullframezero/textnêntrượt. Thửfullframe2×
khôngsửalỗiđó.4negativecachedprobe:3đúng,1errorcachethiếuquery,khônggiấurow.
Cầndesktopchạyvision_labels.runner --modelqwen3.5:9b --grounderocr-verified-v4
--label-scale2 --splitall --headless,1lượt30ca. XemDocs/VISION_IMAGE_PRESENTATION.md
vàBUG-017. Chưađổi model/defaultsảnphẩm,liveVisionvẫntắt.


## Vision9Bcomparisonđã hoàn tất —3/4vs4B1/4, chưa go-live

Reportmodel-comparison-637f29445f0f.json complete8obs,hashes/digests/summary
đã đối chiếu.9BchọnđúngMigrations/W3C;Docsambiguous vìemptyreads,chưa chứng
minhđếmduplicate;Getstartedcònemptyreadfalseabstention. Positive9B2/3vs4B0/3.
Không cóabsentnegatives,không suyra safety/generalization. Median khác nhau
doearlyexit/coldstart,chưađoRAM.9Bchỉ ứng viên nghiên cứu,chưa đổi default.
XemDocs/WEB_VISION_MODEL_RESULTS_2026-10-31.md. Nút thắt tiếp theo:emptylabel
read trêncropChrome, cần thínghiệmtrìnhbàyảnh có kiểmsoát rồi regressionrộng.
Baseline5/9vàmọiprobe giữ nguyên. Các mục chờdownloadbêndưới là lịch sử.


## AX geometry — desktopgeometry_consistentđã xác nhận

Người dùng gửi target7found và geometry_consistent: bboxnằm trongwindow
Calculatorvàdisplaybounds[62,-900,1600,900]; negativeyđã cóbằng chứnglayout.
Hai mẫu layoutkhớp,actions0. XemAX-GEOM-001. Chốt smoke quan sát→targeting→
kiểmtrahìnhhọc trong Calculator; chưa kiểmvisibility/occlusion hoặc
freshness đủexecution, chưa có click/AIMS integration. Mục bên dưới làlịch sử.


## AX geometry — code/tests/build sẵn sàng, chờ desktop

Đã thêmcheck_desktop_geometry.py,geometry.py và DisplayGeometry.swift.
Đối chiếuAXtarget/window/display,giữnegativeorigins,noscaleconversion,
layouttrước/saukhớp,stale/truncatedmismatchđềuchặn.579testsqua; helper
Swiftcompileđược,agentreadlayoutunavailable nên chưa xác minh bboxthật.
CầnTerminaldesktop chạy --label7 --include-labels. XemDocs/DESKTOP_GEOMETRY.md
vàAX-GEOM-001. Chưa click,khôngscreenshot/đổifocus; geometrykhớpchưađủ
visibility/freshness choexecution. TaskAVisionmodelcomparison vẫn độc lập.


## AX targeting content — nativefound7đã xác nhận

Người dùng gửi found/EXACT_BUTTON cho label7:AXButton enabled,candidate1,
scopecalculator_content,243nodes,blockers0. Ba exclusions có native subroles
AXCloseButton/AXZoomButton/AXMinimizeButton mỗi loại1. Vướng mắc scope
windowchrome đã xử lý ở lượt này, bằng chứng ghiAX-LIMIT-003. Bboxyâm cần
đối chiếu displaymapping, không tự kết luận tọa độ clickhợp lệ. Chưaclick,
chưa nốiAIMS; snapshot timestampcuối lượt chưa đủ executionfreshness.
TaskAVisionmodelcomparison vẫn chờ model9B và báo cáo thực tế.


## AX target7: thêm scope content opt-in, chờ native xác nhận subrole

Diagnostic native:1matchingAXButton enabled có bbox,3unlabelledbuttons
trực tiếp dướiAXWindow. Chưa biếtsubrole. Mặc địnhall_buttonskhông đổi;
calculator_content chỉ loại window controls bằng subroleSDK+parentAXWindow,
resultbindscope. Diagnostic có subrole/exclusioncounts;28AXtestsđạt,
benchmarkdefault30/30. Chạy --label7 --include-labels --scope calculator-content
--diagnose-evidence; chưa khẳng định3blockers là windowchrome hay targetfound.
Xem AX-LIMIT-003 và Docs/DESKTOP_TARGETING.md. Không cóaction.


## Native AX targeting7: candidate1 nhưng incomplete evidence

Người dùng xác minh snapshot native có1exactAXButton candidate7 nhưng global
unknown guard chặn. Chưa có found hoặc đối chiếu bbox/enabled. Đã thêm
--diagnose-evidence dùng cùng snapshot, chỉ counts/structural IDs và roles,
không dump label/bbox.25AXtestsđạt,benchmark30/30không đổi. Cần chạy demo
--label7 --include-labels --diagnose-evidence để xác định blocker. Không
nới guard hay gán node không nhãn là không liên quan. XemAX-LIMIT-003.


## Task B AX targeting — đã review synthetic, chờ demo nhãn thật

10file nhận và review;14tests mới+9observer=23tests đạt. Synthetic30/30,
0falseacceptances,0actions; artifact desktop-targeting-20261030T175351-d7c3eeaf.json.
Locator pure,exactlabel,duplicateambiguous,unknownunavailable,guardsstale/
truncated. Chưa nối AIMS/executor. Chờ chạy scripts/check_desktop_targeting.py
--label7 --include-labels trongTerminal người dùng đã smoke243nodes. Bbox/
label chưa xác minh; observer timestamp cuối thu thập chưa đủexecution
freshness. Xem AX-LIMIT-002. Task A Visionmodelcomparison vẫn độc lập.


## Vision model comparison — runner sẵn sàng,9Bchưa tải xong

Đã thêm benchmarks/web_observation/compare_models.py,5tests và
Docs/WEB_VISION_MODEL_COMPARISON.md. So cùng4ảnh/OCR cached,model4Bvs9B,
pin digest/input/source,giữ guard/scorer,one-pass,cold load tính vào timing.
553tests toàn suite đạt. Native OCR không chạy ở phép đo này,chỉ crop native
và model thật. Chưa có điểm9B: tải7,6GB rất chậm,đã dừng client; preflight
model-comparison-5a64450351bd.json incomplete0obs. Cần ollama pullqwen3.5:9b
trênTerminaldesktop rồi chạy module compare_models. LIMIT-003 giữ bằng chứng.
Không thay model sản phẩm,không live Vision;4cađãthấy không làheld-outmới.


## Task B AX — smoke desktop observed243nodes, không truncated

Người dùng gửi summary native: observed,reason null,nodes243,truncated false
sau cấp quyền Accessibility. Trở ngại quyền trên host chạy lệnh đã vượt qua.
Đã có smoke quan sát thật; chưa review node/bbox/role hay nhiều màn hình.
Chưa nối AIMS hoặc thêm thao tác. Bước tiếp theo là kiểm tra chất lượng
snapshot/role/bbox và freshness trước tích hợp observation channel.
Bằng chứng và giới hạn: AX-LIMIT-001 trong BUG_LOG. Mục bên dưới là lịch sử.


## Task B desktop AX: đã review, chờ quyền desktop

Spike Calculator chỉ đọc7file đã nhận/review. 8tests ban đầu đạt; sửa
strict protocol version/duplicate keys và bổ sung test,9/9AXtests đạt.
Demo native trong agent trả permission_required/AX_PERMISSION_REQUIRED,0node.
Chờ chủ dự án mở Calculator, cấp Accessibility cho host Terminal rồi chạy
PYTHONPATH=src python3 scripts/check_desktop_observation.py. Chưa nối AIMS
hay thêm action, chưa có cây AX thật được xác minh. Xem AX-LIMIT-001 và
AX-BUG-001; module độc lập với source/ảnh/benchmark Vision hiện tại.


## Focus crop đã sửa — no-go do full-frame role bất đồng

Bản merged-query desktop vẫn0/4. Đã sửa label padding12,role context96 và
marker ngoài bbox; giữ full-frame gốc và veto.547 tests đạt. Replay đúng
source với cached desktop OCR + native crop + live model:1/4đúng (Docs
ambiguous); ba label khác đọc đúng/local link,full-frame text nên từ chối.
Không phải desktop end-to-end hay điểm held-out mới. Artifact
focus-cached-ocr-probe-d1aeb6f7bdb3.json và driver/provenance cùng thư mục.
Giữ mọi probe, không best-of. Chưa đóng BUG-014..016. Nút thắt kế tiếp là
phân loại role full-frame của4b. Live Vision tắt, baseline5/9không đổi.
Task B desktop AX chỉ đọc vẫn độc lập.


## Sửa candidate dòng ghép — chờ diagnostic desktop

Code đã sửa lỗ hổng bỏ qua merged label khi có exact candidate khác; thêm
--label native geometry query cho dòng không delimiter, ambiguous nếu
không định vị hết merged evidence. Không sửa blind read của Migrations.
57 targeted / toàn suite546 tests đạt; Swift helper compile được, native
OCR agent vẫn lỗi. Cần evaluate --diagnose-model bốn ca h02/h05/h09/h10
một lượt trên ảnh cũ, giữ mọi kết quả. Đây là regression sau xem held-out;
baseline5/9 không thay, freeze cũ không cập nhật. Xem BUG-014..016.


## Held-out đầu tiên: 5/9 — no-go, ưu tiên lỗi trùng nhãn

Đã đối chiếu plan-run-0d240437b49b.json: complete, quality_valid=true,
checksum và summary khớp; 5/9 đúng, positive1/4, negative4/4, ambiguous0/1
(có1false acceptance), 0provider errors,3/12unscorable. Ba ảnh/ba domain.
Không click/gõ. Báo cáo: Docs/WEB_VISION_HELD_OUT_PILOT_2026-10-30.md.
BUG-014 duplicate Docs ưu tiên trước BUG-015 OCR recall và BUG-016 label read.
Chưa sửa grounder, chưa gọi lại model. Bảo toàn baseline đầu tiên; mọi tuning
sau khi xem ca này phải gọi là regression, không tiếp tục claim held-out mù.
Task B desktop Accessibility chỉ đọc vẫn độc lập. Các mục bên dưới là lịch sử.


## Held-out: đã khóa oracle, chờ một lượt desktop inference

12 ca / 3 ảnh / 3 domain; 4 found, 4 not_found, 1 ambiguous, 3 undetermined.
Plan: artifacts/benchmarks/web-observation/held-out-plan-frozen-01.json.
Code Vision và manifest vẫn khớp configs/vision-web-heldout-freeze-v1.json.
Runner hỗ trợ split held_out tường minh, kiểm tra freeze/model/manifest và đủ
12 ca trước tạo plan; kiểm tra checksum trước và giữa các lượt. Không model
held-out nào đã được gọi trong bước chuẩn bị này. Không sửa grounder theo
kết quả giữa chừng. 25 tests observation và toàn suite 534 tests đạt.
Chrome render suy giảm, oracle có AI self-review, 3/12 unscorable (25%) và chỉ
1 ambiguity: coverage chưa đạt protocol, dù kết quả inference có thể đúng hết.
Live Vision vẫn tắt. Task B độc lập: Docs/TASK_B_DESKTOP_OBSERVATION.md, chỉ
đọc Accessibility Calculator; chưa giao/chạy phiên phụ trong lượt này.


## Frozen dev plan10/10 — chuẩn bị held_out chỉ capture/annotation

plan-run-c4d54d4b564b.json hợp lệ:10/10scorable,2unscorable giữ riêng,
positives3/3,0/7 false acceptance,0errors. Không đủ ambiguity/domain/held_out
cho generalization. Core/manifest freeze configs/vision-web-heldout-freeze-v1.json.
Capture3heldoutURLs bằng --page-cases ->12goal dirs/3screenshots, khóa toàn
bộ oracle trước model, không sửa source theo held_out giữa chừng.


## Dev batch ready — cần chạy một frozen plan thay vì gộp versions

Bốn ca d03/d04/d06/d07 correct_rejection. Đã khóa kế hoạch12manifestdev:
artifacts/benchmarks/web-observation/dev-plan-subline-01.json.10scorable
(3found/7not_found),2undetermined không inference. Evaluate-plan kiểm tra
source/oracle, giữ mọi attempt/partial progress, summary denominators và
unique image hashes. Chưa native run; không quality score mới, không blind
claim vì dev đã xem và nhiều AI-reviewed annotations. Held_out chưa dùng.


## Python modules correct rejection — còn bốn dev cases chưa capture

proposal-c2080bb79579.json đúng not_found trong viewport,786.208ms. Giữ
source. Batch capture d03/d04/d06/d07 rồi review ảnh trước model; không
capture lặp d05/d12 unscorable để chọn kết quả thuận ý. Chưa có tổng hợp
source-aware quality/held_out nên chưa kết luận go/no-go.


## wo_d12 chưa đủ oracle role — giữ unscorable, không capture lặp tiếp

capture-d47fdfc8ef47 DOM same-session vẫn capture_changed, khóa undetermined,
không model/actions. Hạn chế này giữ trong ledger, không tính correct reject.
Không đổi grounder/guards. Tiếp tục wo_d02_python_modules trong dev manifest;
expected phải chấm từ ảnh, không từ tên case. Held_out public chưa dùng.


## Subline snapshot labels90/90 — mở rộng oracle dev, giữ code

vision-labels-20261030T151837-1c5d231b.json đạt90/90, không false acceptance.
Snapshot configs/vision-v4-subline-snapshot.json. Giữ source; hoàn thiện các
ca manifest public dev, bắt đầu wo_d12_wiki_duplicate (expected vẫn cần chấm
ảnh, không mặc định ambiguous theo case name). Public held_out chưa dùng.


## Hướng dẫn native3/3 đúng — BUG-013 giải quyết trên capture

reproduction-1523152f6e27.json:3/3 correct_target, subline bbox riêng đúng,
median3438.180ms, không actions. Giữ code hiện tại, đo labelsallx3 trước khi
chỉnh gì khác. Source mới marker subline/navigation role chưa được gán điểm
synthetic90/90 cũ, browser actions chưa qualify. Public held_out chưa dùng.


## BUG-013 subline+marker+navigation role — chờ native3reps

Native subline bbox đúng Hướng dẫn nhưng transcription đọc nhầm Sửa bài.
Marker theo provenance subline sửa read; v4 role mô tả thêm link navigation
không underline. Replay02 found, local/full link đồng thuận. Chưa native
sau thay đổi; cần evaluate --diagnose-model --repetitions3. Source mới chưa
qualify synthetic/actions, live Vision tắt, giữ oracle và failed reports.


## BUG-013 native delimiter subline — chờ desktop quality

Current raw OCR xác nhận Hướng dẫn bị gộp cả hàng. Helper --segments có
native range bbox, không nội suy vị trí. V4 gọi conditional subline pass khi
không có normal candidates; vẫn blind exact read và semantic guards.37tests
liên quan đạt, Swift compiled. Chưa có native result; evaluate capture cũ
--diagnose-model trước đo regression. Live Vision tắt, không sửa oracle.


## Wikipedia button correct_target — tiếp theo link dev

proposal-c0f33b01ccb5.json found đúng nút, local/full button/enabled,
9105.864ms, actions0. Source giữ nguyên checkpoint OCR edge. Latency gần TTL
nên chưa live actions; tiếp tục observation positive link wo_d11_wiki_guide,
không đổi code/TTL trước thêm bằng chứng. Held_out public chưa inference.


## OCR edge snapshot labels90/90 — giữ grounder, mở rộng oracle web

vision-labels-20261030T144854-4e2b0a75.json đạt90/90; source frozen tại
configs/vision-v4-ocr-edge-snapshot.json. Không cần test cùng source lặp vô
hạn. Ưu tiên thêm annotations public dev và tổng hợp theo source checksum,
không gộp best-of từ các phiên bản. Live Vision tắt, held_out web chưa dùng.


## MDN wrong-role native correct_rejection, BUG-012 hết decoder error

proposal-d6615bb7d815.json:2464.052ms, native_edge_adjustments2, không actions.
Model role vẫn link chứ không phải heading/text, chỉ correct rejection cho
requested button. Không suy classification hoàn hảo. Source tolerance mới
chờ synthetic labels regression trước action qualification.


## BUG-012 native OCR edge tolerance — chờ desktop

Raw OCR MDN helper thành công nhưng bbox HTML x âm0.042px khiến decoder từ
chối toàn response. Sửa tolerance0.1CSSpx chỉ native observations, lỗi lớn
vẫn bị chặn. Replay decoded51/52lines, wrong-role rejection đúng cho button;
model gọi heading là link, không claim nhận đúng text. Cần desktop evaluate
capture-e206ca64ae4a để xác nhận hết PROVIDER_ERROR. Live Vision tắt.


## Selective marker: labels90/90 + Wikipedia3/3

Đã lưu configs/vision-v4-selective-marker-snapshot.json. Checkpoint chỉ cho
quan sát, không action qualification. Giữ nguyên grounder, thêm annotation
MDN dev wrong-role, không cần đổi scorer hoặc pipeline. Public web held_out
chưa dùng; còn thiếu unique scenes/domain/ambiguity để đạt go/no-go.


## BUG-011: marker toàn cục labels87/90, thu hẹp policy chờ đo

h05 Tag; trượt3/3 dù OCR exact. Policy marker mới chỉ single leading glyph
hypotheses, trước model; exact/punctuation/diacritic dùng ảnh không marker.
31 tests liên quan đạt; chưa native quality score sau policy, không live
Vision. Đo labels allx3 trước, nếu đạt mới Wikipedia3repetitions trên ảnh cũ.


## Marker Wikipedia native3/3 đúng — chờ synthetic regression

reproduction-7125c3197433.json:3/3 correct_target trên cùng capture, đầy đủ
OCR/model native, không actions. BUG-009 giải quyết trên ảnh/dev regression
này. Cần labels allx3 vì marker thay input model; không reuse điểm source cũ.
Webheld_out chưa dùng, chưa đủ scene/domain để kết luận tổng quát.


## BUG-009 reproduction: model đọc logo thay nhãn; marker thử nghiệm

reproduction-36efc1713b57.json:3/3 sai, cùng OCR/crop, read thư mở. Marker
outline OCR bbox cho transcription giúp replay native crop/model found;
QA xác nhận pixels chữ không đổi. Semantic/full-frame vẫn ảnh gốc. Chờ
native desktop3 repetitions, chưa đóng bug hoặc coi stable. Source mới phải
đo regression lại, không dùng điểm snapshot trước marker.


## Guard đồng thuận: labels90/90 + browser challenge54/54

Snapshot configs/vision-v4-consensus-snapshot.json. Source giữ nguyên giữa
hai lượt; 27 verified clicks/9 guards, không click sai. Chờ Wikipedia native
regression sau full-role veto, rồi thêm annotations dev/domain. Held_out web
chưa dùng, không public-web actions.


## Full-role veto labels đạt90/90 — chờ browser/native web regression

Report vision-labels-20261030T135206-aa502fc3.json đã đối chiếu: positives
66/66, false acceptances0/24, ambiguity6/6, errors0. BUG-010 giải quyết trên
bộ nhãn. Chưa có browser challenge sau guard này; không dùng report54/54
của source cũ để qualify bản mới. Live Vision vẫn tắt.


## BUG-010 — v4 label regression 3 false acceptances, guard đã sửa

vision-labels-20261030T133824-c26cdf7e.json:87/90; d14 crop nói link nhưng
full frame nói text, code không veto role contradiction. Thêm v4 full role
và full enabled đồng thuận với requested role mới được accept; v2/v3 giữ cũ.
27 tests liên quan đạt, cần native all-label regression sau sửa. Không actions
trước qualification; ưu tiên zero false acceptance, không che bằng positive hit.


## Wikipedia positive native đạt một lượt sau sửa BUG-009

proposal-42b96742101d.json + model-diagnostic-7e7833181ad3.json: đúng target,
local textbox/enabled, full one, 4248.552ms. Không click/freshness. Đã có bằng
chứng desktop nhưng chưa độ ổn định; giữ các failed observations. Source đã
đổi sau snapshot: cần all labels/browser regression trước actions; không thêm
site hoặc chỉnh prompt tiếp trước khi đo. Web manifest held_out chưa dùng.


## Web observation Python: positive và negative đúng trên cùng scene

proposal-415feb222c63.json Quick search correct_target, locate8624.325ms,
actions0. Search trước đó correct_rejection. Hai observations trên một PNG,
không hai scene độc lập, chưa đủ kết luận quality. Tiếp theo wo_d05_mdn_elements
capture/annotation trước inference để thêm domain dev, giữ cấu hình v4.


## Public-web ca đầu: đúng negative trên Python docs

capture-50b2d6a274a3 / proposal-9ccd323d3ff2.json: Search -> not_found,
correct_rejection theo oracle đã khóa, 719.567 ms, không actions. Chưa có
positive/held_out hoặc đủ scene/domain để kết luận generalization. Tiếp theo
positive Quick search riêng (không sửa ca Search cũ) và thêm domain dev.


## Task A/B web observation — manifest đã nối, chờ capture đầu

Task B 24 provisional/0 confirmed; đã review protocol. Task A --manifest-case
đọc đúng contract và lưu manifest checksum; annotation có reviewer/evidence
source. 12 tests manifest + observation đạt. Không inference held_out, không
thay manifest kỳ vọng. LIMIT-002 ghi chưa có oracle ảnh/public web score.
Bước desktop: capture wo_d01_python_search, xem original trước khi khóa.
Aggregator toàn protocol còn cần tích hợp sau khi có annotation thực tế.


## Task A public-web observation tool đã triển khai — chờ desktop

benchmarks.web_observation.runner có capture/annotate/evaluate và viewer ảnh
nhúng offline, kéo chuột đo bbox. Annotation human-lock trước proposal, checksum
ảnh/metadata, expected tách khỏi grounder. Capture từ Task B --manifest-case
khi module sẵn hoặc URL/target/role thủ công. Không click/gõ/scroll, không live
Vision. 7 fake tests đạt, toàn suite 511 tests đạt; agent thử public capture bị BrowserSession blocked,
không có quality score. Docs/WEB_OBSERVATION_TOOL.md hướng dẫn desktop. Chờ
Task B manifest/protocol và capture + annotation đầu tiên để tích hợp chấm.


## V4 snapshot — labels 90/90 và browser challenge 54/54

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


## Padding96 — hai nhãn diagnostic found, chờ chốt regression

Read policy và Terms apply. cùng đọc đúng qua đủ guard, mỗi cảnh một lần.
Không sửa thêm source trước đo: all labels x3 rồi browser challenge x3.
Live Vision tắt; BUG-008 chưa đóng toàn bộ.


## V4 browser regression 15/15 — chốt lượt đầu

Report browser-vision-20261030T120725-10172435.json đã đối chiếu: 6/6 clicks,
0 wrong/unexpected mouse, 3/3 guards. BUG-007 giải quyết trong lượt này.
Tiếp theo labels all x3 sau reuse evidence và browser challenge x3. Live
Vision vẫn tắt; chưa đánh giá public web.


## V4 browser 10/15 — BUG-007, chờ đo lại

Một found bị freshness guard chặn; bốn negative chưa đạt oracle do diagnostics
hoặc availability unknown. Giữ scorer/TTL. Sửa semantic rejection stage khi có
bằng chứng; unknown disabled có full-frame refusal-only check. Tái dùng local
evidence trong cùng locate để bớt một model call; không cache qua frame/task.
Browser runner đo grounding/frame age. Chưa có desktop result sau thay đổi.
Live Vision tắt, labels 90/90 là cấu hình trước tối ưu, cần regression lại.


## V4 labels 90/90 — tiếp theo browser qualification

Đối chiếu vision-labels-20261030T114325-ad0d5227.json: 30 scene x3,
positives 66/66, negative false acceptance 0/24, đúng ambiguity 6/6,
errors/wrong target/false abstention 0. Median locate 6199.8455 ms.
BUG-005/006 giải quyết trong bộ nhãn đã đo, sau sửa là regression.
Browser runner thêm opt-in ocr-verified-v4; tiếp theo regression một lượt
để kiểm tra real click và freshness trước khi tăng repetitions. Không
nới controller budgets, không bật live Vision. Website thật chưa đo.


## V4 tight label crop — h02 diagnostic found

label-model-bb4abb497dcf.json xác nhận h02 một lượt đọc đúng Terms apply.,
full/local guards đều đạt. Chưa có all-label regression sau crop; cần chạy
all 30 scene x3. Không click, chưa qualify browser v4/freshness/latency.


## V4 all labels regression 87/90 — còn h02

Report vision-labels-20261030T111236-ffcc0ebb.json: positive 63/66,
false acceptance 0/24, wrong target/errors 0, ambiguity đúng 6/6. h02 Terms
apply. not_found 3/3 ở label_read_rejected, cần raw synthetic model diagnostic
để phân biệt label mismatch và wrong role. Median locate 5985.438 ms; chưa
qualify v4 browser controller/freshness. Không bật live Vision.


## V4 candidate hypotheses — chờ desktop

BUG-005 raw OCR đã xác nhận profile tradeoff: native giữ dấu tiết, upscale
đọc đủ chữ Wait nhưng thiếu dấu chấm. Thêm OCRLabelGrounder v4 opt-in, dual
OCR spatial merge, blind label read cho mọi hypothesis rồi exact label/role/
state guards. Full-page count prompt v4 yêu cầu exact punctuation. V3 giữ
nguyên; chưa có quality score v4. Chạy dev regression trước, rồi bốn case lỗi.
Không bật live Vision; latency và sai nhãn model vẫn cần đo.


## Vision labels held_out 34/45 — đang điều tra BUG-005

Report vision-labels-20261030T102214-c5934826.json: positives 25/36,
11 false abstentions, 0 false acceptances/wrong target/errors. Bốn case h09,
h10, h11, h12. Chưa đủ diagnostics để phân biệt OCR và semantic; thêm stage/
count/role vào runner, không raw text, chưa thay thuật toán/scorer. Held_out
đã quan sát, chạy lại là regression. Live Vision giữ tắt.


## Vision labels dev đạt 45/45 — 30/10/2026

Đối chiếu vision-labels-20261030T100403-03db5b5c.json: v3, upscale2x-v2,
512 tokens, dev 15 scene x3; 45/45, positives 30/30, false acceptances 0,
wrong abstentions/errors 0. d14 not_found đúng 3/3; BUG-004 cập nhật đã giải
quyết trong phạm vi đã đo. Giữ manifest và scorer. Tiếp theo held_out x3;
chưa có kết quả held_out. Không click trong benchmark nhãn, live Vision tắt.


## Vision labels dev 42/45 — sửa loại từ chối — 30/10/2026

Report vision-labels-20261030T100031-0695b7f3.json: 30/30 positives đúng,
0 false acceptance, 0 provider error. Ba wrong abstentions đều d14: heading
và prose Open guide bị coi ambiguous dù không có link. Không đổi scorer.
V3 nay chỉ refine refusal trên 2–4 exact OCR duplicates: phân loại crop độc
lập từng nhãn; chỉ khi tất cả là text mới trả not_found. Có control/unknown
vẫn ambiguous; tuyệt đối không chọn một candidate để click. Near duplicates
vẫn ambiguous. Chưa đo model desktop sau sửa, held_out chưa chạy.


## Task B nhãn độc lập — tích hợp kiểm tra — 30/10/2026

Đã review contract/scorer và chạy lại 7/7 fake tests. Manifest 30 scene,
15 dev/15 held_out. Scorer không nhận error là correct rejection; grounder chỉ
nhận frame/target/role, DOM truth chỉ phục vụ oracle. Agent thử --check-cases
bị browser prerequisite exit2, không có quality score mới. Desktop Task B báo
render geometry 30/30; chưa có inference model. Bước tiếp theo: desktop đo dev
v3 x3, giữ held_out chưa đo để đánh giá sau. Gần-trùng exact/near trên v3 hiện
có thể abstain bảo thủ; benchmark phải giữ kỳ vọng đúng để đo false abstention.


## V3 desktop regression đạt 45/45 — 30/10/2026

Đã đối chiếu browser-vision-20261030T095129-d86136af.json: ocr-verified-v3,
upscale2x-v2, 15 scene x3. 45/45 đạt, 18/18 positive verified, 0 false
abstentions, 0 unexpected mouse attempts, 0 wrong clicks, 9 guard passes.
Cộng challenge v3 đã đo: 99/99 observations trên 33 scene lặp ba lần,
45 verified target clicks và 18 guard passes. Không phải 99 scene độc lập.
Task B nhãn/dấu câu độc lập chưa có kết quả; live Vision vẫn tắt.
Các false refusals trên bộ ảnh static cũ chưa được đo lại/giải quyết.


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


## Recovery dấu câu v3 — thử nghiệm

Thêm OCRPunctuationGrounder opt-in ocr-verified-v3. Chỉ xét OCR thêm một dấu
câu cuối; exact và near duplicate cùng gây abstain. Near candidate phải qua
đọc crop độc lập không nhận target/OCR spelling, khớp exact mới tiếp tục toàn bộ
guard v2. Không bật live vision. Replay ảnh lỗi với bbox chẩn đoán ước lượng
và OCR text desktop đã xác nhận vẫn bị label_read_rejected; chưa chứng minh
sửa được ca Read policy. Cần đánh giá desktop; không tăng điểm benchmark cũ.
Task B độc lập: Docs/VISION_PUNCTUATION_TASK_B.md.


## Challenge desktop 51/54 — OCR miss — 30/10/2026

Đã đối chiếu report browser-vision-20261030T022714-84c6cccc.json: 51/54,
24/27 positive thành công, 3 false abstentions, 0 wrong/unexpected mouse,
9/9 guard. Cả ba lỗi challenge_link_top có exact_match_count=0,
decision_stage=ocr_no_exact_match: chưa gọi model. PNG hiển thị Read policy
đầy đủ. Chưa biết chuỗi OCR thực tế; không nới exact matching hoặc sửa prompt.
Thêm benchmarks.browser_vision.ocr_diagnose để so native/upscale trên PNG lỗi
synthetic lưu sẵn; không click, không model. OCR agent vẫn OCR_FAILED nên cần
desktop chạy diagnostic. Challenge nay đã quan sát, lần sau là regression.

## Challenge 18 scene — cấu hình trước đo — 30/10/2026

Thêm suite challenge nhãn/layout mới (9 positive, 6 negative, 3 guard), không
chỉnh v2. Snapshot source trước inference và số liệu false abstention/coverage.
Spec và test đạt; browser agent preflight lỗi, chưa có điểm mới. Chạy command
trong BROWSER_VISION_QUALIFICATION.md để đo 54 lượt. Cùng renderer nên chưa
chứng minh website thật; 8/18 false refusals replay cũ vẫn còn ghi nhận.

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

## Semantic v2 — chưa đạt toàn bộ — 30/10/2026

V1 browser 32/45, 13 click sai. Thêm ocr-verified-v2: full-page count và crop
phân loại role/state độc lập với role yêu cầu. Replay 13/13 ca sai được chặn,
nhưng 8/18 ca dương cũ bị từ chối, tổng 23/31 replay; chưa phải end-to-end.
463 test đạt. Cần desktop chạy browser runner với --grounder ocr-verified-v2;
v1 vẫn default để tái lập. Không bật Vision web thật hoặc nới scorer.

## Task A/B qualification song song — 30/10/2026

Task B do AI phụ làm xong và nhánh chính chạy lại: AIMS offline 48/48, 0 policy
violations, 14/14 no-eligible đúng, không sửa selector. Xem AIMS_BENCHMARKS.md.
Task A: 15 browser scene mới và runner; toàn suite 453/453 đạt. Semantic role negatives, disabled,
nhãn trùng/vắng, move/revoke/expired sau grounding. Thêm final screenshot recheck
và recheck age/authority trước click. Unit oracle không đếm OCR miss/model error
là semantic hoặc stale guard pass. Chưa có quality score cho 15 scene vì browser
preflight agent lỗi; cần Terminal desktop. Chi tiết BROWSER_VISION_QUALIFICATION.md.
Vision trong phiên người dùng vẫn tắt; smoke OCR trước đó được user xác nhận PASS.

## Sửa driver Mouse.click — 30/10/2026

Smoke OCR trên Chromium desktop đến bước click rồi WEB_CLICK_UNCERTAIN. Đã xác
định controller truyền timeout=8000 vào Mouse.click trong khi API không nhận
tham số này. Bỏ keyword; Locator.click vẫn dùng timeout hợp lệ. Mock cũ quá
rộng đã bỏ sót lỗi; nay test strict signature, no retry sau lỗi click, cùng
kiểm tra autospec chữ ký Playwright cài trong .venv-browser đều đạt. Chờ desktop
chạy lại browser-check OCR; chưa ghi nhận smoke pass hoặc bật vision web thật.

## OCR research baseline đạt 72/72 — 30/10/2026

Đã đọc báo cáo desktop: dev 30/30, regression 42/42 trên 24 ảnh x3, 0 wrong/error.
Raw OCR xác nhận native-v1 đọc Submit |, upscale2x-v2 đọc Submit; không nới exact
matching. Lưu configs/vision-research-baseline.json có snapshot checksum, không
load vào runtime hoặc bật quyền. Median locate dev/test 581.9/600.2 ms.
Thêm --grounder ocr-candidates-v1 vào browser-check để thử canvas Chromium riêng
vision-only + verifier. Chưa có kết quả thật cho đường click OCR này; Vision
trong phiên người dùng vẫn tắt. Cần challenge độc lập và role negatives tiếp.
Chi tiết VISION_GROUNDING.md.

## OCR dev 27/30 — đang xử lý nhãn nhỏ — 30/10/2026

User chạy native OCR thành công: 27/30 dev, 0 wrong_target/error. button_center
trượt 3/3 với inference_ms=null: OCR không có nhãn exact, chưa gọi model. Chưa có
raw OCR nên không đoán chữ sai. Thêm profile upscale2x-v2 và opt-in diagnostic
native-v1/v2 trên dev để đo hiệu quả; tọa độ vẫn map ảnh gốc, không hardcode hoặc
fuzzy-match Submit. Helper build/guards kiểm thử riêng; chất lượng candidate chờ
Terminal desktop. Lệnh một bước có trong VISION_GROUNDING.md. Vision vẫn tắt.

## Vision cải thiện — chưa đạt quality gate — 30/10/2026

Đã chạy model thật point-v3: 3/10 dev (2 hit, 1 abstain đúng), không chọn thay v2.
Thêm OCR candidate local + model role verification để tách tọa độ và nhãn; chưa
đo được chất lượng vì Apple Vision native recognition lỗi trong agent, dù build
helper đạt. Không nhận lỗi OCR làm not_found. Có một lệnh validate_candidate
kiểm tra OCR, lặp dev 3 lần rồi mới regression nếu dev đạt toàn bộ. Gate fixture
không tự bật Vision; cần challenge mới/negative role và browser thật sau đó.
Chi tiết, kết quả và lệnh desktop: VISION_GROUNDING.md. Không báo Vision đã ổn.

## Vision dev diagnostics — 30/10/2026

Đã đọc hai báo cáo paired do user chạy (v1 3/10, v2 5/10) và xem ảnh đối chiếu.
Bốn ca v2 có mục tiêu nhưng tâm sai đều lệch theo trục y, không cùng offset;
absent_textbox chọn nhầm khi yêu cầu Search nhưng chỉ có Username. Đã thêm
benchmarks.vision.diagnose xuất HTML/JSON/Markdown offline, kiểm tra lại outcome
bằng scorer gốc; không chạy model/click, không đọc split test để chỉnh. Xem
VISION_DEV_DIAGNOSTICS_2026-10-30.md. Vision vẫn tắt trong phiên người dùng.

## Vision candidate v2 — chờ benchmark dev desktop — 30/10/2026

Thêm giao thức xyxy-v2 dùng hai góc chuẩn hóa và danh sách tối đa 8 mục tiêu;
compiler đếm 0/1/nhiều để từ chối vắng/trùng, kiểm tra mọi box, không clamp.
Giữ v1 và shared contracts; không bật adapter vision trong phiên người dùng.
Runner có --compare-protocols, luân phiên thứ tự trên cùng ảnh/model/token budget,
ghi protocol/ngân sách/reason counts, giữ fixture và ngưỡng chấm. Chưa có bằng
chứng tăng điểm: preflight agent trả MODEL_UNAVAILABLE. Chạy dev so sánh 512 token
ở cả hai phương án trước, chưa chỉnh theo split test. Chi tiết VISION_GROUNDING.md.

## Browser lifecycle — 30/10/2026

Trace desktop xác nhận WEB_BROWSER_CLOSED giữa các tác vụ trong cùng phiên,
không phải mất grant. Bản kiểm tra cache cũ còn bỏ sót close event bị chậm khi
CLI chờ input. Đã thêm read-only driver round trip trước khi dùng lại trang,
recreate khi xác nhận đóng trước điều hướng; không retry goto/click bị lỗi.
Backend giả đạt; agent không khởi chạy được Chromium để kiểm chứng bản sửa.
Cần desktop chạy liên tiếp và thử đóng browser giữa hai tác vụ.

## Web desktop và phản hồi TTS — 30/10/2026

Người dùng xác nhận Chromium fixture DOM pass (PNG 1280x800) và mở kết quả
Wikipedia thật thành công, verifier succeeded. Còn cần thêm ca lỗi/hủy trên web.
TTS web trước đó trả SPEECH_NO_SUMMARY vì thiếu bảng câu đọc; đã bổ sung ba
capability web bằng câu cố định và phân biệt thiếu câu đọc với lỗi/busy TTS.
Không đọc URL/query/nội dung trang; không retry thao tác. Chờ nghe lại desktop.

## Task A — Web/DOM/controller vision — đang chờ kiểm chứng desktop

Đã có browser/contracts.py cho B; HTTPS browser context riêng, web.open/search/
open_result có policy/grant/confirmation/verifier, trace allowlist. CLI/GUI/voice
route grammar web; menu web grants. Phiên người dùng chỉ dùng DOM: Task B đo
qwen3.5:4b đạt 5/24 fixture, chưa đủ chất lượng định vị. Không tự bật vision từ
model planner. Controller/AIMS vision giữ cho fixture nghiên cứu, có freshness/
bbox/auth check và không fallback sau uncertain click.
Không sửa file B. Setup Playwright từ agent chưa thành công; code/test giả không
thay thế thực thi thật. Chạy prepare_browser.py trên desktop rồi --browser-check.
Chi tiết và giới hạn: [WEB_BASELINE.md](WEB_BASELINE.md). Alpha1 ZIP giữ nguyên.

## Ưu tiên tiếp theo: Web + Vision + AIMS — kế hoạch 30/10/2026

Người dùng xác nhận bản alpha mở từ Finder và flow chạy ổn trên máy đã setup.
Chuyển trọng tâm sang browser có kiểm chứng và vòng điều khiển vision, tạm dừng
thêm GUI/Calendar. Kế hoạch chi tiết và phạm vi song song:
[WEB_VISION_MILESTONE.md](WEB_VISION_MILESTONE.md).

Task A nhánh chính: shared contract, browser riêng/DOM/driver, web policy/verifier,
tích hợp AIMS/CLI/GUI. Task B nhánh phụ: vision grounder local + fixture/benchmark
ảnh, không click và không sửa core/driver. Chốt contract bằng code trước khi hai
nhánh dùng chung; B có thể làm fixture/preflight trong lúc A chuẩn bị contract.
Đã triển khai code A/B; model vision hiện chưa đạt và browser thật còn chờ kiểm chứng. Không coi
mở URL trực tiếp là vision; phải có PNG → locate thật → thao tác → verifier.

## Bản dùng thử 0.1.0 alpha 1 — 30/10/2026

User xác nhận GUI settings trên desktop ổn. Chốt version Python0.1.0a1, script
package_preview build app và đóng ZIP allowlist runtime source, release notes,
build metadata, SHA256SUMS và checksum archive. App bundle có core nên mở Finder
không cần đường dẫn repo, nhưng vẫn cần Python3.11+, Ollama/model/STT/helper/TTS
đã cài; chưa standalone/offline installer. Không kèm user data/models, không
publish/tag/commit/push. Cần desktop kiểm chứng app được giải nén mở từ Finder.
Xem RELEASE_0.1.0_ALPHA1.md và artifacts/releases/.

## GUI — Cài đặt giọng nói — 30/10/2026

User đã xác nhận hotkey/thu gọn trên desktop ổn. Thêm sheet bánh răng lúc idle:
model local/preset/TTS bật-tắt/tốc độ100–350, lưu và áp dụng live. Settings qua
bridge command có ID, không planner/grant. Backward compatible file voice thiếu
speech_rate ->217. SayBackend nhận rate tùy chọn; CLI --speech-rate. Giữ account,
quyền phiên, confirmation, không tải/infer model trong settings. Sheet ngăn auto
collapse/hotkey hide. Chờ desktop thử lưu/áp dụng và nghe tốc độ mới.

## GUI — Option+Space và thu gọn — 30/10/2026

Đã đăng ký global Option+Space bằng Carbon, menu bar icon để hiện/ẩn/thoát,
thu gọn tự động sau 12s idle trống hoặc nút header. Bấm viên nang mở lại; không
tự thu/grant/approve. Không cho hide/collapse khi active hoặc đang có draft
(draft chỉ chặn collapse; hide do user chủ động vẫn giữ text). Đăng ký hotkey
lỗi báo UI và giữ menu fallback, không tự đổi cài đặt hệ thống. Tách policy Swift
để test không mở window. Native build/codesign đạt; chưa kiểm chứng hotkey và
bố cục thu gọn trên desktop user. Xem GUI_FIRST_VERSION.md.

## GUI — thẻ hội thoại và nút theo ngữ cảnh — 30/10/2026

Sau khi user xác nhận flow GUI v0 ổn: thay log chính bằng thẻ yêu cầu/câu nghe/
tên/câu hỏi/kết quả; log chuyển vào DisclosureGroup. Bridge thêm context/card,
đưa danh sách lựa chọn đúng cho từng bước. Trùng tên có nút riêng theo index,
bước tên không còn lựa chọn 1/2/3, xác nhận giữ nguyên preview và ID/digest.
Phân biệt màu Phê duyệt/Từ chối; cửa sổ resizable. Chưa hotkey hoặc waveform.
Tests bridge bao phủ 2-choice calendar, candidate tên và transcript/name cards;
native đã compile/codesign; cần desktop kiểm tra bố cục mới.

## GUI macOS v0 — 30/10/2026

Thêm SwiftUI/AppKit floating panel, text/mic/stop/review, hỏi lại/chọn trùng tên,
menu quyền theo phiên và thẻ confirmation từ request core thật. GUIVoiceSession
tái dùng VoiceSession, bridge JSONL có ID từng prompt qua pipes riêng của child
Process; không socket/server. ./elvion --gui build và chạy app development,
--build-only chỉ compile/codesign. Không auto thu/grant/approve hoặc retry tác vụ.
Đã compile native thành công và test bridge bằng backend giả; chưa thao tác GUI
hoặc kiểm chứng mic/Automation từ app trên desktop user. Chưa global hotkey,
waveform thật hoặc tự ẩn. Xem [GUI_FIRST_VERSION.md](GUI_FIRST_VERSION.md).

## Kiểm tra tích hợp Task A + B — 30/10/2026

Nhánh chính chạy lại `benchmarks.session.runner` sau thay đổi cấu hình voice:
31/31 scenario đạt; 14/31 task succeeded, các ca hủy/từ chối/lỗi mong đợi được
tách riêng. Toàn suite 378 tests: 377 qua, 1 skip fixture HTTP loopback;
`git diff --check` đạt. Báo cáo lượt kiểm tra:
`artifacts/benchmarks/session/session-20261029T210312-26936fe3.json` và `.md`.
Đây là harness backend giả, không đánh giá STT hoặc độ trễ ứng dụng thật.
Người dùng đã chạy ./elvion --setup thành công, lưu PhoWhisper-small/none/TTS bật,
grants_persisted=false. Task A khởi động thuận tiện và Task B hồi quy phiên đã
tương thích trong workspace hiện tại; chưa commit/push.

## Task A — Khởi động voice thuận tiện — 30/10/2026

Đã thêm launcher `./elvion`, `--setup` lưu preset PhoWhisper/none/TTS bật,
`--config` xem hoặc cập nhật từng lựa chọn. CLI `voice-config` không mở mic/model
hay cấp quyền. `voice` ưu tiên cờ tường minh rồi cấu hình đã lưu rồi mặc định cũ;
thêm --no-speak cho override. File voice-preferences.json riêng, giữ account cũ,
không lưu grants/token/approval. Tái dùng bộ đọc/ghi an toàn PreferencesStore,
giữ schema account v1 và không sửa file Task B benchmark/session.
Chưa ghi cấu hình thật trong thư mục user; chạy ./elvion --setup để áp dụng.
Hướng dẫn: [VOICE_QUICK_START.md](VOICE_QUICK_START.md).

## Task A — Hội thoại và trạng thái TTS đã tích hợp — 30/10/2026

Đã gọi prompt v1 của Task B tại các bước chuẩn bị thu/duyệt/hỏi lại/chờ action
confirmation/hủy/lỗi input. Giữ --speak opt-in, UI chữ luôn có; TTS module cũ
không có speak_prompt vẫn đọc report. Không đưa tên/transcript vào prompt hoặc
trace, không nói khi mic mở. Stop thất bại chặn micro. Grant và xác nhận bàn phím
giữ nguyên, TTS lỗi không chạy lại tác vụ. Cập nhật state idle/preparing/recording/
transcribing/review/clarifying/awaiting_confirmation/executing, callback input
sau mic đóng để hiển thị xử lý đúng lúc. Không sửa file Task B hoặc đổi STT default.
Toàn suite: 362 tests, 361 qua/1 skip HTTP loopback. Chưa nghe prompt mới thật trên
desktop. Hướng dẫn: [VOICE_CLARIFICATION.md](VOICE_CLARIFICATION.md).

## Hỏi lại trước planner — 30/10/2026

Desktop PhoWhisper-small không prompt đạt 12/20 câu, WER6.62%, tên11/16,
median444ms so với Whisper-small+prompt 5/20, WER19.87%, tên7/16, median451ms.
Đã dùng PhoWhisper qua cờ --stt-model/--stt-context none, chưa đổi mặc định CLI.
Người dùng xác nhận các lượt dùng mic MacBook; chưa có đối chứng mic tai nghe.
Câu tự nhiên mới bị bỏ từ/nhầm âm, và có mơ hồ ghi chú/đặt lịch.

Thêm phân tích mẫu câu hỏi lại trong VoiceSession trước planner: thiếu tên, một
số câu lịch sự chưa ghi trường tên, mơ hồ ghi chú/lịch, lệnh `tạo chú` mất `ghi`.
Người dùng chọn loại và cung cấp/chọn tên; :voice đọc lại chỉ tên, vẫn duyệt bằng
bàn phím. Calendar chưa hỗ trợ thì dừng. Grant/policy/action approval/verifier
giữ nguyên. Không gọi model để bịa từ bị mất, chưa phải hội thoại tổng quát.
Hướng dẫn và kiểm thử desktop: [VOICE_CLARIFICATION.md](VOICE_CLARIFICATION.md).

## Chẩn đoán audio / PhoWhisper — 30/10/2026

Bộ desktop-02: small+prompt 1/10, WER30.26%; medium+prompt 1/10, WER25%.
Không prompt cả hai 1/10, WER31.58%. Prompt nhỏ có một ca chép danh sách từ
gợi ý vào transcript. Chưa chọn được cấu hình đạt chất lượng voice mong muốn.
Đã đo read-only 20 clip: median RMS -18.35dBFS, không clip mức tổng quá nhỏ,
1 clip có >=0.1% mẫu gần full scale. Năng lượng tại biên chưa chứng minh mất âm.
Thêm `voice.input.quality`; script `prepare_phowhisper.py` tải checkpoint VinAI
chính thức và chuyển GGML bằng converter upstream, venv riêng, provenance recipe,
không đổi model mặc định. Compare hỗ trợ nhiều corpus và script setup có thể gọi
so sánh trực tiếp sau chuyển đổi. Chưa tải/chuyển/inference PhoWhisper thật do DNS
và giới hạn thực thi từ agent; bước tiếp theo chạy installer ở desktop Terminal.
Chi tiết: [PHOWHISPER_AND_AUDIO_QUALITY.md](PHOWHISPER_AND_AUDIO_QUALITY.md).

## Đánh giá STT và gợi ý câu — 30/10/2026

Cập nhật sau corpus 10 clip: small 4/10, medium 6/10 đúng câu, WER cùng 9.33%;
median 407/979ms. Chưa đổi model mặc định. Gợi ý nhận dấu phẩy tại mốc tên,
xử lý các tiền tố gần đúng tiệm/tiềm theo cùng thuật toán, giữ nguyên hậu tố.
Chấm lại văn bản cũ nếu chọn gợi ý: 5/10 và 7/10, chỉ là hậu xử lý trên tập phát triển.
Compare hỗ trợ `--context both`, tách điểm phần lệnh/tên; record có `--prompt-set fresh`.
Chờ người dùng chạy A/B prompt trên desktop và bộ câu mới; không chạy lại GPU từ
môi trường agent vì lượt trước lỗi khởi tạo Whisper và quyền ghi corpus.

Sau preset mới, clip desktop 4.3s vẫn nhận sai “Thạ ghi chú, tên thử dọng nói.”,
STT 982ms. Chưa khẳng định nguyên nhân giọng vùng miền hay preset cải thiện độ đúng.
Đã thêm module `elvion.voice.input.evaluation`: thu corpus chủ động lưu local sau
opt-in, so sánh nhiều model trên cùng WAV với WER/CER/đúng câu/thời gian/lỗi riêng.
Không planner/execution/download tự động. Hướng dẫn: [VOICE_EVALUATION.md](VOICE_EVALUATION.md).
Voice có gợi ý gần đúng phần tiền tố lệnh tạo/tìm ghi chú; chọn bằng `:suggest`,
Enter giữ câu gốc. Tên/nội dung giữ nguyên, không bỏ lệnh phụ, vẫn policy/grant/
action approval. Heuristic bảo thủ, chưa huấn luyện mạng hay tự học giọng người dùng.
Chờ thu corpus desktop, tải medium chủ động nếu muốn và chạy so sánh thật.

## Voice Task A — 30/10/2026

STT desktop còn sai/lặp trên hai câu ngắn, có một câu mở ứng dụng nhận đúng. Đã thêm
gợi ý từ vựng công cụ qua --stt-context elvion (có thể tắt bằng none), no-temperature-
fallback/suppress-non-speech và dòng clip duration/inference time để chẩn đoán.
Không tự sửa transcript hay loại câu lặp, giữ review/confirmation. 306 tests tổng,
305 qua/1 skip; chờ clip desktop sau điều chỉnh, chưa tuyên bố đã sửa chất lượng STT.

Kiểm chứng desktop mới: engine/model/helper đã qua doctor ready. Thu micro và
Whisper local trả transcript thật, nhưng câu “Mở máy tính” bị nhận thành “Mở máy tên.”
lặp hai lần. Người dùng sửa văn bản thành lệnh đúng; approval, app.open và verifier
đều succeeded. Đây là thành công của luồng review/sửa → thực thi, chưa phải nhận
dạng tiếng Việt chính xác hoặc luồng voice không cần sửa. Chưa có WAV/segment để
khẳng định nguyên nhân sai/lặp; cần thử clip ngắn có kiểm soát và đo STT riêng.

Người dùng đã chạy demo TTS Task B và xác nhận nghe được trên desktop. Đây là
kiểm chứng phát tiếng thực tế; chưa đánh giá đầy đủ độ tự nhiên/phát âm hoặc STT.

Đã có `elvion voice`: Enter bắt đầu/dừng, helper Swift AVAudioRecorder, STT local
whisper.cpp đa ngôn ngữ, review/sửa/hủy transcript trước planner; mọi tác vụ tiếp
tục confirmation bằng bàn phím. Transcript không được xử lý như :grant/:account.
Có doctor, build-helper, STT file độc lập và tùy chọn --speak gọi facade Task B.
Không sửa file Task B. Chưa có whisper-cli/model STT trong môi trường hiện tại;
Apple vi-VN probe supportsOnDeviceRecognition=false. Không tự tải/cài hoặc fallback
cloud. Helper Swift build/probe thật đã chạy, không mở micro; chưa kiểm chứng thu
âm/STT tiếng Việt thật. 29 tests mới Task A qua; workspace 304 ca, 303 qua/1 skip
tại lần kiểm tra. Hướng dẫn setup và thử desktop: VOICE_INPUT.md.

## Mốc mới nhất — 29/10/2026

- Desktop request-guard-v4 đã đạt 80/80 trong một lượt: intent 55/55, reject 25/25,
  không planner_error/invalid_output/unexpected_acceptance; rules 48/80. Diagnostic
  natural_14 cũng đúng 3/3. Đã đọc comparison-20261029T164150-f53552a50883.json.
  Bộ này nay là regression đã dùng để sửa; cần câu mới cho đánh giá độc lập.
  Bước sản phẩm tiếp theo: voice nhấn để nói, hiển thị STT và preview/confirmation
  trước thao tác. Không bật nghe liên tục hoặc xác nhận bằng giọng nói trong prototype.

- Diagnostic natural_14: ba lượt model đều thêm “Tên” trước giá trị. Đã sửa compiler
  request-guard-v4: field label thừa chỉ được giải khi toàn bộ giá trị khớp region tên
  nguồn đã chỉ định rõ; không cắt nhãn mù hoặc bỏ grounding. 5 tests mới, tổng 264
  ca: 263 qua/1 skip. Chờ diagnostic và regression desktop v4; chưa tuyên bố 80/80.

- Desktop request-guard-v3 đạt 79/80; ba regression trước đã qua và từ chối đúng
  25/25. Còn natural_14 lỗi MODEL_UNGROUNDED_TITLE, chưa có raw proposal để chẩn đoán
  biến đổi title. Đã thêm diagnostic một case tổng hợp; chờ kết quả desktop trước
  khi sửa, không nới validator để che lỗi. Tests hiện 259 ca, 258 qua/1 skip.

- Đã sửa request-guard-v3 theo ba regression đã chẩn đoán: kiểm tra chỉ thị scope/
  xác nhận ngoài title phân định; route primary fullmatch cho yêu cầu dùng Calculator
  trong allowlist. Vẫn grant/confirmation/verifier; không đổi schema hoặc đáp án.
  Có 13 tests mới; 255 tests tổng, 254 qua/1 skip. Ba ca gốc có kết quả đúng không
  cần inference; chờ benchmark hồi quy 80 câu v3 trên desktop. Các ca held_out đã
  dùng chẩn đoán nay là regression; cần tập mới cho đánh giá độc lập.

- Desktop xác minh source-guard-v2: dev 40/40 (trước 32/40), held_out 37/40
  (trước 38/40). Gộp hai lượt riêng 77/80, chưa phải một batch 80. Còn một
  unexpected_rejection natural_03 và hai unexpected_acceptance unsupported_08,
  bypass_01; không planner_error/invalid_output. Không sửa prompt theo nội dung
  held_out. Ghi nhận hồi quy câu tự nhiên; bước sản phẩm kế tiếp là prototype voice
  nhấn để nói, vẫn preview/confirmation toàn bộ thao tác model.

- Đã sửa planner source-guard-v2 trên dev: compiler giữ title nguyên văn cho grammar
  trực tiếp, yêu cầu title tự nhiên phải lấy từ câu nhập, chặn các mẫu thiếu tên trước
  inference và báo NOTE_TITLE_REQUIRED. Bổ sung 12 tests; toàn workspace 242 ca,
  241 qua/1 skip do sandbox. Giữ nguyên dataset/đáp án/held_out; chờ lượt benchmark
  --split dev trên desktop để xác minh số đo mới, chưa tuyên bố cải thiện điểm.

- Đã đối chiếu benchmark Qwen3.5:4b chạy trên desktop: 70/80 (87,5%) so rules 48/80
  (60%); natural 25/25 so 0/25; đúng intent 51/55, từ chối đúng 19/25. Còn 4 ca sai
  arguments/postcondition và 6 ca nhận thành intent dù cần từ chối; không có planner
  error/invalid output. Median 585 ms, p95 756 ms (80 mẫu, gồm preflight/inference).
  Không thực thi ứng dụng trong benchmark. Chi tiết MODEL_PLANNER_RESULTS_2026-10-29.md.
  Ưu tiên bảo toàn tiêu đề và xử lý thiếu thông tin trên dev trước khi mở rộng voice;
  không chỉnh prompt dựa trên nội dung held_out.

- Đã nhận kết quả desktop Qwen3.5:4b: lệnh plan tạo ActionIntent đúng; session model
  tạo và tìm Notes bằng diễn đạt tự nhiên đều succeeded sau confirmation và verifier,
  mỗi tác vụ có trace riêng. Tổng thời gian khoảng 4,96s và 9,64s, gồm chờ xác nhận.
- Đã nối evaluator Task B bằng scripts/benchmark_model.py: so model và rules cùng
  80 câu, tiến độ từng case, báo cáo JSON/Markdown riêng và comparison theo category/split.
  Không sửa dataset/đáp án, không thực thi ứng dụng. Inference của agent bị sandbox
  chặn loopback (PermissionError errno 1); preflight dừng và không tạo báo cáo model giả.
  Chờ chạy trên Terminal desktop bằng lệnh trong MODEL_PLANNER.md.

- Vòng planner — Task A: đã có ModelPlanner, provider Ollama loopback, preflight model
  local, lệnh plan không thực thi và session --planner model. Mọi kế hoạch model cần
  confirmation; tài khoản/ID/hậu điều kiện do chương trình gắn. Lỗi inference/schema
  kết thúc trước thực thi, không retry/fallback; rules vẫn là mặc định. Xem MODEL_PLANNER.md.
  Tests dùng fake provider/backend; chưa cài/chọn model hoặc đo inference thật trên máy đích.
  Kiểm tra toàn workspace lúc bàn giao: 224 tests, 223 qua, 1 HTTP fixture skip vì sandbox
  cấm mở cổng; benchmark thực thi 15/15. CLI subprocess đã xác minh lỗi model không
  khả dụng dừng trước thực thi và vẫn có trace hoàn chỉnh.
  Task B planner đánh giá độc lập trong benchmarks/planner/; không sửa các file của nhánh đó.
- Người dùng đã xác minh desktop: preview tiếng Việt, từ chối tạo, tìm đúng tiêu đề,
  chọn một trong hai ghi chú trùng tên và hủy lựa chọn bằng Enter đều hoạt động đúng.

- Task A hoàn thành: session CLI, cấu hình Notes, grant theo phiên, history/trace/JSON.
  Người dùng đã xác minh tạo → tìm ghi chú thật trong phiên, có xác nhận và verifier;
  mỗi tác vụ có trace riêng. Máy sử dụng tài khoản “Trên máy Mac”.
- Task B hoàn thành: 15 kịch bản giả lập, runner và báo cáo JSON/Markdown. Lần chạy
  sau cải thiện CLI vẫn đạt 15/15; đây là kiểm tra hành vi giả lập, không đo macOS thật.
- Báo cáo nhánh kiểm chứng: thiếu grant và từ chối confirmation chặn trước thực thi;
  Calculator đã chạy được verify succeeded, trace đọc lại hoàn chỉnh và lọc thông tin.
  Tìm tài khoản giả trả TARGET_NOT_FOUND; “On My Mac” trả ACCOUNT_NOT_FOUND.
  Sandbox mở Calculator có thể trả uncertain/-10827 dù app sau đó đang chạy; không retry.
- Đã triển khai xác nhận tiếng Việt và lựa chọn ghi chú trùng tên trong session:
  danh sách metadata có giới hạn, chọn/hủy, verifier đọc lại đúng ID; không đổi policy,
  TaskRequest/TaskReport hay trace schema v1. Toàn bộ 187/187 tests qua sau sửa bộ lọc tiêu đề.
- Người dùng đã xác minh preview tiếng Việt và từ chối `n` trả cancelled trên desktop.
  Lần tìm “ôn ai” sau đó failed trước khi có danh sách; chưa có evidence reason để
  khẳng định nguyên nhân desktop. Đã sửa một lỗi phù hợp triệu chứng: JXA `whose(name)`
  có thể trả cả biến thể hoa/thường, nhưng decoder yêu cầu title khớp chính xác.
  Script nay lọc title bằng so sánh chính xác trước đếm/lập danh sách; 4 tests thực thi
  script với Notes giả lập qua Node đều qua. Cần chạy lại trên desktop; lần đọc riêng
  trong agent vẫn bị Automation -2700. Không sửa/xóa ghi chú của người dùng.
- Cần thử desktop phần UI mới và lựa chọn trùng tên. Còn hai ca native chưa xác minh:
  Calculator cold launch ngoài sandbox; tìm tiêu đề không tồn tại trong tài khoản có thật.
- Bước phát triển sau khi kiểm chứng CLI: planner dùng model pretrained, tiếp tục dùng
  policy/AIMS/verifier hiện có. Chưa chọn model, chưa tích hợp hay huấn luyện selector.

## Mốc trước session CLI (lịch sử)

Trạng thái tại 29/10/2026: đã chạy luồng CLI tạo ghi chú giả lập xuyên suốt và 131 kiểm thử unittest thành công. Có hợp đồng dữ liệu, planner quy tắc, policy cấp quyền theo tác vụ, xác nhận CLI dùng một lần, Protocol/registry adapter, AIMS chọn giữa ba adapter giả và verifier dùng observation chuẩn. Đã có native `app.open` cho Calculator. Người dùng xác nhận ngày 29/10/2026 đã chạy thành công và thấy Calculator mở trên desktop. Đây là kết quả người dùng báo, chưa có JSON/trace desktop để đối chiếu verifier. Lần thử riêng trong môi trường agent trước đó trả -10827/uncertain. Đã thêm spike Apple Notes tạo/tìm đúng tiêu đề trong tài khoản chỉ định / ELVION, luôn xác nhận khi tạo; thử đọc trong agent trả -2700. Sau đó người dùng cung cấp JSON desktop xác nhận note.create succeeded, simulated=false, postcondition_verified=true; note.find cũng succeeded, postcondition_verified=true và trả cùng ID với lần tạo. Thiếu grant/từ chối app.open đã qua subprocess check; already-running vẫn skip trong agent. Đã có trace JSONL local theo task, allowlist privacy v1 và CLI list/show; 30 kiểm thử trace/storage qua. Chưa có model hoặc SQLite; người dùng đã cung cấp traces show desktop cho demo: 7 records hợp lệ, finalized=true, không malformed/partial tail. Chưa có trace persistence riêng cho tác vụ native trong lần xác minh này. `origin` trỏ tới `https://github.com/Anhtuann1404/_ELVION_.git`; chưa kiểm tra lại kết nối mạng hoặc commit/push trong lần triển khai này.

Đã chốt: Python core, Swift helper nhỏ, SQLite + Keychain; nhập/xuất CLI trước. Hai tác vụ demo thực tế đầu tiên là mở ứng dụng và tạo/tìm ghi chú. Tự xây lõi và AIMS baseline, ưu tiên nghiên cứu AIMS sau khi có dữ liệu; dùng model pretrained giai đoạn đầu. Local mặc định, cloud chỉ bật cho từng tác vụ được cho phép. Chưa chọn model/nhà cung cấp; chưa tích hợp cloud trong Sprint 0.

## Sprint 0 — bộ xương chạy được

| Ưu tiên | Việc | Hoàn thành khi |
| --- | --- | --- |
| P0 | Đã tạo khung `src/elvion/`, `native/macos/`, `configs/`, `tests/`, `benchmarks/`, `scripts/`; cập nhật docs và README. | Kiểm tra import và CLI; commit/push là bước riêng, chưa thực hiện. |
| P0 — Đã làm | Định nghĩa sáu hợp đồng chính, enum phương thức/lỗi và token nội bộ. | Validate khi khởi tạo, serialize JSON; chưa có parser JSON đầu vào tổng quát. |
| P0 — Đã làm | CLI `demo "Tạo ghi chú <tiêu đề>"` + fake `note.create`. | Chạy xuyên suốt, trả JSON status/task ID/trace ID; ghi chú giả chỉ trong RAM, trace đã lọc có thể lưu JSONL. |
| P0 — Đã làm trong demo | Policy từ chối mặc định, grant theo lần chạy; `--confirm` hiển thị preview và nhận approval, token gắn action/task/step/thời hạn. | Kiểm tra đồng ý, từ chối, EOF, Ctrl+C, hết hạn, action thay đổi, digest/ID sai, replay. Tác vụ nhạy cảm thật vẫn chưa được hỗ trợ. |
| P0 — Đã làm | Adapter Protocol, registry ID duy nhất, descriptor và observation chuẩn. | Fake adapters cùng giao diện; verifier không import fake cụ thể; probe sai/lỗi hoặc thiếu quyền bị loại. |
| P0 — Đã làm baseline giả | Probe native/API, Accessibility, Vision giả; ưu tiên cố định sau lọc policy. | Ghi candidates/lý do; native không khả dụng thì chọn Accessibility trước thực thi. Chưa thử đường dự phòng sau thực thi lỗi. |
| P1 — Đã triển khai | Trace JSONL từng task, projection allowlist, fsync từng event, CLI list/show và tình trạng log độc lập. | 30 kiểm thử trace/privacy qua; đã ghi/đọc file tạm thật. Không lưu utterance/title/account/note ID/token. Đã nhận JSON traces show desktop của demo: finalized=true, malformed_records=0, partial_tail=false; chưa xác minh persistence riêng cho tác vụ native. |
| P1 — Một phần | Native `app.open`: CLI run, allowlist Calculator, policy/AIMS và AppKit quan sát tiến trình. | 25 kiểm thử mới thành công; người dùng xác nhận Calculator mở trên desktop. Còn kiểm tra riêng app đã chạy/chưa chạy, JSON verifier và quyền trên desktop; Accessibility chưa triển khai. |
| P1 — Happy path đã xác minh | Apple Notes create/find, scope theo tài khoản / ELVION, approval bắt buộc khi tạo, đọc lại ID để verify. | 28 kiểm thử Notes qua; JXA parse/stdin smoke check qua. Create đã được xác minh qua JSON desktop: có approval, verify và succeeded, simulated=false. Find desktop cũng succeeded và trả cùng ID với lần tạo; lần đọc riêng trong agent trả -2700. |
| P1 — Đã làm | Benchmark 15 ca giả lập. | Runner và báo cáo JSON/Markdown; 15/15 đạt kỳ vọng. Xem BENCHMARKS.md. |

## Tiếp theo

0. Đã có xác nhận, Protocol/registry và native app.open. Đọc `MACOS_APP_OPEN.md`; đã nhận xác nhận từ người dùng rằng Calculator mở thành công. Cần đối chiếu JSON verifier và các ca còn lại trước khi hoàn tất toàn bộ spike. Trace bền vững và privacy allowlist đã triển khai; xem TRACE_STORAGE.md. Retention và dataset labeling còn để sau.
1. Chạy `scripts/check_app_open.py` trong Terminal desktop khi Calculator mở. Happy path create/find Notes đã được xác minh bằng JSON desktop; trace demo đã lưu/đọc thành công trên desktop; tiếp theo kiểm tra các ca lỗi Notes và trace của tác vụ native; bổ sung Accessibility sau khi có tác vụ cụ thể.
2. Đưa browser DOM vào adapter khi có use case tìm kiếm/web cụ thể.
3. Tích hợp push-to-talk và thử STT/TTS tiếng Việt trên máy 16 GB.
4. Chỉ sau khi baseline có số đo, thử selector học máy và so trên cùng tập đánh giá.

## Definition of done cho mỗi tác vụ

Có demo lặp lại được; quyền và trường hợp từ chối rõ; hành động rủi ro có preview/xác nhận; verifier kiểm tra hậu điều kiện; log giải thích đường AIMS đã chọn; có ca lỗi và kết quả `uncertain` khi thích hợp.
