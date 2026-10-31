"""Immutable, privacy-preserving revalidation contract."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RevalidationEvidence:
    schema_version: int = 1
    bundle_id: str = 'com.apple.calculator'
    scope: str = 'calculator_content'
    snapshot_id: str = ''
    target_node_id: str = ''
    provenance: bool = False
    same_host_session: bool = False
    capture_start_ns: int = 0
    capture_end_ns: int = 0
    probe_start_ns: int = 0
    probe_end_ns: int = 0
    native_probe_duration_ns: int = 0
    process_marker_before: str | None = None
    process_marker_after: str | None = None
    pid_before: int = 0
    pid_after: int = 0
    permission_before: bool | None = None
    permission_after: bool | None = None
    target_count_before: int | None = None
    target_count_after: int | None = None
    binding_before: bool | None = None
    binding_after: bool | None = None
    target_enabled_before: bool | None = None
    target_enabled_after: bool | None = None
    target_bbox_stable: bool | None = None
    window_bbox_stable: bool | None = None
    display_layout_stable: bool | None = None
    app_hidden_before: bool | None = None
    app_hidden_after: bool | None = None
    window_minimized_before: bool | None = None
    window_minimized_after: bool | None = None
    hit_test_supported: bool | None = None
    hits: tuple[str, ...] = ()
    native_identity_since_snapshot_proven: bool = False


@dataclass(frozen=True)
class RevalidationResult:
    status: str
    reason: str
    bounded_observation_checks_passed: bool = False
    native_identity_since_snapshot_proven: bool = False
    actions: int = 0
    authority_granted: bool = False
    whole_target_visibility_verified: bool = False
    freshness_for_execution: bool = False
