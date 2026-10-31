"""Task B integration: fresh result observations, never AXPress return codes."""
import time
from elvion.calculator_verification.formatting import parse_display_number


class CalculatorResultReader:
    def __init__(self, profile):
        self.profile = profile
        self.backend = None

    def prepare(self):
        # Task B may be absent/in progress; absence must not enable dispatch.
        from elvion.calculator_verification.contracts import ResultRegionProfile
        from elvion.calculator_verification.observer import NativeResultBackend
        from elvion.calculator_verification.verifier import _valid_profile
        p = self.profile
        if not _valid_profile(p) or p.surface!='current_entry':
            raise ValueError('VERIFIER_PROFILE_REQUIRED')
        self.backend = NativeResultBackend()
        self.backend.prepare()

    def capture(self):
        from elvion.calculator_verification import capture_calculator_entry
        return capture_calculator_entry(include_current_entry=True,backend=self.backend)

    def is_zero(self, observation, target, now_ns):
        from elvion.calculator_verification.contracts import CalculatorObservation
        from elvion.calculator_verification.observer import SESSION_ID
        o = observation
        return (type(o) is CalculatorObservation and o.status=='observed' and
                o.bundle_id=='com.apple.calculator' and type(o.pid) is int and
                bool(o.observation_id) and o.session_id==SESSION_ID and
                o.native_identity_continuity_proven is False and
                o.profile==self.profile and o.profile.reviewed is True and
                o.profile.surface=='current_entry' and
                o.provenance is True and o.same_host_session is True and
                o.permission_granted is True and o.region_unique is True and
                o.result_included is True and type(o.result_text) is str and
                parse_display_number(o.result_text)=='0' and o.pid==target['pid'] and
                o.process_marker==target['process_marker'] and
                type(o.capture_start_ns) is int and type(o.capture_end_ns) is int and
                0 < o.capture_start_ns <= o.capture_end_ns <= now_ns and
                now_ns-o.capture_start_ns <= 2_000_000_000)

    def verify(self, before, after, now_ns):
        from elvion.calculator_verification import verify_result_transition,CalculatorExpectation
        result = verify_result_transition(before,after,CalculatorExpectation(surface='current_entry'),now_ns=now_ns)
        return (result.status=='verified' and result.transition_observed is True and
                result.action_causality_proven is False)


def verify_calculator_transition(intent, result, adapter):
    before, dispatch_ns = adapter.baseline_for(intent.step_id)
    if before is None or dispatch_ns is None:
        return False
    after = adapter.reader.capture()  # independent read after the native receipt
    if not (before.capture_end_ns <= dispatch_ns < after.capture_start_ns):
        return False
    return adapter.reader.verify(before, after, time.monotonic_ns())
