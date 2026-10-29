# Trace cục bộ và lọc dữ liệu

## Trạng thái ngày 29/10/2026

Đã triển khai trace JSONL theo tác vụ, privacy schema v1, lệnh traces list/show,
đường dữ liệu mặc định và xử lý lỗi lưu độc lập với kết quả hành động.
131 unit tests thành công: 101 ca cũ + 30 ca trace/privacy/storage/CLI.
Tests ghi/đọc file thật trong thư mục tạm, không mở Notes/Calculator hay ghi dữ liệu cá nhân.

## Cách dùng

Từ lần chạy mới, demo/run/notes tự lưu trace. Các tác vụ trước khi có tính năng này
không được khôi phục tự động từ lịch sử chat hoặc stdout cũ.

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Kiểm tra trace" --grant note.create
PYTHONPATH=src python3 -m elvion traces list
```

Lấy trace_id trong kết quả hoặc danh sách rồi thay UUID vào lệnh:

```sh
PYTHONPATH=src python3 -m elvion traces show "UUID_CUA_TRACE"
```

Mặc định macOS: ~/Library/Application Support/ELVION/traces/<trace_id>.jsonl.
Linux: $XDG_DATA_HOME/ELVION/traces hoặc ~/.local/share/ELVION/traces.
Bản filesystem hiện dành cho macOS/Linux; chưa kiểm chứng cơ chế permission trên Windows.

Có thể chọn thư mục riêng, ví dụ ./runtime đã được Git ignore:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Kiểm tra trace" --grant note.create --data-dir ./runtime
PYTHONPATH=src python3 -m elvion traces list --data-dir ./runtime --limit 5
```

Mọi lệnh đọc phải dùng cùng --data-dir với lần ghi nếu chọn đường riêng.
Muốn tắt cho một lần chạy, thêm --no-trace. Cờ này không tạo thư mục trace.
Hiện nguồn cấu hình là CLI; configs/defaults.toml vẫn chưa được nạp.
Gọi orchestrator trực tiếp từ Python chỉ bật persistence khi inject TraceStore;
unit tests cũ và scripts/check_app_open.py không tự ghi vào home.

## Dữ liệu được lưu

| Giữ lại | Loại bỏ trước khi ghi |
| --- | --- |
| task_id/step_id/trace_id, confirmation_id dạng UUID | Câu lệnh, tiêu đề/body ghi chú, tên tài khoản |
| Trạng thái, capability thuộc allowlist, simulated | Preview, confirmation response/token/digest |
| Adapter/method, candidates, eligibility, reason đã biết | note_id Core Data, đường dẫn cá nhân, ảnh/audio |
| Policy version đã đăng ký trong privacy schema | Raw exception/stderr, message tự do, key/API token |
| Timestamp UTC, elapsed_ms/duration_ms | Mọi trường và giá trị tự do chưa được allowlist |
| Các cờ verify/already_running và mã native dạng số | Evidence đầy đủ từ ứng dụng |

Không hash tiêu đề hoặc ID ghi chú để thay cho việc loại bỏ.
Đây là allowlist projection, không phải chỉ regex dò chuỗi giống secret.
Adapter/policy/reason mới cần cập nhật schema và tests trước khi ghi metadata đó.
Trình đọc cũng project lại từng record; không hiển thị trường lạ dù ai đó sửa JSONL.
TaskReport stdout và preview tương tác vẫn phục vụ người dùng như trước; bảo vệ nêu trên
áp dụng cho file trace/history, không phải cơ chế làm sạch mọi nội dung hiển thị CLI.

## Ghi và đọc

Mỗi task/trace mới tạo file độc quyền bằng UUID, không ghi đè trace trùng.
Thư mục traces có mode 0700, file 0600; kiểm tra owner, chặn symlink ở thư mục traces/file,
không đọc file có hardlink. Không thay quyền toàn bộ data-dir do người dùng chỉ định.
Không phải mã hóa hoặc kho audit chống sửa đổi; đây là lịch sử debug local của người dùng.

Mỗi event được lọc rồi ghi một dòng và fsync trước bước tiếp theo. Cuối task có record
task_result đã lọc. Ghi từng event giúp giữ các bước trước đó nếu process bị ngắt.
Các elapsed_ms dùng đồng hồ monotonic từ lúc bắt đầu task, bao gồm thời gian chờ confirmation
và các bước ghi event; duration_ms chưa tính thời gian ghi record task_result cuối.

Trình đọc giới hạn 1 MiB/256 records mỗi trace, tối đa 100 mục mỗi lần list.
JSON sai, dòng cuối dang dở, schema/identity sai được đánh dấu malformed/incomplete;
không in nội dung raw bị hỏng. finalized=true nghĩa có task_result cuối hợp lệ, không đồng
nghĩa tác vụ succeeded. awaiting_confirmation có thể được finalized như một kết quả trả về,
chưa có cơ chế resume task từ trace.

Chưa có tự xóa theo thời hạn, nén, upload hoặc tự chuyển thành dataset huấn luyện.
Người dùng quản lý file local; không đưa trace vào Git. .gitignore loại mọi folder traces/.

## Khi lỗi lưu

TaskReport có trường trace:

- saved: đã ghi task_result và đóng file thành công.
- partial: đã ghi được một số record, phần còn lại không hoàn chỉnh.
- failed: không bắt đầu được hoặc chưa ghi được record hoàn chỉnh.
- disabled: persistence không bật.

Kèm path, records_written và error_code cố định. Ví dụ TRACE_STORAGE_UNAVAILABLE,
TRACE_WRITE_FAILED. Không trả raw exception chứa đường dẫn/secret vào log.
CLI cảnh báo ở stderr nếu partial/failed, còn stdout vẫn là một TaskReport JSON.
Task status và exit code vẫn theo hành động: lỗi log không biến tác vụ thành thất bại
và không tự chạy lại hành động. Chế độ này ưu tiên tác vụ tiếp tục với log trong RAM;
chưa có policy bắt buộc audit bền vững trước các hành động nhạy cảm.

## File triển khai

| File | Vai trò |
| --- | --- |
| storage/trace_privacy.py | Schema v1, allowlist và projection dùng cho cả ghi/đọc. |
| storage/traces.py | Đường dữ liệu, writer theo task, fsync, quyền file, reader giới hạn. |
| core/orchestrator.py | Ghi event/summary, timing và trả tình trạng persistence riêng. |
| core/runtime.py | Inject TraceStore vào composition app/notes; demo cũng hỗ trợ. |
| interface/cli.py | Mặc định bật trace, --no-trace/--data-dir, traces list/show và cảnh báo. |
| tests/test_traces.py | 30 ca privacy/durability/lỗi/quyền/reader/CLI. |

## Kiểm chứng

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Đã kiểm tra ghi/đọc qua file tạm thật, từng event flush trước confirmation,
không rò tiêu đề/tài khoản/note ID/secret, native errors dạng số, replay file không ghi đè,
short write, ENOSPC giữa dòng, fsync failure, symlink, malformed/deeply nested JSON,
file quá lớn, thư mục không ghi được và CLI opt-out/cảnh báo.
Chưa thử persistence tại đường home mặc định trong môi trường agent bị giới hạn;
đường mặc định được kiểm tra bằng thư mục tạm, cần desktop acceptance qua lệnh CLI mới.
