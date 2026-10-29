"""Durability, privacy projection and failure behavior using temporary directories only."""
import contextlib
from datetime import datetime, timedelta, timezone
import errno
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from elvion.core.contracts import ErrorCode, TaskRequest, TaskStatus, utc_now
from elvion.core.orchestrator import DemoOrchestrator
from elvion.interface.cli import main
from elvion.storage.trace_privacy import sanitize_record
from elvion.storage.traces import MAX_TRACE_BYTES, TraceStorageError, TraceStore

GRANTS = frozenset({"note.create"})


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "elvion"
        self.store = TraceStore(self.root)
        self.request = TaskRequest(utterance="Tạo ghi chú PRIVATE-TITLE-123")

    def run_demo(self, *, grants=GRANTS):
        return DemoOrchestrator(trace_store=self.store).run(self.request, grants)

    def test_complete_task_is_persisted_and_readable(self):
        report = self.run_demo()
        self.assertEqual(report.trace["status"], "saved")
        path = Path(report.trace["path"])
        self.assertTrue(path.is_file())
        data = self.store.show(str(self.request.trace_id))
        self.assertTrue(data["finalized"])
        self.assertEqual(data["records"][-1]["status"], "succeeded")
        self.assertEqual(data["records"][-1]["capability"], "note.create")
        self.assertTrue(data["records"][-1]["diagnostics"]["postcondition_verified"])
        self.assertGreaterEqual(data["records"][-1]["duration_ms"], 0)
        self.assertEqual(report.trace["records_written"], len(data["records"]))
        self.assertEqual(self.store.recent()[0]["trace_id"], str(self.request.trace_id))

    def test_private_title_note_id_messages_and_token_not_in_file(self):
        report = self.run_demo()
        text = Path(report.trace["path"]).read_text()
        self.assertNotIn("PRIVATE-TITLE-123", text)
        self.assertNotIn(report.evidence["note_id"], text)
        for key in ('"message"', '"utterance"', '"preview"', '"action_digest"', '"note_id"'):
            self.assertNotIn(key, text)

    def test_restricted_directory_and_file_modes(self):
        report = self.run_demo()
        self.assertEqual(stat.S_IMODE(self.store.directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(Path(report.trace["path"]).stat().st_mode), 0o600)

    def test_denied_task_is_logged_without_execution(self):
        report = self.run_demo(grants=frozenset())
        self.assertEqual(report.error_code, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(report.trace["status"], "saved")
        records = self.store.show(str(self.request.trace_id))["records"]
        self.assertNotIn("executing", [item["status"] for item in records])
        self.assertEqual(records[-1]["error_code"], "PERMISSION_DENIED")

    def test_aims_candidates_and_policy_saved(self):
        self.run_demo()
        records = self.store.show(str(self.request.trace_id))["records"]
        selection = next(record for record in records if "candidates" in record)
        self.assertEqual(selection["policy_version"], "demo-v2")
        self.assertEqual(selection["selected_adapter"], "fake_notes.native_api")
        self.assertEqual(len(selection["candidates"]), 3)
        self.assertTrue(selection["candidates"][0]["eligible"])

    def test_events_are_flushed_before_confirmation_handler(self):
        agent = DemoOrchestrator(require_confirmation=True, trace_store=self.store)
        from elvion.core.contracts import ConfirmationResponse
        def decline(confirmation):
            data = self.store.show(str(self.request.trace_id))
            self.assertFalse(data["finalized"])
            self.assertEqual(data["records"][-1]["status"], "awaiting_confirmation")
            self.assertNotIn("PRIVATE-TITLE-123", json.dumps(data))
            return ConfirmationResponse(confirmation_id=confirmation.confirmation_id,
                                        action_digest=confirmation.action_digest, approved=False)
        report = agent.run(self.request, GRANTS, confirmation_handler=decline)
        self.assertEqual(report.status, TaskStatus.CANCELLED)
        self.assertTrue(self.store.show(str(self.request.trace_id))["finalized"])

    def test_pending_preview_does_not_leak_to_saved_trace(self):
        report = DemoOrchestrator(require_confirmation=True, trace_store=self.store).run(self.request, GRANTS)
        self.assertIsNotNone(report.confirmation_request)
        self.assertNotIn("PRIVATE-TITLE-123", Path(report.trace["path"]).read_text())
        self.assertEqual(self.store.show(str(self.request.trace_id))["records"][-1]["status"], "awaiting_confirmation")

    def test_unavailable_storage_does_not_retry_or_change_task_outcome(self):
        self.root.write_text("A file cannot serve as data directory")
        agent = DemoOrchestrator(trace_store=self.store)
        report = agent.run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(report.trace["status"], "failed")
        self.assertEqual(report.trace["error_code"], "TRACE_STORAGE_UNAVAILABLE")
        self.assertEqual(len(agent.store.notes), 1)

    def test_write_failure_after_execution_keeps_success_and_marks_partial(self):
        session = self.store.start(task_id=self.request.task_id, trace_id=self.request.trace_id)
        original = session.write
        def write(raw, *, kind):
            if raw.get("status") == TaskStatus.VERIFYING:
                with patch("elvion.storage.traces.os.write", side_effect=OSError(errno.ENOSPC, "secret detail")):
                    original(raw, kind=kind)
            else:
                original(raw, kind=kind)
        with patch.object(self.store, "start", return_value=session), patch.object(session, "write", side_effect=write):
            agent = DemoOrchestrator(trace_store=self.store)
            report = agent.run(self.request, GRANTS)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(report.trace["status"], "partial")
        self.assertEqual(report.trace["error_code"], "TRACE_WRITE_FAILED")
        self.assertEqual(len(agent.store.notes), 1)
        self.assertNotIn("secret detail", json.dumps(report.to_dict()))
        self.assertFalse(self.store.show(str(self.request.trace_id))["finalized"])

    def test_short_writes_are_completed(self):
        actual_write = os.write
        def short_write(fd, payload):
            return actual_write(fd, payload[:11])
        with patch("elvion.storage.traces.os.write", side_effect=short_write):
            report = self.run_demo()
        self.assertEqual(report.trace["status"], "saved")
        self.assertTrue(self.store.show(str(self.request.trace_id))["finalized"])

    def test_mid_line_disk_failure_is_read_as_incomplete(self):
        session = self.store.start(task_id=self.request.task_id, trace_id=self.request.trace_id)
        raw = {"task_id": self.request.task_id, "trace_id": self.request.trace_id,
               "created_at": utc_now(), "status": "queued", "utterance": "SECRET"}
        actual_write = os.write
        calls = [0]
        def broken_write(fd, payload):
            calls[0] += 1
            if calls[0] > 1:
                raise OSError(errno.ENOSPC, "private path")
            return actual_write(fd, payload[:15])
        with patch("elvion.storage.traces.os.write", side_effect=broken_write):
            session.write(raw, kind="event")
        self.assertEqual(session.error_code, "TRACE_WRITE_FAILED")
        data = self.store.show(str(self.request.trace_id))
        self.assertFalse(data["finalized"])
        self.assertTrue(data["partial_tail"])
        self.assertEqual(data["malformed_records"], 1)
        self.assertNotIn("SECRET", session.path.read_text())

    def test_fsync_failure_is_reported_separately(self):
        session = self.store.start(task_id=self.request.task_id, trace_id=self.request.trace_id)
        with patch("elvion.storage.traces.os.fsync", side_effect=OSError("private")):
            session.write({"task_id": self.request.task_id, "trace_id": self.request.trace_id,
                           "created_at": utc_now(), "status": "queued"}, kind="event")
        self.assertEqual(session.error_code, "TRACE_WRITE_FAILED")
        self.assertEqual(session.fd, -1)

    def test_existing_trace_is_not_overwritten(self):
        report = self.run_demo()
        path = Path(report.trace["path"])
        before = path.read_bytes()
        with self.assertRaises(TraceStorageError):
            self.store.start(task_id=self.request.task_id, trace_id=self.request.trace_id)
        self.assertEqual(path.read_bytes(), before)

    def test_symlinked_trace_directory_is_rejected(self):
        self.root.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        self.store.directory.symlink_to(outside, target_is_directory=True)
        report = self.run_demo()
        self.assertEqual(report.trace["status"], "failed")
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_file_is_not_read_or_overwritten(self):
        self.store.directory.mkdir(parents=True)
        outside = Path(self.temp.name) / "private.txt"
        outside.write_text("PRIVATE")
        link = self.store.directory / f"{self.request.trace_id}.jsonl"
        link.symlink_to(outside)
        with self.assertRaises(TraceStorageError):
            self.store.show(str(self.request.trace_id))
        self.assertEqual(self.store.recent(), [])
        self.run_demo()
        self.assertEqual(outside.read_text(), "PRIVATE")

    def test_path_traversal_and_invalid_limits_are_rejected(self):
        with self.assertRaises(TraceStorageError) as raised:
            self.store.show("../../private")
        self.assertEqual(raised.exception.code, "TRACE_INVALID_ID")
        for limit in (0, 101, -1, True):
            with self.assertRaises(TraceStorageError):
                self.store.recent(limit)

    def test_empty_history_does_not_create_directories(self):
        self.assertEqual(self.store.recent(), [])
        self.assertFalse(self.root.exists())
        with self.assertRaises(TraceStorageError):
            self.store.show(str(uuid4()))
        self.assertFalse(self.root.exists())

    def test_reader_strips_extra_private_fields_from_existing_json(self):
        report = self.run_demo()
        path = Path(report.trace["path"])
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row.update({"message": "PRIVATE", "token": "PRIVATE", "preview": {"account": "PRIVATE"}})
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        data = self.store.show(str(self.request.trace_id))
        self.assertTrue(data["finalized"])
        self.assertNotIn("PRIVATE", json.dumps(data))

    def test_malformed_tail_or_wrong_identity_is_not_reported_finalized(self):
        report = self.run_demo()
        path = Path(report.trace["path"])
        with path.open("a") as stream:
            stream.write('{"secret":"PRIVATE",')
        data = self.store.show(str(self.request.trace_id))
        self.assertFalse(data["finalized"])
        self.assertGreater(data["malformed_records"], 0)
        self.assertNotIn("PRIVATE", json.dumps(data))

    def test_deeply_nested_corruption_is_skipped_without_exposing_content(self):
        report = self.run_demo()
        path = Path(report.trace["path"])
        with path.open("a") as stream:
            stream.write("[" * 2000 + '"PRIVATE"' + "]" * 2000 + "\n")
        data = self.store.show(str(self.request.trace_id))
        self.assertFalse(data["finalized"])
        self.assertEqual(data["malformed_records"], 1)
        self.assertNotIn("PRIVATE", json.dumps(data))

    def test_oversized_history_file_is_rejected(self):
        self.store.directory.mkdir(parents=True)
        path = self.store.directory / f"{self.request.trace_id}.jsonl"
        path.write_bytes(b"x" * (MAX_TRACE_BYTES + 1))
        with self.assertRaises(TraceStorageError) as raised:
            self.store.show(str(self.request.trace_id))
        self.assertEqual(raised.exception.code, "TRACE_TOO_LARGE")

    def test_internal_exception_closes_trace_and_leaves_incomplete_history(self):
        agent = DemoOrchestrator(trace_store=self.store)
        agent.planner = Mock(side_effect=RuntimeError("SECRET"))
        with self.assertRaises(RuntimeError):
            agent.run(self.request, GRANTS)
        data = self.store.show(str(self.request.trace_id))
        self.assertFalse(data["finalized"])
        self.assertNotIn("SECRET", json.dumps(data))


class PrivacyProjectionTests(unittest.TestCase):
    def base(self):
        return {"task_id": str(uuid4()), "trace_id": str(uuid4()), "created_at": utc_now(), "status": "succeeded"}

    def test_nested_secrets_and_unknown_values_are_dropped(self):
        raw = {**self.base(), "utterance": "PRIVATE", "message": "PRIVATE", "account": "PRIVATE",
               "confirmation_request": {"preview": "PRIVATE"}, "policy_version": "PRIVATE",
               "evidence": {"token": "PRIVATE", "note_id": "PRIVATE", "reason": "PRIVATE", "postcondition_verified": True},
               "candidates": [{"adapter_id": "PRIVATE", "method": "native_api", "reason": "ELIGIBLE", "eligible": True}]}
        record = sanitize_record(raw, kind="task_result")
        self.assertNotIn("PRIVATE", json.dumps(record))
        self.assertTrue(record["diagnostics"]["postcondition_verified"])

    def test_timestamp_normalized_and_invalid_numeric_metadata_dropped(self):
        raw = {**self.base(), "created_at": datetime(2026, 10, 29, 19, 0, tzinfo=timezone(timedelta(hours=7))),
               "duration_ms": 10 ** 1000,
               "evidence": {"native_error": "PRIVATE", "os_status": -10827}}
        record = sanitize_record(raw, kind="task_result")
        self.assertEqual(record["created_at"], "2026-10-29T12:00:00Z")
        self.assertNotIn("duration_ms", record)
        self.assertEqual(record["diagnostics"], {"os_status": -10827})

    def test_invalid_identity_is_never_stringified(self):
        class Secret:
            def __str__(self):
                raise AssertionError("Must not stringify an arbitrary object")
        with self.assertRaises(ValueError):
            sanitize_record({**self.base(), "task_id": Secret()}, kind="event")


class TraceCLITests(unittest.TestCase):
    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def test_cli_writes_lists_and_shows_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            code, report, _ = self.invoke(["demo", "Tạo ghi chú PRIVATE", "--grant", "note.create", "--data-dir", directory])
            self.assertEqual(code, 0)
            self.assertEqual(report["trace"]["status"], "saved")
            _, listing, _ = self.invoke(["traces", "list", "--data-dir", directory])
            self.assertEqual(listing["traces"][0]["trace_id"], report["trace_id"])
            _, data, _ = self.invoke(["traces", "show", report["trace_id"], "--data-dir", directory])
            self.assertTrue(data["finalized"])
            self.assertNotIn("PRIVATE", json.dumps(data))

    def test_trace_enabled_by_default_uses_app_data_path(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("elvion.storage.traces.default_data_dir", return_value=Path(directory)):
            code, report, _ = self.invoke(["demo", "Tạo ghi chú PRIVATE", "--grant", "note.create"])
        self.assertEqual(code, 0)
        self.assertEqual(report["trace"]["status"], "saved")

    def test_opt_out_creates_no_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "not-created"
            code, report, _ = self.invoke(["demo", "Tạo ghi chú PRIVATE", "--grant", "note.create", "--no-trace", "--data-dir", str(target)])
            self.assertEqual(code, 0)
            self.assertEqual(report["trace"]["status"], "disabled")
            self.assertFalse(target.exists())

    def test_failed_log_warns_without_failing_successful_action(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file"
            path.write_text("not a directory")
            code, report, warning = self.invoke(["demo", "Tạo ghi chú PRIVATE", "--grant", "note.create", "--data-dir", str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "succeeded")
            self.assertEqual(report["trace"]["status"], "failed")
            self.assertIn("Trace persistence warning", warning)

    def test_bad_trace_id_has_fixed_error_without_raw_path(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, _ = self.invoke(["traces", "show", "../../SECRET", "--data-dir", directory])
        self.assertEqual(code, 1)
        self.assertEqual(result, {"error_code": "TRACE_INVALID_ID"})


if __name__ == "__main__":
    unittest.main()
