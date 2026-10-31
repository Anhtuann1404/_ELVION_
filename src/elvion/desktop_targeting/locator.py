"""Pure, conservative exact-label targeting over a supplied AX snapshot."""

from datetime import datetime, timedelta
from collections import Counter
from math import isfinite
import time
import unicodedata

from elvion.desktop_observation.contracts import DesktopElement, DesktopSnapshot

from .contracts import DesktopTargetResult


MAX_NODES = 300
MAX_DEPTH = 12
MAX_LABEL = 256
ROLE = 'AXButton'
BUNDLE = 'com.apple.calculator'
SCOPES = ('all_buttons','calculator_content')
WINDOW_SUBROLES = frozenset(('AXCloseButton','AXMinimizeButton','AXZoomButton','AXFullScreenButton'))


def _text(value, *, maximum=256, optional=False):
    return ((optional and value is None) or
            (type(value) is str and 0 < len(value) <= maximum and
             not any(unicodedata.category(char).startswith('C') for char in value)))


def _normal(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())


def _incomplete_reason(element, normalized):
    if element.role == ROLE and element.label is None:
        return 'BUTTON_LABEL_MISSING'
    if element.role is None and element.label is None:
        return 'ROLE_AND_LABEL_MISSING'
    if element.role is None and _normal(element.label) == normalized:
        return 'EXACT_LABEL_ROLE_MISSING'
    return None


def _scoped_elements(snapshot, scope):
    nodes={element.id:element for element in snapshot.elements}
    excluded=[]
    if scope=='calculator_content':
        excluded=[element for element in snapshot.elements if element.role==ROLE and
                  element.subrole in WINDOW_SUBROLES and element.parent_id is not None and
                  nodes[element.parent_id].role=='AXWindow']
    ids={element.id for element in excluded}
    return tuple(element for element in snapshot.elements if element.id not in ids),excluded


def _box_valid(box) -> bool:
    return (type(box) is tuple and len(box) == 4 and
            all(type(value) in (int, float) and isfinite(value) for value in box) and
            box[2] > 0 and box[3] > 0)


def _snapshot_valid(snapshot) -> bool:
    if type(snapshot) is not DesktopSnapshot:
        return False
    if (type(snapshot.schema_version) is not int or snapshot.schema_version != 1 or
            not _text(snapshot.id, maximum=64) or not _text(snapshot.bundle_id) or
            type(snapshot.pid) is not int or snapshot.pid <= 0 or
            not _text(snapshot.captured_at_utc, maximum=40) or
            type(snapshot.captured_at_monotonic_ns) is not int or
            snapshot.captured_at_monotonic_ns <= 0 or
            type(snapshot.truncated) is not bool or
            snapshot.truncation_reason not in (None, 'TIME_BUDGET', 'NODE_LIMIT', 'DEPTH_LIMIT') or
            snapshot.truncated != (snapshot.truncation_reason is not None) or
            type(snapshot.elements) is not tuple or not 1 <= len(snapshot.elements) <= MAX_NODES):
        return False
    try:
        stamp = datetime.fromisoformat(snapshot.captured_at_utc.replace('Z', '+00:00'))
        if stamp.utcoffset() != timedelta(0):
            return False
    except ValueError:
        return False
    depths = {}
    for index, element in enumerate(snapshot.elements):
        if type(element) is not DesktopElement:
            return False
        if (not _text(element.id, maximum=32) or element.id in depths or
                not _text(element.parent_id, maximum=32, optional=True) or
                not _text(element.role, optional=True) or
                not _text(element.subrole, optional=True) or
                type(element.enabled) not in (bool, type(None)) or
                not _text(element.label, optional=True) or
                (element.bbox is not None and not _box_valid(element.bbox))):
            return False
        if index == 0:
            if element.parent_id is not None:
                return False
            depth = 0
        else:
            if element.parent_id not in depths:
                return False
            depth = depths[element.parent_id] + 1
        if depth > MAX_DEPTH:
            return False
        depths[element.id] = depth
    return True


