# Task A: browser riêng, DOM, controller vision và AIMS

## Trạng thái

Đã tạo shared contracts và đường web trong CLI/voice/GUI. Browser Chromium
fixture DOM và CLI web thật đã chạy trong `.venv-browser`: mở trang công
khai, tìm DuckDuckGo, mở kết quả Wikipedia bằng DOM, verifier đạt. Lệnh
`:web-read` trong CLI đọc đoạn trích trang đang mở; reader đã kiểm chứng
native trên Wikipedia và Python Tutorial. `:web-summary` dùng model Ollama
local để chọn tối đa ba trích dẫn nguyên văn; CLI chỉ hiển thị trích dẫn
khớp đúng paragraph nguồn. Đây là các ca DOM cụ thể, chưa chứng minh mọi site
hoặc Vision live. GUI đã build với các grant web mới; bản ZIP alpha1 cũ
chưa phát hành lại.

## Cài từ Terminal desktop

Trong thư mục ELVION:

```sh
python3 scripts/prepare_browser.py
```

Lệnh chủ động tạo `.venv-browser`, cài Playwright và Chromium. Không dùng Python
global, không đụng venv của PhoWhisper. Chỉ khi toàn bộ cài đặt thành công mới ghi
marker `browser-ready`; launcher ./elvion chọn interpreter mới khi có marker.
Đã có venv nhưng pip fail thì vẫn giữ interpreter cũ cho các tính năng alpha.
Không yêu cầu cài lại model/STT. Setup lỗi thì gửi output; không dùng sudo pip.

## Kiểm chứng fixture thật trước

```sh
./elvion --browser-check
```

Mở Chromium context riêng, HTML tổng hợp trong bộ nhớ, click nút bằng DOM,
đọc trạng thái dataset sau click và chụp PNG. Không public network, không profile
cá nhân, không model. Đây là test có hành động thật trong browser fixture opt-in.

Chỉ để nghiên cứu trên fixture tổng hợp: thay MODEL bằng model local đã kiểm tra.
Model qwen3.5:4b hiện chưa đạt chất lượng để click trên web thật:

```sh
./elvion --browser-check --mode vision --vision-model MODEL
./elvion --browser-check --mode auto --vision-model MODEL
```

Hai chế độ dùng nút canvas không có DOM locator. Target là chữ hiển thị trong
ảnh; tọa độ chuẩn chỉ nằm trong HTML fixture/verifier, không truyền grounder.
Driver dùng box model trả, kiểm tra frame/page/revision/age<=10s rồi click tâm,
verifier đọc dataset độc lập. Suy luận chậm quá ngân sách thì dừng; không cập nhật
timestamp để giả frame mới. Preflight/check này không tự tải model.

## Dùng web live

Mở `./elvion` hoặc `./elvion --gui` từ repository sau setup. Đừng dùng app alpha1
đã giải nén để thử code mới. Cấp từng quyền ở voice> hoặc menu khiên GUI:

```text
:grant web.open web.search web.open_result
Mở web https://example.com
Tìm trên web thuật toán A*
Mở kết quả 1
```

Trong phiên CLI `python -m elvion session`, sau khi mở trang:

```text
:web-read
:web-summary
```

`:web-summary` cần model local: khởi động phiên bằng
`PYTHONPATH=src:. .venv-browser/bin/python -m elvion session --planner model --model qwen3.5:4b --grant web.open --confirm`
(hoặc dùng `--conversation-model`). Model chỉ chọn trong 30 đoạn đầu,
tối đa 7.000 ký tự nội dung đã trích xuất. Mỗi trích dẫn phải khớp nguyên
văn với đúng đoạn trước khi hiển thị; nguồn trả URL và số đoạn. Đây là
điểm chính kiểu trích xuất, không phải diễn giải độc lập hoặc xác minh
mọi phát biểu ngữ nghĩa của model. Nội dung trang không được dùng làm
chỉ dẫn thao tác.

Bản chọn ID: phần mềm cắt sẵn các span nguyên văn, model chỉ chọn tối đa
ba ID, phần mềm lấy quote trực tiếp từ nguồn. Có thể lấy nhiều span khác
nhau trong cùng paragraph; nguồn không có nội dung phù hợp trả về thông
báo cố định. Bộ đo và giới hạn ở `Docs/WEB_SUMMARY_CHECKS.md`.

Mỗi bước cần xác nhận riêng. Query được gửi DuckDuckGo; title/URL kết quả hiển
thị tạm, không lưu raw vào trace. Dùng đúng grammar trên; chưa mở rộng model
planner sang mọi cách diễn đạt tự nhiên. Prefix web được route trước planner
text hiện có; không ảnh hưởng luồng Notes.

Open là điều hướng trực tiếp; search là URL query + đọc DOM kết quả. Không gọi
hai thao tác đó là vision. Open_result dùng DOM click link trên trang search;
CLI/voice/GUI hiện chỉ đăng ký adapter DOM, không tự gắn model planner làm
vision grounder. Nếu DOM không có locator phù hợp thì dừng. Đường controller/AIMS
vision còn được giữ cho test và fixture nghiên cứu có chủ động chỉ định model.
Capability vision trong metadata chỉ xác nhận nhận ảnh, không chứng minh định vị đúng.

