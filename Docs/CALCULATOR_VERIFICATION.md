# Calculator: ô nhập hiện tại và kết quả phép tính

## Hợp đồng hiện tại — 31/10/2026

Diagnostic native sau Clear chỉ có AXStaticText/identifier rỗng, parent
AXScrollArea/StandardInputView, window AXWindow. Không có StandardResultView.
Vì nhấn digit7 thay đổi entry, smoke AXPress dùng surface `current_entry`,
không dùng computed result. Lịch sử lỗi nằm ở AXRESULT-001 trong BUG_LOG.md.

Hai API tách biệt:

| Surface | API opt-in | Selector | Expectation |
| --- | --- | --- | --- |
| current_entry | capture_calculator_entry(include_current_entry=True) | Tuple cố định đã quan sát dưới StandardInputView | CalculatorExpectation(surface='current_entry') |
| result | capture_calculator_result(include_result=True, profile=...) | Profile result đã review, từ chối StandardInputView | CalculatorExpectation() mặc định result |

`ResultRegionProfile.surface` mặc định result để tương thích API cũ.
Trường observation.result_text giữ tên cũ nhưng chỉ được diễn giải cùng
profile.surface. Hai observation phải cùng surface, profile, session, process
và thời gian hợp lệ. Result expectation không chấp nhận entry observation.
Entry profile cố định, không dựa vào expected value hoặc vị trí. Native vẫn
phải duyệt đủ, có một window và đúng một region; không fallback sang result,
history hoặc node khác. Không gọi model, không sửa chuỗi thành số mong muốn.

### Native AX formatting

Diagnostic native phát hiện U+200E ở mép chuỗi một chữ số. Parser chung
`parse_display_number` chỉ bỏ LRM U+200E và ASCII spaces ở hai mép rồi
kiểm tra grammar số ASCII. Không xóa LRM nội bộ, các bidi control khác,
dấu âm, decimal hoặc toán tử. Raw observation không thay đổi. Cùng parser
được dùng bởi verifier và precondition action. Chờ smoke native sau sửa;
unit/fake tests không chứng minh desktop đã chuyển 0→7.

## Smoke chỉ đọc được dùng cho Task A

```sh
PYTHONPATH=src python3 scripts/check_calculator_verification.py --include-current-entry
```

Người dùng mở Calculator và tự đưa về 0 trước Enter đầu. Sau đó tự nhấn 7,
rồi Enter lần hai. Không gọi AXPress trong demo này. Opt-in entry riêng mới
cho phép đọc giá trị entry; include-result không cấp quyền đọc entry. Không
in raw value, chỉ summary. Hai cờ cùng lúc hoặc kèm profile result trong entry
mode bị từ chối để tránh nhầm scope.

Verified nghĩa là quan sát numeric entry 0→7; không chứng minh đã tính toán,
causality, quyền thực thi hoặc exactly-once. Số 17/-7/7.1 không khớp 7;
biểu thức như 1+6 trả unsupported format. History không được đọc. Cấu trúc
native đúng không chứng minh AXValue trả string; vẫn chờ smoke value thật.

## Phần thiết kế result v1 và các ghi nhận trước khi tách surface

Các phần dưới đây là mô tả v1 cho computed result. Không dùng ví dụ result
v1 làm kiểm chứng cho thao tác chỉ nhấn digit7. Giới hạn identity/TOCTOU và
clock vẫn áp dụng cho cả hai surface.

# Calculator result transition verification — read-only spike

## Design

The verifier recognizes **only an observed 0 → 7 transition** from the result region of an already-running `com.apple.calculator`. `verified` means the postcondition and a change between two observations were observed. It does not prove ELVION caused the change or that an action occurred exactly once. All outcomes carry `actions=0`, `authority_granted=false`, `action_causality_proven=false`.

