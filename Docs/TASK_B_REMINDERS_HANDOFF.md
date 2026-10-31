# Bàn giao Task B — lõi nhắc việc local

Ngày: 31/10/2026. Phạm vi: package `src/elvion/reminders/`, CLI riêng,
tests/benchmark riêng và tài liệu. Không sửa planner, executor, policy, voice,
conversation, CLI chính hoặc tiến trình nền.

## Tích hợp sau này

Nhánh chính có thể gọi `ReminderStore(data_dir, clock=...)` và các API trong
[REMINDERS.md](REMINDERS.md). `collect_due(now)` chỉ ghi occurrence + event
trong transaction và trả event mới; `list_pending_events()` đọc lại những
event chưa acknowledge. Event có ID/revision/snapshot nội dung và lịch. Trước
khi phát thông báo, consumer cần đọc lại reminder để xác nhận `active` và
revision còn khớp, rồi quyết định khi nào `acknowledge_event(id)`. Không xem
ack như hoàn thành reminder lặp. Chưa có API notification delivery hoặc
exactly-once bên ngoài SQLite.

Planner sau này cần biên dịch câu tự nhiên thành `Schedule` có cấu trúc,
timezone/đích đã được người dùng duyệt; quyền và confirmation phải do nhánh
chính tích hợp trước khi gọi mutation. Voice/TTS chỉ là consumer của event
đã qua ranh giới đó, không được tự cấp quyền hay tạo reminder từ model reply.

## Chính sách và giới hạn

One-time quá hạn tạo một event. Lịch lặp bỏ lỡ nhiều kỳ tạo tối đa một event
đại diện, sau đó nhảy đến kỳ tương lai; không lưu số kỳ đoán. DST không tồn
tại/trùng bị từ chối; catch-up quét tối đa 3660 ngày, xa hơn trả
`SCHEDULE_RANGE_UNSUPPORTED` và rollback. Hai process poll cùng kỳ được
`BEGIN IMMEDIATE` + unique constraint tuần tự hóa. Pending event tồn tại qua
restart và có thể đọc lại nhiều lần. Sửa nội dung vô hiệu pending cũ rồi
rearm kỳ cũ nhất cho lần poll tiếp theo; sửa lịch bắt đầu từ lịch mới. Hủy/
complete làm pending cũ không còn hiệu lực; đã acknowledge giữ lịch sử. Race giữa đọc event và notification
bên ngoài vẫn là trách nhiệm consumer tương lai.

## Kiểm chứng

- `PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_reminders*.py' -q`:
  11/11 đạt với clock giả, SQLite tạm và hai connection cạnh tranh.
- `PYTHONPATH=src:. python3 -m benchmarks.reminders.runner --output-dir /private/tmp/elvion-reminder-benchmark`:
  9/9 scenario tổng hợp, missed/unexpected/duplicate/stale/external actions
  đều 0. Oracle cố định; fault injection bỏ event làm benchmark trượt.
- CLI chạy qua nhiều process với `--data-dir` tạm: create → list/show → update
  → poll-due → events → ack → complete; ID giữ nguyên, DB tồn tại qua process.
- Toàn bộ suite: `PYTHONPATH=src:. python3 -m unittest discover -s tests -q`:
  743 tests đạt, 1 skipped.
- Chưa kiểm thử notification, daemon, voice hoặc lời nhắc từ ngôn ngữ tự nhiên.

## Đề xuất ghi BUG_LOG.md cho nhánh chính

Trong triển khai, phiên đầu của `Schedule.once` trả `SCHEDULE_INVALID` khi
datetime thiếu timezone; đã sửa thành `TIMEZONE_REQUIRED`, test validation
đạt. Phiên đầu của `update_reminder` giữ pending event với snapshot nội dung
cũ sau khi sửa nội dung; đã sửa mọi thay đổi tăng revision, invalidated
pending cũ và rearm kỳ pending cũ nhất khi chỉ đổi nội dung. Test regression
đạt. Đây là lỗi trong module mới, không ảnh hưởng
CLI/voice hiện có; chỉ đã kiểm chứng bằng SQLite/test tổng hợp, chưa có
consumer notification thật. Nếu nhánh chính tích hợp, ghi hai ranh giới này
vào nhật ký và kiểm tra lại khi có consumer.
