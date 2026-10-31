"""Hand-authored oracle cases, fixed before calling the locator."""

from dataclasses import dataclass, replace

from elvion.desktop_observation.contracts import DesktopElement, DesktopSnapshot


NOW = 2_000_000_000
BOX = (10.0, -20.0, 40.0, 30.0)  # Negative screen origin is legal.


def node(id, label=None, *, role='AXButton', enabled=True, bbox=BOX, parent='root'):
    return DesktopElement(id, parent, role, None, enabled, bbox, label)


ROOT = DesktopElement('root', None, 'AXApplication', None, True, None, None)


def snapshot(*elements, **changes):
    base = DesktopSnapshot(1, 'synthetic-ax-1', 'com.apple.calculator', 123,
                           '2026-10-31T00:00:00Z', 1_000_000_000,
                           (ROOT,) + tuple(elements), False, None)
    return replace(base, **changes)


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    label: str
    expected_status: str
    expected_node_id: str | None
    ax_snapshot: DesktopSnapshot
    now_ns: int = NOW
    max_age_ms: int = 2000


CASES = (
    Case('ax01_digit', 'positive', '7', 'found', 'seven', snapshot(node('seven', '7'))),
    Case('ax02_plus', 'positive', '+', 'found', 'plus', snapshot(node('plus', '+'))),
    Case('ax03_equals', 'positive', '=', 'found', 'equals', snapshot(node('equals', '='))),
    Case('ax04_vietnamese', 'unicode', 'Cộng', 'found', 'vn', snapshot(node('vn', 'Cộng'))),
    Case('ax05_punctuation', 'punctuation', 'Save.', 'found', 'period', snapshot(node('period', 'Save.'))),
    Case('ax06_whitespace', 'normalization', '  Cộng   ngay  ', 'found', 'space',
         snapshot(node('space', 'Cộng ngay'))),
    Case('ax07_casefold', 'normalization', 'clear', 'found', 'clear', snapshot(node('clear', 'CLEAR'))),
    Case('ax08_negative_origin', 'geometry', '8', 'found', 'eight',
         snapshot(node('eight', '8', bbox=(-250.0, -30.0, 50.0, 50.0)))),
    Case('ax09_absent', 'negative', '9', 'not_found', None, snapshot(node('seven', '7'))),
    Case('ax10_near_punctuation', 'negative', 'Save', 'not_found', None,
         snapshot(node('period', 'Save.'))),
    Case('ax11_diacritic', 'negative', 'Cong', 'not_found', None, snapshot(node('vn', 'Cộng'))),
    Case('ax12_wrong_role', 'wrong_role', '7', 'not_found', None,
         snapshot(node('text', '7', role='AXStaticText'))),
    Case('ax13_disabled', 'unavailable', '7', 'unavailable', None,
         snapshot(node('seven', '7', enabled=False))),
    Case('ax14_enabled_unknown', 'unavailable', '7', 'unavailable', None,
         snapshot(node('seven', '7', enabled=None))),
    Case('ax15_bbox_missing', 'unavailable', '7', 'unavailable', None,
         snapshot(node('seven', '7', bbox=None))),
    Case('ax16_duplicate', 'duplicate', '7', 'ambiguous', None,
         snapshot(node('a', '7'), node('b', '7'))),
    Case('ax17_duplicate_disabled', 'duplicate', '7', 'ambiguous', None,
         snapshot(node('a', '7'), node('b', '7', enabled=False))),
    Case('ax18_label_missing', 'unknown', '7', 'unavailable', None,
         snapshot(node('unknown', None))),
    Case('ax19_role_missing_exact', 'unknown', '7', 'unavailable', None,
         snapshot(node('seven', '7'), node('unknown', '7', role=None))),
    Case('ax20_role_and_label_missing', 'unknown', '7', 'unavailable', None,
         snapshot(node('unknown', None, role=None))),
    Case('ax21_stale', 'freshness', '7', 'stale', None,
         snapshot(node('seven', '7')), now_ns=4_000_000_000),
    Case('ax22_future_clock', 'freshness', '7', 'stale', None,
         snapshot(node('seven', '7')), now_ns=999_000_000),
    Case('ax23_truncated', 'incomplete', '7', 'unavailable', None,
         snapshot(node('seven', '7'), truncated=True, truncation_reason='NODE_LIMIT')),
    Case('ax24_bad_parent', 'invalid', '7', 'error', None,
         snapshot(node('orphan', '7', parent='missing'))),
    Case('ax25_duplicate_id', 'invalid', '7', 'error', None,
         snapshot(node('same', '7'), node('same', '8'))),
    Case('ax26_bad_bbox', 'invalid', '7', 'error', None,
         snapshot(node('seven', '7', bbox=(0.0, 0.0, -1.0, 3.0)))),
    Case('ax27_bad_schema', 'invalid', '7', 'error', None,
         snapshot(node('seven', '7'), schema_version=2)),
    Case('ax28_bool_pid', 'invalid', '7', 'error', None,
         snapshot(node('seven', '7'), pid=True)),
    Case('ax29_threshold_edge', 'freshness', '7', 'found', 'seven',
         snapshot(node('seven', '7')), now_ns=3_000_000_000),
    Case('ax30_unknown_duplicate', 'unknown', '7', 'unavailable', None,
         snapshot(node('seven', '7'), node('unlabelled', None))),
)


def check_cases(cases=CASES):
    if len(cases) < 24 or len({case.id for case in cases}) != len(cases):
        raise ValueError('Expected at least 24 unique cases')
    for case in cases:
        if (case.expected_status not in {'found', 'not_found', 'ambiguous', 'unavailable',
                                         'stale', 'unsupported', 'error'} or
                (case.expected_status == 'found') != (case.expected_node_id is not None)):
            raise ValueError(f'Invalid oracle: {case.id}')
    return cases
