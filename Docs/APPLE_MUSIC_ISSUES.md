# Nhật ký lỗi và vướng mắc: Apple Music Subsystem (Nhánh `codex/apple-music`)

Nhật ký này theo dõi các vấn đề kỹ thuật, giới hạn hệ điều hành và rào cản xuất hiện trong quá trình phát triển tính năng điều khiển Apple Music trên macOS. File này do nhánh `codex/apple-music` quản lý và sẽ gửi cho nhánh chính tích hợp vào `Docs/BUG_LOG.md`.

---

### AM-ISSUE-001: Giới hạn tìm kiếm danh mục trực tuyến (Apple Music Online Catalog) qua Scripting Dictionary

- **Triệu chứng**: Không thể tìm kiếm các bài hát nằm ngoài thư viện cục bộ/đám mây của người dùng chỉ bằng AppleScript hoặc JXA đơn thuần.
- **Phạm vi/Phiên bản**: macOS 15.x / 14.x, Music.app phiên bản 1.6.5 (bundle `com.apple.Music`).
- **Cách tái hiện hoặc bằng chứng**:
  - Tra cứu cấu trúc `com.apple.Music.sdef` tại `/System/Applications/Music.app/Contents/Resources/com.apple.Music.sdef`:
    Lệnh `search` có `direct-parameter type="playlist"` và quyền truy cập `com.apple.Music.library.read`.
  - Không có đối tượng nào đại diện cho un-added streaming catalog trong sdef.
  - Chạy `osascript -e 'tell application "Music" to search playlist 1 for "..."'` chỉ trả về kết quả trong playlist đã lưu của tài khoản.
- **Tác động**:
  - Người dùng yêu cầu tìm bài hát bất kỳ trên Apple Music chỉ tìm được nếu bài hát đó đã có trong thư viện (`playlist 1` hoặc các playlist khác).
  - Không thể tìm và phát bài hát từ kho trực tuyến 100 triệu bài nếu bài đó chưa được add vào library.
- **Nguyên nhân đã xác minh**:
  - Apple thiết kế AppleScript dictionary của Music.app chỉ cho phép tương tác với Library và Playlists cá nhân.
  - Tìm kiếm kho trực tuyến yêu cầu Web API (Apple MusicKit REST API, cần Developer Team ID, MusicKit Private Key và User Token) hoặc UI automation trên giao diện WebKit của Music.app.
- **Trạng thái**: Đã xác nhận giới hạn (Documented Blocker).
- **Cách xử lý & Giới hạn còn lại**:
  - Triển khai đầy đủ tính năng tìm kiếm và phát trong thư viện người dùng (`music.search` và `music.play`).
  - Đối với bài hát không có trong thư viện, trả về thông báo rõ ràng `TARGET_NOT_FOUND` và thông báo giới hạn hiện tại của hệ thống.
  - Không giả lập tìm catalog online rồi báo là đã điều khiển được ứng dụng thật.

---

### AM-ISSUE-002: Lỗi truy cập hỗ trợ Accessibility (-25211) khi dùng System Events

- **Triệu chứng**: Khi cố gắng điều khiển hoặc quan sát UI của Music.app thông qua System Events (`Application("System Events").processes["Music"]`), lệnh thất bại với mã lỗi `-25211`.
- **Phạm vi/Phiên bản**: macOS Sonoma / Sequoia, môi trường Terminal/Automator/Subprocess chạy `osascript`.
- **Cách tái hiện hoặc bằng chứng**:
  - Chạy: `osascript -e 'tell application "System Events" to get name of first window of process "Music"'`
  - Kết quả: `System Events gặp lỗi: osascript không phải là truy cập hỗ trợ được cho phép. (-25211)`
- **Tác động**: Không thể dùng Accessibility API / GUI Scripting qua `osascript` làm phương tiện điều khiển hay quan sát đáng tin cậy mà không yêu cầu người dùng cấp quyền Accessibility trong System Settings > Privacy & Security > Accessibility.
- **Nguyên nhân đã xác minh**: Cơ chế TCC (Transparency, Consent, and Control) của macOS cô lập quyền Accessibility của các script process chưa được cấp quyền riêng biệt.
- **Trạng thái**: Đã giải quyết bằng giải pháp thay thế (Resolved via direct Apple Events).
- **Cách xử lý**:
  - Không phụ thuộc vào System Events hay Accessibility để quan sát/điều khiển Music.app.
  - Sử dụng giao tiếp trực tiếp Apple Events qua JXA (`Application("com.apple.Music")`), lệnh này trả về exit code 0 bình thường mà không yêu cầu quyền Accessibility.
  - Sử dụng AppKit (`NSRunningApplication`) để kiểm tra trạng thái tiến trình chạy của Music.app.

---

### AM-ISSUE-003: Lỗi mã hóa ký tự và Injection khi nội suy chuỗi vào AppleScript

- **Triệu chứng**: Tên bài hát tiếng Việt có dấu, hoặc chứa dấu ngoặc kép (`"`), dấu nháy đơn (`'`), dấu gạch chéo ngược (`\`) hoặc ký tự điều khiển có thể làm gãy cú pháp câu lệnh AppleScript hoặc gây lỗi bảo mật injection.
- **Phạm vi/Phiên bản**: Mọi phiên bản macOS chạy câu lệnh AppleScript qua chuỗi ghép.
- **Cách tái hiện hoặc bằng chứng**:
  - Tên bài hát như `Don't Stop Believin'` hoặc `Bài "Hit" Mới` khi ghép vào chuỗi `search playlist 1 for "{name}"` sẽ gây lỗi cú pháp: `Syntax Error: Expected end of line, etc. but found identifier.`
- **Tác động**: Ứng dụng crash, tìm kiếm thất bại, hoặc có nguy cơ injection câu lệnh.
- **Nguyên nhân đã xác minh**: Chuỗi tham số được nội suy trực tiếp vào mã thực thi thay vì truyền qua cấu trúc dữ liệu an toàn.
- **Trạng thái**: Đã giải quyết (Resolved).
- **Cách xử lý & Kiểm chứng thực tế**:
  - Sử dụng JXA với cơ chế đọc JSON payload từ `stdin` (`$.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile`), dữ liệu được parse bằng `JSON.parse` chuẩn hóa.
  - Không truyền chuỗi tìm kiếm qua argv hay code interpolation.
  - Đã kiểm chứng thành công với các ký tự đặc biệt tiếng Việt, ngoặc kép, nháy đơn, ký tự giống câu lệnh shell (`rm -rf`, `; tell app ...`).