def locate_control(snapshot: DesktopSnapshot, *, label: str, role: str = ROLE,
                   now_ns: int | None = None, max_age_ms: int = 2000,
                   scope: str = 'all_buttons') -> DesktopTargetResult:
    """Find one exact, enabled button with a native AX bbox in a fresh snapshot."""
    if (type(scope) is not str or scope not in SCOPES or
            type(role) is not str or role != ROLE or type(max_age_ms) is not int or
            not 1 <= max_age_ms <= 10_000 or
            (now_ns is not None and (type(now_ns) is not int or now_ns <= 0)) or
            not _text(label, maximum=MAX_LABEL) or not label.strip()):
        return DesktopTargetResult('unsupported', 'UNSUPPORTED_REQUEST')
    if not _snapshot_valid(snapshot):
        return DesktopTargetResult('error', 'INVALID_SNAPSHOT')
    if snapshot.bundle_id != BUNDLE:
        return DesktopTargetResult('unsupported', 'UNSUPPORTED_BUNDLE')
    if now_ns is None:
        now_ns = time.monotonic_ns()
    age_ns = now_ns - snapshot.captured_at_monotonic_ns
    if age_ns < 0:
        return DesktopTargetResult('stale', 'CLOCK_IN_FUTURE', snapshot_id=snapshot.id,scope=scope)
    age_ms = age_ns / 1_000_000
    if snapshot.truncated:
        return DesktopTargetResult('unavailable', 'TRUNCATED_SNAPSHOT',
                                   snapshot_id=snapshot.id, age_ms=age_ms,scope=scope)
    if age_ms > max_age_ms:
        return DesktopTargetResult('stale', 'SNAPSHOT_EXPIRED',
                                   snapshot_id=snapshot.id, age_ms=age_ms,scope=scope)

    normalized = _normal(label)
    elements,_ = _scoped_elements(snapshot,scope)
    buttons = [element for element in elements
               if element.role == ROLE and element.label is not None and
               _normal(element.label) == normalized]
    count = len(buttons)
    basic = {'snapshot_id': snapshot.id, 'candidate_count': count, 'age_ms': age_ms,'scope':scope}
    if count > 1:
        return DesktopTargetResult('ambiguous', 'DUPLICATE_BUTTONS', **basic)
    uncertain = any(_incomplete_reason(element, normalized) for element in elements)
    if uncertain:
        return DesktopTargetResult('unavailable', 'INCOMPLETE_AX_EVIDENCE', **basic)
    if count == 0:
        return DesktopTargetResult('not_found', 'NO_EXACT_BUTTON', **basic)
    candidate = buttons[0]
    if candidate.enabled is not True:
        return DesktopTargetResult('unavailable', 'BUTTON_NOT_ENABLED', **basic)
    if candidate.bbox is None:
        return DesktopTargetResult('unavailable', 'BUTTON_BBOX_MISSING', **basic)
    return DesktopTargetResult('found', 'EXACT_BUTTON', snapshot_id=snapshot.id,
                               node_id=candidate.id, role=ROLE, enabled=True,
                               bbox=candidate.bbox, candidate_count=1, age_ms=age_ms,scope=scope)


def evidence_summary(snapshot: DesktopSnapshot, *, label: str, scope: str = 'all_buttons') -> dict:
    """Opt-in diagnostic counts/structural IDs only; no labels, boxes or authority."""
    if (type(scope) is not str or scope not in SCOPES or not _snapshot_valid(snapshot) or
            not _text(label) or not label.strip()):
        return {'available':False,'reason':'INVALID_DIAGNOSTIC_INPUT'}
    normalized=_normal(label);counts=Counter();examples=[]
    nodes={element.id:element for element in snapshot.elements}
    elements,excluded=_scoped_elements(snapshot,scope)
    candidates=[element for element in elements if element.role==ROLE and
                element.label is not None and _normal(element.label)==normalized]
    for element in elements:
        reason=_incomplete_reason(element,normalized)
        if reason is None:continue
        counts[reason]+=1
        if len(examples)<8:
            chain=[];parent=element.parent_id
            while parent is not None:
                ancestor=nodes[parent];chain.append({'id':ancestor.id,'role':ancestor.role})
                parent=ancestor.parent_id
            examples.append({'id':element.id,'role':element.role,'subrole':element.subrole,'reason':reason,
                             'ancestor_chain':chain})
    return {'available':True,'nodes':len(snapshot.elements),'blocker_counts':dict(counts),
            'target_scope':scope,'excluded_window_controls':len(excluded),
            'excluded_subroles':dict(Counter(element.subrole for element in excluded)),
            'blocker_examples':examples,'examples_truncated':sum(counts.values())>len(examples),
            'matching_buttons':len(candidates),
            'matching_enabled':sum(c.enabled is True for c in candidates),
            'matching_disabled':sum(c.enabled is False for c in candidates),
            'matching_unknown_enabled':sum(c.enabled is None for c in candidates),
            'matching_with_bbox':sum(c.bbox is not None for c in candidates),
            'scope':'diagnostic only; no labels or click coordinates; does not relax targeting guards'}
