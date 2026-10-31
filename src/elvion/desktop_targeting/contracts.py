"""A proposal tied to one AX snapshot; never an action authority."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DesktopTargetResult:
    status: str  # found | not_found | ambiguous | unavailable | stale | unsupported | error
    reason: str
    snapshot_id: str | None = None
    node_id: str | None = None
    role: str | None = None
    enabled: bool | None = None
    bbox: tuple[float, float, float, float] | None = None
    candidate_count: int = 0
    age_ms: float | None = None
    scope: str = 'all_buttons'
