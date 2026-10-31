"""Hand-authored oracle before evaluator; no desktop or model calls."""

from dataclasses import dataclass, replace

from elvion.desktop_visibility.contracts import VisibilityEvidence


NOW = 2_000_000_000
GOOD_HITS = ('target_or_child',) * 5
BASE = VisibilityEvidence(
    1, 'probe-1', 'snapshot-1', 'com.apple.calculator', 123, 'n115',
    'calculator_content', (1103.0, -519.0, 48.0, 48.0),
    (1093.0, -706.0, 230.0, 408.0), 1.0,
    1_000_000_000, 1_100_000_000, True, True, True, True, True, True, True,
    True, True, False, False, True, True, GOOD_HITS)


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    expected_status: str
    evidence: VisibilityEvidence
    now_ns: int = NOW
    max_age_ms: int = 1000


def c(id, group, expected, **changes):
    return Case(id, group, expected, replace(BASE, **changes))


CASES = (
    c('v01_center_corners', 'positive', 'visible'),
    c('v02_negative_origin', 'positive', 'visible', target_bbox=(-200.0, -300.0, 40.0, 40.0),
      window_bbox=(-250.0, -400.0, 200.0, 200.0)),
    c('v03_mixed_scale', 'positive', 'visible', display_scale=2.0),
    c('v04_minimized', 'blocked', 'blocked', window_minimized=True, hits=()),
    c('v05_hidden', 'blocked', 'blocked', app_hidden=True, hits=()),
    c('v06_other_pid_opaque', 'overlay', 'blocked', hits=('other_pid',) + GOOD_HITS[1:]),
    c('v07_same_app_popup', 'overlay', 'blocked', hits=('other_window',) + GOOD_HITS[1:]),
    c('v08_transparent_unknown', 'overlay', 'unknown', hits=('unknown',) + GOOD_HITS[1:]),
    c('v09_overlay_unknown', 'overlay', 'unknown', hits=('ancestor_only',) + GOOD_HITS[1:]),
    c('v10_wrong_window_same_pid', 'binding', 'unknown', window_bound=False),
    c('v11_duplicate_label', 'binding', 'unknown', unique_target=False),
    c('v12_ancestor_only', 'hit_identity', 'unknown', hits=('ancestor_only',) * 5),
    c('v13_wrong_child', 'hit_identity', 'unknown', hits=('unknown',) + GOOD_HITS[1:]),
    c('v14_layout_change', 'change', 'unknown', layout_unchanged=False),
    c('v15_geometry_change', 'change', 'unknown', target_bound=False),
    c('v16_state_change', 'change', 'unknown', state_unchanged=False),
    c('v17_off_display', 'geometry', 'unknown', display_contains_target=False),
    c('v18_partial_clipping', 'geometry', 'unknown', window_contains_target=False,
      window_bbox=(1093.0, -706.0, 35.0, 408.0)),
    c('v19_not_frontmost', 'foreground', 'visible', frontmost=False),
    c('v20_missing_minimized', 'missing_field', 'unknown', window_minimized=None),
    c('v21_missing_permission', 'permission', 'unknown', permission_granted=False),
    c('v22_unsupported_hit_test', 'hit_test', 'unknown', hit_test_supported=False, hits=()),
    Case('v23_stale', 'clock', 'unknown', BASE, now_ns=2_000_000_001),
    Case('v24_future_clock', 'clock', 'unknown', BASE, now_ns=999_999_999),
    c('v25_other_session', 'clock', 'unknown', same_host_clock=False),
    c('v26_malformed_bbox', 'protocol', 'error', target_bbox=(0.0, 0.0, -1.0, 10.0)),
    c('v27_bool_pid', 'protocol', 'error', pid=True),
    c('v28_bad_hits', 'protocol', 'error', hits=('target_or_child',) * 6),
)


def check_cases(cases=CASES):
    cases = tuple(cases)
    if len(cases) < 24 or len({case.id for case in cases}) != len(cases):
        raise ValueError('Expected at least 24 distinct cases')
    if any(case.expected_status not in {'visible', 'blocked', 'unknown', 'error'} for case in cases):
        raise ValueError('Invalid oracle status')
    return cases
