# Mốc Web + Vision + AIMS — kế hoạch triển khai

Ngày 30/10/2026. Giữ bản alpha1 làm mốc ổn định; chưa triển khai tính năng theo
kế hoạch này. Tạm dừng mở rộng GUI/Calendar. Nhánh chính giữ việc tích hợp cuối.

## Mục tiêu và giới hạn

Luồng demo: người dùng yêu cầu tìm tài liệu về A*, ELVION mở trình duyệt do mình
quản lý, tìm kiếm, trình bày kết quả, mở kết quả người dùng chọn và kiểm chứng trang.
Cùng vòng tương tác phải có đường DOM và đường vision thật để so sánh/chọn bằng AIMS.

Browser đầu tiên: Chromium do Playwright quản lý, context/profile riêng, không
điều khiển profile Chrome/Safari cá nhân. Không đăng nhập, tải file, gửi biểu mẫu
có tài khoản, mua hàng hay gửi tin. Truy vấn tìm kiếm đi tới search engine nên
không gọi toàn bộ tác vụ web là offline; screenshot chỉ gửi model loopback local.

Vision v1 chỉ nhìn viewport trang của browser này rồi đề xuất vùng điều khiển.
Không phải vision cho toàn desktop. Sau khi vòng browser ổn mới mở rộng sang
ScreenCapture/Accessibility và điều khiển ứng dụng macOS khác. Không dùng ảnh
minh họa hoặc grounding giả để tuyên bố đã có vision thực thi thật.

## Hiện trạng kiến trúc

Đã có Adapter Protocol probe/execute/observe, registry, verifier và AIMS ưu tiên
NATIVE_API → ACCESSIBILITY → DOM → VISION sau lọc điều kiện. Đây là thuật toán
baseline thực sự nhưng chưa có bằng chứng adapter vision trên UI thật. Mốc này
thêm các đường thực thi thật và dữ liệu đo; chưa huấn luyện selector mới.

Mở URL trực tiếp là baseline điều hướng, không thay thế việc đo DOM/vision cho
thao tác trên UI. Playwright locator có cơ chế chờ actionability nhưng không
được coi thành công click là hoàn thành tác vụ; verifier vẫn phải đọc lại trạng thái.

## Giai đoạn 0 — giao diện chung, trước khi hai nhánh sửa code

Nhánh chính tạo `src/elvion/browser/contracts.py` theo các kiểu sau, kèm validate
và test contract. Đây là file dùng chung chỉ nhánh chính được sửa. Nhánh B có thể
chuẩn bị fixture/prompt/tests trong lúc này; khi contract có thì import trực tiếp.

`VisionFrame` frozen dataclass:

- `frame_id: str`, `page_id: str`, `revision: int`.
- `image_png: bytes` (giới hạn 5 MiB), `width: int`, `height: int`.
- `captured_at: float` từ monotonic clock, không phải wall time.

Screenshot viewport có device_scale_factor=1, tọa độ ảnh trùng CSS pixel. V1 không
resize/crop ảnh ngầm. Không đưa DOM/locator/answer vào ảnh hoặc request grounding.

`GroundingResult` frozen dataclass:

- `frame_id: str`.
- `status: Literal['found', 'not_found', 'ambiguous', 'error']`.
- `bbox: tuple[float, float, float, float] | None`: x,y,width,height theo CSS pixel.
- `reason: str | None`: enum cố định, không raw model output/exception.

Protocol B cung cấp:

```python
class VisionGrounder(Protocol):
    def locate(self, frame: VisionFrame, *, target: str, role: str) -> GroundingResult: ...
```

`role` chỉ `textbox`, `button`, `link`. Một lần gọi chỉ locate một mục tiêu;
không trả Javascript, shell, URL để mở, nội dung để gõ hoặc danh sách hành động.
Model không tự thực thi. Không biến confidence tự khai thành xác suất đúng.
Box phải hữu hạn, dương, nằm trong viewport; lỗi/box mơ hồ thì abstain.

