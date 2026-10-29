# Kiểm thử demo

Chạy từ thư mục gốc, không cần thư viện ngoài:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

`test_demo.py` kiểm tra validate/serialize, planner, quyền mặc định từ chối,
token gắn task/digest/thời hạn, idempotency trong bộ nhớ, AIMS chọn đường khả thi,
verifier không tin success giả, kết quả uncertain không retry và exit code/JSON của CLI.
Unit tests không mở ứng dụng macOS thật. `fixtures/` dành cho dữ liệu giả lập khi cần;
không đưa dữ liệu cá nhân vào tests. Chưa cần cài pytest.

`test_confirmation_and_registry.py` kiểm tra confirmation gắn action/digest/thời hạn,
replay/reissue, từ chối/EOF/Ctrl+C, quyền không bị approval thay thế, registry/probe,
observation và lỗi execute/verify. Tổng hiện tại: 48 ca unittest.

`test_macos_apps.py` thêm 25 ca cho allowlist/app policy, native backend,
app đã chạy/chưa chạy, launch lỗi/timeout, observation PID và kiểm chứng độc lập.
Dùng runner/backend được kiểm soát, không mở app thật trong bộ tests. Tổng 73 ca.
Kiểm chứng tích hợp native được ghi riêng tại `Docs/MACOS_APP_OPEN.md`.

`test_apple_notes.py`: 28 ca scope, planner, policy, confirmation bắt buộc, verifier,
backend JSON/stdin, dữ liệu trùng/sai scope, lỗi Automation và same-step cache.
Tổng hiện tại: 101 unit tests. Không tự tạo Notes thật trong tests.

`test_traces.py`: thêm 30 ca cho privacy allowlist, JSONL/reader, fsync/short write/disk-full,
symlink, collision, file hỏng, CLI history và không retry khi log lỗi. Tổng hiện tại 131 tests.
CLI tests cũ thêm --no-trace để không ghi dữ liệu vào home; ca persistence dùng thư mục tạm.
