"""Pure, conservative evaluator of one bounded AX probe."""

from math import isfinite
import time

from .contracts import VisibilityEvidence, VisibilityResult


HITS = frozenset(('target_or_child', 'other_pid', 'other_window', 'ancestor_only', 'unknown'))
SCOPES = frozenset(('all_buttons', 'calculator_content'))


def _box(box):
    return (type(box) is tuple and len(box) == 4 and
            all(type(v) in (int, float) and isfinite(v) for v in box) and
            box[2] > 0 and box[3] > 0)


def _inside(child, parent):
    x, y, w, h = child
    px, py, pw, ph = parent
    return px <= x and py <= y and x + w <= px + pw and y + h <= py + ph


def _valid(e):
    if type(e) is not VisibilityEvidence:
        return False
    return (type(e.schema_version) is int and e.schema_version == 1 and
            all(type(v) is str and 0 < len(v) <= 64 and not any(ord(c) < 32 for c in v)
                for v in (e.reference_id, e.snapshot_id, e.target_node_id)) and
            e.bundle_id == 'com.apple.calculator' and type(e.pid) is int and e.pid > 0 and
            e.target_scope in SCOPES and _box(e.target_bbox) and _box(e.window_bbox) and
            e.window_contains_target == _inside(e.target_bbox, e.window_bbox) and
            type(e.display_scale) in (int, float) and isfinite(e.display_scale) and e.display_scale > 0 and
            type(e.snapshot_ns) is int and e.snapshot_ns > 0 and
            type(e.probe_ns) is int and e.probe_ns > 0 and
            all(type(v) is bool for v in (e.same_host_clock, e.target_bound, e.window_bound,
                e.unique_target, e.layout_unchanged, e.state_unchanged,
                e.display_contains_target, e.window_contains_target, e.hit_test_supported)) and
            all(type(v) in (bool, type(None)) for v in
                (e.permission_granted, e.app_hidden, e.window_minimized, e.frontmost)) and
            type(e.hits) is tuple and len(e.hits) <= 5 and all(type(h) is str and h in HITS for h in e.hits))


def evaluate_visibility(evidence: VisibilityEvidence, *, now_ns: int | None = None,
                        max_age_ms: int = 1000) -> VisibilityResult:
    if (type(max_age_ms) is not int or not 1 <= max_age_ms <= 10_000 or
            (now_ns is not None and (type(now_ns) is not int or now_ns <= 0)) or
            not _valid(evidence)):
        return VisibilityResult('error', 'INVALID_EVIDENCE')
    if now_ns is None:
        now_ns = time.monotonic_ns()
    age_ms = (now_ns - evidence.snapshot_ns) / 1_000_000
    base = dict(reference_id=evidence.reference_id, snapshot_id=evidence.snapshot_id,
                bundle_id=evidence.bundle_id, pid=evidence.pid,
                target_node_id=evidence.target_node_id, target_scope=evidence.target_scope,
                age_ms=age_ms if age_ms >= 0 else None, checked_points=len(evidence.hits))

    def result(status, reason, verified=(), unverified=()):
        return VisibilityResult(status, reason, predicates_verified=tuple(verified),
                                predicates_unverified=tuple(unverified),
                                sampled_visibility_verified=(status == 'visible'), **base)

    if not evidence.same_host_clock or now_ns < evidence.snapshot_ns or now_ns < evidence.probe_ns or evidence.probe_ns < evidence.snapshot_ns:
        return result('unknown', 'CLOCK_BINDING_UNVERIFIED', unverified=('same_host_clock', 'time_order'))
    if age_ms > max_age_ms:
        return result('unknown', 'EVIDENCE_STALE', unverified=('freshness',))
    if evidence.permission_granted is not True:
        return result('unknown', 'AX_PERMISSION_UNAVAILABLE', unverified=('permission',))
    if evidence.app_hidden is True:
        return result('blocked', 'APP_HIDDEN', verified=('app_hidden',))
    if evidence.window_minimized is True:
        return result('blocked', 'WINDOW_MINIMIZED', verified=('window_minimized',))
    if evidence.app_hidden is None or evidence.window_minimized is None:
        return result('unknown', 'WINDOW_STATE_UNKNOWN', unverified=('app_hidden', 'window_minimized'))
    if not all((evidence.target_bound, evidence.window_bound, evidence.unique_target,
                evidence.layout_unchanged, evidence.state_unchanged)):
        return result('unknown', 'TARGET_BINDING_UNVERIFIED',
                      unverified=('target_window_layout_state_binding',))
    if not evidence.display_contains_target or not evidence.window_contains_target:
        return result('unknown', 'TARGET_CLIPPED_OR_OFF_DISPLAY',
                      unverified=('display_window_containment',))
    if not evidence.hit_test_supported or len(evidence.hits) != 5:
        return result('unknown', 'HIT_TEST_UNAVAILABLE', unverified=('five_point_hit_test',))
    if any(hit in ('other_pid', 'other_window') for hit in evidence.hits):
        return result('blocked', 'SAMPLED_POINT_OCCLUDED',
                      verified=('target_binding', 'sampled_occlusion'), unverified=('whole_target_pixels',))
    if all(hit == 'target_or_child' for hit in evidence.hits):
        return result('visible', 'FIVE_AX_POINTS_BOUND_TO_TARGET',
                      verified=('target_binding', 'window_state', 'five_point_ax_hit_test'),
                      unverified=('whole_target_pixels', 'execution_freshness'))
    return result('unknown', 'HIT_IDENTITY_UNVERIFIED',
                  verified=('target_binding',), unverified=('all_five_points',))
