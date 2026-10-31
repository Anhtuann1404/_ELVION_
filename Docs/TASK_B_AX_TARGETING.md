# Task B — Tìm control trong snapshot AX, chỉ đọc

Hãy thực hiện task này trong repository `/Users/yingjunn_/Study_/ELVION`.
Đọc `AGENTS.md` trước. Làm đến khi có code, tests, benchmark và tài liệu bàn
giao; không chỉ trả kế hoạch. Không commit/push/reset/stash.

## 1. Bối cảnh và mục tiêu

ELVION là trợ lý macOS local-first, có planner/executor/permissions/verifier.
Nhánh chính đang so sánh model Vision web. Task này hoàn toàn độc lập: xây
bước **xác định control từ snapshot Accessibility đã có**, chưa thao tác.

Spike quan sát ở `src/elvion/desktop_observation/` đã chạy trên desktop:
người dùng báo `observed`,243 nodes,truncated=false cho Calculator. Chưa
review từng node/role/bbox và chưa tích hợp AIMS. Không suy từ243 nodes rằng
mọi control đã được đọc hoặc có label đầy đủ.

Đọc các file sau để dùng đúng contract hiện hành:

- `src/elvion/desktop_observation/contracts.py`
- `src/elvion/desktop_observation/observer.py`
- `src/elvion/desktop_observation/__init__.py`
- `scripts/check_desktop_observation.py`
- `Docs/DESKTOP_OBSERVATION.md`

Mục tiêu minh họa: tìm nút có nhãn chính xác `7`, `+` hoặc `=` trong
snapshot Calculator, trả node ID, role, enabled và bbox nếu đủ bằng chứng.
Không đoán rằng macOS nhất thiết cung cấp những nhãn này: ngôn ngữ và mode
Calculator có thể làm chúng khác. Chỉ hỗ trợ label thực sự được AX cung cấp.

## 2. Phạm vi file độc lập

Chỉ tạo các file mới sau:

1. `src/elvion/desktop_targeting/__init__.py`
2. `src/elvion/desktop_targeting/contracts.py`
3. `src/elvion/desktop_targeting/locator.py`
4. `scripts/check_desktop_targeting.py`
5. `benchmarks/desktop_targeting/__init__.py`
6. `benchmarks/desktop_targeting/cases.py`
7. `benchmarks/desktop_targeting/runner.py`
8. `tests/test_desktop_targeting.py`
9. `tests/test_desktop_targeting_benchmark.py`
10. `Docs/DESKTOP_TARGETING.md`

Không sửa module quan sát, Swift helper, core contracts, AIMS, permissions,
planner, CLI/voice/GUI, Vision, browser, các benchmark cũ, model config hoặc
artifact của nhánh chính. Không cài/tải model/dependency. Nếu thấy lỗi ngoài
phạm vi, ghi bằng chứng và đề xuất trong tài liệu bàn giao, không tự sửa.
Nhánh chính tích hợp `BUG_LOG.md`/`CURRENT_TASKS.md`; gửi mọi bug/vướng mắc,
nguyên nhân đã biết, cách xử lý, kiểm chứng và giới hạn để nhánh chính ghi.

## 3. API v1

Export hàm:

```python
locate_control(
    snapshot: DesktopSnapshot,
    *,
    label: str,
    role: str = 'AXButton',
    now_ns: int | None = None,
    max_age_ms: int = 2000,
) -> DesktopTargetResult
```

`now_ns=None` dùng `time.monotonic_ns()`. Cho phép truyền thời gian cố định
để test. Đây là pure targeting: không network, subprocess, gọi AX, chụp ảnh,
model, đọc file hoặc tự quan sát lại. Demo/benchmark là caller riêng.

Result là dataclass immutable, tối thiểu:

- `status`: found/not_found/ambiguous/unavailable/stale/unsupported/error.
- `reason`: mã cố định, không nhét exception/label riêng tư vào reason.
- `snapshot_id`, `node_id`, `role`, `enabled`, `bbox` tùy chọn.
- `candidate_count` và age_ms nếu tính được, không dump tree vào result.

Chỉ found được mang node_id/bbox có thể dùng để tham chiếu mục tiêu.
Kết quả không phải authority token, không cấp quyền click và không chứng
minh element đang hiện/focus/clickable. ID chỉ có ý nghĩa trong snapshot đó.

## 4. Quy tắc tìm và từ chối

MVP chỉ nhận bundle `com.apple.calculator`, schema_version1 và role AXButton.
Bundle/role khác trả unsupported. Không ánh xạ role khác sang AXButton.

Kiểm tra snapshot trước khi tìm: kiểu dữ liệu chính xác (bool không là int),
PID/timestamps hợp lệ, ID duy nhất, root/parent/depth/size giới hạn tương thích
observer, bbox hữu hạn với width/height dương. Dataclass frozen vẫn có thể
được tạo sai bằng tay, nên không mặc định rằng mọi instance đều đã validate.
Không gọi private parser của module quan sát hoặc nhân bản code không cần thiết.

Freshness dùng monotonic cùng host: tuổi quá max_age_ms trả stale; timestamp
tương lai/clock sai phải từ chối, không clamp tuổi về0. max_age_ms là integer
trong1..10000. Snapshot truncated luôn unavailable cho MVP, kể cả đã thấy
một ứng viên. Không bật fallback tự đọc lại. Ghi rõ snapshot timestamp hiện
ở cuối lượt thu thập: filter tuổi không bảo đảm atomic snapshot, từng node có
thể cũ hơn; chưa có freshness đủ cho thực thi.

