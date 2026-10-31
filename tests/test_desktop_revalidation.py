from dataclasses import replace
import json
import subprocess
import unittest
from types import SimpleNamespace

from elvion.desktop_revalidation import RevalidationResult, evaluate_revalidation
from elvion.desktop_revalidation.backend import RevalidationBackend
from benchmarks.desktop_revalidation.cases import BASE, NOW


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite(tests)
    suite.addTests(unittest.FunctionTestCase(fn) for name, fn in sorted(globals().items())
                   if name.startswith('test_') and callable(fn))
    return suite


def test_fixed_clock_and_mutation():
    assert evaluate_revalidation(BASE, now_ns=NOW).status == 'ready'
    changed = replace(BASE, binding_after=False, target_enabled_after=False)
    assert evaluate_revalidation(changed, now_ns=NOW).status == 'blocked'
    assert evaluate_revalidation(replace(BASE, capture_start_ns=3_000_000_000), now_ns=NOW).reason == 'CAPTURE_TOO_LONG'
    assert evaluate_revalidation(replace(BASE, native_probe_duration_ns=2_100_000_000), now_ns=NOW).reason == 'PROBE_TOO_LONG'


def test_binding_and_identity_not_inferred_from_matching_attributes():
    ambiguous = replace(BASE, binding_after=None)
    result = evaluate_revalidation(ambiguous, now_ns=NOW)
    assert result.status == 'unknown'
    assert result.native_identity_since_snapshot_proven is False
    assert result.authority_granted is False
    assert result.freshness_for_execution is False


def test_protocol_rejects_duplicate_keys_and_bool_integer():
    backend = RevalidationBackend(runner=lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=b'{"version":1,"version":1,"pid":1,"process_marker":"x","permission":true}'))
    try:
        backend.begin()
        assert False, 'duplicate key accepted'
    except ValueError as exc:
        assert str(exc) == 'PROBE_PROTOCOL_ERROR'
    backend = RevalidationBackend(runner=lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({'version':1,'pid':True,'process_marker':'x','permission':True}).encode()))
    try:
        backend.begin()
        assert False, 'bool PID accepted'
    except ValueError as exc:
        assert str(exc) == 'PROBE_PROTOCOL_ERROR'


def test_timeout_is_bounded_error():
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired('helper', 3)
    backend = RevalidationBackend(runner=timeout)
    try:
        backend.begin()
        assert False, 'timeout accepted'
    except ValueError as exc:
        assert str(exc) == 'PROBE_TIMEOUT'
