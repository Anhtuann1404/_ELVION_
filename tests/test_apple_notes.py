"""Scoped Notes behavior with controlled backends; never touch a real Notes account."""
import contextlib
from dataclasses import replace
from datetime import timedelta
import io
import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from elvion.adapters.apple_notes import (
    AppleNotesAdapter, AppleNotesBackend, NoteMetadata, NotesBackendError, _NOTES_SCRIPT,
)
from elvion.core.contracts import (
    ConfirmationResponse, ContractError, ErrorCode, TaskRequest, TaskStatus, utc_now,
)
from elvion.core.notes import NOTES_APP_ID, NOTES_FOLDER, NotesScope
from elvion.core.runtime import NotesOrchestrator
from elvion.interface.cli import main
from elvion.planning.notes import plan_notes
from elvion.planning.rules import UnsupportedCommand
from elvion.policy.confirmation import ConfirmationError
from elvion.policy.notes import NotesPolicy

CREATE = frozenset({"note.create"})
FIND = frozenset({"note.find"})


def approve(request):
    return ConfirmationResponse(confirmation_id=request.confirmation_id,
                                action_digest=request.action_digest, approved=True)


def make_backend():
    backend = Mock(spec=AppleNotesBackend)
    data = NoteMetadata("note-1", "Ôn AI", "On My Mac", NOTES_FOLDER)
    backend.create.return_value = data
    backend.find.return_value = data
    backend.get.return_value = data
    return backend


class ScopePlannerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.scope = NotesScope(account="On My Mac")

    def test_account_required_and_controls_rejected(self):
        for account in ("", " ", "On My Mac\n", "a\x00b", 42):
            with self.subTest(account=account), self.assertRaises(ContractError):
                NotesScope(account=account)

    def test_create_and_find_bind_real_app_and_scope(self):
        for command, capability in (("Tạo ghi chú Ôn AI", "note.create"), ("Tìm ghi chú Ôn AI", "note.find")):
            intent = plan_notes(TaskRequest(utterance=command), scope=self.scope)
            self.assertEqual(intent.capability, capability)
            self.assertEqual(intent.target, {"app": NOTES_APP_ID, "account": "On My Mac", "folder": "ELVION"})
            self.assertEqual(intent.arguments["title"], "Ôn AI")

    def test_unsupported_or_multiline_title_rejected(self):
        for command in ("Tạo ghi chú", "Xóa ghi chú Ôn AI", "Tìm ghi chú a\nb", "Tạo ghi chú " + "a" * 257):
            with self.subTest(command=command), self.assertRaises(UnsupportedCommand):
                plan_notes(TaskRequest(utterance=command), scope=self.scope)

    def test_account_folder_or_argument_tampering_denied(self):
        intent = plan_notes(TaskRequest(utterance="Tạo ghi chú Ôn AI"), scope=self.scope)
        policy = NotesPolicy(self.scope)
        self.assertTrue(policy.allows(intent, CREATE))
        for altered in (replace(intent, target={**intent.target, "account": "iCloud"}),
                        replace(intent, target={**intent.target, "folder": "Personal"}),
                        replace(intent, arguments={"title": "Ôn AI", "body": "extra"})):
            self.assertFalse(policy.allows(altered, CREATE))
        self.assertFalse(policy.allows(intent, FIND))

    def test_create_confirmation_cannot_be_disabled(self):
        intent = plan_notes(TaskRequest(utterance="Tạo ghi chú Ôn AI"), scope=self.scope)
        policy = NotesPolicy(self.scope, require_confirmation=False)
        self.assertTrue(policy.requires_confirmation(intent))
        with self.assertRaises(ConfirmationError):
            policy.authorize(intent, CREATE)
        request = policy.request_confirmation(intent, CREATE)
        self.assertIn("folder", request.preview)
        self.assertIn("if missing", request.preview)
        token = policy.authorize(intent, CREATE, approve(request))
        self.assertTrue(token.permits(intent))

    def test_find_confirmation_is_optional_but_capability_stays_required(self):
        intent = plan_notes(TaskRequest(utterance="Tìm ghi chú Ôn AI"), scope=self.scope)
        policy = NotesPolicy(self.scope)
        self.assertFalse(policy.requires_confirmation(intent))
        self.assertTrue(policy.allows(intent, FIND))
        self.assertFalse(policy.allows(intent, CREATE))


