# Desktop revalidation spike (Task B)

## Contract and design

This is one read-only, Calculator-only check of an already running app. `ready` means a freshly reacquired `AXButton` matched the snapshot descriptor and five sampled AX hit tests during one bounded probe. It grants no action authority. Every result has `actions=0`, `authority_granted=false`, `whole_target_visibility_verified=false`, and `freshness_for_execution=false`. The other statuses are `blocked` for a demonstrated violation, `unknown` for missing/ambiguous evidence, and `error` for invalid input or protocol.

The descriptor binds bundle ID, PID plus `NSRunningApplication.launchDate` as a process-instance marker, `calculator_content` scope, label, role, subrole, enabled state, target/window bboxes, and the display layout. Targeting first uses its existing NFC/casefold/whitespace rule. The native probe compares raw AX labels; the demo therefore allows `ready` only for ASCII decimal labels, where that comparison agrees with targeting, and returns `unknown` for other labels. A fresh AX traversal rejects absent and duplicate matching labels. Snapshot `node_id` is only an index in one serialized tree; it is never a native handle. Equal attributes do not prove native object identity. The Swift helper retains the reacquired target and window `AXUIElement` references only within that helper process and rereads them after five hit tests. The result deliberately reports `native_identity_since_snapshot_proven=false`; a consumer requiring native continuity must treat even `ready` as `unknown` for its own purpose. No hash of attributes is used as an ID.

The demo records Python `time.monotonic_ns()` before observation, after observation, and around the native probe, all in one host/session. It computes age from the *start* of observation (8-second bound), bounds observation duration (5 seconds) and probe duration (2 seconds), and rejects future or out-of-order times. These are spike limits, not action freshness guarantees. The existing snapshot timestamp is recorded at the end and is **not** used to prove node age. An imported snapshot or a different clock/session has no trusted start provenance and stays `unknown`. Python and Swift monotonic values are never subtracted from each other. Native probe duration is reported in its own `ProcessInfo.systemUptime` domain.

The native helper reads target/window binding, enabled/minimized/hidden and process marker before and after hit testing. The Python coordinator rereads display layout after the probe. A change blocks `ready`; missing post evidence is `unknown`. Five `AXUIElementCopyElementAtPosition` samples follow the visibility contract; any other PID/window blocks, while ancestor-only or uncertain hits remain `unknown`. Bboxes, PID, or frontmost state alone never establish visibility. Five points do not prove all pixels visible. Matching pre/post samples cannot exclude an intervening change or a race after return.

No retry, fallback, screenshot, OCR, model, AX action, app launch, focus change, or raw AX tree output is performed. The helper uses public AX and AppKit APIs only: [AXUIElementCopyElementAtPosition](https://developer.apple.com/documentation/applicationservices/1462077-axuielementcopyelementatposition), [AXUIElement](https://developer.apple.com/documentation/applicationservices/axuielement_h), [NSRunningApplication](https://developer.apple.com/documentation/appkit/nsrunningapplication), and [kAXMinimizedAttribute](https://developer.apple.com/documentation/applicationservices/kaxminimizedattribute).

## Integration

The pure `evaluate_revalidation(evidence, now_ns=...)` has no I/O. The native backend and demo provide bounded evidence; callers must not turn `ready` into a confirmation token. Run the synthetic suite with `PYTHONPATH=src:. python3 -m benchmarks.desktop_revalidation.runner`. On the user's desktop, open Calculator manually, then run:

```sh
PYTHONPATH=src python3 scripts/check_desktop_revalidation.py --label '7' --include-labels
```

Without `--include-labels`, no label collection starts. The command prints a redacted summary. It does not change Calculator state.

## Verification in the agent session

The Swift helper compiled with macOS Swift 5. Its read-only `begin` probe returned `pid=0`, `permission=false` in this agent session. The opt-in demo stopped with `DISPLAY_LAYOUT_UNAVAILABLE` before AX collection; this says nothing about the user's Terminal permissions. The eight new test functions passed when executed directly; the available Python environments did not have `pytest`. The fixed synthetic benchmark passed 40/40 cases with zero false ready and zero actions. This is not a live `ready` demonstration.

## BUG_LOG handoff proposal

Main-branch owner should record that existing desktop snapshots have only end-of-read timestamps and unstable node IDs. Symptom: a recent-looking snapshot may contain an older node, and matching descriptor attributes cannot prove native continuity. Evidence: `DesktopObservation.swift` timestamp placement and this spike's synthetic long-observation/identity cases. Impact: an executor cannot treat prior snapshot or visibility result as action authority. Status: known limitation; this spike bounds a new observation and checks pre/post but does not close TOCTOU. Next step: integrate a trusted capture-start provenance and an action-time verifier in the executor, with desktop validation under the user's own AX/display permissions.


## Main-branch integration review — 31/10/2026

The main branch reran all eight test functions and the 40-case scorer:
40/40, 2 ready, 22 blocked, 12 unknown, 4 error, zero false ready, zero actions.
Because the project uses unittest and these tests are module-level functions,
load_tests adapters now register them as FunctionTestCase instances. Running
`PYTHONPATH=src:. python3 -m unittest tests.test_desktop_revalidation tests.test_desktop_revalidation_benchmark -q`
collects and passes eight tests without installing pytest. Evaluator/backend
behavior is unchanged. Native Calculator readiness still needs a desktop run.


## User desktop smoke — 31/10/2026

The user supplied a native Calculator summary with status=ready,
reason=BOUNDED_AX_SAMPLES_MATCH and bounded_observation_checks_passed=true.
Actions remained zero; authority, execution freshness, identity continuity
since the previous snapshot and whole-target pixel visibility remained false.
This confirms one positive native smoke under the user's desktop environment,
not an action demonstration or validation of all desktop mutation cases.
