"""One read-only sampled AX visibility probe for an already-open Calculator."""

import argparse
from dataclasses import asdict
import json
import subprocess

from elvion.desktop_observation import observe_app
from elvion.desktop_targeting import locate_control
from elvion.desktop_targeting.geometry import DisplayGeometryBackend, check_geometry
from elvion.desktop_visibility.backend import VisibilityBackend
from elvion.desktop_visibility.contracts import VisibilityEvidence, VisibilityResult
from elvion.desktop_visibility.evaluator import evaluate_visibility


def main(argv=None, *, observer=observe_app, geometry_backend=None, visibility_backend=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='7')
    parser.add_argument('--include-labels', action='store_true')
    args = parser.parse_args(argv)
    if not args.include_labels:
        print(json.dumps({'status': 'unknown', 'reason': 'LABEL_OPT_IN_REQUIRED', 'actions': 0}))
        return 2
    try:
        geometry_backend = geometry_backend or DisplayGeometryBackend()
        visibility_backend = visibility_backend or VisibilityBackend()
        geometry_backend.prepare()
        visibility_backend.prepare()  # Build before the short-lived AX snapshot.
        before = geometry_backend.read()
        observed = observer('com.apple.calculator', include_labels=True)
        if observed.status != 'observed' or observed.snapshot is None:
            print(json.dumps({'status': 'unknown', 'reason': observed.reason or 'OBSERVATION_UNAVAILABLE',
                              'upstream_status': observed.status, 'actions': 0}))
            return 2
        target = locate_control(observed.snapshot, label=args.label, scope='calculator_content')
        if target.status != 'found':
            print(json.dumps({'status': 'unknown', 'reason': target.reason,
                              'target_status': target.status, 'actions': 0}))
            return 2
        after = geometry_backend.read()
        if before != after:
            print(json.dumps({'status': 'unknown', 'reason': 'DISPLAY_LAYOUT_CHANGED', 'actions': 0}))
            return 2
        geometry = check_geometry(observed.snapshot, target, after)
        if geometry['status'] != 'geometry_consistent':
            print(json.dumps({'status': 'unknown', 'reason': geometry['reason'], 'actions': 0}))
            return 2
        evidence = visibility_backend.probe(observed.snapshot, target, geometry,
                                            label=args.label, same_session_observation=True)
        result = (evaluate_visibility(evidence) if type(evidence) is VisibilityEvidence
                  else evidence if type(evidence) is VisibilityResult
                  else VisibilityResult('error', 'PROBE_PROTOCOL_ERROR'))
        print(json.dumps(asdict(result)))
        return 0 if result.status == 'visible' else 1
    except (ValueError, OSError, subprocess.SubprocessError, TypeError, KeyError, RecursionError):
        print(json.dumps({'status': 'error', 'reason': 'VISIBILITY_BACKEND_UNAVAILABLE', 'actions': 0}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
