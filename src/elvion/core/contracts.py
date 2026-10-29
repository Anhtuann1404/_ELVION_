"""Validated, JSON-serializable contracts shared by ELVION modules."""

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from math import isfinite
from uuid import UUID, uuid4


class ContractError(ValueError):
    """Input does not satisfy the internal contract."""


class TaskStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


class Method(StrEnum):
    NATIVE_API = "native_api"
    ACCESSIBILITY = "accessibility"
    DOM = "dom"
    VISION = "vision"


class ActionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class ErrorCode(StrEnum):
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNSUPPORTED = "UNSUPPORTED"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_EXPIRED = "CONFIRMATION_EXPIRED"
    CONFIRMATION_INVALID = "CONFIRMATION_INVALID"
    UNCERTAIN_EXTERNAL_EFFECT = "UNCERTAIN_EXTERNAL_EFFECT"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be non-empty text")


def require_uuid(value: object, name: str) -> None:
    if not isinstance(value, UUID):
        raise ContractError(f"{name} must be UUID")


def require_time(value: object, name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ContractError(f"{name} must be a timezone-aware datetime")


def json_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        require_time(value, "datetime")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: json_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ContractError("JSON object keys must be text")
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    raise ContractError("Value is not JSON serializable")


def require_mapping(value: object, name: str) -> None:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be a JSON object")
    json_value(value)


class Contract:
    def to_dict(self) -> dict:
        return json_value(self)


@dataclass(frozen=True, kw_only=True)
class TaskRequest(Contract):
    utterance: str
    task_id: UUID = field(default_factory=uuid4)
    trace_id: UUID = field(default_factory=uuid4)
    source: str = "text"
    locale: str = "vi-VN"
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_text(self.utterance, "utterance")
        require_uuid(self.task_id, "task_id")
        require_uuid(self.trace_id, "trace_id")
        require_text(self.locale, "locale")
        require_time(self.created_at, "created_at")
        if self.source != "text":
            raise ContractError("Only text input is implemented")


@dataclass(frozen=True, kw_only=True)
class ActionIntent(Contract):
    task_id: UUID
    capability: str
    target: dict
    arguments: dict
    postcondition: dict
    step_id: UUID = field(default_factory=uuid4)
    idempotency_key: UUID = field(default_factory=uuid4)
    preconditions: tuple[str, ...] = ()
    risk: str = "low"

    def __post_init__(self) -> None:
        for name in ("task_id", "step_id", "idempotency_key"):
            require_uuid(getattr(self, name), name)
        require_text(self.capability, "capability")
        for name in ("target", "arguments", "postcondition"):
            require_mapping(getattr(self, name), name)
        require_text(self.target.get("app"), "target.app")
        require_text(self.postcondition.get("kind"), "postcondition.kind")
        if self.risk not in ("low", "medium", "high"):
            raise ContractError("risk must be low, medium or high")
        if not isinstance(self.preconditions, tuple):
            raise ContractError("preconditions must be a tuple of text")
        for condition in self.preconditions:
            require_text(condition, "precondition")

    def digest(self) -> str:
        # Recompute at use time: nested dictionaries can change despite frozen=True.
        self.__post_init__()
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, kw_only=True)
class ProbeResult(Contract):
    adapter_id: str
    method: Method
    supported: bool
    prerequisites_met: bool
    reason: str

    def __post_init__(self) -> None:
        require_text(self.adapter_id, "adapter_id")
        require_text(self.reason, "reason")
        if not isinstance(self.method, Method):
            raise ContractError("method must be Method")
        if type(self.supported) is not bool or type(self.prerequisites_met) is not bool:
            raise ContractError("probe flags must be boolean")


@dataclass(frozen=True, kw_only=True)
class ActionResult(Contract):
    status: ActionStatus
    method: Method
    evidence: dict = field(default_factory=dict)
    error_code: ErrorCode | None = None
    retryable: bool = False
    external_effect_possible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, ActionStatus) or not isinstance(self.method, Method):
            raise ContractError("status and method must be enum values")
        require_mapping(self.evidence, "evidence")
        if self.error_code is not None and not isinstance(self.error_code, ErrorCode):
            raise ContractError("error_code must be ErrorCode or None")
        if type(self.retryable) is not bool or type(self.external_effect_possible) is not bool:
            raise ContractError("result flags must be boolean")
        if self.status == ActionStatus.SUCCESS and self.error_code is not None:
            raise ContractError("success cannot have an error_code")
        if self.status == ActionStatus.UNCERTAIN and self.external_effect_possible and self.retryable:
            raise ContractError("uncertain effects cannot be retried automatically")


