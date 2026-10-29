# Tích hợp macOS

Spike đầu tiên app.open được triển khai tại `src/elvion/adapters/macos_apps.py`:

- `/usr/bin/open -a` gửi yêu cầu LaunchServices mở Calculator tại đường dẫn cố định.
- Script JXA cố định trong Python đọc AppKit NSRunningApplication qua `/usr/bin/osascript`.
- Không dùng System Events, gửi Apple Events đến Calculator hoặc GUI scripting trong spike này.

Không cần compiler hay dependency mới. Swift helper/IPC và Keychain vẫn chưa triển khai;
thêm khi tác vụ tiếp theo cần. Chiến lược Python core + native helper giữ nguyên,
backend có thể được thay bằng Swift trong cùng Adapter Protocol.
Xem `Docs/MACOS_APP_OPEN.md` để biết kiểm chứng và hạn chế môi trường hiện tại.