class NotesPipelineTests(unittest.TestCase):
    def setUp(self):
        self.scope = NotesScope(account="On My Mac")
        self.backend = make_backend()
        self.agent = NotesOrchestrator(self.scope, backend=self.backend)
        self.create = TaskRequest(utterance="Tạo ghi chú Ôn AI")
        self.find = TaskRequest(utterance="Tìm ghi chú Ôn AI")

    def test_missing_grants_touch_no_native_api(self):
        for request in (self.create, self.find):
            report = self.agent.run(request, confirmation_handler=approve)
            self.assertEqual(report.error_code, ErrorCode.PERMISSION_DENIED)
        self.backend.check_available.assert_not_called()
        self.backend.create.assert_not_called()
        self.backend.find.assert_not_called()
        self.backend.get.assert_not_called()

    def test_no_handler_returns_pending_without_creating(self):
        report = self.agent.run(self.create, CREATE)
        self.assertEqual(report.status, TaskStatus.AWAITING_CONFIRMATION)
        self.backend.create.assert_not_called()

    def test_decline_never_creates_folder_or_note(self):
        report = self.agent.run(self.create, CREATE,
                                confirmation_handler=lambda r: replace(approve(r), approved=False))
        self.assertEqual(report.status, TaskStatus.CANCELLED)
        self.backend.create.assert_not_called()
        self.backend.find.assert_not_called()
        self.backend.get.assert_not_called()

    def test_create_is_approved_then_independently_read(self):
        def handler(request):
            self.backend.create.assert_not_called()
            self.assertIn("On My Mac", request.preview)
            self.assertIn("Ôn AI", request.preview)
            return approve(request)
        report = self.agent.run(self.create, CREATE, confirmation_handler=handler)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertFalse(report.simulated)
        self.assertEqual(report.evidence["note_id"], "note-1")
        self.backend.create.assert_called_once()
        self.backend.get.assert_called_once_with(self.scope, "note-1")
        self.assertNotIn("Ôn AI", json.dumps(report.events, ensure_ascii=False, default=str))
        self.assertNotIn("On My Mac", json.dumps(report.events, default=str))

    def test_find_reads_exact_title_then_verifies_id(self):
        report = self.agent.run(self.find, FIND)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.backend.find.assert_called_once_with(self.scope, "Ôn AI")
        self.backend.get.assert_called_once_with(self.scope, "note-1")
        self.backend.create.assert_not_called()

    def test_missing_account_or_duplicate_title_fails_without_write(self):
        for code in (ErrorCode.TARGET_NOT_FOUND, ErrorCode.AMBIGUOUS_TARGET):
            self.backend.find.side_effect = NotesBackendError(code, "NOTE_NOT_FOUND")
            report = self.agent.run(self.find, FIND)
            self.assertEqual(report.status, TaskStatus.FAILED)
            self.assertEqual(report.error_code, code)
        self.backend.create.assert_not_called()

    def test_automation_denial_is_failed_not_success(self):
        self.backend.create.side_effect = NotesBackendError(ErrorCode.PERMISSION_DENIED, "AUTOMATION_DENIED")
        report = self.agent.run(self.create, CREATE, confirmation_handler=approve)
        self.assertEqual(report.status, TaskStatus.FAILED)
        self.assertEqual(report.error_code, ErrorCode.PERMISSION_DENIED)
        self.backend.get.assert_not_called()

    def test_write_timeout_is_uncertain_and_not_retried(self):
        self.backend.create.side_effect = NotesBackendError(ErrorCode.TRANSIENT_FAILURE, "AUTOMATION_TIMEOUT_OR_FAILURE",
                                                           external_effect_possible=True)
        report = self.agent.run(self.create, CREATE, confirmation_handler=approve)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        self.backend.create.assert_called_once()
        self.backend.get.assert_not_called()

    def test_create_claim_without_matching_read_never_succeeds(self):
        for data in (NoteMetadata("other", "Ôn AI", "On My Mac", "ELVION"),
                     NoteMetadata("note-1", "Other", "On My Mac", "ELVION"),
                     NoteMetadata("note-1", "Ôn AI", "iCloud", "ELVION"),
                     NoteMetadata("note-1", "Ôn AI", "On My Mac", "Personal"),
                     NoteMetadata("note-1", "Ôn AI", "On My Mac", "ELVION", shared=True),
                     NoteMetadata("note-1", "Ôn AI", "On My Mac", "ELVION", locked=True)):
            backend = make_backend()
            backend.get.return_value = data
            report = NotesOrchestrator(self.scope, backend=backend).run(
                self.create, CREATE, confirmation_handler=approve)
            self.assertEqual(report.status, TaskStatus.UNCERTAIN)
            self.assertEqual(report.error_code, ErrorCode.VERIFICATION_FAILED)

    def test_automation_error_on_read_after_create_is_uncertain(self):
        self.backend.get.side_effect = NotesBackendError(ErrorCode.TRANSIENT_FAILURE, "AUTOMATION_FAILED")
        report = self.agent.run(self.create, CREATE, confirmation_handler=approve)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)

    def test_same_create_intent_never_written_twice_in_process(self):
        adapter = AppleNotesAdapter(self.scope, capability="note.create", backend=self.backend)
        intent = plan_notes(self.create, scope=self.scope)
        policy = NotesPolicy(self.scope)
        confirmation = policy.request_confirmation(intent, CREATE)
        token = policy.authorize(intent, CREATE, approve(confirmation))
        first = adapter.execute(intent, token)
        second = adapter.execute(intent, token)
        self.assertEqual(first.evidence, second.evidence)
        self.backend.create.assert_called_once()

    def test_uncertain_create_is_not_repeated_when_called_again(self):
        adapter = AppleNotesAdapter(self.scope, capability="note.create", backend=self.backend)
        intent = plan_notes(self.create, scope=self.scope)
        policy = NotesPolicy(self.scope)
        confirmation = policy.request_confirmation(intent, CREATE)
        token = policy.authorize(intent, CREATE, approve(confirmation))
        self.backend.create.side_effect = RuntimeError("private details")
        with self.assertRaises(RuntimeError):
            adapter.execute(intent, token)
        result = adapter.execute(intent, token)
        self.assertEqual(result.error_code, ErrorCode.UNCERTAIN_EXTERNAL_EFFECT)
        self.backend.create.assert_called_once()