@dataclass(frozen=True, kw_only=True)
class ConfirmationRequest(Contract):
    step_id: UUID
    action_digest: str
    app: str
    preview: str
    expires_at: datetime
    confirmation_id: UUID = field(default_factory=uuid4)
    recipient: str | None = None

    def __post_init__(self) -> None:
        require_uuid(self.step_id, "step_id")
        require_uuid(self.confirmation_id, "confirmation_id")
        require_text(self.app, "app")
        require_text(self.preview, "preview")
        require_time(self.expires_at, "expires_at")
        if (not isinstance(self.action_digest, str) or len(self.action_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.action_digest)):
            raise ContractError("action_digest must be a SHA-256 hex digest")
        if self.recipient is not None:
            require_text(self.recipient, "recipient")


@dataclass(frozen=True, kw_only=True)
class AuthorizationToken(Contract):
    task_id: UUID
    step_id: UUID
    action_digest: str
    expires_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.task_id, "task_id")
        require_uuid(self.step_id, "step_id")
        require_time(self.expires_at, "expires_at")
        if (not isinstance(self.action_digest, str) or len(self.action_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.action_digest)):
            raise ContractError("action_digest must be a SHA-256 hex digest")

    def permits(self, intent: ActionIntent) -> bool:
        return (self.task_id == intent.task_id and self.step_id == intent.step_id
                and self.action_digest == intent.digest() and utc_now() < self.expires_at)


@dataclass(frozen=True, kw_only=True)
class ConfirmationResponse(Contract):
    confirmation_id: UUID
    action_digest: str
    approved: bool

    def __post_init__(self) -> None:
        require_uuid(self.confirmation_id, "confirmation_id")
        if (not isinstance(self.action_digest, str) or len(self.action_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.action_digest)):
            raise ContractError("action_digest must be a SHA-256 hex digest")
        if type(self.approved) is not bool:
            raise ContractError("approved must be boolean")


@dataclass(frozen=True, kw_only=True)
class CapabilityDescriptor(Contract):
    name: str
    platform: str
    app: str
    method: Method
    required_permissions: tuple[str, ...]
    supported_actions: tuple[str, ...]
    can_verify: bool
    estimated_latency_ms: int
    version: str = "0.1"
    simulated: bool = False

    def __post_init__(self) -> None:
        for name in ("name", "platform", "app", "version"):
            require_text(getattr(self, name), name)
        if not isinstance(self.method, Method):
            raise ContractError("method must be Method")
        for name in ("required_permissions", "supported_actions"):
            values = getattr(self, name)
            if not isinstance(values, tuple):
                raise ContractError(f"{name} must be tuple of text")
            for value in values:
                require_text(value, name)
        if not self.supported_actions:
            raise ContractError("supported_actions must not be empty")
        if type(self.can_verify) is not bool or type(self.simulated) is not bool:
            raise ContractError("descriptor flags must be boolean")
        if type(self.estimated_latency_ms) is not int or self.estimated_latency_ms < 0:
            raise ContractError("estimated_latency_ms must be a non-negative integer")


@dataclass(frozen=True, kw_only=True)
class ObservationRequest(Contract):
    app: str
    kind: str
    subject_id: str

    def __post_init__(self) -> None:
        for name in ("app", "kind", "subject_id"):
            require_text(getattr(self, name), name)


class ObservationStatus(StrEnum):
    OBSERVED = "observed"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, kw_only=True)
class Observation(Contract):
    status: ObservationStatus
    data: dict = field(default_factory=dict)
    observed_at: datetime = field(default_factory=utc_now)
    error_code: ErrorCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ObservationStatus):
            raise ContractError("status must be ObservationStatus")
        require_mapping(self.data, "data")
        require_time(self.observed_at, "observed_at")
        if self.error_code is not None and not isinstance(self.error_code, ErrorCode):
            raise ContractError("error_code must be ErrorCode or None")
        if self.status == ObservationStatus.OBSERVED and self.error_code is not None:
            raise ContractError("observed cannot have an error_code")
