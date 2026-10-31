"""Single allowlisted AXPress adapter with durable dispatch reservations."""
import time

from elvion.core.contracts import (ActionResult,ActionStatus,CapabilityDescriptor,ErrorCode,
    Method,Observation,ObservationStatus,ProbeResult)
from elvion.desktop_action.contracts import ADAPTER_ID,BUNDLE,CAPABILITY,READ_GRANT,PressOutcome,supports


class CalculatorAXAdapter:
    def __init__(self, *, backend, reader, journal, current_grants, clock=time.monotonic_ns):
        self.backend,self.reader,self.journal = backend,reader,journal
        self.current_grants,self.clock = current_grants,clock
        self._baseline = {}
        self._dispatch = {}
        self._available = False

    def prepare(self):
        self.backend.prepare()
        self.reader.prepare()
        self._available = True

    @property
    def descriptor(self):
        return CapabilityDescriptor(name=ADAPTER_ID,platform='macos',app=BUNDLE,
            method=Method.ACCESSIBILITY,required_permissions=(CAPABILITY,READ_GRANT),
            supported_actions=(CAPABILITY,),can_verify=self._available,
            estimated_latency_ms=1000,simulated=False)

    def probe(self,intent):
        ready = self._available and supports(intent)
        return ProbeResult(adapter_id=ADAPTER_ID,method=Method.ACCESSIBILITY,
            supported=supports(intent),prerequisites_met=ready,
            reason='CALCULATOR_AX_READY' if ready else 'VERIFICATION_UNAVAILABLE')

    def baseline_for(self,step_id):
        return self._baseline.get(step_id),self._dispatch.get(step_id)

    def execute(self,intent,token):
        def authorized():
            return (supports(intent) and token.permits(intent) and
                    {CAPABILITY,READ_GRANT}.issubset(self.current_grants()))
        def outcome(status,error,reason,possible=False,native_error=None):
            data={'reason':reason}
            if native_error is not None:data['native_error']=native_error
            return ActionResult(status=status,method=Method.ACCESSIBILITY,error_code=error,
                evidence=data,external_effect_possible=possible,retryable=False)
        if not self._available or not authorized():
            return outcome(ActionStatus.FAILED,ErrorCode.PERMISSION_DENIED,'AUTHORIZATION_DENIED')
        try:
            before = self.reader.capture()
            zero = self.reader.is_zero(before,intent.target,self.clock())
        except Exception:
            zero = False
        if not zero:
            return outcome(ActionStatus.FAILED,ErrorCode.VERIFICATION_FAILED,'CALCULATOR_BEFORE_NOT_ZERO_OR_UNKNOWN')
        self._baseline[intent.step_id] = before
        def final_authorized():
            return authorized() and self.reader.is_zero(before,intent.target,self.clock())
        def reserve():
            reserved = self.journal.reserve(intent.idempotency_key,intent.digest())
            if reserved:self._dispatch[intent.step_id] = self.clock()
            return reserved
        pressed = self.backend.press(intent,token,authorized=final_authorized,reserve=reserve)
        if type(pressed) is not PressOutcome or pressed.status not in ('dispatched','blocked','uncertain'):
            raise ValueError('INVALID_PRESS_OUTCOME')
        if pressed.status=='dispatched':
            return outcome(ActionStatus.SUCCESS,None,pressed.reason,True,pressed.native_error)
        if pressed.status=='uncertain' or pressed.external_effect_possible:
            return outcome(ActionStatus.UNCERTAIN,ErrorCode.UNCERTAIN_EXTERNAL_EFFECT,
                pressed.reason,True,pressed.native_error)
        return outcome(ActionStatus.FAILED,ErrorCode.STALE_OBSERVATION,pressed.reason)

    def observe(self,request):
        # Common protocol exposes only safe metadata, not raw display values.
        if request.app!=BUNDLE or request.kind!='calculator_result':
            return Observation(status=ObservationStatus.UNAVAILABLE,error_code=ErrorCode.UNSUPPORTED)
        observed=self.reader.capture()
        return Observation(status=ObservationStatus.OBSERVED if observed.status=='observed'
            else ObservationStatus.UNAVAILABLE,data={'result_available':observed.status=='observed'})