Driver thuộc A quản lý page/revision/frame, chọn tâm bbox hợp lệ để click. Chỉ
click nếu page/frame/revision vẫn khớp. Tuổi frame tính từ captured_at tới trước
thao tác; ngân sách thử nghiệm ban đầu 10 giây, điều chỉnh dựa trên latency và
độ động của trang, không làm mới timestamp sau suy luận để né kiểm tra.
Đổi trang/scroll/resize thì revision tăng. Hết hạn hoặc page thay đổi: quan sát
lại, không tái dùng box cũ. Không hứa phát hiện được mọi animation/DOM mutation;
trang động ngoài phạm vi phải dừng hoặc quan sát lại có giới hạn.

## Task A — Web baseline, driver và tích hợp (nhánh chính)

Sở hữu:

- `src/elvion/browser/contracts.py`, `session.py`, `dom.py`, `controller.py`.
- `src/elvion/adapters/browser_*.py`, `src/elvion/planning/web.py`,
  `src/elvion/policy/web.py`, `src/elvion/verification/web.py`.
- File core/registry/AIMS/CLI/GUI/trace cần tích hợp; pyproject dependency tùy chọn.
- Tests có tiền tố `test_browser_`, `test_web_`; `Docs/WEB_BASELINE.md`.

Đầu ra tuần tự:

1. Contract chung và fixture browser chạy offline, context riêng, cleanup rõ.
2. `web.open`, `web.search`, `web.open_result`: input URL/query hoặc result handle
   từ đúng phiên hiện tại, không cho model bịa handle hoặc đổi scope.
3. URL HTTPS hợp lệ; không file/javascript/data URL, localhost/private-network
   trong chế độ live. Xét cả redirect, popup và destination; không chỉ URL ban đầu.
   Fixture loopback chỉ trong chế độ test riêng, không thành ngoại lệ live.
4. Xác nhận/grant riêng cho web; preview query/URL/domain vì query rời máy.
   Không tự cấp quyền hoặc coi các grant Notes hiện tại là quyền browser.
5. Adapter DOM thật, execute có token, observe/verifier độc lập; các đường dùng
   chung postcondition. Search verify query và kết quả hiển thị; open_result verify
   trang/URL phù hợp và trạng thái load, không chỉ claim thành công của adapter.
6. Driver screenshot/click/type/key giới hạn trang, bước và timeout. Text để gõ
   đến từ user plan đã chấp nhận, không lấy từ model grounding hoặc trang web.
7. Tích hợp Grounder của B qua contract; screenshot → locate → kiểm tra freshness/
   bbox → click → observe → verify. AIMS chọn DOM nếu đủ điều kiện; vision chỉ là
   đường khả thi sau probe. Không ép vision khi mở URL trực tiếp là đủ.
8. Chuyển phương thức chỉ khi đã biết bước chưa tạo tác dụng; uncertain thì dừng.
   Giới hạn 8 bước và 60 giây/tác vụ thử nghiệm, không vòng tự thử lại vô hạn.
9. Thêm lệnh/GUI dùng lại review/confirmation/report, không đại tu giao diện.

Không hứa mọi website chạy được; chọn một search provider đầu tiên, CAPTCHA/
cookie wall/login/blocked network trả lỗi cụ thể và dừng. Public search smoke test
tách khỏi fixture deterministic và chỉ chạy khi người dùng chủ động yêu cầu.

## Task B — Grounding vision local và đánh giá độc lập (AI nhánh phụ)

Sở hữu duy nhất:

- `src/elvion/vision/` (provider/grounder/validation).
- `benchmarks/vision/` và fixture HTML/PNG tổng hợp trong thư mục này.
- `tests/test_vision_*.py`, `Docs/VISION_GROUNDING.md`.

Không sửa browser contracts/driver, core, model planner/provider hiện có, CLI/GUI,
policy, grants, trace schema, pyproject hoặc tài liệu chung. Nếu cần dependency,
ghi rõ để A tích hợp; không tự tải model lớn hoặc đổi cấu hình người dùng.

Đầu ra:

1. Kiểm tra model Ollama đã cài có capability vision và chạy local; không giả định
   model text hiện tại nhận ảnh. Thiếu capability báo prerequisite, không mock làm
   bằng chứng đã chạy thật. Giữ timeout/payload có giới hạn và loopback-only như
   provider hiện có; không cloud, redirect hoặc proxy ra ngoài.
