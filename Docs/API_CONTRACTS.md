# Hợp đồng nội bộ v0.1 (thiết kế và phần đã triển khai)

V1 có thể dùng lời gọi Python nội bộ; đây là schema logic, không bắt buộc mở HTTP server. Các adapter tuân theo cùng phiên bản hợp đồng. `task_id`, `step_id`, `trace_id` là UUID; thời gian UTC ISO 8601. Phân biệt lỗi từ chối, thiếu quyền, không hỗ trợ, lỗi tạm thời và kết quả không chắc chắn.

## Lệnh và trạng thái

```json
{"task_id":"uuid","utterance":"Mở ghi chú và tạo ghi chú mới","source":"text","locale":"vi-VN","created_at":"2026-10-29T00:00:00Z"}
```

`TaskStatus`: `queued | planning | awaiting_confirmation | executing | verifying | succeeded | failed | cancelled | uncertain`. Mỗi trạng thái phát kèm `trace_id` và thông báo ngắn, tránh trả về thành công nếu chỉ mới bấm nút.

## Intent, capability và adapter

```json
{"step_id":"uuid","capability":"note.create","target":{"app":"Notes"},"arguments":{"title":"Ý tưởng"},"preconditions":[],"postcondition":{"kind":"note_exists","title":"Ý tưởng"},"risk":"low","idempotency_key":"uuid"}
```

`CapabilityDescriptor` khai báo `name`, `platform`, `app`, `method` (`native_api | accessibility | dom | vision`), `required_permissions`, `supported_actions`, `can_verify`, `estimated_latency_ms`, `version`. Protocol hiện tại: `probe(intent: ActionIntent) -> ProbeResult`, `execute(intent: ActionIntent, token: AuthorizationToken) -> ActionResult`, `observe(request: ObservationRequest) -> Observation`. Descriptor có thêm `simulated` để phân biệt demo và tích hợp thật. Probe không gây tác dụng ngoài. Adapter không tự quyết định xác nhận.

`ActionResult` gồm `status: success | failed | uncertain`, `method`, `evidence`, `error_code`, `retryable`, `external_effect_possible`. Với hành động gửi, gọi, xoá, `uncertain` và `external_effect_possible=true` chặn tự động thử lại.

## Chọn đường và quyền

`SelectRequest` gồm intent, các `ProbeResult`, quyền đang có và ràng buộc thời gian. `SelectResult` gồm `selected_method`, danh sách `candidates` (eligible, score, reason) và `policy_version`. Selector chỉ chọn đường đã qua policy.

`ConfirmationRequest` gồm `confirmation_id`, `step_id`, `action_digest`, `app`, `recipient` nếu có, `preview`, `expires_at`. `ConfirmationResponse` gồm `confirmation_id`, `action_digest`, `approved: boolean`. Nếu nội dung/người nhận thay đổi, digest đổi và phải hỏi lại. Policy quyết định khi nào cần xác nhận; adapter chỉ nhận `AuthorizationToken` phạm vi hẹp, hết hạn nhanh, gắn đúng digest.

## Quyền dùng model cloud

Giai đoạn CLI, model cloud chỉ chạy sau khi người dùng chủ động cho phép theo tác vụ. Phạm vi phải gắn với `task_id`, mục đích, dữ liệu được phép gửi và thời hạn tác vụ. Không tự động fallback sang cloud khi local thất bại. Trước mỗi lần gửi, kiểm tra phạm vi; dữ liệu hoặc mục đích mới cần hỏi lại. Quyền này không thay thế xác nhận hành động gửi tin, sửa hoặc xóa dữ liệu. Schema chi tiết và nhà cung cấp chưa chốt; chưa yêu cầu triển khai cloud trong Sprint 0.

## Lỗi chuẩn

`PERMISSION_DENIED`, `UNSUPPORTED`, `TARGET_NOT_FOUND`, `AMBIGUOUS_TARGET`, `STALE_OBSERVATION`, `TRANSIENT_FAILURE`, `VERIFICATION_FAILED`, `CONFIRMATION_REQUIRED`, `CONFIRMATION_EXPIRED`, `CONFIRMATION_INVALID`, `UNCERTAIN_EXTERNAL_EFFECT`. Không trả thông tin xác thực trong exception, trace hoặc kết quả UI.

## Ví dụ luồng gửi tin

`message.compose` tạo bản nháp → policy tạo confirmation với người nhận, kênh, nội dung → người dùng xác nhận digest → `message.send` qua adapter có quyền → verifier kiểm tra ID/trạng thái gửi nếu nguồn hỗ trợ → `succeeded` hoặc `uncertain`. Tuyệt đối không tự gửi khi chỉ có yêu cầu soạn bản nháp.


