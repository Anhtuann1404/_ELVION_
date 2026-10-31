"""Opt-in, read-only Calculator result collector with bounded native IPC."""

from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from elvion.models.structured import strict_json
from .contracts import CalculatorObservation, ResultRegionProfile
from .verifier import _valid_profile,standard_entry_profile

SOURCE = Path(__file__).resolve().parents[3] / 'native/macos/CalculatorResultObservation.swift'
LIMIT = 16_384
KEYS = frozenset(('version', 'status', 'reason', 'pid', 'process_marker', 'permission',
                  'region_unique', 'value', 'diagnostic'))
REASONS = frozenset(('APP_NOT_RUNNING', 'AX_PERMISSION_REQUIRED', 'AX_TRAVERSAL_INCOMPLETE',
                     'STRUCTURE_ONLY', 'RESULT_REGION_NOT_FOUND', 'RESULT_REGION_AMBIGUOUS',
                     'RESULT_VALUE_READ', 'RESULT_VALUE_UNAVAILABLE', 'PROCESS_OR_PERMISSION_CHANGED',
                     'ENTRY_VALUE_READ','ENTRY_VALUE_UNAVAILABLE','ENTRY_REGION_NOT_FOUND','ENTRY_REGION_AMBIGUOUS'))
SESSION_ID = uuid4().hex


