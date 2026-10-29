"""Run a bounded single-step task through shared policy and adapter contracts."""
from collections.abc import Callable
from dataclasses import dataclass, field, replace
import time
from uuid import UUID

from elvion.adapters.registry import AdapterRegistry
from elvion.core.adapter import Adapter
from elvion.aims.selector import select
from elvion.core.contracts import (
    ActionIntent, ActionResult, ActionStatus, ConfirmationRequest, ConfirmationResponse, Contract,
    ContractError, ErrorCode, Method, TaskRequest, TaskStatus, utc_now,
)
from elvion.planning.rules import UnsupportedCommand, plan
from elvion.storage.traces import TraceSession, TraceStorageError, TraceStore
from elvion.policy.confirmation import ConfirmationError, ConfirmationRejected
from elvion.policy.rules import CapabilityPolicy, PermissionDenied

ConfirmationHandler = Callable[[ConfirmationRequest], ConfirmationResponse]


@dataclass(frozen=True, kw_only=True)
class TaskReport(Contract):
    task_id: UUID
    trace_id: UUID
    status: TaskStatus
    message: str
    selected_method: Method | None
    error_code: ErrorCode | None
    events: list[dict]
    evidence: dict = field(default_factory=dict)
    simulated: bool = True
    confirmation_request: ConfirmationRequest | None = None
    duration_ms: float = 0.0
    capability: str | None = None
    policy_version: str | None = None
    trace: dict = field(default_factory=lambda: {"status": "disabled", "path": None,
                                               "records_written": 0, "error_code": None})


Verifier = Callable[[ActionIntent, ActionResult, Adapter], bool]
Planner = Callable[[TaskRequest], ActionIntent]