## Phần đã triển khai trong demo CLI — 29/10/2026

- `core/contracts.py`: các hợp đồng task/action, ConfirmationRequest/Response, AuthorizationToken, CapabilityDescriptor, ObservationRequest/Observation; kiểm tra khi khởi tạo và serialize JSON.
- `core/adapter.py`: Protocol chung. `adapters/registry.py` đăng ký ID duy nhất, tra cứu và kiểm tra probe có khớp descriptor. Probe lỗi, thiếu quyền adapter hoặc không thể verify bị loại trước AIMS.
- `ObservationRequest` gồm `app`, `kind`, `subject_id`. `Observation` có `status: observed | not_found | unavailable`, `data`, `observed_at`, `error_code`. Verifier kiểm tra cả ID và title, không phụ thuộc FakeNotesAdapter cụ thể.
- `policy/confirmation.py`: tạo preview, lưu request trong bộ nhớ, nhận response, kiểm tra ID/digest/thời hạn và tiêu thụ một lần. Reissue cùng step thu hồi preview cũ. Đổi action cần preview và approval mới.
- CLI `--confirm` bật policy yêu cầu xác nhận cho demo low-risk; các action ngoài whitelist vẫn bị từ chối. Không có cờ tự động đồng ý. Preview/prompt ở stderr, TaskReport JSON ở stdout. `y`, `yes`, `có` cho phép; phản hồi khác hoặc EOF từ chối. Ctrl+C trong lúc chờ hủy tác vụ.
- Capability grant và approval độc lập: `--confirm` không thay thế `--grant note.create`. Policy kiểm tra lại trước cấp token, token không được sống lâu hơn confirmation đã duyệt.
- Approval false trả `cancelled`/`PERMISSION_DENIED`; hết hạn trả `failed`/`CONFIRMATION_EXPIRED`; ID/digest sai hoặc replay trả `failed`/`CONFIRMATION_INVALID`. Không thực thi trong các trường hợp này.
- Không có confirmation handler: trả `awaiting_confirmation` cùng preview và không thực thi; request được bỏ, chưa có resume. Muốn chạy cần tạo tác vụ mới với handler.
- TaskReport và trace có task ID/trace ID/status/method/candidates; không lưu preview, title, token trong events. Preview riêng được hiển thị cho người dùng hoặc trả khi chưa có handler; không lưu xuống đĩa.
- Adapter execute ném exception hoặc trả method sai: `uncertain`, không retry/fallback. Observation lỗi hoặc không khớp: `uncertain`/`VERIFICATION_FAILED`.
- Token/approval chỉ phục vụ tiến trình tin cậy, không phải credential ký số cho IPC hoặc sandbox bảo mật. Dict con vẫn mutable; digest tính lại trước authorize và execute để phát hiện thay đổi.
- DemoOrchestrator chỉ chấp nhận fake. AppOrchestrator dùng registry riêng chứa native adapter simulated=false cho app.open/Calculator; không có gửi tin/xóa hay model/cloud.

SelectRequest/SelectResult dạng dataclass, parser JSON đầu vào tổng quát, thu hồi quyền lưu bền vững,
SQLite/Keychain, helper IPC và quản lý vòng đời dữ liệu còn là các bước sau; trace JSONL đã triển khai bên dưới.


## Native app.open — 29/10/2026

- `run "Mở Máy tính" --grant app.open` tạo intent capability `app.open`, target `{app: "com.apple.calculator"}`, arguments rỗng và postcondition `{kind: "app_running", bundle_id: "com.apple.calculator"}`.
- AppPolicy chỉ cho phép đúng action/target này. Không nhận đường dẫn, URL, shell command hoặc launch arguments từ người dùng. Grant ELVION không cấp hay thay thế quyền hệ điều hành.
- TaskOrchestrator dùng chung luồng cho demo/native; registry phải khớp execution mode. `simulated` trong report phản ánh mode thật; run không có đường dự phòng fake.
- Backend kiểm tra bundle ID/executable tại đường dẫn cố định; dùng `/usr/bin/open -a /System/Applications/Calculator.app` với argv, shell=false. Quan sát qua script JXA cố định gọi AppKit NSRunningApplication, ID truyền bằng argv.
- ObservationRequest: app/subject_id là bundle ID, kind app_running. Data trả bundle_id/running/pids; verifier yêu cầu đúng ID và PID hợp lệ. Hậu điều kiện chỉ là process running, không phải window visible/frontmost.
- App đã chạy: không gọi launch, nhưng verifier vẫn đọc lại. App chưa chạy: gửi launch một lần rồi poll tối đa khoảng 5 giây; một lệnh native có timeout 3 giây nên lần quan sát cuối có thể kéo dài quá mốc poll.
- Lệnh launch nonzero/timeout có thể đã sinh tác dụng, trả uncertain, không retry. Lỗi quan sát trước launch dừng failed; lỗi kiểm chứng sau launch trả uncertain. Missing app được giữ là TARGET_NOT_FOUND trong report/candidate.
- Diagnostics chỉ giữ native exit code và OSStatus dạng số, không ghi raw stderr. Lần thử trong agent: uncertain, TRANSIENT_FAILURE, native_exit_code=1, os_status=-10827. Sau đó, ngày 29/10/2026 người dùng xác nhận Calculator mở thành công trên desktop; chưa cung cấp JSON/trace để đối chiếu kết quả verifier.


