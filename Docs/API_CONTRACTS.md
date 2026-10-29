# Hợp đồng nội bộ v0.1 (đề xuất)

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

`CapabilityDescriptor` khai báo `name`, `platform`, `app`, `method` (`native_api | accessibility | dom | vision`), `required_permissions`, `supported_actions`, `can_verify`, `estimated_latency_ms`, `version`. Adapter có các hàm `probe(context) -> ProbeResult`, `execute(intent, context) -> ActionResult`, `observe(context) -> Observation`. Probe không gây tác dụng ngoài. Adapter không tự quyết định xác nhận.

`ActionResult` gồm `status: success | failed | uncertain`, `method`, `evidence`, `error_code`, `retryable`, `external_effect_possible`. Với hành động gửi, gọi, xoá, `uncertain` và `external_effect_possible=true` chặn tự động thử lại.

## Chọn đường và quyền

`SelectRequest` gồm intent, các `ProbeResult`, quyền đang có và ràng buộc thời gian. `SelectResult` gồm `selected_method`, danh sách `candidates` (eligible, score, reason) và `policy_version`. Selector chỉ chọn đường đã qua policy.

`ConfirmationRequest` gồm `confirmation_id`, `step_id`, `action_digest`, `app`, `recipient` nếu có, `preview`, `expires_at`. `ConfirmationResponse` gồm `confirmation_id`, `action_digest`, `approved: boolean`. Nếu nội dung/người nhận thay đổi, digest đổi và phải hỏi lại. Policy quyết định khi nào cần xác nhận; adapter chỉ nhận `AuthorizationToken` phạm vi hẹp, hết hạn nhanh, gắn đúng digest.

## Quyền dùng model cloud

Giai đoạn CLI, model cloud chỉ chạy sau khi người dùng chủ động cho phép theo tác vụ. Phạm vi phải gắn với `task_id`, mục đích, dữ liệu được phép gửi và thời hạn tác vụ. Không tự động fallback sang cloud khi local thất bại. Trước mỗi lần gửi, kiểm tra phạm vi; dữ liệu hoặc mục đích mới cần hỏi lại. Quyền này không thay thế xác nhận hành động gửi tin, sửa hoặc xóa dữ liệu. Schema chi tiết và nhà cung cấp chưa chốt; chưa yêu cầu triển khai cloud trong Sprint 0.

## Lỗi chuẩn

`PERMISSION_DENIED`, `UNSUPPORTED`, `TARGET_NOT_FOUND`, `STALE_OBSERVATION`, `TRANSIENT_FAILURE`, `VERIFICATION_FAILED`, `CONFIRMATION_REQUIRED`, `CONFIRMATION_EXPIRED`, `UNCERTAIN_EXTERNAL_EFFECT`. Không trả thông tin xác thực trong exception, trace hoặc kết quả UI.

## Ví dụ luồng gửi tin

`message.compose` tạo bản nháp → policy tạo confirmation với người nhận, kênh, nội dung → người dùng xác nhận digest → `message.send` qua adapter có quyền → verifier kiểm tra ID/trạng thái gửi nếu nguồn hỗ trợ → `succeeded` hoặc `uncertain`. Tuyệt đối không tự gửi khi chỉ có yêu cầu soạn bản nháp.
