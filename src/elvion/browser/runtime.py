from functools import partial
from elvion.adapters.registry import AdapterRegistry
from elvion.adapters.browser_dom import BrowserDOMAdapter
from elvion.core.orchestrator import TaskOrchestrator
from elvion.planning.web import CAPABILITIES, plan_web
from elvion.policy.web import WebPolicy
from elvion.verification.web import verify_web
from elvion.core.contracts import Method


def web_runtime(session, trace_store=None, *, grounder=None):
    adapters = [BrowserDOMAdapter(session, cap) for cap in sorted(CAPABILITIES)]
    if grounder is not None:
        adapters.append(BrowserDOMAdapter(session, 'web.open_result', method=Method.VISION, grounder=grounder))
    return TaskOrchestrator(registry=AdapterRegistry(tuple(adapters)),
        policy=WebPolicy(session), verifier=verify_web, planner=partial(plan_web, session=session),
        trace_store=trace_store, simulated=False, success_message='Browser state independently verified')
