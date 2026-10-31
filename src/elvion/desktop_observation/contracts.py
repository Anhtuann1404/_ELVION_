"""Immutable, validated observations; coordinates are native AX screen points."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DesktopElement:
    id: str
    parent_id: str | None
    role: str | None
    subrole: str | None
    enabled: bool | None
    bbox: tuple[float, float, float, float] | None
    label: str | None = None


@dataclass(frozen=True)
class DesktopSnapshot:
    schema_version: int
    id: str
    bundle_id: str
    pid: int
    captured_at_utc: str
    captured_at_monotonic_ns: int
    elements: tuple[DesktopElement, ...]
    truncated: bool
    truncation_reason: str | None


@dataclass(frozen=True)
class DesktopObservationResult:
    status: str  # observed | permission_required | app_not_running | unsupported | error
    snapshot: DesktopSnapshot | None = None
    reason: str | None = None
