"""Immutable evidence and conclusion; neither grants action authority."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VisibilityEvidence:
    schema_version: int
    reference_id: str
    snapshot_id: str
    bundle_id: str
    pid: int
    target_node_id: str
    target_scope: str
    target_bbox: tuple[float, float, float, float]
    window_bbox: tuple[float, float, float, float]
    display_scale: float
    snapshot_ns: int
    probe_ns: int
    same_host_clock: bool
    permission_granted: bool | None
    target_bound: bool
    window_bound: bool
    unique_target: bool
    layout_unchanged: bool
    state_unchanged: bool
    display_contains_target: bool
    window_contains_target: bool
    app_hidden: bool | None
    window_minimized: bool | None
    frontmost: bool | None
    hit_test_supported: bool
    hits: tuple[str, ...]  # target_or_child | other_pid | other_window | ancestor_only | unknown


@dataclass(frozen=True)
class VisibilityResult:
    status: str  # visible | blocked | unknown | error
    reason: str
    reference_id: str | None = None
    snapshot_id: str | None = None
    bundle_id: str | None = None
    pid: int | None = None
    target_node_id: str | None = None
    target_scope: str | None = None
    age_ms: float | None = None
    checked_points: int = 0
    predicates_verified: tuple[str, ...] = ()
    predicates_unverified: tuple[str, ...] = ()
    sampled_visibility_verified: bool = False
    whole_target_visibility_verified: bool = False
    freshness_for_execution: bool = False
    actions: int = 0
