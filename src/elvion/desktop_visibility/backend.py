"""Bounded read-only native AX probe; no actions or screenshots."""

from hashlib import sha256
from pathlib import Path
import json
from math import isfinite
import os
import subprocess
import sys
import tempfile

from elvion.desktop_observation.contracts import DesktopSnapshot
from elvion.desktop_targeting.contracts import DesktopTargetResult
from elvion.models.structured import strict_json

from .contracts import VisibilityEvidence, VisibilityResult
from .evaluator import _box, _valid


SOURCE = Path(__file__).resolve().parents[3] / 'native/macos/DesktopVisibility.swift'
MAX_OUTPUT = 65_536


class VisibilityBackend:
    def __init__(self, *, runner=subprocess.run):
        self.runner = runner
        digest = sha256(SOURCE.read_bytes()).hexdigest()[:16]
        self.binary = SOURCE.parents[2] / 'artifacts/native' / f'desktop-visibility-{digest}'

    def prepare(self):
        if sys.platform != 'darwin':
            raise ValueError('MACOS_REQUIRED')
        if self.binary.is_file() and os.access(self.binary, os.X_OK):
            return
        try:
            self.binary.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.binary.parent, prefix='.visibility-build-') as folder:
                path = Path(folder)
                source, binary = path / 'main.swift', path / 'helper'
                source.write_bytes(SOURCE.read_bytes())
                result = self.runner(['/usr/bin/swiftc', '-swift-version', '5', '-module-cache-path',
                                      str(path / 'cache'), str(source), '-o', str(binary)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=60, check=False, shell=False)
                if result.returncode != 0 or not binary.is_file():
                    raise ValueError('VISIBILITY_BUILD_FAILED')
                binary.chmod(0o700)
                os.replace(binary, self.binary)
        except (OSError, subprocess.SubprocessError):
            raise ValueError('VISIBILITY_BUILD_FAILED') from None

    def probe(self, snapshot: DesktopSnapshot, target: DesktopTargetResult,
              geometry: dict, *, label: str, same_session_observation: bool = False):
        if (type(snapshot) is not DesktopSnapshot or type(target) is not DesktopTargetResult or
                type(geometry) is not dict or target.status != 'found' or
                target.snapshot_id != snapshot.id or target.node_id is None or
                geometry.get('status') != 'geometry_consistent' or
                geometry.get('snapshot_id') != snapshot.id or
                geometry.get('node_id') != target.node_id or
                geometry.get('target_scope') != target.scope or
                geometry.get('bbox') != target.bbox or
                not _box(geometry.get('window_bbox')) or
                not _box(geometry.get('display_bbox')) or
                type(geometry.get('display_scale')) not in (int, float) or
                not isfinite(geometry['display_scale']) or geometry['display_scale'] <= 0 or
                type(snapshot.pid) is not int or snapshot.pid <= 0 or
                type(snapshot.captured_at_monotonic_ns) is not int or
                snapshot.captured_at_monotonic_ns <= 0 or
                snapshot.bundle_id != 'com.apple.calculator' or
                type(label) is not str or not label or type(same_session_observation) is not bool):
            return VisibilityResult('error', 'INVALID_PROBE_INPUT')
        nodes = {node.id: node for node in snapshot.elements}
        node = nodes.get(target.node_id)
        if (node is None or type(node.label) is not str or not 1 <= len(node.label) <= 256 or
                any(ord(c) < 32 for c in node.label) or
                node.bbox != target.bbox or node.role != 'AXButton' or node.enabled is not True):
            return VisibilityResult('error', 'INVALID_PROBE_INPUT')
        request = {'version': 1, 'pid': snapshot.pid, 'bundle_id': snapshot.bundle_id,
                   'snapshot_id': snapshot.id, 'target_node_id': target.node_id,
                   'target_scope': target.scope, 'target_label': node.label,
                   'target_subrole': node.subrole, 'target_bbox': target.bbox,
                   'window_bbox': geometry['window_bbox'], 'display_bbox': geometry['display_bbox'],
                   'display_scale': geometry['display_scale'],
                   'snapshot_ns': snapshot.captured_at_monotonic_ns,
                   'same_host_clock': same_session_observation}
        payload = json.dumps(request).encode()
        if len(payload) > MAX_OUTPUT:
            return VisibilityResult('error', 'INVALID_PROBE_INPUT')
        try:
            response = self.runner([str(self.binary)], input=payload,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   timeout=5, check=False, shell=False)
            if response.returncode != 0 or type(response.stdout) is not bytes:
                raise ValueError
            if len(response.stdout) > MAX_OUTPUT:
                return VisibilityResult('error', 'OUTPUT_LIMIT')
            raw = strict_json(response.stdout.decode('utf-8'))
            if type(raw) is not dict or set(raw) != set(VisibilityEvidence.__dataclass_fields__):
                raise ValueError
            for key in ('snapshot_id', 'bundle_id', 'pid', 'target_node_id', 'target_scope',
                        'target_bbox', 'window_bbox', 'display_scale', 'snapshot_ns', 'same_host_clock'):
                expected = request[key]
                observed = tuple(raw[key]) if key.endswith('_bbox') and type(raw[key]) is list else raw[key]
                if type(observed) is not type(expected) and key not in ('target_bbox', 'window_bbox'):
                    raise ValueError
                if observed != expected:
                    raise ValueError
            for key in ('target_bbox', 'window_bbox', 'hits'):
                if type(raw[key]) is not list:
                    raise ValueError
                raw[key] = tuple(raw[key])
            evidence = VisibilityEvidence(**raw)
            if not _valid(evidence):
                raise ValueError
            return evidence
        except subprocess.TimeoutExpired:
            return VisibilityResult('error', 'PROBE_TIMEOUT')
        except (OSError, subprocess.SubprocessError, ValueError, UnicodeError, TypeError, KeyError):
            return VisibilityResult('error', 'PROBE_PROTOCOL_ERROR')
