"""Pure 0 → 7 postcondition verifier; no I/O or native calls."""

from .contracts import CalculatorExpectation, CalculatorObservation, CalculatorVerificationResult, ResultRegionProfile
from .formatting import parse_display_number

MAX_CAPTURE_NS = 5_000_000_000
MAX_TOTAL_AGE_NS = 30_000_000_000

# Observed in the user's structure-only diagnostic. Empty identifier is an
# exact absent/empty attribute, never a wildcard or a value-based selector.
STANDARD_RESULT_STRUCTURE = ('AXStaticText', '', 'AXScrollArea', 'StandardResultView')
STANDARD_ENTRY_STRUCTURE = ('AXStaticText', '', 'AXScrollArea', 'StandardInputView')


def standard_entry_profile():
    return ResultRegionProfile(*STANDARD_ENTRY_STRUCTURE,reviewed=True,surface='current_entry')


def _valid_profile(profile):
    return (type(profile) is ResultRegionProfile and profile.reviewed is True and
            profile.locale == 'en_US' and profile.role in ('AXTextField','AXStaticText','AXTextArea') and
            type(profile.surface) is str and profile.surface in ('result','current_entry') and
            all(type(getattr(profile, key)) is str and
                (0 if key == 'identifier' else 1) <= len(getattr(profile, key)) <= 80 and
                not any(ord(c) < 32 or ord(c) == 127 for c in getattr(profile, key))
                for key in ('role', 'identifier', 'parent_role', 'parent_identifier')) and
            ((profile.surface=='current_entry' and
              (profile.role,profile.identifier,profile.parent_role,profile.parent_identifier)==STANDARD_ENTRY_STRUCTURE) or
             (profile.surface=='result' and profile.parent_identifier!='StandardInputView' and
              (profile.identifier!='' or
               (profile.role,profile.identifier,profile.parent_role,profile.parent_identifier)==STANDARD_RESULT_STRUCTURE))))


def _valid_observation(obs):
    return (type(obs) is CalculatorObservation and type(obs.schema_version) is int and obs.schema_version == 1 and
            obs.status in ('observed', 'unknown', 'error') and
            type(obs.reason) is str and len(obs.reason) <= 80 and
            type(obs.observation_id) is str and len(obs.observation_id) <= 80 and
            type(obs.session_id) is str and len(obs.session_id) <= 80 and
            obs.bundle_id == 'com.apple.calculator' and type(obs.pid) is int and obs.pid >= 0 and
            (obs.process_marker is None or type(obs.process_marker) is str and 1 <= len(obs.process_marker) <= 128) and
            type(obs.same_host_session) is bool and type(obs.provenance) is bool and
            type(obs.capture_start_ns) is int and type(obs.capture_end_ns) is int and
            (obs.permission_granted is None or type(obs.permission_granted) is bool) and
            (obs.profile is None or type(obs.profile) is ResultRegionProfile) and
            (obs.region_unique is None or type(obs.region_unique) is bool) and
            (obs.result_text is None or type(obs.result_text) is str and len(obs.result_text) <= 64) and
            type(obs.result_included) is bool and type(obs.native_identity_continuity_proven) is bool and
            obs.native_identity_continuity_proven is False)


def _number(text):
    return parse_display_number(text)


def verify_result_transition(before: CalculatorObservation, after: CalculatorObservation,
                             expectation: CalculatorExpectation = CalculatorExpectation(),
                             *, now_ns: int) -> CalculatorVerificationResult:
    def out(status, reason, match=None):
        return CalculatorVerificationResult(status, reason, match, status == 'verified')
    if (type(now_ns) is not int or now_ns <= 0 or type(expectation) is not CalculatorExpectation or
            type(expectation.schema_version) is not int or expectation.schema_version != 1 or
            type(expectation.policy_version) is not int or expectation.policy_version != 1 or
            expectation.before_value != '0' or expectation.after_value != '7' or
            type(expectation.surface) is not str or expectation.surface not in ('result','current_entry') or
            not _valid_observation(before) or not _valid_observation(after)):
        return out('error', 'INVALID_INPUT')
    if before.status == 'error' or after.status == 'error':
        return out('error', 'OBSERVATION_ERROR')
    if before.status != 'observed' or after.status != 'observed':
        return out('unknown', 'OBSERVATION_UNAVAILABLE')
    if (not before.provenance or not after.provenance or
            not before.same_host_session or not after.same_host_session or
            not before.session_id or before.session_id != after.session_id):
        return out('unknown', 'PROVENANCE_UNAVAILABLE')
    if (not before.observation_id or not after.observation_id or
            before.observation_id == after.observation_id):
        return out('unknown', 'OBSERVATION_ID_UNUSABLE')
    a, b, c, d = before.capture_start_ns, before.capture_end_ns, after.capture_start_ns, after.capture_end_ns
    if min(a, b, c, d) <= 0 or not a <= b < c <= d <= now_ns:
        return out('error', 'CLOCK_ORDER_INVALID')
    if b-a > MAX_CAPTURE_NS or d-c > MAX_CAPTURE_NS:
        return out('unknown', 'CAPTURE_TOO_LONG')
    if now_ns-a > MAX_TOTAL_AGE_NS:
        return out('unknown', 'EVIDENCE_STALE')
    if before.pid <= 0 or after.pid <= 0 or not before.process_marker or not after.process_marker:
        return out('unknown', 'PROCESS_INSTANCE_UNAVAILABLE')
    if before.pid != after.pid or before.process_marker != after.process_marker:
        return out('unknown', 'PROCESS_INSTANCE_CHANGED')
    if before.permission_granted is not True or after.permission_granted is not True:
        return out('unknown', 'AX_PERMISSION_UNAVAILABLE')
    if not _valid_profile(before.profile) or not _valid_profile(after.profile) or before.profile != after.profile:
        return out('unknown', 'REGION_PROFILE_UNVERIFIED')
    if before.profile.surface!=expectation.surface or after.profile.surface!=expectation.surface:
        return out('unknown','OBSERVATION_SURFACE_MISMATCH')
    if before.region_unique is not True or after.region_unique is not True:
        return out('unknown', 'RESULT_REGION_AMBIGUOUS')
    if not before.result_included or not after.result_included or before.result_text is None or after.result_text is None:
        return out('unknown', 'RESULT_VALUE_UNAVAILABLE')
    first, last = _number(before.result_text), _number(after.result_text)
    if first is None or last is None:
        return out('unknown', 'UNSUPPORTED_RESULT_FORMAT')
    if first != expectation.before_value:
        return out('not_verified', 'BEFORE_VALUE_NOT_ZERO', False)
    if last != expectation.after_value:
        return out('not_verified', 'AFTER_VALUE_NOT_SEVEN', False)
    return out('verified', 'ENTRY_TRANSITION_OBSERVED' if expectation.surface=='current_entry'
               else 'RESULT_TRANSITION_OBSERVED', True)
