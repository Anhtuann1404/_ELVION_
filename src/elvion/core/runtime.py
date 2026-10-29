"""Composition root for the explicitly selected native macOS app workflow."""
from elvion.adapters.macos_apps import MacOSAppAdapter
from elvion.adapters.registry import AdapterRegistry
from elvion.core.orchestrator import TaskOrchestrator
from elvion.policy.apps import AppPolicy
from elvion.verification.apps import verify_application
from elvion.storage.traces import TraceStore


class AppOrchestrator(TaskOrchestrator):
    def __init__(self, *, require_confirmation: bool = False,
                 adapter: MacOSAppAdapter | None = None, trace_store: TraceStore | None = None):
        adapter = adapter if adapter is not None else MacOSAppAdapter()
        super().__init__(registry=AdapterRegistry((adapter,)),
                         policy=AppPolicy(require_confirmation=require_confirmation),
                         verifier=verify_application, simulated=False, trace_store=trace_store)


class NotesOrchestrator(TaskOrchestrator):
    """Real Notes workflow with an explicit scope and an injected scoped planner."""

    def __init__(self, scope, *, require_confirmation: bool = False, backend=None,
                 trace_store: TraceStore | None = None):
        from functools import partial
        from elvion.adapters.apple_notes import AppleNotesAdapter, AppleNotesBackend
        from elvion.planning.notes import plan_notes
        from elvion.policy.notes import NotesPolicy
        from elvion.verification.apple_notes import verify_apple_note

        backend = backend if backend is not None else AppleNotesBackend()
        adapters = tuple(AppleNotesAdapter(scope, capability=capability, backend=backend)
                         for capability in ("note.create", "note.find"))
        super().__init__(registry=AdapterRegistry(adapters),
                         policy=NotesPolicy(scope, require_confirmation=require_confirmation),
                         verifier=verify_apple_note, simulated=False,
                         planner=partial(plan_notes, scope=scope),
                         success_message="Scoped Apple Notes operation verified by a fresh metadata read", trace_store=trace_store)
