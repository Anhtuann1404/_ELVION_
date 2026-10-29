"""Deny by default; capability grants and action confirmations are independent."""
from datetime import timedelta

from elvion.core.contracts import (
    ActionIntent, AuthorizationToken, ConfirmationRequest, ConfirmationResponse, utc_now,
)
from elvion.policy.confirmation import ConfirmationManager


class PermissionDenied(ValueError):
    pass


class CapabilityPolicy:
    version = "base-v1"

    def __init__(self, *, require_confirmation: bool = False,
                 confirmations: ConfirmationManager | None = None):
        self.require_confirmation = require_confirmation
        self.confirmations = confirmations if confirmations is not None else ConfirmationManager()

    def allows(self, intent: ActionIntent, grants: frozenset[str]) -> bool:
        return False

    def requires_confirmation(self, intent: ActionIntent) -> bool:
        return self.require_confirmation

    def confirmation_effects(self, intent: ActionIntent) -> tuple[str, ...]:
        return ()

    def request_confirmation(self, intent: ActionIntent, grants: frozenset[str]) -> ConfirmationRequest:
        if not self.allows(intent, grants):
            raise PermissionDenied("Action is outside policy or missing capability grant")
        return self.confirmations.create(intent, additional_effects=self.confirmation_effects(intent))

    def authorize(self, intent: ActionIntent, grants: frozenset[str],
                  response: ConfirmationResponse | None = None) -> AuthorizationToken:
        if not self.allows(intent, grants):
            raise PermissionDenied("Capability is not granted or action is outside policy")
        expires_at = utc_now() + timedelta(minutes=1)
        if self.requires_confirmation(intent):
            approved_request = self.confirmations.consume(intent, response)
            expires_at = min(expires_at, approved_request.expires_at)
        return AuthorizationToken(task_id=intent.task_id, step_id=intent.step_id,
                                  action_digest=intent.digest(), expires_at=expires_at)


class DemoPolicy(CapabilityPolicy):
    version = "demo-v2"

    def allows(self, intent: ActionIntent, grants: frozenset[str]) -> bool:
        return (intent.capability == "note.create" and intent.capability in grants
                and intent.target == {"app": "FakeNotes"} and intent.risk == "low"
                and not intent.preconditions
                and set(intent.arguments) == {"title"}
                and isinstance(intent.arguments["title"], str)
                and bool(intent.arguments["title"].strip())
                and intent.postcondition == {"kind": "note_exists", "title": intent.arguments["title"]})

