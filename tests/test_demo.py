"""Behavior checks for permissions, selection, verification and the CLI contract."""
import contextlib
from dataclasses import replace
from datetime import timedelta
import io
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from elvion.adapters.fake_notes import FakeNotesAdapter, FakeNoteStore
from elvion.aims.selector import select
from elvion.core.contracts import (
    ActionResult, ActionStatus, AuthorizationToken, ConfirmationRequest, ContractError,
    ErrorCode, Method, TaskRequest, TaskStatus, utc_now,
)
from elvion.core.orchestrator import DemoOrchestrator
from elvion.interface.cli import main
from elvion.planning.rules import UnsupportedCommand, plan
from elvion.policy.rules import DemoPolicy

GRANTS = frozenset({"note.create"})


class ContractTests(unittest.TestCase):
    def test_empty_and_wrong_type_requests_are_rejected(self):
        for value in ("", "  ", None, 42):
            with self.subTest(value=value), self.assertRaises(ContractError):
                TaskRequest(utterance=value)

    def test_uuid_and_timestamp_validation(self):
        with self.assertRaises(ContractError):
            TaskRequest(utterance="Hello", task_id="not-a-uuid")
        with self.assertRaises(ContractError):
            TaskRequest(utterance="Hello", created_at=utc_now().replace(tzinfo=None))

    def test_serialization_is_json_with_utc_and_ids(self):
        request = TaskRequest(utterance="Tạo ghi chú Ôn AI")
        payload = json.loads(json.dumps(request.to_dict()))
        self.assertEqual(payload["task_id"], str(request.task_id))
        self.assertTrue(payload["created_at"].endswith("Z"))
        self.assertEqual(payload["utterance"], request.utterance)

    def test_confirmation_requires_valid_digest(self):
        intent = plan(TaskRequest(utterance="Tạo ghi chú Ôn AI"))
        values = dict(step_id=intent.step_id, action_digest=intent.digest(), app="FakeNotes",
                      preview="Create fake note", expires_at=utc_now() + timedelta(minutes=1))
        self.assertEqual(ConfirmationRequest(**values).to_dict()["app"], "FakeNotes")
        with self.assertRaises(ContractError):
            ConfirmationRequest(**{**values, "action_digest": "bad"})

    def test_non_json_intent_data_rejected(self):
        intent = plan(TaskRequest(utterance="Tạo ghi chú Ôn AI"))
        for arguments in ({"title": float("nan")}, {42: "title"}, {"title": object()}):
            with self.subTest(arguments=arguments), self.assertRaises(ContractError):
                replace(intent, arguments=arguments)

    def test_uncertain_external_effect_cannot_be_marked_retryable(self):
        with self.assertRaises(ContractError):
            ActionResult(status=ActionStatus.UNCERTAIN, method=Method.NATIVE_API,
                         external_effect_possible=True, retryable=True)


class PlannerTests(unittest.TestCase):
    def test_supported_command_preserves_title(self):
        intent = plan(TaskRequest(utterance="  TẠO ghi chú Ôn AI  "))
        self.assertEqual(intent.arguments, {"title": "Ôn AI"})
        self.assertEqual(intent.target, {"app": "FakeNotes"})

    def test_unknown_commands_and_missing_title_rejected(self):
        for command in ("Tạo ghi chú", "Mở Safari", "Gửi tin nhắn Tạo ghi chú X"):
            with self.subTest(command=command), self.assertRaises(UnsupportedCommand):
                plan(TaskRequest(utterance=command))


class AdapterAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.intent = plan(TaskRequest(utterance="Tạo ghi chú Ôn AI"))
        self.store = FakeNoteStore()
        self.adapter = FakeNotesAdapter(Method.NATIVE_API, self.store)
        self.token = DemoPolicy().authorize(self.intent, GRANTS)

    def test_probe_does_not_create_notes(self):
        self.adapter.probe(self.intent)
        self.assertEqual(self.store.notes, {})

    def test_mutation_after_authorization_is_blocked(self):
        self.intent.arguments["title"] = "Changed"
        result = self.adapter.execute(self.intent, self.token)
        self.assertEqual(result.error_code, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(self.store.notes, {})

    def test_other_task_and_expired_token_are_blocked(self):
        tokens = [replace(self.token, task_id=uuid4()),
                  replace(self.token, expires_at=utc_now() - timedelta(seconds=1))]
        for token in tokens:
            self.assertEqual(self.adapter.execute(self.intent, token).status, ActionStatus.FAILED)
        self.assertEqual(self.store.notes, {})

    def test_retry_same_step_does_not_duplicate_note(self):
        first = self.adapter.execute(self.intent, self.token)
        second = self.adapter.execute(self.intent, self.token)
        self.assertEqual(first.evidence, second.evidence)
        self.assertEqual(len(self.store.notes), 1)

    def test_reused_idempotency_key_with_changed_action_is_rejected(self):
        self.adapter.execute(self.intent, self.token)
        changed = replace(self.intent, arguments={"title": "New"},
                          postcondition={"kind": "note_exists", "title": "New"})
        token = DemoPolicy().authorize(changed, GRANTS)
        self.assertEqual(self.adapter.execute(changed, token).status, ActionStatus.FAILED)
        self.assertEqual(list(self.store.notes.values()), ["Ôn AI"])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.request = TaskRequest(utterance="Tạo ghi chú Ôn AI")

    def test_default_deny_causes_no_write_or_execution(self):
        agent = DemoOrchestrator()
        report = agent.run(self.request)
        self.assertEqual(report.error_code, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(agent.store.notes, {})
        self.assertNotIn("executing", [e["status"] for e in report.events])
        candidates = report.events[2]["candidates"]
        self.assertTrue(all(not c["eligible"] for c in candidates))

    def test_granted_task_verified_before_success(self):
        agent = DemoOrchestrator()
        report = agent.run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(report.selected_method, Method.NATIVE_API)
        self.assertEqual(list(agent.store.notes.values()), ["Ôn AI"])
        self.assertEqual([e["status"] for e in report.events][-3:],
                         ["executing", "verifying", "succeeded"])
        for event in report.events:
            self.assertEqual(event["trace_id"], str(self.request.trace_id))
        self.assertNotIn("Ôn AI", json.dumps(report.to_dict(), ensure_ascii=False))

    def test_native_unavailable_selects_accessibility_before_execution(self):
        report = DemoOrchestrator(native_available=False).run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(report.selected_method, Method.ACCESSIBILITY)
        self.assertFalse(report.events[2]["candidates"][0]["eligible"])

    def test_no_available_adapter_fails_without_write(self):
        agent = DemoOrchestrator()
        for adapter in agent.adapters:
            adapter.available = False
        report = agent.run(self.request, GRANTS)
        self.assertEqual(report.error_code, ErrorCode.UNSUPPORTED)
        self.assertEqual(agent.store.notes, {})

    def test_claimed_success_without_note_is_uncertain(self):
        agent = DemoOrchestrator()
        false_success = ActionResult(status=ActionStatus.SUCCESS, method=Method.NATIVE_API,
                                     evidence={"note_id": str(uuid4())})
        with patch.object(agent.adapters[0], "execute", return_value=false_success) as execute:
            report = agent.run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        self.assertEqual(report.error_code, ErrorCode.VERIFICATION_FAILED)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(agent.store.notes, {})

    def test_uncertain_effect_stops_without_fallback_execution(self):
        agent = DemoOrchestrator()
        uncertain = ActionResult(status=ActionStatus.UNCERTAIN, method=Method.NATIVE_API,
                                 error_code=ErrorCode.UNCERTAIN_EXTERNAL_EFFECT,
                                 external_effect_possible=True)
        with patch.object(agent.adapters[0], "execute", return_value=uncertain), \
             patch.object(agent.adapters[1], "execute") as fallback:
            report = agent.run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        fallback.assert_not_called()

    def test_unknown_command_creates_no_note(self):
        agent = DemoOrchestrator()
        report = agent.run(TaskRequest(utterance="Mở Safari"), GRANTS)
        self.assertEqual(report.error_code, ErrorCode.UNSUPPORTED)
        self.assertEqual(agent.store.notes, {})

    def test_selector_policy_veto(self):
        agent = DemoOrchestrator()
        probes = [a.probe(plan(self.request)) for a in agent.adapters]
        selected, _ = select(probes, policy_allowed=False)
        self.assertIsNone(selected)


class CLITests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([*args, "--no-trace"])
        return code, json.loads(output.getvalue())

    def test_granted_cli_emits_json_success(self):
        code, payload = self.run_cli(["demo", "Tạo ghi chú Ôn AI", "--grant", "note.create"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "succeeded")
        self.assertTrue(payload["simulated"])

    def test_denied_cli_has_failure_exit_status(self):
        code, payload = self.run_cli(["demo", "Tạo ghi chú Ôn AI"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "PERMISSION_DENIED")


if __name__ == "__main__":
    unittest.main()
