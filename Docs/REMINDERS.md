# Lõi nhắc việc local — contract V1

Module `elvion.reminders` độc lập với planner, voice và notification. Dữ liệu
nằm ở `<data-dir>/reminders/reminders.sqlite3`, mặc định dùng
`default_data_dir()` của ELVION. CLI thử riêng là `scripts/check_reminders.py`.

## Kiểu và API

- `Schedule`: `once(at)` là datetime có timezone; `daily(local_time,
  start_date)` hoặc `weekly(local_time, weekdays, start_date)` dùng giờ địa
  phương, ngày bắt đầu và timezone IANA của reminder. Weekday là 0=Thứ hai
  đến 6=Chủ nhật.
- `Reminder`: UUID ổn định, nội dung tối đa 500 ký tự, `active`/
  `completed`/`cancelled`, thời điểm tạo/sửa UTC, timezone, lịch hiện tại,
  revision bắt đầu từ 1 và `next_at` UTC hoặc rỗng.
- `Occurrence`: một kỳ cụ thể của reminder/revision, khóa duy nhất theo
  `(reminder_id, revision, scheduled_at)`. Một reminder lặp có thể có nhiều
  occurrence qua các lượt xử lý.
- `DueEvent`: mục outbox có UUID ổn định, snapshot nội dung và revision,
  `scheduled_at`, `detected_at`, `catch_up`, trạng thái `pending`/
  `acknowledged`/`invalidated`. Không phải bằng chứng đã phát thông báo.

`ReminderStore(data_dir=None, clock=...)` có `create_reminder(content,
schedule, timezone)`, `get_reminder(id)`, `list_reminders(status=None)`,
`update_reminder(id, content=None, schedule=None, timezone=None)`,
`cancel_reminder(id)`, `complete_reminder(id)`, `collect_due(now=None)`,
`list_pending_events()`, `acknowledge_event(id)`. Mutations dùng transaction;
`clock` phải trả datetime có timezone. API trả dataclass bất biến; lỗi có mã
ổn định `ReminderError.code`, không đưa nội dung/SQLite exception ra ngoài.

`complete_reminder` kết thúc toàn bộ reminder, không chỉ kỳ hiện tại.
`acknowledge_event` chỉ đánh dấu đã xử lý một event. Acknowledge lại event
đã acknowledge trả chính event đó; event đã invalidated trả `EVENT_STALE`.
Mọi thay đổi tăng revision, vô hiệu pending event cũ; acknowledged history giữ
nguyên snapshot. Sửa riêng nội dung sẽ đặt lại kỳ pending cũ nhất để poll kế
tiếp tạo một event mới với nội dung mới. Sửa lịch bắt đầu lại từ lịch mới,
không tự chuyển event cũ sang lịch mới. Cancel/complete giữ lịch sử và vô hiệu
pending event. Consumer
đã lấy event phải đọc lại reminder/revision/status trước khi có tác dụng bên
ngoài; điều này chưa loại bỏ race với một notification service tương lai.

## Thời gian và catch-up

- Mọi instant lưu UTC; lịch lặp giữ timezone IANA và giờ địa phương. Không
  cộng 86400 giây UTC để tính ngày tiếp theo.
- Lịch lặp bắt đầu từ ngày chỉ định, nhưng không tạo kỳ trước thời điểm tạo
  hoặc cập nhật. `next_at` là kỳ đầu tiên không trước mốc đó.
- `collect_due`: một lần tại/qua hạn sinh một event. Với lịch lặp, mỗi
  reminder sinh **tối đa một** event trong một lượt dù bỏ lỡ nhiều kỳ; event
  đại diện cho kỳ cũ nhất chưa xử lý. Sau đó `next_at` nhảy tới kỳ đầu tiên
  trong tương lai. `catch_up=true` khi kỳ đại diện trước `now`.
- Không tính số kỳ bỏ lỡ; không lưu con số ước đoán. Poll lại cùng `now`
  không tạo thêm event. Event pending vẫn ở SQLite qua restart cho đến ack
  hoặc invalidation.
- Giờ địa phương không tồn tại hoặc bị lặp do DST bị từ chối với
  `SCHEDULE_DST_INVALID` khi xác định kỳ đó. Không tự dịch giờ hoặc chọn fold.
  Nếu lịch lặp về sau gặp ngày DST không hợp lệ, `collect_due` rollback toàn
  lượt và báo mã lỗi để người dùng sửa lịch; không phát event giả.

Tính kỳ tiếp theo từ thời điểm hiện tại dùng tối đa 8 ngày ứng viên. Khi
catch-up, quét các ngày được chọn trong khoảng bỏ lỡ để phát hiện giờ DST
không hợp lệ, giới hạn 3660 ngày; khoảng xa hơn trả
`SCHEDULE_RANGE_UNSUPPORTED` và không thay đổi dữ liệu. Không duyệt từng
giây hoặc tạo từng event trong thời gian tắt app. SQLite `BEGIN IMMEDIATE`
tuần tự hóa hai connection/process; unique constraints bảo vệ chống trùng.
Outbox là at-least-once khi consumer đọc lại pending event; module chưa gửi
notification nên không tuyên bố exactly-once delivery.

## Giới hạn

Không nhận câu tự nhiên, không tự chạy nền, không đọc mic, không gọi model,
không phát TTS hay notification. `poll-due` chỉ ghi outbox. Chưa có lịch theo
tháng, snooze, xóa vĩnh viễn hoặc đồng bộ thiết bị. Mọi dữ liệu thử nghiệm dùng
thư mục tạm và nội dung tổng hợp; không ghi nội dung vào log/handoff.

## CLI thử độc lập

Chạy từ thư mục repo; `--data-dir` đứng trước subcommand. Những lệnh sau chỉ
dùng dữ liệu tổng hợp, không gửi thông báo:

```sh
PYTHONPATH=src:. python3 scripts/check_reminders.py --help
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo create --content "Nhắc thử tổng hợp" --kind once --at 2026-11-01T08:00:00+07:00
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo create --content "Ôn tập" --kind daily --time 08:30 --start-date 2026-11-01 --timezone Asia/Ho_Chi_Minh
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo create --content "Họp thử" --kind weekly --time 09:00 --start-date 2026-11-02 --weekdays 0,4 --timezone Asia/Ho_Chi_Minh
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo list
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo show UUID
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo update UUID --content "Ôn tập đã sửa"
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo poll-due --now 2026-11-01T02:00:00+00:00
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo events
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo ack EVENT_UUID
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo cancel UUID
PYTHONPATH=src:. python3 scripts/check_reminders.py --data-dir /private/tmp/elvion-reminders-demo complete UUID
```

Thay `UUID` bằng ID từ `create`/`list`, `EVENT_UUID` bằng ID từ `events`.
`update` cũng nhận bộ cờ lịch như `create`; muốn đổi lịch thì cung cấp đủ
`--kind` và các trường bắt buộc của loại đó. `--help` không mở SQLite.
CLI mặc định timezone `Asia/Ho_Chi_Minh`; ISO datetime một lần phải có offset.

Benchmark hồi quy tổng hợp:

```sh
PYTHONPATH=src:. python3 -m benchmarks.reminders.runner
```
