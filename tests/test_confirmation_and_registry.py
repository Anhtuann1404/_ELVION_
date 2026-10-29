"""Confirmation binding and adapter-boundary behavior, without real side effects."""
import contextlib
from dataclasses import replace
from datetime import timedelta
import io
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from elvion.adapters.fake_notes import FakeNoteStore, FakeNotesAdapter
from elvion.adapters.registry import AdapterRegistry
from elvion.core.adapter import Adapter
from elvion.core.contracts import (
    ActionStatus, ConfirmationResponse, ContractError, ErrorCode, Method, ObservationRequest,
    ObservationStatus, ProbeResult, TaskRequest, TaskStatus, utc_now,
)
from elvion.core.orchestrator import DemoOrchestrator
from elvion.interface.cli import main
from elvion.planning.rules import plan
from elvion.policy.confirmation import ConfirmationError, ConfirmationManager, ConfirmationRejected
from elvion.policy.rules import DemoPolicy, PermissionDenied

GRANTS = frozenset({"note.create"})


def approve(request):
    return ConfirmationResponse(confirmation_id=request.confirmation_id,
                                action_digest=request.action_digest, approved=True)


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.intent = plan(TaskRequest(utterance="Tạo ghi chú Ôn AI"))
        self.now = utc_now()
        self.manager = ConfirmationManager(clock=lambda: self.now)
        self.policy = DemoPolicy(require_confirmation=True, confirmations=self.manager)

    def test_missing_grant_cannot_be_replaced_by_approval(self):
        request = self.manager.create(self.intent)
        with self.assertRaises(PermissionDenied):
            self.policy.authorize(self.intent, frozenset(), approve(request))

    def test_missing_response_cannot_authorize(self):
        with self.assertRaises(ConfirmationError) as raised:
            self.policy.authorize(self.intent, GRANTS)
        self.assertEqual(raised.exception.code, ErrorCode.CONFIRMATION_REQUIRED)

    def test_valid_approval_is_single_use(self):
        request = self.policy.request_confirmation(self.intent, GRANTS)
        token = self.policy.authorize(self.intent, GRANTS, approve(request))
        self.assertTrue(token.permits(self.intent))
        with self.assertRaises(ConfirmationError):
            self.policy.authorize(self.intent, GRANTS, approve(request))

    def test_changed_action_requires_new_confirmation(self):
        request = self.policy.request_confirmation(self.intent, GRANTS)
        changed = replace(self.intent, arguments={"title": "Changed"},
                          postcondition={"kind": "note_exists", "title": "Changed"})
        with self.assertRaises(ConfirmationError) as raised:
            self.policy.authorize(changed, GRANTS, approve(request))
        self.assertEqual(raised.exception.code, ErrorCode.CONFIRMATION_INVALID)
        with self.assertRaises(ConfirmationError):
            self.policy.authorize(self.intent, GRANTS, approve(request))

    def test_recipient_change_invalidates_digest(self):
        message = replace(self.intent, capability="message.send", target={"app": "FakeMessenger"},
                          arguments={"recipient": "alice", "content": "Hello"},
                          postcondition={"kind": "message_sent"}, risk="high")
        request = self.manager.create(message)
        self.assertEqual(request.recipient, "alice")
        changed = replace(message, arguments={"recipient": "bob", "content": "Hello"})
        with self.assertRaises(ConfirmationError):
            self.manager.consume(changed, approve(request))

    def test_expired_approval_cannot_authorize(self):
        request = self.policy.request_confirmation(self.intent, GRANTS)
        self.now += timedelta(seconds=60)
        with self.assertRaises(ConfirmationError) as raised:
            self.policy.authorize(self.intent, GRANTS, approve(request))
        self.assertEqual(raised.exception.code, ErrorCode.CONFIRMATION_EXPIRED)

    def test_rejection_consumes_confirmation(self):
        request = self.manager.create(self.intent)
        with self.assertRaises(ConfirmationRejected):
            self.manager.consume(self.intent, replace(approve(request), approved=False))
        with self.assertRaises(ConfirmationError):
            self.manager.consume(self.intent, approve(request))

    def test_unknown_id_and_wrong_digest_rejected(self):
        request = self.manager.create(self.intent)
        for response in (replace(approve(request), confirmation_id=uuid4()),
                         replace(approve(request), action_digest="0" * 64)):
            with self.assertRaises(ConfirmationError):
                self.manager.consume(self.intent, response)

    def test_new_preview_revokes_previous_preview(self):
        old = self.manager.create(self.intent)
        new = self.manager.create(self.intent)
        with self.assertRaises(ConfirmationError):
            self.manager.consume(self.intent, approve(old))
        self.manager.consume(self.intent, approve(new))

    def test_response_does_not_accept_truthy_strings(self):
        request = self.manager.create(self.intent)
        with self.assertRaises(ContractError):
            ConfirmationResponse(confirmation_id=request.confirmation_id,
                                 action_digest=request.action_digest, approved="yes")


