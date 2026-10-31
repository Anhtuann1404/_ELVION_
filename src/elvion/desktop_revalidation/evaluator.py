"""Pure evaluation of one bounded revalidation observation."""

from .contracts import RevalidationEvidence, RevalidationResult

MAX_AGE_NS = 8_000_000_000
MAX_CAPTURE_NS = 5_000_000_000
MAX_PROBE_NS = 2_000_000_000
HITS = frozenset(('target_or_child', 'other_pid', 'other_window', 'ancestor_only', 'unknown'))


def evaluate_revalidation(evidence: RevalidationEvidence, *, now_ns: int) -> RevalidationResult:
    def result(status, reason):
        return RevalidationResult(status, reason, status == 'ready')

    if type(evidence) is not RevalidationEvidence or type(now_ns) is not int or now_ns <= 0:
        return result('error', 'INVALID_INPUT')
    if (type(evidence.schema_version) is not int or evidence.schema_version != 1 or
            evidence.bundle_id != 'com.apple.calculator' or
            evidence.scope != 'calculator_content' or
            type(evidence.snapshot_id) is not str or not evidence.snapshot_id or
            type(evidence.target_node_id) is not str or not evidence.target_node_id or
            type(evidence.provenance) is not bool or type(evidence.same_host_session) is not bool or
            type(evidence.native_identity_since_snapshot_proven) is not bool or
            evidence.native_identity_since_snapshot_proven or
            any(type(getattr(evidence, key)) is not int for key in
                ('capture_start_ns', 'capture_end_ns', 'probe_start_ns', 'probe_end_ns',
                 'pid_before', 'pid_after', 'native_probe_duration_ns')) or
            any(getattr(evidence, key) is not None and type(getattr(evidence, key)) is not bool
                for key in ('permission_before', 'permission_after', 'binding_before', 'binding_after',
                            'target_enabled_before', 'target_enabled_after', 'target_bbox_stable',
                            'window_bbox_stable', 'display_layout_stable', 'app_hidden_before',
                            'app_hidden_after', 'window_minimized_before', 'window_minimized_after',
                            'hit_test_supported')) or
            any(getattr(evidence, key) is not None and
                (type(getattr(evidence, key)) is not int or getattr(evidence, key) < 0 or getattr(evidence, key) > 300)
                for key in ('target_count_before', 'target_count_after')) or
            type(evidence.hits) is not tuple or len(evidence.hits) > 5 or
            any(type(hit) is not str or hit not in HITS for hit in evidence.hits) or
            any(marker is not None and (type(marker) is not str or len(marker) > 128)
                for marker in (evidence.process_marker_before, evidence.process_marker_after))):
        return result('error', 'INVALID_EVIDENCE')
    if not evidence.provenance or not evidence.same_host_session:
        return result('unknown', 'PROVENANCE_UNAVAILABLE')
    a, b, c, d = (evidence.capture_start_ns, evidence.capture_end_ns,
                  evidence.probe_start_ns, evidence.probe_end_ns)
    if min(a, b, c, d) <= 0 or not a <= b <= c <= d <= now_ns:
        return result('error', 'CLOCK_ORDER_INVALID')
    if b-a > MAX_CAPTURE_NS:
        return result('blocked', 'CAPTURE_TOO_LONG')
    if d-c > MAX_PROBE_NS:
        return result('blocked', 'PROBE_TOO_LONG')
    if evidence.native_probe_duration_ns < 0:
        return result('error', 'CLOCK_ORDER_INVALID')
    if evidence.native_probe_duration_ns > MAX_PROBE_NS:
        return result('blocked', 'PROBE_TOO_LONG')
    if now_ns-a > MAX_AGE_NS:
        return result('blocked', 'EVIDENCE_STALE')
    if evidence.pid_before <= 0:
        return result('unknown', 'PROCESS_ID_UNAVAILABLE')
    if evidence.pid_after == 0:
        return result('blocked', 'APP_NOT_RUNNING')
    if evidence.pid_after < 0:
        return result('error', 'INVALID_EVIDENCE')
    if evidence.pid_before != evidence.pid_after:
        return result('blocked', 'PID_CHANGED')
    if not evidence.process_marker_before or not evidence.process_marker_after:
        return result('unknown', 'PROCESS_INSTANCE_UNAVAILABLE')
    if evidence.process_marker_before != evidence.process_marker_after:
        return result('blocked', 'PROCESS_INSTANCE_CHANGED')
    if evidence.permission_before is False or evidence.permission_after is False:
        return result('blocked', 'AX_PERMISSION_LOST')
    if evidence.permission_before is None or evidence.permission_after is None:
        return result('unknown', 'AX_PERMISSION_UNKNOWN')
    for count in (evidence.target_count_before, evidence.target_count_after):
        if count == 0:
            return result('blocked', 'TARGET_DISAPPEARED')
        if count is not None and count > 1:
            return result('blocked', 'TARGET_DUPLICATE')
    if evidence.target_count_before is None or evidence.target_count_after is None:
        return result('unknown', 'TARGET_COUNT_UNKNOWN')
    if evidence.binding_before is False or evidence.binding_after is False:
        return result('blocked', 'TARGET_BINDING_CHANGED')
    if evidence.target_enabled_before is False or evidence.target_enabled_after is False:
        return result('blocked', 'TARGET_DISABLED')
    for key, reason in (('target_bbox_stable', 'TARGET_MOVED'),
                        ('window_bbox_stable', 'WINDOW_MOVED'),
                        ('display_layout_stable', 'DISPLAY_LAYOUT_CHANGED')):
        if getattr(evidence, key) is False:
            return result('blocked', reason)
    if evidence.app_hidden_before is True or evidence.app_hidden_after is True:
        return result('blocked', 'APP_HIDDEN')
    if evidence.window_minimized_before is True or evidence.window_minimized_after is True:
        return result('blocked', 'WINDOW_MINIMIZED')
    if evidence.hit_test_supported is False:
        return result('unknown', 'HIT_TEST_UNSUPPORTED')
    if any(hit in ('other_pid', 'other_window') for hit in evidence.hits):
        return result('blocked', 'SAMPLED_POINT_BLOCKED')
    required = ('binding_before', 'binding_after', 'target_enabled_before',
                'target_enabled_after', 'target_bbox_stable', 'window_bbox_stable',
                'display_layout_stable', 'hit_test_supported')
    if (any(getattr(evidence, key) is not True for key in required) or
            any(getattr(evidence, key) is not False for key in
                ('app_hidden_before', 'app_hidden_after', 'window_minimized_before',
                 'window_minimized_after'))):
        return result('unknown', 'POST_PROBE_EVIDENCE_INCOMPLETE')
    if len(evidence.hits) != 5 or any(hit != 'target_or_child' for hit in evidence.hits):
        return result('unknown', 'SAMPLED_VISIBILITY_UNCERTAIN')
    return result('ready', 'BOUNDED_AX_SAMPLES_MATCH')
