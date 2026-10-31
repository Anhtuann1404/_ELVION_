"""One read-only revalidation of a manually opened Calculator button."""

import argparse
from dataclasses import asdict
import json
import sys
import time

from elvion.desktop_observation import observe_app
from elvion.desktop_observation.observer import NativeBackend as ObservationBackend
from elvion.desktop_targeting import locate_control
from elvion.desktop_targeting.geometry import DisplayGeometryBackend, check_geometry
from elvion.desktop_revalidation import RevalidationEvidence, RevalidationResult, evaluate_revalidation
from elvion.desktop_revalidation.backend import RevalidationBackend


def run_once(label, *, observer=observe_app, geometry_backend=None,
             revalidation_backend=None, clock=time.monotonic_ns):
    geometry_backend = geometry_backend or DisplayGeometryBackend()
    revalidation_backend = revalidation_backend or RevalidationBackend()
    geometry_backend.prepare()
    revalidation_backend.prepare()
    if observer is observe_app:
        observation_backend = ObservationBackend()
        if not observation_backend._prepare():
            return RevalidationResult('error', 'OBSERVATION_BUILD_FAILED')
        def observe():
            return observer('com.apple.calculator', include_labels=True, backend=observation_backend)
    else:
        def observe():
            return observer('com.apple.calculator', include_labels=True)
    layout_before = geometry_backend.read()
    capture_start = clock()
    process_before = revalidation_backend.begin()
    observed = observe()
    capture_end = clock()
    if observed.status != 'observed' or observed.snapshot is None:
        return RevalidationResult('unknown', observed.reason or 'OBSERVATION_UNAVAILABLE')
    snapshot = observed.snapshot
    target = locate_control(snapshot, label=label, scope='calculator_content')
    if target.status != 'found':
        return RevalidationResult('unknown', target.reason or 'TARGET_UNAVAILABLE')
    if process_before['pid'] != snapshot.pid:
        return RevalidationResult('blocked', 'PID_CHANGED')
    if not process_before['process_marker']:
        return RevalidationResult('unknown', 'PROCESS_INSTANCE_UNAVAILABLE')
    # Numeric ASCII labels have the same exact-match semantics in both collectors.
    node = next((n for n in snapshot.elements if n.id == target.node_id), None)
    if node is None or node.label is None or not node.label.isascii() or not node.label.isdecimal():
        return RevalidationResult('unknown', 'NATIVE_LABEL_EQUIVALENCE_UNPROVEN')
    layout_middle = geometry_backend.read()
    if layout_before != layout_middle:
        return RevalidationResult('blocked', 'DISPLAY_LAYOUT_CHANGED')
    # Geometry uses the snapshot's own clock only for its structural check;
    # freshness is evaluated from this coordinator's capture-start clock.
    geometry = check_geometry(snapshot, target, layout_middle,
                              now_ns=snapshot.captured_at_monotonic_ns)
    if geometry['status'] != 'geometry_consistent':
        return RevalidationResult('unknown', geometry['reason'])
    probe_start = clock()
    native = revalidation_backend.probe(pid=snapshot.pid,
        process_marker=process_before['process_marker'], label=node.label,
        subrole=node.subrole, target_bbox=target.bbox,
        window_bbox=geometry['window_bbox'], display_bbox=geometry['display_bbox'],
        display_scale=geometry['display_scale'])
    probe_end = clock()
    layout_after = geometry_backend.read()
    now = clock()
    evidence = RevalidationEvidence(snapshot_id=snapshot.id, target_node_id=target.node_id,
        provenance=True, same_host_session=True,
        capture_start_ns=capture_start, capture_end_ns=capture_end,
        probe_start_ns=probe_start, probe_end_ns=probe_end,
        native_probe_duration_ns=native['duration_ns'],
        process_marker_before=process_before['process_marker'],
        process_marker_after=native['process_marker'], pid_before=process_before['pid'],
        pid_after=native['pid'], permission_before=(process_before['permission'] and
                                                     native['permission_before']),
        permission_after=native['permission_after'],
        target_count_before=native['target_count_before'], target_count_after=native['target_count_after'],
        binding_before=native['binding_before'], binding_after=native['binding_after'],
        target_enabled_before=native['target_enabled_before'],
        target_enabled_after=native['target_enabled_after'],
        target_bbox_stable=native['target_bbox_stable'],
        window_bbox_stable=native['window_bbox_stable'],
        display_layout_stable=layout_middle == layout_after,
        app_hidden_before=native['app_hidden_before'], app_hidden_after=native['app_hidden_after'],
        window_minimized_before=native['window_minimized_before'],
        window_minimized_after=native['window_minimized_after'],
        hit_test_supported=native['hit_test_supported'], hits=native['hits'])
    return evaluate_revalidation(evidence, now_ns=now)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='7')
    parser.add_argument('--include-labels', action='store_true')
    args = parser.parse_args(argv)
    if not args.include_labels:
        result = RevalidationResult('unknown', 'LABEL_OPT_IN_REQUIRED')
    else:
        try:
            result = run_once(args.label)
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            reason = str(exc)
            allowed = {'MACOS_REQUIRED', 'REVALIDATION_BUILD_FAILED', 'DISPLAY_BUILD_FAILED',
                       'DISPLAY_LAYOUT_UNAVAILABLE', 'DISPLAY_READ_FAILED', 'DISPLAY_PROTOCOL_ERROR',
                       'PROBE_TIMEOUT', 'PROBE_PROTOCOL_ERROR', 'PROBE_BACKEND_ERROR',
                       'INVALID_PROBE_INPUT'}
            result = RevalidationResult('error', reason if reason in allowed else 'BACKEND_UNAVAILABLE')
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.status == 'ready' else 1


if __name__ == '__main__':
    sys.exit(main())
