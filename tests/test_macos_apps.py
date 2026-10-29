"""Native integration logic with controlled OS responses; no real app launched here."""
import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from elvion.adapters.macos_apps import (
    AppState, BackendError, MacOSAppAdapter, MacOSAppBackend,
)
from elvion.adapters.registry import AdapterRegistry
from elvion.core.app_catalog import CALCULATOR_BUNDLE_ID as BUNDLE_ID
from elvion.core.contracts import (
    ActionResult, ActionStatus, ErrorCode, Method, Observation, ObservationStatus,
    TaskRequest, TaskStatus,
)
from elvion.core.orchestrator import DemoOrchestrator
from elvion.core.runtime import AppOrchestrator
from elvion.interface.cli import main
from elvion.planning.rules import UnsupportedCommand, plan
from elvion.policy.apps import AppPolicy
from elvion.verification.apps import verify_application

GRANTS = frozenset({"app.open"})


def backend_mock(*, running=False):
    backend = Mock(spec=MacOSAppBackend)
    backend.state.return_value = AppState(BUNDLE_ID, (123,) if running else ())
    return backend


class AppPlanningAndPolicyTests(unittest.TestCase):
    def test_vietnamese_and_english_app_name_resolve_same_bundle(self):
        for text in ("Mở Máy tính", "  MỞ   Calculator ", "Mở máy tính"):
            intent = plan(TaskRequest(utterance=text))
            self.assertEqual(intent.capability, "app.open")
            self.assertEqual(intent.target, {"app": BUNDLE_ID})
            self.assertEqual(intent.arguments, {})

    def test_arbitrary_apps_paths_urls_and_shell_fragments_rejected(self):
        for text in ("Mở Safari", "Mở /bin/sh", "Mở https://example.com", "Mở Máy tính; echo test"):
            with self.subTest(text=text), self.assertRaises(UnsupportedCommand):
                plan(TaskRequest(utterance=text))

    def test_policy_rejects_missing_grant_extra_arguments_and_other_app(self):
        intent = plan(TaskRequest(utterance="Mở Máy tính"))
        policy = AppPolicy()
        self.assertTrue(policy.allows(intent, GRANTS))
        self.assertFalse(policy.allows(intent, frozenset()))
        for altered in (replace(intent, arguments={"args": ["--test"]}),
                        replace(intent, target={"app": "com.apple.Safari"}),
                        replace(intent, postcondition={"kind": "anything"})):
            self.assertFalse(policy.allows(altered, GRANTS))

    def test_demo_mode_rejects_real_adapter(self):
        with self.assertRaises(ValueError):
            DemoOrchestrator(registry=AdapterRegistry((MacOSAppAdapter(),)))


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.backend = backend_mock()
        self.adapter = MacOSAppAdapter(backend=self.backend)
        self.request = TaskRequest(utterance="Mở Máy tính")
        self.intent = plan(self.request)
        self.token = AppPolicy().authorize(self.intent, GRANTS)

    def test_probe_is_read_only(self):
        self.assertTrue(self.adapter.probe(self.intent).prerequisites_met)
        self.backend.launch.assert_not_called()

    def test_missing_grant_stops_before_any_native_operation(self):
        report = AppOrchestrator(adapter=self.adapter).run(self.request)
        self.assertEqual(report.error_code, ErrorCode.PERMISSION_DENIED)
        self.assertFalse(report.simulated)
        self.backend.check_available.assert_not_called()
        self.backend.state.assert_not_called()
        self.backend.launch.assert_not_called()

    def test_missing_app_preserves_reason_and_never_launches(self):
        self.backend.check_available.side_effect = BackendError(ErrorCode.TARGET_NOT_FOUND, "missing")
        report = AppOrchestrator(adapter=self.adapter).run(self.request, GRANTS)
        self.assertEqual(report.error_code, ErrorCode.TARGET_NOT_FOUND)
        self.backend.launch.assert_not_called()

    def test_launch_then_fresh_running_state_verifies_success(self):
        self.backend.state.side_effect = [AppState(BUNDLE_ID, ()), AppState(BUNDLE_ID, (123,))]
        report = AppOrchestrator(adapter=self.adapter).run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertFalse(report.simulated)
        self.assertTrue(report.evidence["postcondition_verified"])
        self.backend.launch.assert_called_once_with(BUNDLE_ID)
        self.assertEqual(self.backend.state.call_count, 2)

    def test_already_running_skips_launch_but_reads_again_for_verification(self):
        self.backend.state.return_value = AppState(BUNDLE_ID, (123,))
        report = AppOrchestrator(adapter=self.adapter).run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertTrue(report.evidence["already_running"])
        self.backend.launch.assert_not_called()
        self.assertEqual(self.backend.state.call_count, 2)

    def test_changed_intent_fails_before_native_call(self):
        self.intent.target["app"] = "com.apple.Safari"
        result = self.adapter.execute(self.intent, self.token)
        self.assertEqual(result.error_code, ErrorCode.PERMISSION_DENIED)
        self.backend.state.assert_not_called()
        self.backend.launch.assert_not_called()

    def test_token_rechecked_after_read_before_launch(self):
        token = Mock(wraps=self.token)
        token.permits.side_effect = [True, False]
        result = self.adapter.execute(self.intent, token)
        self.assertEqual(result.error_code, ErrorCode.PERMISSION_DENIED)
        self.backend.state.assert_called_once()
        self.backend.launch.assert_not_called()

    def test_launch_timeout_or_nonzero_is_uncertain_no_retry(self):
        self.backend.launch.side_effect = BackendError(ErrorCode.TRANSIENT_FAILURE, "private detail",
                                                       external_effect_possible=True,
                                                       native_exit_code=1, os_status=-10827)
        report = AppOrchestrator(adapter=self.adapter).run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        self.assertEqual(report.evidence["os_status"], -10827)
        self.assertNotIn("private detail", json.dumps(report.to_dict()))
        self.backend.launch.assert_called_once()

    def test_failed_state_query_stops_before_launch(self):
        self.backend.state.side_effect = BackendError(ErrorCode.VERIFICATION_FAILED, "failed")
        report = AppOrchestrator(adapter=self.adapter).run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.FAILED)
        self.backend.launch.assert_not_called()

    def test_confirmation_decline_never_launches(self):
        from elvion.core.contracts import ConfirmationResponse
        def decline(request):
            return ConfirmationResponse(confirmation_id=request.confirmation_id,
                                        action_digest=request.action_digest, approved=False)
        report = AppOrchestrator(adapter=self.adapter, require_confirmation=True).run(
            self.request, GRANTS, confirmation_handler=decline)
        self.assertEqual(report.status, TaskStatus.CANCELLED)
        self.backend.state.assert_not_called()
        self.backend.launch.assert_not_called()


