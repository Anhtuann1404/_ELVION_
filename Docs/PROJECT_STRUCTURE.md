# Cấu trúc dự án và dữ liệu

Chốt bộ khung ngày 29/10/2026. Một package Python trong `src/`, Swift helper riêng;
chưa cần microservice hay module cho nền tảng khác. Package có docstring mô tả trách nhiệm;
chỉ thêm implementation khi bắt đầu dùng. CLI có trợ giúp, phiên bản, demo tạo ghi chú giả run mở Calculator thật và notes tạo/tìm ghi chú thật với native adapter có scope.

## Thư mục

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `Docs/` | Kế hoạch, kiến trúc, hợp đồng và quyết định. |
| `src/elvion/interface/` | CLI, nhập/xuất và trình bày xác nhận. |
| `src/elvion/core/` | Hợp đồng dữ liệu chung, trạng thái và điều phối. |
| `src/elvion/planning/` | Tạo kế hoạch có giới hạn; bắt đầu bằng quy tắc. |
| `src/elvion/policy/` | Quyền, phạm vi ủy quyền và quyết định xác nhận. |
| `src/elvion/aims/` | Chọn phương thức đủ điều kiện và giải thích lựa chọn. |
| `src/elvion/adapters/` | Fake adapter, native/API, Accessibility, DOM và Vision khi cần. |
| `src/elvion/verification/` | Kiểm tra hậu điều kiện; trả uncertain khi thiếu bằng chứng. |
| `src/elvion/models/` | Adapter suy luận local/cloud, STT/TTS về sau; không chứa weights. |
| `src/elvion/storage/` | Mã truy cập SQLite, trace và Keychain; không chứa dữ liệu chạy thật. |
| `native/macos/` | Swift helper; hiện chỉ có hướng dẫn, chưa có Swift project. |
| `configs/` | Cấu hình mặc định dự kiến và hướng dẫn; không chứa secret. |
| `tests/fixtures/` | Dữ liệu giả lập nhỏ, có thể công khai. |
| `benchmarks/scenarios/` | Kịch bản đánh giá có thể tái lập. |
| `scripts/` | Script hỗ trợ khi có nhu cầu; hiện có hướng dẫn chạy. |

`pyproject.toml` khai báo Python >=3.11, package và entry point `elvion`.
Hiện không có runtime dependency ngoài thư viện chuẩn. Không tạo thư mục con cho
mọi phương thức adapter hoặc engine model trước khi triển khai.

## Ranh giới phụ thuộc

- Interface gọi core; core điều phối planning, policy, AIMS, adapter và verifier.
- Hợp đồng chung thuộc core; các module không import entry point CLI.
- Adapter và model adapter không tự cấp quyền; AIMS chỉ chọn đường policy cho phép.
- Chi tiết macOS nằm trong adapter/Swift helper; core không phụ thuộc trực tiếp API macOS.
- Storage cung cấp truy cập dữ liệu; không tự quyết định quyền hoặc phương thức thao tác.

Đây là hướng phụ thuộc của kiến trúc. TaskOrchestrator dùng chung pipeline; DemoOrchestrator lắp fake notes, AppOrchestrator lắp native app adapter, NotesOrchestrator lắp hai native Notes adapter và planner riêng. Registry và Protocol chung đã được triển khai.

## Phân chia dữ liệu

| Loại | Nơi lưu dự kiến | Git |
| --- | --- | --- |
| Code, docs, cấu hình mẫu | Trong repo | Có |
| Fixtures giả lập, kịch bản benchmark nhỏ | `tests/fixtures/`, `benchmarks/scenarios/` | Có |
| Tác vụ, bước, quyền theo tác vụ, metadata bằng chứng | SQLite trong thư mục dữ liệu ứng dụng | Không |
| Trace quyết định và kết quả đã lọc | Thư mục dữ liệu ứng dụng | Không |
| Token/API key | macOS Keychain | Không |
| Model weights và cache | Thư mục cache ứng dụng | Không |
| Ảnh màn hình, âm thanh, nội dung ghi chú | Chỉ lưu khi cần theo chính sách rõ | Không |
| Dataset huấn luyện AIMS và kết quả thử nghiệm | Ngoài repo; tạm thời có thể dùng `artifacts/` đã ignore | Không tự động |

Trên macOS, dữ liệu ứng dụng đặt tại `~/Library/Application Support/ELVION/`,
cache ở `~/Library/Caches/ELVION/`. CLI mới tự tạo traces/ khi chạy tác vụ; có --data-dir hoặc --no-trace. Agent chỉ kiểm thử ghi/đọc trong thư mục tạm. Retention, SQLite, cache và Keychain còn cần triển khai.
Không đưa cả cơ sở dữ liệu, bản ghi xác nhận hoặc nội dung cá nhân vào Git.

`.gitignore` loại cấu hình local, dữ liệu runtime, artifacts, weights và file SQLite.
Ignore không xóa file đã được Git track; cần kiểm tra danh sách thay đổi trước commit.

## Trace cho AIMS

Trace JSONL hiện ghi task/step/trace ID, phiên bản policy, đặc trưng bối cảnh tối thiểu,
candidates đủ/không đủ điều kiện, lý do loại, đường được chọn, kết quả kiểm chứng,
độ trễ và fallback. Không mặc định ghi toàn bộ yêu cầu, nội dung ứng dụng hoặc secret.
Một đường thành công chưa chứng minh đó là đường tối ưu; nhãn huấn luyện cần dựa trên
đánh giá so sánh phương thức. Chọn tiêu chí gắn nhãn và cách chia tập trước huấn luyện.

## Bước triển khai kế tiếp

Đã có luồng demo và native app.open qua policy/AIMS/adapter/verifier. Tiếp theo xác minh native trên desktop (môi trường agent hiện trả -10827), trace JSONL đã triển khai và create/find Notes đã được người dùng xác minh qua JSON desktop. Tiếp theo kiểm tra trace home mặc định và các ca lỗi desktop. Cloud, voice và huấn luyện làm sau.
