"""Verify a note through the common adapter interface and typed observation."""
from elvion.core.adapter import Adapter
from elvion.core.contracts import ActionIntent, ActionResult, Observation, ObservationRequest, ObservationStatus


def verify_note(intent: ActionIntent, result: ActionResult, adapter: Adapter) -> bool:
    note_id = result.evidence.get("note_id")
    if not isinstance(note_id, str):
        return False
    observation = adapter.observe(ObservationRequest(app=intent.target["app"], kind="note", subject_id=note_id))
    return (isinstance(observation, Observation) and observation.status == ObservationStatus.OBSERVED
            and observation.data.get("note_id") == note_id
            and intent.postcondition.get("kind") == "note_exists"
            and observation.data.get("title") == intent.postcondition.get("title"))