class AppVerificationTests(unittest.TestCase):
    def setUp(self):
        self.intent = plan(TaskRequest(utterance="Mở Máy tính"))
        self.result = ActionResult(status=ActionStatus.SUCCESS, method=Method.NATIVE_API,
                                   evidence={"bundle_id": BUNDLE_ID})
        self.adapter = Mock()

    def test_launch_success_without_running_process_is_not_verified(self):
        self.adapter.observe.return_value = Observation(status=ObservationStatus.OBSERVED,
                                                        data={"bundle_id": BUNDLE_ID, "running": False, "pids": []})
        self.assertFalse(verify_application(self.intent, self.result, self.adapter, timeout_seconds=0))

    def test_observation_wrong_app_or_invalid_pids_is_not_verified(self):
        for data in ({"bundle_id": "other", "running": True, "pids": [123]},
                     {"bundle_id": BUNDLE_ID, "running": True, "pids": [True]},
                     {"bundle_id": BUNDLE_ID, "running": True, "pids": []}):
            self.adapter.observe.return_value = Observation(status=ObservationStatus.OBSERVED, data=data)
            self.assertFalse(verify_application(self.intent, self.result, self.adapter, timeout_seconds=0))

    def test_delayed_start_is_polled_with_bounded_wait(self):
        self.adapter.observe.side_effect = [
            Observation(status=ObservationStatus.OBSERVED, data={"bundle_id": BUNDLE_ID, "running": False, "pids": []}),
            Observation(status=ObservationStatus.OBSERVED, data={"bundle_id": BUNDLE_ID, "running": True, "pids": [123]}),
        ]
        now = [0.0]
        def sleep(seconds):
            now[0] += seconds
        self.assertTrue(verify_application(self.intent, self.result, self.adapter,
                                         clock=lambda: now[0], sleep=sleep))
        self.assertEqual(self.adapter.observe.call_count, 2)


