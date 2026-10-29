"""Shared adapter interface; independent of any app, OS or fake implementation."""
from typing import Protocol, runtime_checkable

from elvion.core.contracts import (
    ActionIntent, ActionResult, AuthorizationToken, CapabilityDescriptor,
    Observation, ObservationRequest, ProbeResult,
)


@runtime_checkable
class Adapter(Protocol):
    @property
    def descriptor(self) -> CapabilityDescriptor: ...

    def probe(self, intent: ActionIntent) -> ProbeResult:
        """Read-only capability/readiness check; must not mutate external state."""
        ...

    def execute(self, intent: ActionIntent, token: AuthorizationToken) -> ActionResult:
        """Execute only the exact authorized action, with no self-authorization."""
        ...

    def observe(self, request: ObservationRequest) -> Observation:
        """Read current state independently from execute's success claim."""
        ...
