# ELVION

> **ELVION** — Trợ lý cá nhân điều khiển macOS bằng giọng nói và chữ, ưu tiên xử lý trên máy (local-first) cho MacBook Pro M5.

---

## Giới thiệu

ELVION là dự án dài hạn hướng tới xây dựng một trợ lý cá nhân thông minh, an toàn, với khả năng tự động lựa chọn giao diện điều khiển (AIMS - Adaptive Interaction Mode Selection) giữa Native/API, Accessibility/DOM và Vision UI.

Hệ thống được thiết kế theo nguyên tắc:
- **Local-first**: Ưu tiên xử lý dữ liệu và suy luận trực tiếp trên thiết bị; cloud model chỉ được gọi khi có sự cho phép cụ thể theo từng tác vụ.
- **Bảo mật & Quyền riêng tư**: Chính sách quyền nghiêm ngặt, xác nhận ràng buộc với hành động cụ thể bằng digest cho các thao tác có tác động bên ngoài (gửi tin, sửa/xóa dữ liệu).
- **Kiểm chứng độc lập**: Verifier đánh giá kết quả thực thi dựa trên bằng chứng và hậu điều kiện (postcondition).

---

## Tài liệu chi tiết

Toàn bộ tài liệu thiết kế và đặc tả kiến trúc được đặt trong thư mục [`Docs/`](Docs/):

1. [**Docs/PROJECT_PLAN.md**](Docs/PROJECT_PLAN.md): Tầm nhìn, nguyên tắc sản phẩm, các mốc phát triển và tiêu chí đánh giá.
2. [**Docs/ARCHITECTURE.md**](Docs/ARCHITECTURE.md): Kiến trúc module, luồng thực thi và cơ chế AIMS.
3. [**Docs/API_CONTRACTS.md**](Docs/API_CONTRACTS.md): Đặc tả hợp đồng dữ liệu nội bộ, adapter, quyền và mã lỗi chuẩn.
4. [**Docs/TECH_STACK.md**](Docs/TECH_STACK.md): Lựa chọn công nghệ (Python core, Swift helper, SQLite, Keychain) và nguyên tắc thay thế.
5. [**Docs/CURRENT_TASKS.md**](Docs/CURRENT_TASKS.md): Kế hoạch Sprint 0 (Bộ xương chạy được), backlog và tiêu chí nghiệm thu.
6. [**Docs/DECISIONS.md**](Docs/DECISIONS.md): Nhật ký các quyết định kiến trúc đã thống nhất và điểm còn mở.


## Trạng thái triển khai

Đã có luồng demo CLI tạo ghi chú giả lập: planner quy tắc, policy mặc định từ chối,
AIMS baseline trên ba adapter giả qua Protocol/registry, xác nhận tương tác tùy chọn, thực thi và đọc lại để kiểm chứng. Tác vụ trả JSON
với trạng thái, task ID, trace ID và các sự kiện. Ghi chú chỉ tồn tại trong bộ nhớ của lần chạy.
Đã có native adapter `app.open` cho Calculator. Ngày 29/10/2026, người dùng xác nhận lệnh chạy thành công và Calculator mở trên desktop. Lần chạy riêng trong môi trường agent trước đó trả lỗi LaunchServices -10827. Đã lưu trace JSONL local có lọc; chưa gọi model, lưu SQLite, dùng Keychain hay triển khai Swift helper.
`configs/defaults.toml` vẫn là cấu hình thiết kế, CLI chưa nạp file này.

## Chạy bộ khung

Yêu cầu Python 3.11 trở lên. Chạy tại thư mục gốc, không cần cài thư viện ngoài:

```sh
PYTHONPATH=src python3 -m elvion
PYTHONPATH=src python3 -m elvion --help
PYTHONPATH=src python3 -m elvion --version
```

Khi cần cài package vào môi trường phát triển riêng:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
elvion --help
```

Lệnh cài editable cần build backend setuptools; có thể cần mạng nếu môi trường chưa có.

## Cấu trúc và dữ liệu

Xem [Docs/PROJECT_STRUCTURE.md](Docs/PROJECT_STRUCTURE.md) để biết trách nhiệm từng thư mục,
ranh giới phụ thuộc và nơi lưu dữ liệu. Code và dữ liệu giả lập nhỏ đi cùng Git;
dữ liệu cá nhân, secret, model weights và kết quả nghiên cứu không đưa vào repo.


## Demo đầu tiên

Đủ quyền cho lần chạy này:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI" --grant note.create
```

Thiếu quyền: trả `PERMISSION_DENIED`, exit code 1 và không tạo ghi chú:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI"
```

Giả lập native không khả dụng: AIMS chọn Accessibility giả trước khi thực thi:

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI" --grant note.create --disable-native
```