class NativeBackendTests(unittest.TestCase):
    def setUp(self):
        self.runner = Mock()
        self.backend = MacOSAppBackend(runner=self.runner)

    def test_launch_uses_fixed_argv_without_shell(self):
        self.runner.return_value = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(self.backend, "check_available"):
            self.backend.launch(BUNDLE_ID)
        args, kwargs = self.runner.call_args
        self.assertEqual(args[0], ["/usr/bin/open", "-a", "/System/Applications/Calculator.app"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 3.0)

    def test_state_uses_appkit_script_and_validates_bundle_and_pids(self):
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({"bundle_id": BUNDLE_ID, "pids": [123]}), "")
        with patch.object(self.backend, "check_available"):
            self.assertTrue(self.backend.state(BUNDLE_ID).running)
        self.assertEqual(self.runner.call_args.args[0][-1], BUNDLE_ID)
        self.assertIn("NSRunningApplication", self.runner.call_args.args[0][-2])

    def test_invalid_observation_json_rejected(self):
        for output in ("invalid", "[]", '{"bundle_id":"other","pids":[1]}',
                       json.dumps({"bundle_id": BUNDLE_ID, "pids": [True]})):
            self.runner.return_value = subprocess.CompletedProcess([], 0, output, "")
            with patch.object(self.backend, "check_available"), self.assertRaises(BackendError):
                self.backend.state(BUNDLE_ID)

    def test_timeout_marks_launch_effect_possible(self):
        self.runner.side_effect = subprocess.TimeoutExpired("open", 3)
        with patch.object(self.backend, "check_available"), self.assertRaises(BackendError) as raised:
            self.backend.launch(BUNDLE_ID)
        self.assertTrue(raised.exception.external_effect_possible)

    def test_nonzero_launch_preserves_only_numeric_diagnostics(self):
        self.runner.return_value = subprocess.CompletedProcess([], 1, "private", "secret Code=-10827")
        with patch.object(self.backend, "check_available"), self.assertRaises(BackendError) as raised:
            self.backend.launch(BUNDLE_ID)
        self.assertEqual(raised.exception.os_status, -10827)
        self.assertNotIn("secret", str(raised.exception))

    def test_other_platform_rejected_without_subprocess(self):
        with patch("elvion.adapters.macos_apps.sys.platform", "linux"), self.assertRaises(BackendError):
            self.backend.check_available(BUNDLE_ID)
        self.runner.assert_not_called()

    def test_app_bundle_identity_and_executable_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Contents/MacOS").mkdir(parents=True)
            executable = root / "Contents/MacOS/Calculator"
            executable.write_text("test fixture only")
            executable.chmod(0o700)
            with patch("elvion.adapters.macos_apps.sys.platform", "darwin"), \
                 patch("elvion.adapters.macos_apps.os.access", return_value=True), \
                 patch.object(self.backend, "app_path", root):
                for bundle_id, expected_valid in ((BUNDLE_ID, True), ("other", False)):
                    with (root / "Contents/Info.plist").open("wb") as stream:
                        plistlib.dump({"CFBundleIdentifier": bundle_id, "CFBundleExecutable": "Calculator"}, stream)
                    if expected_valid:
                        self.backend.check_available(BUNDLE_ID)
                    else:
                        with self.assertRaises(BackendError):
                            self.backend.check_available(BUNDLE_ID)
        self.runner.assert_not_called()


class NativeCLITests(unittest.TestCase):
    def test_cli_no_grant_is_json_failure_and_never_launches(self):
        stdout = io.StringIO()
        with patch("elvion.adapters.macos_apps.subprocess.run") as native, contextlib.redirect_stdout(stdout):
            code = main(["run", "--no-trace", "Mở Máy tính"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "PERMISSION_DENIED")
        self.assertFalse(payload["simulated"])
        native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
