"""Calculator-only AX observation. No actions, activation or private values."""

from datetime import datetime, timedelta
from hashlib import sha256
from math import isfinite
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from elvion.models.structured import strict_json

from .contracts import DesktopElement, DesktopObservationResult, DesktopSnapshot


ALLOWED_BUNDLE = 'com.apple.calculator'
MAX_OUTPUT = 1024 * 1024
MAX_NODES = 300
MAX_DEPTH = 12
RUN_TIMEOUT = 5
SOURCE = Path(__file__).resolve().parents[3] / 'native/macos/DesktopObservation.swift'


def _error(reason: str) -> DesktopObservationResult:
    return DesktopObservationResult('error', reason=reason)


def _valid_string(value, *, maximum=256, optional=False):
    if optional and value is None:
        return True
    return type(value) is str and 0 < len(value) <= maximum and not any(ord(c) < 32 for c in value)


def _parse(raw: bytes, bundle_id: str, include_labels: bool) -> DesktopObservationResult:
    if not isinstance(raw, bytes) or len(raw) > MAX_OUTPUT:
        return _error('OUTPUT_LIMIT')
    try:
        data = strict_json(raw.decode('utf-8'))
        if (type(data) is not dict or set(data) != {'version', 'status', 'snapshot', 'reason'} or
                type(data['version']) is not int or data['version'] != 1):
            raise ValueError
        status, reason, snap = data['status'], data['reason'], data['snapshot']
        if status not in {'observed', 'permission_required', 'app_not_running', 'unsupported', 'error'}:
            raise ValueError
        if reason is not None and reason not in {
                'AX_PERMISSION_REQUIRED', 'APP_NOT_RUNNING', 'UNSUPPORTED_REQUEST',
                'AX_ROOT_UNREADABLE'}:
            raise ValueError
        if status != 'observed':
            expected_reason = {'permission_required': 'AX_PERMISSION_REQUIRED',
                               'app_not_running': 'APP_NOT_RUNNING',
                               'unsupported': 'UNSUPPORTED_REQUEST',
                               'error': 'AX_ROOT_UNREADABLE'}[status]
            if snap is not None or reason != expected_reason:
                raise ValueError
            return DesktopObservationResult(status, reason=reason)
        if reason is not None or type(snap) is not dict or set(snap) != {
                'schema_version', 'id', 'bundle_id', 'pid', 'captured_at_utc',
                'captured_at_monotonic_ns', 'elements', 'truncated', 'truncation_reason'}:
            raise ValueError
        if (type(snap['schema_version']) is not int or snap['schema_version'] != 1 or
                not _valid_string(snap['id'], maximum=64) or snap['bundle_id'] != bundle_id or
                type(snap['pid']) is not int or snap['pid'] <= 0 or
                not _valid_string(snap['captured_at_utc'], maximum=40) or
                datetime.fromisoformat(snap['captured_at_utc'].replace('Z', '+00:00')).utcoffset() != timedelta(0) or
                type(snap['captured_at_monotonic_ns']) is not int or snap['captured_at_monotonic_ns'] <= 0 or
                type(snap['truncated']) is not bool or
                snap['truncation_reason'] not in (None, 'TIME_BUDGET', 'NODE_LIMIT', 'DEPTH_LIMIT') or
                (snap['truncated'] != (snap['truncation_reason'] is not None)) or
                type(snap['elements']) is not list or len(snap['elements']) > MAX_NODES):
            raise ValueError
        elements, ids, depths = [], set(), {}
        for row in snap['elements']:
            if type(row) is not dict or set(row) != {'id', 'parent_id', 'role', 'subrole', 'enabled', 'bbox', 'label'}:
                raise ValueError
            if (not _valid_string(row['id'], maximum=32) or row['id'] in ids or
                    not _valid_string(row['parent_id'], maximum=32, optional=True) or
                    (row['parent_id'] is not None and row['parent_id'] not in ids) or
                    not _valid_string(row['role'], optional=True) or
                    not _valid_string(row['subrole'], optional=True) or
                    row['enabled'] not in (True, False, None) or
                    (row['enabled'] is not None and type(row['enabled']) is not bool) or
                    not _valid_string(row['label'], optional=True) or
                    (not include_labels and row['label'] is not None)):
                raise ValueError
            box = row['bbox']
            if box is not None:
                if (type(box) is not list or len(box) != 4 or
                        any(type(v) not in (int, float) or not isfinite(v) for v in box) or
                        box[2] <= 0 or box[3] <= 0):
                    raise ValueError
                box = tuple(float(v) for v in box)
            ids.add(row['id'])
            depth = 0 if row['parent_id'] is None else depths[row['parent_id']] + 1
            if depth > MAX_DEPTH or (elements and row['parent_id'] is None):
                raise ValueError
            depths[row['id']] = depth
            elements.append(DesktopElement(row['id'], row['parent_id'], row['role'], row['subrole'],
                                           row['enabled'], box, row['label']))
        if not elements or elements[0].parent_id is not None:
            raise ValueError
        snapshot = DesktopSnapshot(1, snap['id'], bundle_id, snap['pid'],
                                   snap['captured_at_utc'], snap['captured_at_monotonic_ns'],
                                   tuple(elements), snap['truncated'], snap['truncation_reason'])
        return DesktopObservationResult('observed', snapshot)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return _error('PROTOCOL_ERROR')


class NativeBackend:
    """Build a content-addressed helper, then run it with bounded IPC time."""

    def __init__(self, *, runner=subprocess.run):
        self.runner = runner
        digest = sha256(SOURCE.read_bytes()).hexdigest()[:16]
        self.binary = SOURCE.parents[2] / 'artifacts/native' / f'desktop-observation-{digest}'

    def _prepare(self) -> bool:
        if self.binary.is_file() and os.access(self.binary, os.X_OK):
            return True
        try:
            self.binary.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.binary.parent, prefix='.desktop-observe-') as folder:
                path = Path(folder)
                source, binary = path / 'main.swift', path / 'helper'
                source.write_bytes(SOURCE.read_bytes())
                built = self.runner(['/usr/bin/swiftc', '-swift-version', '5',
                                     '-module-cache-path', str(path / 'cache'), str(source),
                                     '-o', str(binary)], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=60, check=False, shell=False)
                if built.returncode != 0 or not binary.is_file():
                    return False
                binary.chmod(0o700)
                os.replace(binary, self.binary)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def observe(self, bundle_id: str, include_labels: bool) -> bytes:
        if not self._prepare():
            raise RuntimeError('BUILD_FAILED')
        args = [str(self.binary), bundle_id] + (['--include-labels'] if include_labels else [])
        result = self.runner(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=RUN_TIMEOUT, check=False, shell=False)
        if result.returncode != 0:
            raise RuntimeError('NATIVE_FAILED')
        return result.stdout


def observe_app(bundle_id: str, *, include_labels: bool = False, backend=None) -> DesktopObservationResult:
    """Observe an already-running Calculator; backend injection is for fake tests."""
    if type(bundle_id) is not str or bundle_id != ALLOWED_BUNDLE or type(include_labels) is not bool:
        return DesktopObservationResult('unsupported', reason='UNSUPPORTED_REQUEST')
    if backend is None:
        if sys.platform != 'darwin':
            return DesktopObservationResult('unsupported', reason='MACOS_REQUIRED')
        try:
            backend = NativeBackend()
        except OSError:
            return _error('BUILD_FAILED')
    try:
        raw = backend.observe(bundle_id, include_labels)
    except subprocess.TimeoutExpired:
        return _error('TIMEOUT')
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return _error('BACKEND_ERROR')
    return _parse(raw, bundle_id, include_labels)