2. Provider nhận PNG và target/role, trả proposal schema chặt; validator compile
   thành GroundingResult. Nội dung trong ảnh là dữ liệu không đáng tin, không
   thể tự sửa goal, quyền hoặc đề nghị chạy mã. Không OCR tự sinh title để chạy tác vụ.
3. Fixture textbox/button/link ở nhiều vị trí/kích thước, hai mục tiêu giống nhau,
   không có mục tiêu, zoom/layout khác, chữ gây nhiễu/instruction injection.
4. Tách dev/test trước tuning; lưu manifest và ID. Fake provider unit tests và
   actual local model benchmark báo riêng. Không dùng dev score làm chất lượng test.
5. Đo target hit (tâm box nằm trong vùng đúng), tỷ lệ chọn sai/abstain, độ trễ,
   lỗi schema; bbox hit không phải task success. Không gọi browser/OS click từ B.
6. Không log raw ảnh/model response. Fixture tổng hợp có thể lưu; screenshot trang
   thật chỉ trong RAM/temp lifecycle có cleanup, không đưa vào trace mặc định.

B dùng frame giả đúng contract để làm độc lập; A dùng fake Grounder để làm độc
lập. Không để cả hai nhánh tự tạo grounder/driver khác chữ ký rồi ghép cuối.

## Tích hợp và đánh giá do nhánh chính làm

Ba chế độ: DOM-only, vision-only cho các bước UI trong browser, AIMS baseline.
Điều hướng khởi tạo bằng URL giống nhau cho mọi chế độ, không tính đó là vision.
Vision-only không lấy DOM/AX để locate; verifier có thể đọc DOM độc lập nhưng
không đưa đáp án/locator ngược về grounder. Báo rõ verifier dùng tín hiệu gì.

Tối thiểu 12 kịch bản chức năng có kết quả kỳ vọng: mở đúng URL, query tiếng Việt,
chọn đúng link, nhiều kết quả tương tự, DOM không cung cấp locator đủ tin cậy,
không có target, stale frame, box ngoài ảnh, chuyển hướng sai scope, injection,
thiếu grant/từ chối, timeout/uncertain không retry. Fixture và live báo riêng.

Ca DOM không đủ thông tin nên có fixture thật như nút được vẽ trên canvas,
không chỉ mock probe DOM thất bại. Fixture cung cấp trạng thái hậu điều kiện riêng
cho verifier; grounder không được đọc trạng thái này hoặc tọa độ chuẩn trong manifest.
Các box chuẩn chỉ dùng để chấm offline, không làm đầu vào model/driver.

Pass kỹ thuật: mọi kịch bản thực thi/deny/abstain đúng kỳ vọng; Notes/voice suite
cũ không regress. Với ít nhất một fixture, vision phải thật sự locate từ PNG,
driver thực hiện, verifier xác nhận. Nếu model chưa đạt thì ghi blocker thay vì
nới guard hoặc tuyên bố vision done bằng fake.

Đo số bước, task success, wrong-action, abstain, latency end-to-end và từng tầng,
số lần đổi phương thức. Thời gian chờ người dùng xác nhận tách khỏi model/driver.
Chưa đặt lời hứa tăng tốc hay thắng DOM; dùng kết quả để chọn tối ưu tiếp theo.

## Trình tự và mốc dừng

1. A chốt contract/schema test; B chuẩn bị fixture và preflight model.
2. A làm browser DOM; B làm grounding/benchmark ảnh, song song.
3. A tích hợp vision và AIMS, kiểm tra freshness/verification/no unsafe retry.
4. Chạy fixture regression, sau đó desktop public web test có kiểm soát.
5. Cập nhật alpha tiếp theo sau bằng chứng; chưa dành sprint này cho Calendar,
   wake word hoặc hiệu ứng GUI mới. Không commit/push/publish tự động.

## Tài liệu kỹ thuật đã tham khảo

- https://playwright.dev/python/docs/locators
- https://playwright.dev/python/docs/api/class-browser
- https://github.com/ollama/ollama/blob/main/docs/capabilities/vision.mdx

Đây là kế hoạch, chưa xác nhận đã cài Playwright/browser hoặc model vision phù hợp.