Label: NFC + gộp khoảng trắng + casefold; giữ nguyên dấu tiếng Việt, dấu câu,
chữ số và ký hiệu. Không fuzzy/edit-distance, bỏ dấu, substring matching,
đoán synonyms, dịch label hay thay `plus` thành `+`. Cấm label rỗng, quá256
ký tự hoặc chứa control characters. Không nhúng label vào lệnh/code.

- Một ứng viên exact label + AXButton + enabled=True + bbox hợp lệ mới có
  thể found, sau tất cả guard.
- Nhiều AXButton trùng nhãn: ambiguous, không chọn đầu tiên, kể cả một nút
  disabled. Ghi chính sách này rõ để deterministic và dễ kiểm thử.
- Nhãn đúng nhưng role khác đã biết không được chọn. Nếu role không rõ ở
  node có exact label, không âm thầm loại để tạo kết quả found giả.
- Candidate disabled/unknown enabled/thiếu bbox: unavailable, không found.
- Không có nhãn khớp chỉ trả not_found khi dữ liệu đủ để kết luận trong cây
  được đọc. Nếu nút chưa có label vì include_labels mặc định tắt hoặc còn
  node có khả năng là ứng viên nhưng thiếu label/role: unavailable với reason
  thiếu bằng chứng. MVP được phép bảo thủ; giải thích policy cho unknowns,
  không chuyển unknown thành not_found nhằm tăng điểm.
- Không khẳng định target không tồn tại ngoài snapshot, ngoài viewport hay
  trong app đang chạy sau thời điểm snapshot.

Bbox là native AX screen points, không phải CSS pixel. Cho phép x/y âm hợp
lệ ở màn hình phụ; không clamp hoặc quy đổi sang tọa độ click. Chỉ kiểm tra
số hữu hạn và kích thước dương. Chưa suy ra visibility từ bbox có giá trị.

## 5. Kiểm thử và benchmark

Tạo ít nhất24 tình huống tổng hợp, gồm positive, absent, duplicate, wrong
role, disabled, unknown enabled, thiếu label/bbox/role, stale, future clock,
truncated, parent/ID sai và Unicode/punctuation. Oracle phải ghi trước gọi
locator; không tính oracle bằng cùng logic locator. Mọi ca/exception nằm
trong mẫu số. Benchmark giả lập không mở Calculator, không có quyền AX.

Scorer tách: found đúng node, found sai, false acceptance trên ca cần từ chối,
false rejection, đúng trạng thái từ chối, error. Found đúng text nhưng sai
node vẫn sai. Report accuracy theo expected status, false acceptances và số
lượt; không gọi tất cả ca từ chối là tác vụ thành công. Không suy benchmark
tổng hợp là chất lượng trên mọi app hoặc kết quả học máy.

Test các nhánh có ý nghĩa, dùng now_ns cố định, không sleep. Kiểm tra result
immutable, purity/không gọi backend, unsupported inputs, negative origins và
thay đổi threshold không đổi oracle. Thêm test scorer bằng một locator cố ý
trả found sai để chắc chắn benchmark báo trượt.

Runner:

```bash
PYTHONPATH=src:. python3 -m benchmarks.desktop_targeting.runner
```

Xuất JSON/Markdown đường dẫn mới vào artifacts/benchmarks/desktop-targeting/;
không ghi đè kết quả cũ. Dataset là synthetic_only, actions=0.

## 6. Demo desktop chỉ đọc

Script nhận label người dùng chỉ định, ví dụ:

```bash
PYTHONPATH=src python3 scripts/check_desktop_targeting.py --label '7' --include-labels
```

Không có --include-labels thì không bật đọc nhãn ngầm: báo hướng dẫn và
không gọi observer để lấy label. Cờ này là opt-in rõ ràng cho demo Calculator.
Khi bật, gọi observe_app đúng một lần với include_labels=True; nếu upstream
permission_required/app_not_running/error thì in summary đúng trạng thái,
không gọi locator với tree rỗng hoặc tự mở app/cấp quyền/thử lại.

Sau snapshot, gọi locator ngay và in summary: trạng thái,reason,snapshot ID,
node ID/role/bbox nếu found,age và candidate_count. Không dump mọi label hay
tiêu đề cửa sổ. Không lưu raw snapshot mặc định; không cần thêm chức năng
ghi snapshot vì spike quan sát đã có công cụ riêng.

Không click/gõ/AX action, đổi focus, mở app hay activate. Người dùng mở
Calculator bằng tay. Nếu label7/+ không được AX cung cấp như dự kiến, báo
unavailable/not_found theo bằng chứng, không tự đổi nhãn để lấy pass.
Nếu cần liệt kê label để điều tra, mô tả đề xuất opt-in trong tài liệu trước,
không tự dump. Demo thực tế có thể nhờ người dùng chạy sau khi bàn giao.

## 7. Hoàn thành và báo cáo

Chạy test mới, benchmark giả lập, suite phù hợp và git diff --check. Không
chạy benchmark Vision hoặc download model của nhánh chính.

Bàn giao ngắn gọn: file/API, chính sách unknown/duplicates/freshness, số test
và số benchmark observations, false acceptances, native desktop đã/chưa đo,
bug/vướng mắc và giải pháp, lệnh demo. Nếu sandbox chặn, vẫn hoàn thành
pure locator/tests/runner, ghi chưa native verified. Không tự cấp quyền hay
khẳng định desktop thành công từ fake tests.

Điểm dừng: locator chỉ đọc và được kiểm thử; chưa nối AIMS hoặc executor.
Nhánh chính sẽ review trước tích hợp, freshness verifier và action adapter
là công việc riêng.
