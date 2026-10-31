"""Bounded read-only native collector; all IPC is strict JSON over stdin/stdout."""

from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

from elvion.models.structured import strict_json
SOURCE = Path(__file__).resolve().parents[3] / 'native/macos/DesktopRevalidation.swift'
LIMIT = 65_536


def _object(raw, keys):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('PROBE_PROTOCOL_ERROR')
    try:
        data = strict_json(raw.decode('utf-8'))
    except (ValueError, UnicodeError, TypeError):
        raise ValueError('PROBE_PROTOCOL_ERROR') from None
    if type(data) is not dict or set(data) != set(keys) or type(data['version']) is not int or data['version'] != 1:
        raise ValueError('PROBE_PROTOCOL_ERROR')
    return data


class RevalidationBackend:
    def __init__(self, *, runner=subprocess.run):
        self.runner = runner
        digest = sha256(SOURCE.read_bytes()).hexdigest()[:16]
        self.binary = SOURCE.parents[2] / 'artifacts/native' / f'desktop-revalidation-{digest}'

    def prepare(self):
        if sys.platform != 'darwin':
            raise ValueError('MACOS_REQUIRED')
        if self.binary.is_file() and os.access(self.binary, os.X_OK):
            return
        try:
            self.binary.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.binary.parent, prefix='.revalidation-build-') as folder:
                path = Path(folder)
                source, binary = path / 'main.swift', path / 'helper'
                source.write_bytes(SOURCE.read_bytes())
                built = self.runner(['/usr/bin/swiftc', '-swift-version', '5', '-module-cache-path',
                                     str(path / 'cache'), str(source), '-o', str(binary)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=60, check=False, shell=False)
                if built.returncode != 0 or not binary.is_file():
                    raise ValueError('REVALIDATION_BUILD_FAILED')
                binary.chmod(0o700)
                os.replace(binary, self.binary)
        except (OSError, subprocess.SubprocessError):
            raise ValueError('REVALIDATION_BUILD_FAILED') from None

    def _run(self, request):
        payload = json.dumps(request, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(payload) > LIMIT:
            raise ValueError('INVALID_PROBE_INPUT')
        try:
            response = self.runner([str(self.binary)], input=payload, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, timeout=3, check=False, shell=False)
        except subprocess.TimeoutExpired:
            raise ValueError('PROBE_TIMEOUT') from None
        except (OSError, subprocess.SubprocessError):
            raise ValueError('PROBE_BACKEND_ERROR') from None
        if response.returncode != 0:
            raise ValueError('PROBE_PROTOCOL_ERROR')
        return response.stdout

    def begin(self):
        raw = _object(self._run({'version': 1, 'mode': 'begin'}),
                      ('version', 'pid', 'process_marker', 'permission'))
        if (type(raw['pid']) is not int or raw['pid'] < 0 or
                (raw['process_marker'] is not None and
                 (type(raw['process_marker']) is not str or not 1 <= len(raw['process_marker']) <= 128)) or
                type(raw['permission']) is not bool):
            raise ValueError('PROBE_PROTOCOL_ERROR')
        return raw

    def probe(self, *, pid, process_marker, label, subrole, target_bbox,
              window_bbox, display_bbox, display_scale):
        request = {'version': 1, 'mode': 'probe', 'pid': pid,
                   'bundle_id': 'com.apple.calculator', 'scope': 'calculator_content',
                   'label': label, 'subrole': subrole, 'target_bbox': target_bbox,
                   'window_bbox': window_bbox, 'display_bbox': display_bbox,
                   'display_scale': display_scale, 'process_marker': process_marker}
        raw = _object(self._run(request), ('version', 'pid', 'process_marker',
            'permission_before', 'permission_after', 'target_count_before', 'target_count_after',
            'binding_before', 'binding_after', 'target_enabled_before', 'target_enabled_after',
            'target_bbox_stable', 'window_bbox_stable', 'app_hidden_before', 'app_hidden_after',
            'window_minimized_before', 'window_minimized_after', 'hit_test_supported', 'hits',
            'duration_ns'))
        if (type(raw['pid']) is not int or not 0 <= raw['pid'] <= 2_147_483_647 or
                (raw['process_marker'] is not None and
                 (type(raw['process_marker']) is not str or len(raw['process_marker']) > 128)) or
                type(raw['duration_ns']) is not int or raw['duration_ns'] < 0 or
                type(raw['hits']) is not list or len(raw['hits']) > 5 or
                any(type(hit) is not str or hit not in
                    ('target_or_child', 'other_pid', 'other_window', 'ancestor_only', 'unknown')
                    for hit in raw['hits'])):
            raise ValueError('PROBE_PROTOCOL_ERROR')
        for key in ('permission_before', 'permission_after', 'binding_before', 'binding_after',
                    'target_enabled_before', 'target_enabled_after', 'target_bbox_stable',
                    'window_bbox_stable', 'app_hidden_before', 'app_hidden_after',
                    'window_minimized_before', 'window_minimized_after'):
            if raw[key] is not None and type(raw[key]) is not bool:
                raise ValueError('PROBE_PROTOCOL_ERROR')
        if type(raw['hit_test_supported']) is not bool:
            raise ValueError('PROBE_PROTOCOL_ERROR')
        for key in ('target_count_before', 'target_count_after'):
            if raw[key] is not None and (type(raw[key]) is not int or not 0 <= raw[key] <= 300):
                raise ValueError('PROBE_PROTOCOL_ERROR')
        raw['hits'] = tuple(raw['hits'])
        return raw
