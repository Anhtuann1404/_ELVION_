"""Read-only preview binding; no result values, launch or focus changes."""
from dataclasses import asdict

from elvion.desktop_observation import observe_app
from elvion.desktop_observation.observer import NativeBackend
from elvion.desktop_targeting import locate_control
from elvion.desktop_targeting.geometry import DisplayGeometryBackend, check_geometry
from elvion.desktop_revalidation.backend import RevalidationBackend
from .contracts import BUNDLE


def discover_target():
    displays = DisplayGeometryBackend()
    process = RevalidationBackend()
    observation = NativeBackend()
    displays.prepare()
    process.prepare()
    if not observation._prepare():
        raise ValueError('OBSERVATION_BUILD_FAILED')
    before = displays.read()
    state = process.begin()
    result = observe_app(BUNDLE, include_labels=True, backend=observation)
    if result.status != 'observed' or result.snapshot is None:
        raise ValueError('CALCULATOR_OBSERVATION_UNAVAILABLE')
    snapshot = result.snapshot
    target = locate_control(snapshot, label='7', scope='calculator_content')
    after = displays.read()
    if before != after or snapshot.pid != state['pid'] or not state['process_marker']:
        raise ValueError('CALCULATOR_PREVIEW_CHANGED')
    geometry = check_geometry(snapshot, target, after)
    if geometry['status'] != 'geometry_consistent':
        raise ValueError('CALCULATOR_TARGET_UNAVAILABLE')
    node = next(n for n in snapshot.elements if n.id == target.node_id)
    if node.label != '7' or node.subrole is not None:
        raise ValueError('CALCULATOR_TARGET_UNSUPPORTED')
    return {'app':BUNDLE, 'pid':snapshot.pid, 'process_marker':state['process_marker'],
            'target_bbox':list(target.bbox), 'window_bbox':list(geometry['window_bbox']),
            'displays':[{**asdict(d),'bbox':list(d.bbox)} for d in after]}
