"""Bounded fresh observations; process running is narrower than window/frontmost."""
import time

from elvion.core.adapter import Adapter
from elvion.core.contracts import ActionIntent, ActionResult, ObservationRequest, ObservationStatus


def verify_application(intent: ActionIntent, result: ActionResult, adapter: Adapter, *,
                       timeout_seconds: float = 5.0, interval_seconds: float = 0.2,
                       clock=time.monotonic, sleep=time.sleep) -> bool:
    bundle_id = intent.target.get("app")
    if (intent.postcondition != {"kind": "app_running", "bundle_id": bundle_id}
            or result.evidence.get("bundle_id") != bundle_id):
        return False
    deadline = clock() + timeout_seconds
    while True:
        observation = adapter.observe(ObservationRequest(app=bundle_id, kind="app_running", subject_id=bundle_id))
        if observation.status != ObservationStatus.OBSERVED:
            return False
        data = observation.data
        if (data.get("bundle_id") == bundle_id and data.get("running") is True
                and isinstance(data.get("pids"), list) and data["pids"]
                and all(type(pid) is int and pid > 0 for pid in data["pids"])):
            return True
        if clock() >= deadline:
            return False
        sleep(min(interval_seconds, max(0.0, deadline - clock())))