class NativeResultBackend:
    def __init__(self, *, runner=subprocess.run):
        self.runner = runner
        self.source_bytes = SOURCE.read_bytes()
        self.source_sha256 = sha256(self.source_bytes).hexdigest()
        self.binary = SOURCE.parents[2] / 'artifacts/native' / f'calculator-result-observation-{self.source_sha256[:16]}'

    def prepare(self):
        if sys.platform != 'darwin':
            raise ValueError('MACOS_REQUIRED')
        if self.binary.is_file() and os.access(self.binary, os.X_OK):
            return
        try:
            self.binary.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.binary.parent, prefix='.calculator-result-build-') as folder:
                path = Path(folder)
                source, binary = path / 'main.swift', path / 'helper'
                source.write_bytes(self.source_bytes)
                built = self.runner(['/usr/bin/swiftc', '-swift-version', '5',
                                     '-module-cache-path', str(path / 'cache'),
                                     str(source), '-o', str(binary)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=60, check=False, shell=False)
                if built.returncode != 0 or not binary.is_file():
                    raise ValueError('BUILD_FAILED')
                binary.chmod(0o700)
                os.replace(binary, self.binary)
        except (OSError, subprocess.SubprocessError):
            raise ValueError('BUILD_FAILED') from None

    def run(self, descriptor):
        payload = json.dumps(descriptor, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(payload) > 8192:
            raise ValueError('INVALID_DESCRIPTOR')
        try:
            response = self.runner([str(self.binary)], input=payload, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, timeout=5, check=False, shell=False)
        except subprocess.TimeoutExpired:
            raise ValueError('OBSERVATION_TIMEOUT') from None
        except (OSError, subprocess.SubprocessError):
            raise ValueError('BACKEND_ERROR') from None
        if response.returncode != 0 or type(response.stdout) is not bytes or len(response.stdout) > LIMIT:
            raise ValueError('PROTOCOL_ERROR')
        try:
            data = strict_json(response.stdout.decode('utf-8'))
        except (ValueError, UnicodeError, TypeError):
            raise ValueError('PROTOCOL_ERROR') from None
        if (type(data) is not dict or set(data) != KEYS or
                type(data['version']) is not int or data['version'] != 1 or
                type(data['status']) is not str or data['status'] not in ('observed', 'unknown', 'diagnostic') or
                type(data['reason']) is not str or data['reason'] not in REASONS or
                type(data['pid']) is not int or not 0 <= data['pid'] <= 2_147_483_647 or
                (data['process_marker'] is not None and
                 (type(data['process_marker']) is not str or not 1 <= len(data['process_marker']) <= 128)) or
                type(data['permission']) is not bool or
                (data['region_unique'] is not None and type(data['region_unique']) is not bool) or
                (data['value'] is not None and (type(data['value']) is not str or not 1 <= len(data['value']) <= 64)) or
                type(data['diagnostic']) is not list or len(data['diagnostic']) > 8):
            raise ValueError('PROTOCOL_ERROR')
        for row in data['diagnostic']:
            base_keys={'role','identifier','parent_role','parent_identifier'}
            if (type(row) is not dict or set(row) not in (base_keys,base_keys | {'window_role'}) or
                    any(type(v) is not str or len(v) > 80 or any(ord(c) < 32 or ord(c) == 127 for c in v)
                        for v in row.values()) or row.get('window_role','') not in ('','AXWindow')):
                raise ValueError('PROTOCOL_ERROR')
        if descriptor['mode'] in ('capture','capture_entry'):
            expected_reason='ENTRY_VALUE_READ' if descriptor['mode']=='capture_entry' else 'RESULT_VALUE_READ'
            if (data['diagnostic'] or data['status'] == 'diagnostic' or (data['status'] == 'observed' and
                    (data['reason'] != expected_reason or data['region_unique'] is not True or
                     data['value'] is None)) or
                    (data['status'] != 'observed' and data['value'] is not None)):
                raise ValueError('PROTOCOL_ERROR')
        elif (data['status'] == 'observed' or data['value'] is not None or
              (data['status'] == 'diagnostic' and data['reason'] != 'STRUCTURE_ONLY') or
              (data['status'] != 'diagnostic' and data['diagnostic'])):
            raise ValueError('PROTOCOL_ERROR')
        return data


def capture_calculator_result(*, include_result: bool = False,
                              profile: ResultRegionProfile | None = None,
                              backend=None, clock=time.monotonic_ns) -> CalculatorObservation:
    if type(include_result) is not bool:
        return CalculatorObservation(status='error', reason='INVALID_INPUT')
    if not include_result:
        return CalculatorObservation(reason='RESULT_OPT_IN_REQUIRED')
    if not _valid_profile(profile) or profile.surface!='result':
        return CalculatorObservation(reason='REGION_PROFILE_REQUIRED')
    return _capture(profile,backend=backend,clock=clock)


def capture_calculator_entry(*, include_current_entry: bool = False, backend=None,
                             clock=time.monotonic_ns) -> CalculatorObservation:
    if type(include_current_entry) is not bool:
        return CalculatorObservation(status='error',reason='INVALID_INPUT')
    if not include_current_entry:
        return CalculatorObservation(reason='ENTRY_OPT_IN_REQUIRED')
    return _capture(standard_entry_profile(),backend=backend,clock=clock)


def _capture(profile,*,backend,clock):
    backend = backend or NativeResultBackend()
    try:
        backend.prepare()
        start = clock()
        entry=profile.surface=='current_entry'
        data = backend.run({'version': 1, 'mode': 'capture_entry' if entry else 'capture',
            ('include_current_entry' if entry else 'include_result'): True,
            'role': profile.role, 'identifier': profile.identifier,
            'parent_role': profile.parent_role, 'parent_identifier': profile.parent_identifier})
        end = clock()
    except ValueError as exc:
        reason = str(exc)
        return CalculatorObservation(status='error', reason=reason if reason in
            ('MACOS_REQUIRED','BUILD_FAILED','INVALID_DESCRIPTOR','OBSERVATION_TIMEOUT',
             'BACKEND_ERROR','PROTOCOL_ERROR') else 'BACKEND_ERROR')
    if type(start) is not int or type(end) is not int or start <= 0 or end < start:
        return CalculatorObservation(status='error', reason='CLOCK_ORDER_INVALID')
    return CalculatorObservation(status='observed' if data['status'] == 'observed' else 'unknown',
        reason=data['reason'], observation_id=uuid4().hex, session_id=SESSION_ID, pid=data['pid'],
        process_marker=data['process_marker'], same_host_session=True, provenance=True,
        capture_start_ns=start, capture_end_ns=end, permission_granted=data['permission'],
        profile=profile, region_unique=data['region_unique'], result_text=data['value'],
        result_included=data['status'] == 'observed')


def diagnose_calculator_region(*, backend=None):
    """Explicit structural diagnostic; never asks native to read AXValue."""
    backend = backend or NativeResultBackend()
    try:
        backend.prepare()
        data = backend.run({'version': 1, 'mode': 'diagnose'})
        return {'status': data['status'], 'reason': data['reason'],
                'candidates': data['diagnostic'],
                'helper_source_sha256':getattr(backend,'source_sha256',None), 'actions': 0}
    except ValueError as exc:
        reason = str(exc)
        return {'status': 'error', 'reason': reason if reason in
                ('MACOS_REQUIRED','BUILD_FAILED','OBSERVATION_TIMEOUT','BACKEND_ERROR',
                 'PROTOCOL_ERROR') else 'BACKEND_ERROR', 'candidates': [], 'actions': 0}