Verifier đọc lại URL/title/ready; search thêm query đúng và kết quả visible.
Open_result đòi URL cuối khớp URL đã duyệt; chuyển hướng sang host khác bị chặn,
canonical redirect khác path có thể không được xác nhận. Captcha/login/cookie wall/
provider thay CSS có thể khiến search không được kiểm chứng. Không retry hành động
uncertain hoặc chuyển phương thức sau một click chưa biết tác dụng.

## Giới hạn driver

Một context/profile Chromium riêng, không extension/profile cá nhân. HTTPS public,
không credentials/port tùy ý/private IP; route GET/HEAD theo host đã duyệt, kiểm tra
DNS public cho mỗi request; websockets bị chặn, service worker và download tắt.
Đây không phải sandbox mạng/SSRF hoàn chỉnh cho website đối nghịch: DNS rebind,
browser networking ngoài route và nội dung động cần hardening trước khi dùng
ngoài phạm vi nghiên cứu kiểm soát. Không đăng nhập hoặc thao tác dữ liệu tài khoản.

Controller UI giới hạn 8 bước/60s, từng action có timeout. Tuổi screenshot tính từ
trước capture; navigation/scroll do controller/resize phải invalidate revision.
V1 hiện chỉ expose click; chưa expose scroll/resize/type tùy ý. Animation tự thay
đổi không được bảo đảm phát hiện hết; chưa coi revision là chứng minh pixel bất biến.
Vision-only không đọc locator DOM để định vị; verifier có thể dùng DOM độc lập.

Contract PNG kiểm tra header/kích thước/giới hạn; grounder B kiểm tra full PNG.
GroundingResult chỉ tọa độ CSS px và status/reason cố định, không chứa code/action.
B không được self-authorize, driver kiểm tra callback authorization trước capture
và ngay trước click. Không ảnh/model response/URL/query raw trong trace mặc định.

## Kiểm thử

`tests/test_browser_workflow.py`: search/open result đúng postcondition, thiếu
grant, decline, wrong URL, uncertain không retry, URL bị cấm, result hết hạn,
freshness/box/authorization, DOM priority/no fallback, vision-only không đọc DOM,
privacy trace và registry chọn vision khi DOM không khả thi. Tất cả dùng backend
giả. Script check_browser mới là phép thử Chromium/model thật opt-in.

Task B đã đo model thật qwen3.5:4b: dev 3/10, test 2/14; chỉ 2 target hit,
3 từ chối đúng, 10 chọn sai và 9 box vượt biên bị chặn. Giữ nguyên guard; chưa
cho phép vision tự click trong phiên người dùng. Chưa hoàn thành benchmark
12 fixture live toàn vòng. Cần cài browser, chạy DOM fixture và public web smoke;
vision cần cải thiện và đánh giá riêng trước khi chốt milestone Web+Vision.

## Chẩn đoán phiên browser

Trace desktop 1859f17d-96e5-4956-8a04-3601905ce242 dừng trong execute
sau khoảng 3 ms; trace cũ không giữ reason nên chưa xác định nguyên nhân.
Đã thêm mã reason cố định cho lỗi driver/navigation/đóng browser, không lưu
exception text. Khi cửa sổ cũ đã đóng hoặc browser mất kết nối trước yêu cầu
điều hướng mới được xác nhận, start giải phóng đối tượng cũ và tạo context mới.
Nếu lỗi xảy ra sau khi dispatch goto/click thì vẫn uncertain, không tự retry.
Kiểm thử vòng đời bằng backend giả đã đạt; cần desktop thử đóng/mở lại browser.

Trace desktop mới 8fbd95b7-817b-47b4-9186-99d1670854c4 và
9ddc8ca9-b68d-4e2a-b10a-748dfca57cbf xác nhận WEB_BROWSER_CLOSED.
Playwright sync is_closed/is_connected là trạng thái cache; trong lúc CLI chờ
input, sự kiện đóng có thể chưa được xử lý. start nay đọc page.title qua driver
để xử lý sự kiện trước khi quyết định dùng lại trang. Chỉ tạo context mới khi
đã xác nhận trang đóng hoặc mất kết nối; lỗi đọc khác dừng bằng mã cố định.
Test hồi quy mô phỏng close event bị chậm, tái sử dụng trang sống và lỗi đọc.
Thử tái hiện Chromium headless riêng từ môi trường agent không khởi chạy được
(WEB_BROWSER_UNAVAILABLE); chưa tính là kiểm chứng browser thật cho bản sửa này.

## Driver coordinate-click fix — 30/10/2026

Desktop smoke OCR trả WEB_CLICK_UNCERTAIN ở controller.click_vision. Đối chiếu
chữ ký Playwright đã cài xác nhận Mouse.click(x,y,button,click_count,delay) không
nhận timeout; controller từng truyền timeout=8000 như Locator.click nên TypeError
xảy ra trước dispatch. Đã bỏ keyword đó. Locator click vẫn có timeout 8s; timeout
này không áp dụng cho Mouse.click. Budget/freshness vẫn kiểm tra trước hành động,
chưa là hard deadline cho transport Mouse. Không giả vờ timeout keyword có hiệu
lực. Mọi exception sau call vẫn uncertain và không retry.

Test freshness/auth dùng callback mouse có chữ ký chặt, và có ca transport lỗi
chỉ gọi click một lần. Đã kiểm tra thêm với create_autospec(Mouse) của Playwright
thật, không mở browser hoặc click thật trong phép kiểm tra chữ ký này. Chờ chạy
lại smoke desktop để xác nhận đường OCR -> tọa độ -> click -> verifier.