class NotesBackendTests(unittest.TestCase):
    def setUp(self):
        self.scope = NotesScope(account="On My Mac")
        self.runner = Mock()
        self.backend = AppleNotesBackend(runner=self.runner)
        self.data = NoteMetadata("note-1", "Ôn AI", "On My Mac", "ELVION").to_dict()
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "data": self.data}), "")

    def test_private_payload_is_stdin_not_script_or_argv(self):
        title = 'Quote " <b> & $(do-not-run)'
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({"ok":True, "data":{**self.data,"title":title}}), "")
        with patch.object(self.backend, "check_available"):
            self.backend.find(self.scope, title)
        args, kwargs = self.runner.call_args
        self.assertNotIn(title, repr(args[0]))
        self.assertEqual(json.loads(kwargs["input"])["title"], title)
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 15.0)
        self.assertIn("htmlEscape", _NOTES_SCRIPT)

    def test_create_passes_expiry_to_script(self):
        request = TaskRequest(utterance="Tạo ghi chú Ôn AI")
        intent = plan_notes(request, scope=self.scope)
        policy = NotesPolicy(self.scope)
        confirmation = policy.request_confirmation(intent, CREATE)
        token = policy.authorize(intent, CREATE, approve(confirmation))
        with patch.object(self.backend, "check_available"):
            self.backend.create(self.scope, "Ôn AI", token)
        payload = json.loads(self.runner.call_args.kwargs["input"])
        self.assertEqual(payload["expires_ms"], int(token.expires_at.timestamp() * 1000))
        self.assertIn("assertUnexpired(payload)", _NOTES_SCRIPT)

    def test_create_without_token_is_rejected_before_runner(self):
        with patch.object(self.backend, "check_available"), self.assertRaises(NotesBackendError):
            self.backend._call("create", self.scope, title="Ôn AI")
        self.runner.assert_not_called()

    def test_script_error_flags_are_preserved_and_raw_stderr_hidden(self):
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({"ok":False,
            "error_code":"PERMISSION_DENIED", "reason":"AUTOMATION_DENIED", "external_effect_possible":False}), "secret")
        with patch.object(self.backend, "check_available"), self.assertRaises(NotesBackendError) as raised:
            self.backend.find(self.scope, "Ôn AI")
        self.assertEqual(raised.exception.code, ErrorCode.PERMISSION_DENIED)
        self.assertFalse(raised.exception.external_effect_possible)
        self.assertNotIn("secret", str(raised.exception))

    def test_corrupt_or_wrong_scope_response_is_rejected(self):
        for output in ("not-json", "[]", '{"ok":true,"data":{}}',
                       json.dumps({"ok":True,"data":{**self.data,"account":"other"}}),
                       json.dumps({"ok":True,"data":{**self.data,"folder":"Personal"}}),
                       json.dumps({"ok":True,"data":{**self.data,"shared":True}})):
            self.runner.return_value = subprocess.CompletedProcess([], 0, output, "")
            with patch.object(self.backend, "check_available"), self.assertRaises(NotesBackendError):
                self.backend.find(self.scope, "Ôn AI")

    def test_timeout_on_read_has_no_write_effect(self):
        self.runner.side_effect = subprocess.TimeoutExpired("osascript", 15)
        with patch.object(self.backend, "check_available"), self.assertRaises(NotesBackendError) as raised:
            self.backend.find(self.scope, "Ôn AI")
        self.assertFalse(raised.exception.external_effect_possible)

    def test_other_platform_rejected_without_subprocess(self):
        with patch("elvion.adapters.apple_notes.sys.platform", "linux"), self.assertRaises(NotesBackendError):
            self.backend.check_available()
        self.runner.assert_not_called()


class NotesCLITests(unittest.TestCase):
    def test_account_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["notes", "Tạo ghi chú Ôn AI", "--grant", "note.create", "--no-trace"])
        self.assertEqual(raised.exception.code, 2)

    def test_missing_grant_never_calls_native_runner(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch("elvion.adapters.apple_notes.subprocess.run") as runner:
            code = main(["notes", "--no-trace", "Tạo ghi chú Ôn AI", "--account", "On My Mac"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["error_code"], "PERMISSION_DENIED")
        runner.assert_not_called()

    def test_creation_without_confirm_flag_still_prompts_and_can_be_declined(self):
        output, prompt = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(prompt), \
             patch("sys.stdin", io.StringIO("n\n")), \
             patch("elvion.adapters.apple_notes.AppleNotesBackend.check_available"), \
             patch("elvion.adapters.apple_notes.subprocess.run") as runner:
            code = main(["notes", "--no-trace", "Tạo ghi chú Ôn AI", "--account", "On My Mac", "--grant", "note.create"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "cancelled")
        self.assertIn("Approve?", prompt.getvalue())
        self.assertIn("On My Mac", prompt.getvalue())
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
