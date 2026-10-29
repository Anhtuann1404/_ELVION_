"""All interaction methods here are simulations sharing an in-memory store."""
from dataclasses import dataclass, field
from uuid import uuid4

from elvion.core.contracts import (
    ActionIntent, ActionResult, ActionStatus, AuthorizationToken, CapabilityDescriptor, ErrorCode, Method,
    Observation, ObservationRequest, ObservationStatus, ProbeResult,
)


@dataclass
class FakeNoteStore:
    notes: dict[str, str] = field(default_factory=dict)
    completed: dict[str, tuple[str, str]] = field(default_factory=dict)


class FakeNotesAdapter:
    def __init__(self, method: Method, store: FakeNoteStore, *, available: bool = True):
        self.method = method
        self.store = store
        self.available = available
        self.adapter_id = f"fake_notes.{method.value}"

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(name=self.adapter_id, platform="simulated", app="FakeNotes",
                                    method=self.method, required_permissions=("note.create",),
                                    supported_actions=("note.create",), can_verify=True,
                                    estimated_latency_ms=0, simulated=True)

    def probe(self, intent: ActionIntent) -> ProbeResult:
        supported = intent.capability == "note.create" and intent.target == {"app": "FakeNotes"}
        return ProbeResult(adapter_id=self.adapter_id, method=self.method, supported=supported,
                           prerequisites_met=self.available,
                           reason="SIMULATED_READY" if self.available else "SIMULATED_UNAVAILABLE")

    def execute(self, intent: ActionIntent, token: AuthorizationToken) -> ActionResult:
        if not token.permits(intent):
            return ActionResult(status=ActionStatus.FAILED, method=self.method,
                                error_code=ErrorCode.PERMISSION_DENIED)
        probe = self.probe(intent)
        if not probe.supported or not probe.prerequisites_met:
            return ActionResult(status=ActionStatus.FAILED, method=self.method,
                                error_code=ErrorCode.UNSUPPORTED)
        # Prevent duplicate creation on the same step within this process.
        key = str(intent.idempotency_key)
        previous = self.store.completed.get(key)
        if previous and previous[0] != intent.digest():
            return ActionResult(status=ActionStatus.FAILED, method=self.method,
                                error_code=ErrorCode.PERMISSION_DENIED)
        note_id = previous[1] if previous else str(uuid4())
        if previous is None:
            self.store.notes[note_id] = intent.arguments["title"]
            self.store.completed[key] = (intent.digest(), note_id)
        return ActionResult(status=ActionStatus.SUCCESS, method=self.method,
                            evidence={"note_id": note_id}, external_effect_possible=False)

    def observe(self, request: ObservationRequest) -> Observation:
        if request.app != "FakeNotes" or request.kind != "note":
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.UNSUPPORTED)
        if request.subject_id not in self.store.notes:
            return Observation(status=ObservationStatus.NOT_FOUND, error_code=ErrorCode.TARGET_NOT_FOUND)
        return Observation(status=ObservationStatus.OBSERVED,
                           data={"note_id": request.subject_id, "title": self.store.notes[request.subject_id]})
