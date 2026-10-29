# Scripts hỗ trợ

Chỉ thêm script khi có thao tác cần lặp lại: demo, benchmark hoặc chuẩn bị dữ liệu.
Hiện chạy từ thư mục gốc mà không cần cài package:

```sh
PYTHONPATH=src python3 -m elvion --help
PYTHONPATH=src python3 -m elvion --version
```

Kiểm tra desktop app.open (giữ Calculator mở trước khi chạy):

```sh
PYTHONPATH=src python3 scripts/check_app_open.py
```

JSON result pass/incomplete/fail, exit code 0/2/1. Thiếu PID Calculator thì skip ca already_running;
không giả lập hoặc đóng app để ép kết quả. Xem Docs/APPLE_NOTES.md cho cách thử ghi chú thật.