Mọi phương thức trong demo đều là fake, không thao tác Apple Notes hoặc cấp quyền macOS.
CLI nhận cú pháp `Tạo ghi chú <tiêu đề>` qua đối số; có bước xác nhận tương tác bằng `--confirm`, chưa có hội thoại nhiều lượt.
Xem [Docs/SPRINT0_WALKTHROUGH.md](Docs/SPRINT0_WALKTHROUGH.md) để hiểu cách hoạt động.

## Kiểm thử

Dùng unittest trong thư viện chuẩn, chưa cần cài pytest:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```


## Xác nhận hành động

```sh
PYTHONPATH=src python3 -m elvion demo "Tạo ghi chú Ôn AI" --grant note.create --confirm
```

CLI hiển thị preview ở stderr. Nhập `y` để đồng ý; `n`, Enter hoặc EOF từ chối,
Ctrl+C trong lúc chờ hủy tác vụ. Quyền capability và xác nhận là hai kiểm tra riêng.
Mỗi confirmation chỉ dùng một lần, hết hạn sau 60 giây và gắn đúng action digest.
Mọi thao tác vẫn là giả lập trong RAM. 131 kiểm thử unittest đã qua, gồm ca native với backend được mô phỏng trong tests.
Xem [Docs/CONFIRMATION_AND_ADAPTERS.md](Docs/CONFIRMATION_AND_ADAPTERS.md) để hiểu cách hoạt động.


## Mở ứng dụng macOS thật

```sh
PYTHONPATH=src python3 -m elvion run "Mở Máy tính" --grant app.open
```

Đây là hành động thật, chỉ cho phép Calculator (`com.apple.calculator`). Có thể thêm
`--confirm` để xem trước và duyệt. Không có grant thì không gọi công cụ native.
`run` hiện có một native adapter; không dùng fake Accessibility/Vision để dự phòng.
Chỉ báo succeeded sau khi AppKit xác nhận có tiến trình đúng bundle ID đang chạy;
chưa kiểm tra cửa sổ đang hiện hoặc ứng dụng đang ở foreground.
Xem [Docs/MACOS_APP_OPEN.md](Docs/MACOS_APP_OPEN.md) để biết chi tiết và giới hạn kiểm chứng hiện tại.


## Apple Notes thật (spike)

Chọn rõ tài khoản, chỉ thao tác trong thư mục ELVION:

```sh
PYTHONPATH=src python3 -m elvion notes "Tạo ghi chú Ôn AI" --account "On My Mac" --grant note.create
PYTHONPATH=src python3 -m elvion notes "Tìm ghi chú Ôn AI" --account "On My Mac" --grant note.find
```

Tạo luôn yêu cầu preview/approval; chưa có nội dung dài, sửa/xóa hoặc đọc toàn bộ kho Notes.
Tìm đúng tiêu đề; trùng tên trả lỗi, không chọn mục đầu. Tên tài khoản phải khớp máy;
không tự chọn default account. Nếu dùng On My Mac, tài khoản này cần được bật trong Notes.
Người dùng đã cung cấp JSON desktop xác nhận tạo ghi chú thật và đọc lại kiểm chứng thành công. Tìm ghi chú cũng succeeded, postcondition_verified=true và trả cùng ID với lần tạo; lần thử đọc riêng trong agent trước đó trả -2700.
Xem [Docs/APPLE_NOTES.md](Docs/APPLE_NOTES.md) cho phạm vi, cách thử và các giới hạn.

Kiểm tra các ca Calculator còn lại khi Calculator đang mở:

```sh
PYTHONPATH=src python3 scripts/check_app_open.py
```


## Lịch sử tác vụ local

Từ lần chạy mới, demo/run/notes tự ghi trace đã lọc vào thư mục dữ liệu ứng dụng,
ngoài repo. Trên macOS: `~/Library/Application Support/ELVION/traces/`.
Không lưu câu lệnh, title/body ghi chú, tên tài khoản, note ID, preview hoặc token.

```sh
PYTHONPATH=src python3 -m elvion traces list
PYTHONPATH=src python3 -m elvion traces show "UUID_CUA_TRACE"
```

Thay UUID_CUA_TRACE bằng trace_id thực tế. Thêm --no-trace vào lệnh tác vụ để tắt một lần,
hoặc --data-dir ./runtime để dùng đường riêng (đọc lịch sử cũng cần cùng --data-dir).
Lỗi lưu được báo riêng tại report.trace và stderr, không tự chạy lại hành động.
Xem [Docs/TRACE_STORAGE.md](Docs/TRACE_STORAGE.md) cho schema, privacy và các giới hạn.