The existing desktop observer does not read AXValue and its snapshot node IDs are local to one traversal. The available native smoke identifies button 7, geometry and sampled visibility, but **does not establish the result region's AX role, identifier, parent, mode or locale**. This spike therefore requires a reviewed `ResultRegionProfile` with an exact role, identifier, parent role and parent identifier, plus a known `en_US` simple decimal display format. It selects a unique node by those structural attributes within exactly one AXWindow. It never chooses a node by value, expected text, first position or size. Missing, duplicate or changed structure returns `unknown`. A separately opted-in diagnostic can list a bounded set of role/identifier/parent metadata for candidate text nodes, without AXValue; it is for profile review, not automatic profile creation. Without a reviewed profile, `capture_calculator_result(include_result=True)` returns `unknown/REGION_PROFILE_REQUIRED` before AX traversal. This is intentional until the user's desktop diagnostic establishes the contract.

With explicit `include_result=True` **and** a reviewed profile, the collector uses public AX to traverse at most 300 nodes/depth 12 for at most 4 seconds, then reads `kAXValueAttribute` **only on the uniquely bound result node**. It reads no other AXValue, history, clipboard, selection or other app. `include_result=False` does not invoke native or traverse. Raw value lives in the returned in-memory observation; CLI/benchmark reports contain only status and match booleans. The backend transmits a fixed JSON descriptor on stdin, uses `shell=False`, bounded I/O and timeout, strict output decoding, and a source-hash binary under `artifacts/native/`.

Each observation records bundle, PID, `NSRunningApplication.launchDate` marker, random observation ID and process-local session ID, same-host/session provenance, Python monotonic capture start/end, structural uniqueness and region fingerprint, permission state, and optionally the result text. The native reference exists only inside its helper process. Matching region attributes across captures does **not** prove native-object continuity. The verifier accepts two independent observations only when both carry trusted same-session provenance, matching session ID/PID/process marker/profile binding, ordered monotonic intervals and a bounded age measured from the **start** of the before capture. It never subtracts Swift `systemUptime` from Python `time.monotonic_ns`. Imported observations do not gain trust by having plausible numbers; the boolean and session ID are caller-provided evidence, not an authentication mechanism. Limits are observational guardrails, not action freshness guarantees.

V1 normalization accepts simple ASCII decimal strings only, optionally surrounded by ordinary ASCII spaces; it preserves signs and decimal points and uses full-string equality for `0` and `7`. Thus `17`, `-7`, and `7.1` are valid values that fail the expectation. Grouping separators, expressions and unknown locale remain unsupported. `precondition_not_met` maps to `not_verified` with reason `BEFORE_VALUE_NOT_ZERO` when a valid simple result is known and differs from 0. Missing/unsupported format is `unknown`. The expectation is fixed at schema/policy version 1, `before_value='0'`, `after_value='7'`; request text and expected value are never used to populate observed value. No retry, fallback, model, action or result from an adapter is accepted as observation.

The branch integrating executor should provide a monotonic `action_started_ns`/`action_finished_ns` receipt and session binding **separately** if it needs to relate observations to its own action. This verifier deliberately makes no causal claim from such a receipt. A later integration should also validate the actual result-region profile on each supported macOS/Calculator locale/mode and preserve the current unknown fallback.

