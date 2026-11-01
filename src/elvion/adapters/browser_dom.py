from elvion.core.contracts import (CapabilityDescriptor, Method, ProbeResult, ActionResult,
    ActionStatus, ErrorCode, Observation, ObservationStatus)
from elvion.planning.web import APP, CAPABILITIES, valid_web_intent
from elvion.browser.session import BrowserError

WEB_FAILURE_REASONS = frozenset({
    'WEB_BROWSER_UNAVAILABLE', 'WEB_BROWSER_CLOSED', 'WEB_NAVIGATION_UNCERTAIN',
    'WEB_SEARCH_NOT_VERIFIED', 'WEB_RESULT_EXPIRED', 'WEB_ACTION_DENIED',
    'WEB_REDIRECT_OUTSIDE_SCOPE',
})


class BrowserDOMAdapter:
    def __init__(self, session, capability, *, method=Method.DOM, grounder=None):
        self.session, self.capability = session, capability
        self.method, self.grounder = method, grounder

    @property
    def descriptor(self):
        return CapabilityDescriptor(name='browser.'+self.method.value+'.'+self.capability, platform='macos', app=APP,
            method=self.method, required_permissions=(self.capability,), supported_actions=(self.capability,),
            can_verify=True, estimated_latency_ms=1000, simulated=False)

    def probe(self, intent):
        supported = intent.capability == self.capability and valid_web_intent(intent, self.session)
        ready = supported and self.session.available()
        if ready and intent.capability == 'web.open_result':
            try:
                if self.method == Method.VISION:
                    self.grounder.provider.check_local()
                else:
                    locator = self.session.result_locator(intent.arguments['handle'])
                    ready = locator.count() == 1 and locator.is_visible()
            except Exception:
                ready = False
        return ProbeResult(adapter_id=self.descriptor.name, method=self.method, supported=supported,
                           prerequisites_met=ready, reason='WEB_BROWSER_READY' if ready else 'WEB_BROWSER_UNAVAILABLE')

    def execute(self, intent, token):
        if intent.capability != self.capability or not token.permits(intent) or not valid_web_intent(intent, self.session):
            return ActionResult(status=ActionStatus.FAILED, method=self.method, error_code=ErrorCode.PERMISSION_DENIED)
        try:
            authorized = lambda: token.permits(intent)
            if intent.capability == 'web.open_result':
                self.session.open_result(intent.arguments['handle'], authorized=authorized,
                    mode='vision' if self.method == Method.VISION else 'dom', grounder=self.grounder)
            elif intent.capability == 'web.search': self.session.search(intent.arguments['query'], authorized=authorized)
            else: self.session.navigate(intent.arguments['url'], authorized=authorized)
        except Exception as error:
            reason = (str(error) if isinstance(error, BrowserError) and str(error) in WEB_FAILURE_REASONS
                      else 'WEB_DRIVER_FAILURE')
            return ActionResult(status=ActionStatus.UNCERTAIN, method=self.method,
                error_code=ErrorCode.UNCERTAIN_EXTERNAL_EFFECT, external_effect_possible=True,
                evidence={'reason': reason})
        return ActionResult(status=ActionStatus.SUCCESS, method=self.method, external_effect_possible=True)

    def observe(self, request):
        if request.app != APP or request.kind != 'web_state' or request.subject_id != 'active-page':
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.UNSUPPORTED)
        try:
            state = self.session.state()
            if state is None: raise ValueError
            return Observation(status=ObservationStatus.OBSERVED, data=state)
        except Exception:
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.VERIFICATION_FAILED)