class ConfirmationPipelineTests(unittest.TestCase):
    def setUp(self):
        self.request = TaskRequest(utterance="Tạo ghi chú Ôn AI")
        self.agent = DemoOrchestrator(require_confirmation=True)

    def test_approval_occurs_before_execution_and_content_not_in_trace(self):
        def handler(request):
            self.assertEqual(self.agent.store.notes, {})
            self.assertIn("Ôn AI", request.preview)
            return approve(request)
        report = self.agent.run(self.request, GRANTS, confirmation_handler=handler)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        states = [event["status"] for event in report.events]
        self.assertLess(states.index("awaiting_confirmation"), states.index("executing"))
        self.assertNotIn("Ôn AI", json.dumps(report.to_dict(), ensure_ascii=False))

    def test_decline_means_cancelled_and_no_write(self):
        report = self.agent.run(self.request, GRANTS,
                                confirmation_handler=lambda r: replace(approve(r), approved=False))
        self.assertEqual(report.status, TaskStatus.CANCELLED)
        self.assertEqual(self.agent.store.notes, {})

    def test_no_handler_means_no_execution(self):
        report = self.agent.run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.AWAITING_CONFIRMATION)
        self.assertIsNotNone(report.confirmation_request)
        self.assertEqual(self.agent.store.notes, {})

    def test_eof_interrupt_and_handler_error_do_not_execute(self):
        for error in (EOFError(), KeyboardInterrupt(), RuntimeError("private secret")):
            def handler(request):
                raise error
            report = self.agent.run(self.request, GRANTS, confirmation_handler=handler)
            self.assertIn(report.status, (TaskStatus.CANCELLED, TaskStatus.FAILED))
            self.assertEqual(self.agent.store.notes, {})
            self.assertNotIn("private secret", json.dumps(report.to_dict()))

    def test_expiry_while_waiting_does_not_execute(self):
        manager = self.agent.policy.confirmations
        now = utc_now()
        manager.clock = lambda: now
        def handler(request):
            nonlocal now
            now += timedelta(seconds=61)
            return approve(request)
        report = self.agent.run(self.request, GRANTS, confirmation_handler=handler)
        self.assertEqual(report.error_code, ErrorCode.CONFIRMATION_EXPIRED)
        self.assertEqual(self.agent.store.notes, {})

    def test_confirmation_does_not_enable_missing_capability(self):
        with patch("builtins.input") as unused:
            report = self.agent.run(self.request, confirmation_handler=approve)
        self.assertEqual(report.error_code, ErrorCode.PERMISSION_DENIED)
        self.assertNotIn("awaiting_confirmation", [e["status"] for e in report.events])
        unused.assert_not_called()


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeNotesAdapter(Method.NATIVE_API, FakeNoteStore())
        self.registry = AdapterRegistry((self.adapter,))
        self.intent = plan(TaskRequest(utterance="Tạo ghi chú Ôn AI"))

    def test_fake_implements_protocol_and_describes_simulation(self):
        self.assertIsInstance(self.adapter, Adapter)
        self.assertTrue(self.adapter.descriptor.simulated)
        self.assertIs(self.registry.get(self.adapter.adapter_id), self.adapter)

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ContractError):
            self.registry.register(self.adapter)

    def test_missing_adapter_permission_skips_probe(self):
        with patch.object(self.adapter, "probe") as probe:
            result = self.registry.probe(self.intent, frozenset())[0]
        self.assertFalse(result.prerequisites_met)
        self.assertEqual(result.reason, "ADAPTER_PERMISSION_DENIED")
        probe.assert_not_called()

    def test_broken_or_mismatched_probe_is_ineligible(self):
        bad_probe = ProbeResult(adapter_id="wrong", method=Method.VISION,
                                supported=True, prerequisites_met=True, reason="ready")
        for kwargs in ({"return_value": bad_probe}, {"side_effect": RuntimeError("secret")}):
            with patch.object(self.adapter, "probe", **kwargs):
                result = self.registry.probe(self.intent, GRANTS)[0]
            self.assertFalse(result.prerequisites_met)
            self.assertEqual(result.reason, "ADAPTER_PROBE_FAILED")

    def test_typed_observation_not_found_and_unsupported(self):
        result = self.adapter.observe(ObservationRequest(app="FakeNotes", kind="note", subject_id="missing"))
        self.assertEqual(result.status, ObservationStatus.NOT_FOUND)
        result = self.adapter.observe(ObservationRequest(app="Other", kind="note", subject_id="missing"))
        self.assertEqual(result.status, ObservationStatus.UNAVAILABLE)

    def test_execute_exception_is_uncertain_and_does_not_fallback(self):
        agent = DemoOrchestrator()
        with patch.object(agent.adapters[0], "execute", side_effect=RuntimeError("secret")), \
             patch.object(agent.adapters[1], "execute") as fallback:
            report = agent.run(TaskRequest(utterance="Tạo ghi chú Ôn AI"), GRANTS)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        self.assertNotIn("secret", json.dumps(report.to_dict()))
        fallback.assert_not_called()

    def test_observe_exception_does_not_turn_into_success(self):
        agent = DemoOrchestrator()
        with patch.object(agent.adapters[0], "observe", side_effect=RuntimeError("secret")):
            report = agent.run(TaskRequest(utterance="Tạo ghi chú Ôn AI"), GRANTS)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        self.assertEqual(report.error_code, ErrorCode.VERIFICATION_FAILED)


class ConfirmationCLITests(unittest.TestCase):
    def run_cli(self, reply):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO(reply)), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["demo", "--no-trace", "Tạo ghi chú Ôn AI", "--grant", "note.create", "--confirm"])
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def test_yes_approves_and_stdout_remains_json(self):
        code, report, preview = self.run_cli("y\n")
        self.assertEqual((code, report["status"]), (0, "succeeded"))
        self.assertIn("Ôn AI", preview)
        self.assertIn("Approve?", preview)

    def test_no_empty_eof_and_unknown_reply_all_decline(self):
        for reply in ("n\n", "\n", "", "maybe\n"):
            code, report, _ = self.run_cli(reply)
            self.assertEqual((code, report["status"]), (1, "cancelled"))
            self.assertNotIn("executing", [e["status"] for e in report["events"]])


if __name__ == "__main__":
    unittest.main()
