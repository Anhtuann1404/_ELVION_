"""Hand-authored expected decisions; timestamps share a fixed synthetic clock."""
from dataclasses import dataclass, replace
from elvion.desktop_revalidation import RevalidationEvidence

NOW = 10_000_000_000
BASE = RevalidationEvidence(snapshot_id='s1', target_node_id='n7', provenance=True,
    same_host_session=True, capture_start_ns=9_200_000_000, capture_end_ns=9_300_000_000,
    probe_start_ns=9_400_000_000, probe_end_ns=9_500_000_000,
    native_probe_duration_ns=100_000_000, process_marker_before='launch-1',
    process_marker_after='launch-1', pid_before=1234, pid_after=1234,
    permission_before=True, permission_after=True, target_count_before=1,
    target_count_after=1, binding_before=True, binding_after=True,
    target_enabled_before=True, target_enabled_after=True, target_bbox_stable=True,
    window_bbox_stable=True, display_layout_stable=True, app_hidden_before=False,
    app_hidden_after=False, window_minimized_before=False, window_minimized_after=False,
    hit_test_supported=True, hits=('target_or_child',)*5)

@dataclass(frozen=True)
class Case:
    name: str
    evidence: RevalidationEvidence | None
    expected: str

CASES = (
    Case('stable', BASE, 'ready'),
    Case('stable_second_snapshot', replace(BASE, snapshot_id='s2'), 'ready'),
    Case('pid_changed', replace(BASE, pid_after=1235), 'blocked'),
    Case('app_no_longer_running', replace(BASE, pid_after=0), 'blocked'),
    Case('pid_missing_before', replace(BASE, pid_before=0), 'unknown'),
    Case('instance_changed', replace(BASE, process_marker_after='launch-2'), 'blocked'),
    Case('instance_missing_before', replace(BASE, process_marker_before=None), 'unknown'),
    Case('instance_missing_after', replace(BASE, process_marker_after=None), 'unknown'),
    Case('target_disappeared_before', replace(BASE, target_count_before=0), 'blocked'),
    Case('target_disappeared_after', replace(BASE, target_count_after=0), 'blocked'),
    Case('target_duplicate_before', replace(BASE, target_count_before=2), 'blocked'),
    Case('target_duplicate_after', replace(BASE, target_count_after=2), 'blocked'),
    Case('target_count_unknown', replace(BASE, target_count_after=None), 'unknown'),
    Case('binding_changed', replace(BASE, binding_after=False), 'blocked'),
    Case('binding_missing', replace(BASE, binding_after=None), 'unknown'),
    Case('target_moved', replace(BASE, target_bbox_stable=False), 'blocked'),
    Case('window_moved', replace(BASE, window_bbox_stable=False), 'blocked'),
    Case('display_changed', replace(BASE, display_layout_stable=False), 'blocked'),
    Case('disabled_after', replace(BASE, target_enabled_after=False), 'blocked'),
    Case('disabled_before', replace(BASE, target_enabled_before=False), 'blocked'),
    Case('hidden_after', replace(BASE, app_hidden_after=True), 'blocked'),
    Case('hidden_before', replace(BASE, app_hidden_before=True), 'blocked'),
    Case('minimized_after', replace(BASE, window_minimized_after=True), 'blocked'),
    Case('permission_lost', replace(BASE, permission_after=False), 'blocked'),
    Case('permission_missing', replace(BASE, permission_after=None), 'unknown'),
    Case('sample_other_pid', replace(BASE, hits=('other_pid',)+('target_or_child',)*4), 'blocked'),
    Case('sample_other_window', replace(BASE, hits=('other_window',)+('target_or_child',)*4), 'blocked'),
    Case('ancestor_only', replace(BASE, hits=('ancestor_only',)+('target_or_child',)*4), 'unknown'),
    Case('sample_unknown', replace(BASE, hits=('unknown',)+('target_or_child',)*4), 'unknown'),
    Case('hit_unsupported', replace(BASE, hit_test_supported=False, hits=()), 'unknown'),
    Case('stale', replace(BASE, capture_start_ns=1_000_000_000, capture_end_ns=1_100_000_000,
                          probe_start_ns=9_400_000_000), 'blocked'),
    Case('long_observation_fresh_end', replace(BASE, capture_start_ns=3_000_000_000), 'blocked'),
    Case('long_probe', replace(BASE, native_probe_duration_ns=2_100_000_000), 'blocked'),
    Case('different_session', replace(BASE, same_host_session=False), 'unknown'),
    Case('imported_snapshot', replace(BASE, provenance=False), 'unknown'),
    Case('future_timestamp', replace(BASE, probe_end_ns=NOW+1), 'error'),
    Case('out_of_order', replace(BASE, probe_start_ns=9_100_000_000), 'error'),
    Case('malformed', replace(BASE, hits=('invalid_hit',)), 'error'),
    Case('timeout', None, 'error'),
    Case('same_attributes_identity_unproven', replace(BASE, binding_after=None), 'unknown'),
)