Public API references checked against the macOS SDK `AXAttributeConstants.h`: `kAXRoleAttribute`, `kAXIdentifierAttribute`, `kAXValueAttribute`; public AX read functions are in `AXUIElement.h`. [Apple AX documentation](https://developer.apple.com/documentation/applicationservices/axuielement_h) and [NSRunningApplication](https://developer.apple.com/documentation/appkit/nsrunningapplication) describe these APIs. No private API is used.

## Desktop use

First run the diagnostic only when reviewing a region profile:

```sh
PYTHONPATH=src python3 scripts/check_calculator_verification.py --diagnose-region
```

After reviewing a unique result-region identifier/role/parent pair, run the read-only two-capture demo with the corresponding profile options:

```sh
PYTHONPATH=src python3 scripts/check_calculator_verification.py --include-result \
  --result-role AXTextField --result-identifier 'REVIEWED_ID' \
  --parent-role AXGroup --parent-identifier 'REVIEWED_PARENT_ID'
```

The command waits for Enter before each capture. The user manually sets Calculator to 0 before the first Enter and manually presses 7 before the second. It never presses buttons itself. The placeholders above are **not** claims about Calculator's actual AX structure. If a profile cannot be established, stop with `unknown`.

## Verification in this agent session

`unittest` collected and passed 11 new tests. The fixed synthetic benchmark passed 41/41 observations with zero false verified and zero actions. The Swift helper compiled; direct protocol probes accepted integer schema 1 and rejected boolean, floating-point and escaped duplicate-key versions. The opt-in structural diagnostic returned `APP_NOT_RUNNING` with no candidates in this agent session; no result value was read, so there is no live 0 → 7 verification here. This does not imply Calculator is unavailable or lacks Accessibility permission in the user's own Terminal session. `git diff --check` passed.

## BUG_LOG handoff proposal

Known limitation: current native smoke proves button targeting/revalidation but not the Calculator result-region AX contract. Symptom: without a reviewed structural profile, a value `7` could belong to a button, expression or history. Evidence: existing observation excludes AXValue and the agent environment cannot read Calculator AX; this spike returns `REGION_PROFILE_REQUIRED`. Impact: a desktop executor cannot yet verify a 0 → 7 postcondition on every host/locale/mode. Status: implemented conservative verifier, awaiting desktop profile and native capture. Next: run bounded diagnostic on the user's Calculator, review role/identifier/parent and locale, then test the opt-in two-capture demo; retain identity/causality limits.

Implementation issue found and fixed: initial Swift JSON decoding accepted `version:true` as schema 1 because Foundation bridged a boolean to `NSNumber`; `JSONSerialization` also collapsed duplicate keys. The helper now checks CF number type and integer encoding and scans decoded top-level key spellings for duplicates before parsing. Direct probes confirmed integer 1 accepted, while boolean, floating-point and escaped duplicate versions exit with protocol error. This is fixed at the helper boundary; live result-region binding remains unverified.


## Native structural profile integration — 31/10/2026

The user's structure-only diagnostic found AXStaticText with no identifier
under AXScrollArea/StandardResultView and a separate input node under
StandardInputView. Empty child identifiers are now accepted ONLY for the
exact reviewed tuple (AXStaticText, '', AXScrollArea, StandardResultView).
This matches an absent/empty identifier, not arbitrary identifiers. Full
traversal and unique window/result-region guards remain required. The known
StandardInputView container is rejected even if a child has a nonempty ID.
No profile is selected by expected value, position or traversal order.

Read-only smoke for this observed structure:

```sh
PYTHONPATH=src python3 scripts/check_calculator_verification.py \
  --include-result --result-role AXStaticText --result-identifier '' \
  --parent-role AXScrollArea --parent-identifier StandardResultView
```

The user sets 0 before the first Enter, then manually presses 7 before the
second Enter. The script performs no AXPress. Structure-only diagnostic and
helper compilation do not yet prove AXValue provides the result; native
0→7 observation still needs confirmation. Keep unknown if value unavailable.


### Native NOT_FOUND follow-up

The user's first capture still returned RESULT_REGION_NOT_FOUND. Do not
infer AXValue failure: selection has not succeeded. Structural diagnostics
now include window_role (AXWindow or empty) and helper_source_sha256. Run
--diagnose-region after manually clearing to 0 to compare the actual initial
state with the earlier diagnostic. This reads structure only and does not
relax window/uniqueness guards or read the input region's value.


## Native smoke confirmed — 31/10/2026

User desktop read-only demo returned verified/ENTRY_TRANSITION_OBSERVED,
surface=current_entry, transition_observed=true, observed_matches_expected=true.
Actions remained zero; authority and causality remained false. This confirms
one manual 0→7 native entry transition with the structural profile and LRM
parser, not automated AXPress or broad format/locale coverage.