class TaskOrchestrator:
    def __init__(self, *, registry: AdapterRegistry, policy: CapabilityPolicy,
                 verifier: Verifier, simulated: bool, planner: Planner | None = None,
                 success_message: str | None = None, trace_store: TraceStore | None = None):
        self.registry = registry
        self.policy = policy
        self.verifier = verifier
        self.simulated = simulated
        self.planner = planner if planner is not None else plan
        self.success_message = success_message
        self.trace_store = trace_store
        self._validate_mode()

    def _validate_mode(self) -> None:
        if any(adapter.descriptor.simulated != self.simulated for adapter in self.registry.all()):
            raise ContractError("Registry adapters do not match the explicit execution mode")

    @property
    def adapters(self):
        return self.registry.all()

    def run(self, request: TaskRequest, grants: frozenset[str] = frozenset(), *,
            confirmation_handler: ConfirmationHandler | None = None) -> TaskReport:
        started = time.perf_counter()
        session = None
        storage = {"status": "disabled", "path": None, "records_written": 0, "error_code": None}
        if self.trace_store is not None:
            try:
                session = self.trace_store.start(task_id=request.task_id, trace_id=request.trace_id)
            except TraceStorageError as error:
                storage = {"status": "failed", "path": None, "records_written": 0, "error_code": error.code}
        try:
            report = self._run(request, grants, confirmation_handler=confirmation_handler,
                               session=session, started=started)
            if session is not None:
                session.write({"task_id": report.task_id, "trace_id": report.trace_id,
                               "created_at": utc_now(), "status": report.status,
                               "selected_method": report.selected_method, "error_code": report.error_code,
                               "duration_ms": report.duration_ms, "capability": report.capability,
                               "policy_version": report.policy_version, "simulated": report.simulated,
                               "evidence": report.evidence}, kind="task_result")
        finally:
            # Exceptions/interruptions also close the FD; events remain readable as an incomplete trace.
            if session is not None:
                session.close()
        if session is not None:
            storage = session.summary()
        return replace(report, trace=storage)

    def _run(self, request: TaskRequest, grants: frozenset[str], *,
             confirmation_handler: ConfirmationHandler | None, session: TraceSession | None,
             started: float) -> TaskReport:
        self._validate_mode()
        capability = None
        events = []
        selected_method = None

        def event(status: TaskStatus, message: str, **details) -> None:
            events.append({"task_id": str(request.task_id), "trace_id": str(request.trace_id),
                           "status": status.value, "message": message,
                           "created_at": utc_now(), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), **details})
            if session is not None:
                session.write(events[-1], kind="event")

        def finish(status: TaskStatus, message: str, error: ErrorCode | None = None,
                   evidence: dict | None = None,
                   confirmation: ConfirmationRequest | None = None) -> TaskReport:
            event(status, message)
            return TaskReport(task_id=request.task_id, trace_id=request.trace_id, status=status,
                              message=message, selected_method=selected_method, error_code=error,
                              events=events, evidence=evidence or {}, simulated=self.simulated,
                              confirmation_request=confirmation,
                              duration_ms=round((time.perf_counter() - started) * 1000, 3),
                              capability=capability, policy_version=self.policy.version)

        event(TaskStatus.QUEUED, "Task queued", simulated=self.simulated)
        event(TaskStatus.PLANNING, "Rule-based planning")
        try:
            intent = self.planner(request)
        except UnsupportedCommand:
            return finish(TaskStatus.FAILED, "Unsupported command or app outside allowlist",
                          ErrorCode.UNSUPPORTED)
        capability = intent.capability
        allowed = self.policy.allows(intent, grants)
        probes = self.registry.probe(intent, grants)
        selected_id, candidates = select(probes, policy_allowed=allowed)
        event(TaskStatus.PLANNING, "AIMS baseline selection", step_id=str(intent.step_id),
              policy_version=self.policy.version, capability=capability, candidates=candidates, selected_adapter=selected_id)
        if not allowed:
            return finish(TaskStatus.FAILED, "Permission denied; no action was executed",
                          ErrorCode.PERMISSION_DENIED)
        if selected_id is None:
            reason_codes = {candidate["reason"] for candidate in candidates}
            error = (ErrorCode.TARGET_NOT_FOUND if "TARGET_NOT_FOUND" in reason_codes
                     else ErrorCode.PERMISSION_DENIED if "PERMISSION_DENIED" in reason_codes
                     else ErrorCode.UNSUPPORTED)
            return finish(TaskStatus.FAILED, "No eligible adapter", error)
        adapter = self.registry.get(selected_id)
        selected_method = adapter.descriptor.method
        response = None
        if self.policy.requires_confirmation(intent):
            confirmation = self.policy.request_confirmation(intent, grants)
            if confirmation_handler is None:
                # No resumable task persistence yet: return the preview, but do not leave pending authority.
                self.policy.confirmations.discard(confirmation.confirmation_id)
                return finish(TaskStatus.AWAITING_CONFIRMATION, "No confirmation handler; no execution",
                              ErrorCode.CONFIRMATION_REQUIRED, confirmation=confirmation)
            event(TaskStatus.AWAITING_CONFIRMATION, "Waiting for explicit user approval",
                  confirmation_id=str(confirmation.confirmation_id))
            try:
                response = confirmation_handler(confirmation)
                token = self.policy.authorize(intent, grants, response)
            except ConfirmationRejected:
                return finish(TaskStatus.CANCELLED, "User declined; no execution", ErrorCode.PERMISSION_DENIED)
            except ConfirmationError as exc:
                return finish(TaskStatus.FAILED, "Confirmation rejected or expired; no execution", exc.code)
            except PermissionDenied:
                return finish(TaskStatus.FAILED, "Policy denied the action; no execution", ErrorCode.PERMISSION_DENIED)
            except (EOFError, KeyboardInterrupt):
                return finish(TaskStatus.CANCELLED, "Confirmation interrupted; no execution",
                              ErrorCode.CONFIRMATION_REQUIRED)
            except Exception:
                return finish(TaskStatus.FAILED, "Confirmation handler failed; no execution",
                              ErrorCode.CONFIRMATION_INVALID)
            finally:
                self.policy.confirmations.discard(confirmation.confirmation_id)
        else:
            try:
                token = self.policy.authorize(intent, grants)
            except PermissionDenied:
                return finish(TaskStatus.FAILED, "Policy denied the action; no execution", ErrorCode.PERMISSION_DENIED)
        event(TaskStatus.EXECUTING, "Executing simulated action" if self.simulated else "Executing native macOS action")
        try:
            result = adapter.execute(intent, token)
            if not isinstance(result, ActionResult) or result.method != selected_method:
                raise ContractError("Execution result does not match selected adapter")
        except Exception:
            return finish(TaskStatus.UNCERTAIN, "Adapter exception or invalid result; no automatic retry",
                          ErrorCode.UNCERTAIN_EXTERNAL_EFFECT)
        if result.status == ActionStatus.UNCERTAIN:
            return finish(TaskStatus.UNCERTAIN, "Uncertain outcome; no automatic retry",
                          result.error_code or ErrorCode.UNCERTAIN_EXTERNAL_EFFECT, evidence=result.evidence)
        if result.status == ActionStatus.FAILED:
            return finish(TaskStatus.FAILED, "Adapter failed; no automatic retry", result.error_code, evidence=result.evidence)
        event(TaskStatus.VERIFYING, "Reading state independently of execution status")
        try:
            verified = self.verifier(intent, result, adapter)
        except Exception:
            verified = False
        if not verified:
            return finish(TaskStatus.UNCERTAIN, "Could not verify the postcondition; no retry",
                          ErrorCode.VERIFICATION_FAILED)
        return finish(TaskStatus.SUCCEEDED,
                      self.success_message or ("Fake note created and verified (memory only)" if self.simulated
                      else "Application running state verified; window focus is not verified"),
                      evidence={**result.evidence, "postcondition_verified": True})


class DemoOrchestrator(TaskOrchestrator):
    """Composition root for the fake note demonstration; never accepts real adapters."""

    def __init__(self, *, native_available: bool = True, require_confirmation: bool = False,
                 registry: AdapterRegistry | None = None, trace_store: TraceStore | None = None):
        from elvion.adapters.fake_notes import FakeNotesAdapter, FakeNoteStore
        from elvion.policy.rules import DemoPolicy
        from elvion.verification.notes import verify_note

        self.store = FakeNoteStore()
        registry = registry if registry is not None else AdapterRegistry(tuple(
            FakeNotesAdapter(method, self.store,
                             available=native_available if method == Method.NATIVE_API else True)
            for method in (Method.NATIVE_API, Method.ACCESSIBILITY, Method.VISION)
        ))
        super().__init__(registry=registry, policy=DemoPolicy(require_confirmation=require_confirmation),
                         verifier=verify_note, simulated=True, trace_store=trace_store)
