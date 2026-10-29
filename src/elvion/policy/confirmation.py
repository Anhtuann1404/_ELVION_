"""In-memory, single-use confirmations bound to an exact action digest."""
from collections.abc import Callable
from datetime import datetime, timedelta
import json
from uuid import UUID

from elvion.core.contracts import (
    ActionIntent, ConfirmationRequest, ConfirmationResponse, ErrorCode, utc_now,
)


class ConfirmationError(ValueError):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code


class ConfirmationRejected(ConfirmationError):
    def __init__(self):
        super().__init__(ErrorCode.PERMISSION_DENIED, "User declined confirmation")


class ConfirmationManager:
    def __init__(self, *, clock: Callable[[], datetime] = utc_now, ttl_seconds: int = 60):
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("Confirmation TTL must be a positive integer")
        self.clock = clock
        self.ttl_seconds = ttl_seconds
        self._pending: dict[UUID, ConfirmationRequest] = {}

    def create(self, intent: ActionIntent, *, additional_effects: tuple[str, ...] = ()) -> ConfirmationRequest:
        # JSON quotes control characters; callers must not render untrusted raw text as commands.
        preview = json.dumps({"capability": intent.capability, "target": intent.target,
                              "arguments": intent.arguments, "risk": intent.risk,
                              "effects": list(additional_effects)},
                             ensure_ascii=False, sort_keys=True)
        request = ConfirmationRequest(
            step_id=intent.step_id, action_digest=intent.digest(), app=intent.target["app"],
            preview=preview, recipient=intent.arguments.get("recipient"),
            expires_at=self.clock() + timedelta(seconds=self.ttl_seconds),
        )
        # Only one outstanding confirmation per step; re-issuing revokes the earlier preview.
        self._pending = {key: value for key, value in self._pending.items()
                         if value.step_id != intent.step_id and value.expires_at > self.clock()}
        self._pending[request.confirmation_id] = request
        return request

    def consume(self, intent: ActionIntent, response: ConfirmationResponse | None) -> ConfirmationRequest:
        if response is None:
            raise ConfirmationError(ErrorCode.CONFIRMATION_REQUIRED, "Confirmation is required")
        if not isinstance(response, ConfirmationResponse):
            raise ConfirmationError(ErrorCode.CONFIRMATION_INVALID, "Invalid confirmation response")
        # Consume before checking: expired, declined, mismatched or replayed replies cannot approve.
        request = self._pending.pop(response.confirmation_id, None)
        if request is None:
            raise ConfirmationError(ErrorCode.CONFIRMATION_INVALID, "Unknown or consumed confirmation")
        if self.clock() >= request.expires_at:
            raise ConfirmationError(ErrorCode.CONFIRMATION_EXPIRED, "Confirmation expired")
        if (request.step_id != intent.step_id or request.action_digest != intent.digest()
                or response.action_digest != request.action_digest):
            raise ConfirmationError(ErrorCode.CONFIRMATION_INVALID, "Action changed or response mismatch")
        if not response.approved:
            raise ConfirmationRejected()
        return request

    def discard(self, confirmation_id: UUID) -> None:
        self._pending.pop(confirmation_id, None)
