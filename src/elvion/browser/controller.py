"""Bounded UI actions: grounding never gets authority to click or supply text."""
import time
from elvion.browser.contracts import GroundingResult, ROLES
from elvion.browser.session import BrowserError
from elvion.aims.selector import select
from elvion.core.contracts import ProbeResult, Method


class BrowserController:
    def __init__(self, session, *, grounder=None, clock=time.monotonic, max_age=10):
        self.session, self.grounder, self.clock, self.max_age = session, grounder, clock, max_age
        self.steps = 0
        self.started = clock()
        self.decisions = []

    def click(self, *, target, role, locator, authorized, mode='auto'):
        if mode not in {'auto', 'dom', 'vision'} or role not in ROLES or not callable(authorized) or not authorized():
            raise BrowserError('WEB_ACTION_DENIED')
        dom = False
        if mode != 'vision' and locator is not None:
            try:
                dom = locator.count() == 1 and locator.is_visible()
            except Exception:
                pass
        probes = [ProbeResult(adapter_id='browser.ui.dom', method=Method.DOM,
                              supported=mode != 'vision', prerequisites_met=dom, reason='WEB_TARGET_UNAVAILABLE'),
                  ProbeResult(adapter_id='browser.ui.vision', method=Method.VISION,
                              supported=mode != 'dom', prerequisites_met=self.grounder is not None, reason='WEB_VISION_UNAVAILABLE')]
        chosen, candidates = select(probes, policy_allowed=authorized())
        self.decisions.append({'chosen':chosen, 'candidates':candidates})
        if chosen == 'browser.ui.vision':
            return self.click_vision(target=target, role=role, authorized=authorized)
        if chosen != 'browser.ui.dom' or self.steps >= 8 or self.clock()-self.started > 60 or not authorized():
            raise BrowserError('WEB_TARGET_UNAVAILABLE')
        self.steps += 1
        self.session.invalidate()
        try:
            locator.click(timeout=8000)
        except Exception:
            # Never switch to vision after an action whose effect is uncertain.
            raise BrowserError('WEB_CLICK_UNCERTAIN') from None

    def click_vision(self, *, target, role, authorized):
        if not callable(authorized) or not authorized() or role not in ROLES or self.grounder is None:
            raise BrowserError('WEB_ACTION_DENIED')
        if self.steps >= 8 or self.clock()-self.started > 60:
            raise BrowserError('WEB_BUDGET_EXHAUSTED')
        self.steps += 1
        frame = self.session.snapshot()
        result = self.grounder.locate(frame, target=target, role=role)
        if not isinstance(result, GroundingResult) or result.status != 'found':
            raise BrowserError('WEB_VISION_ABSTAINED')
        if (result.frame_id != frame.frame_id or self.session.frame_id != frame.frame_id or
                self.session.page_id != frame.page_id or self.session.revision != frame.revision or
                not 0 <= self.clock()-frame.captured_at <= self.max_age or not authorized()):
            raise BrowserError('WEB_STALE_OR_UNAUTHORIZED')
        x, y, width, height = result.bbox
        if x+width > frame.width or y+height > frame.height:
            raise BrowserError('WEB_BOX_OUTSIDE_VIEWPORT')
        # Page/revision alone cannot detect a control moving within the same DOM.
        # Recheck visual evidence, then recheck authority and original frame age.
        if (self.session.frame_is_current(frame) is not True or
                not 0 <= self.clock()-frame.captured_at <= self.max_age or not authorized()):
            raise BrowserError('WEB_STALE_OR_UNAUTHORIZED')
        self.session.invalidate()
        try:
            # Mouse.click has no timeout parameter (unlike Locator.click).
            self.session.page.mouse.click(x+width/2, y+height/2)
        except Exception:
            raise BrowserError('WEB_CLICK_UNCERTAIN') from None