## Apple Notes — 29/10/2026

- NotesOrchestrator inject planner theo NotesScope; không đổi demo hoặc run Calculator.
- CLI notes bắt buộc --account, grant note.create/note.find độc lập. Target gồm app com.apple.Notes, account đã chọn, folder ELVION; arguments chỉ title (một dòng, tối đa 256 ký tự).
- Policy `requires_confirmation(intent)` thay bool đơn thuần: note.create thật luôn cần approval dù không truyền --confirm. Confirmation preview thêm effects, bao gồm khả năng tạo folder ELVION nếu thiếu. Find chỉ cần grant, có thể yêu cầu confirmation bằng flag.
- Hai adapter cùng protocol: macos.notes.note.create và macos.notes.note.find. Descriptor required_permissions theo capability; probe chỉ filesystem, không gọi Apple Events.
- JSON request đi stdin; script JXA cố định. Không chọn default account, không đọc body, không thao tác ngoài folder chỉ định. Duplicate account/folder/title trả AMBIGUOUS_TARGET; shared/locked bị chặn.
- Postcondition note_exists/note_found với title; observe(kind=note, subject_id=note_id) được adapter giới hạn trong scope đã cấu hình. Data gồm ID/title/account/folder/shared/locked; verifier kiểm tra khớp toàn bộ.
- Tạo có kiểm tra expires_ms trong JXA trước mutation. Lỗi sau mutation/timeout trả uncertain, không retry. Same-step cache chỉ trong process; chưa bảo đảm dedup xuyên restart.
- TaskReport success_message được inject theo workflow; simulated=false cho Notes thật. Events không chứa title/account/token; stdout report chỉ metadata ID, reason/mã lỗi nếu có.
- Thử read-only trong agent trả failed TRANSIENT_FAILURE, reason AUTOMATION_FAILED, native_error=-2700. Sau đó người dùng cung cấp JSON desktop xác nhận note.create thực thi sau approval và succeeded sau verify, simulated=false, postcondition_verified=true. Đã nhận JSON desktop cho note.find: succeeded sau verifying, simulated=false, postcondition_verified=true và note ID khớp lần tạo. Không lưu ID ghi chú cá nhân trong docs.


## Trace persistence — 29/10/2026

- TaskReport thêm duration_ms, capability, policy_version và trace={status,path,records_written,error_code}. Đây là tình trạng lưu riêng, không thay TaskStatus hoặc tự retry tác vụ.
- CLI bật TraceStore mặc định cho demo/run/notes, có --data-dir và --no-trace. Library API cần inject trace_store; không ghi home ngầm trong unit tests.
- Mỗi event và task_result được project bằng schema v1 trước JSON serialization/fsync. Không copy raw TaskReport/ConfirmationRequest/evidence vào file. Reader cũng áp dụng projection lại.
- Chỉ giữ UUID, timestamp UTC, trạng thái, capability/adapter/method/policy/reason thuộc allowlist, candidates, timing, cờ verify và diagnostics số. Loại utterance, title/account/note_id/preview/token/digest, message và raw stderr.
- TraceStore list/show đọc dữ liệu đã lọc, báo finalized/malformed/partial_tail và chặn file quá lớn. Trace không phục hồi task hay tự tạo nhãn tối ưu cho AIMS.
- File theo UUID, 0600 trong traces/ 0700; không ghi đè, không follow symlink leaf/directory. Implementation hiện dành macOS/Linux; không là kho audit chống sửa đổi.
- Khi log hỏng: task vẫn chạy với events trong RAM; report.trace partial/failed và stderr cảnh báo mã cố định. Không thay đổi kết quả hành động đã thực thi, không tự retry.
