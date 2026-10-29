"""Deterministic baseline: filter candidates before applying method priority."""
from elvion.core.contracts import Method, ProbeResult

PRIORITY = {Method.NATIVE_API: 0, Method.ACCESSIBILITY: 1, Method.DOM: 2, Method.VISION: 3}


def select(probes: list[ProbeResult], *, policy_allowed: bool) -> tuple[str | None, list[dict]]:
    candidates = []
    for probe in probes:
        if not policy_allowed:
            reason = "POLICY_DENIED"
        elif not probe.supported:
            reason = "UNSUPPORTED"
        elif not probe.prerequisites_met:
            reason = probe.reason
        else:
            reason = "ELIGIBLE"
        candidates.append({"adapter_id": probe.adapter_id, "method": probe.method.value,
                           "eligible": reason == "ELIGIBLE", "reason": reason,
                           "priority": PRIORITY[probe.method]})
    eligible = [c for c in candidates if c["eligible"]]
    winner = min(eligible, key=lambda c: c["priority"]) if eligible else None
    return (winner["adapter_id"] if winner else None), candidates
