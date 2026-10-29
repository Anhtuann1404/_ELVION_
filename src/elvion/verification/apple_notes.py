"""Read a scoped note again; do not trust the execution response alone."""
from elvion.core.adapter import Adapter
from elvion.core.contracts import ActionIntent, ActionResult, Observation, ObservationRequest, ObservationStatus


def verify_apple_note(intent: ActionIntent, result: ActionResult, adapter: Adapter) -> bool:
    note_id = result.evidence.get("note_id")
    if not isinstance(note_id, str) or not note_id:
        return False
    observation = adapter.observe(ObservationRequest(app=intent.target["app"], kind="note", subject_id=note_id))
    if not isinstance(observation, Observation) or observation.status != ObservationStatus.OBSERVED:
        return False
    data = observation.data
    return (data.get("note_id") == note_id and data.get("title") == intent.arguments["title"]
            and data.get("account") == intent.target["account"]
            and data.get("folder") == intent.target["folder"]
            and data.get("shared") is False and data.get("locked") is False)
