"""Behavioral checks for the independent reminder store."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from zoneinfo import ZoneInfo

from elvion.reminders import ReminderError, ReminderStore, Schedule

UTC = timezone.utc


def instant(day, hour=0, minute=0):
    return datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=UTC)


class ReminderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.now = instant("2026-10-31", 0)
        self.store = ReminderStore(self.root, clock=lambda: self.now)
        self.addCleanup(self.store.close)

    def test_crud_unicode_revision_and_lifecycle(self):
        original = self.store.create_reminder("Uống nước — ôn bài", Schedule.once(self.now + timedelta(hours=1)))
        self.assertEqual(self.store.get_reminder(original.id).content, "Uống nước — ôn bài")
        self.assertEqual(len(self.store.list_reminders("active")), 1)
        edited = self.store.update_reminder(original.id, content="Ôn tập BFS")
        self.assertEqual(edited.revision, 2)
        rescheduled = self.store.update_reminder(original.id,
            schedule=Schedule.once(self.now + timedelta(hours=2)))
        self.assertEqual(rescheduled.revision, 3)
        self.assertEqual(self.store.cancel_reminder(original.id).status, "cancelled")
        self.assertEqual(self.store.cancel_reminder(original.id).status, "cancelled")
        with self.assertRaisesRegex(ReminderError, "REMINDER_INACTIVE"):
            self.store.update_reminder(original.id, content="Không đổi")

    def test_validation_and_dst(self):
        for content in ("", " " * 3, "x" * 501):
            with self.subTest(content=len(content)), self.assertRaisesRegex(ReminderError, "CONTENT_INVALID"):
                self.store.create_reminder(content, Schedule.once(self.now))
        with self.assertRaisesRegex(ReminderError, "SCHEDULE_INVALID"):
            Schedule.weekly(time(8), (7,), date(2026, 10, 31))
        with self.assertRaisesRegex(ReminderError, "SCHEDULE_INVALID"):
            Schedule.daily(time(8, tzinfo=UTC), date(2026, 10, 31))
        with self.assertRaisesRegex(ReminderError, "TIMEZONE_REQUIRED"):
            self.store.create_reminder("test", Schedule.once(datetime(2026, 10, 31, 8)))
        with self.assertRaisesRegex(ReminderError, "TIMEZONE_INVALID"):
            self.store.create_reminder("test", Schedule.once(self.now), "Mars/Olympus")
        with self.assertRaisesRegex(ReminderError, "SCHEDULE_DST_INVALID"):
            Schedule.once(datetime(2026, 3, 8, 2, 30, tzinfo=ZoneInfo("America/New_York")))
        with self.assertRaisesRegex(ReminderError, "SCHEDULE_DST_INVALID"):
            Schedule.once(datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York")))
        for day, wall, now in ((date(2026, 3, 8), time(2, 30), instant("2026-03-08", 6)),
                               (date(2026, 11, 1), time(1, 30), instant("2026-11-01", 5))):
            with self.subTest(day=day), ReminderStore(self.root / str(day), clock=lambda: now) as store:
                with self.assertRaisesRegex(ReminderError, "SCHEDULE_DST_INVALID"):
                    store.create_reminder("test", Schedule.daily(wall, day), "America/New_York")

    def test_once_due_exact_overdue_restart_and_ack(self):
        at = self.now + timedelta(hours=1)
        reminder = self.store.create_reminder("test", Schedule.once(at), "UTC")
        self.assertEqual(self.store.collect_due(at - timedelta(microseconds=1)), ())
        event, = self.store.collect_due(at)
        self.assertFalse(event.occurrence.catch_up)
        self.assertEqual(event.occurrence.scheduled_at, at)
        self.assertEqual(self.store.collect_due(at), ())
        with ReminderStore(self.root, clock=lambda: at + timedelta(days=1)) as restarted:
            pending, = restarted.list_pending_events()
            self.assertEqual(pending.id, event.id)
            self.assertEqual(restarted.acknowledge_event(event.id).status, "acknowledged")
            self.assertEqual(restarted.acknowledge_event(event.id).id, event.id)
            self.assertEqual(restarted.list_pending_events(), ())
            self.assertEqual(restarted.get_reminder(reminder.id).status, "active")

    def test_daily_weekly_catchup_and_calendar_boundaries(self):
        daily = self.store.create_reminder("daily", Schedule.daily(time(8), date(2026, 10, 31)), "Asia/Ho_Chi_Minh")
        self.assertEqual(daily.next_at, instant("2026-10-31", 1))
        late = instant("2027-01-02", 10)
        event, = self.store.collect_due(late)
        self.assertTrue(event.occurrence.catch_up)
        self.assertEqual(event.occurrence.scheduled_at, instant("2026-10-31", 1))
        self.assertEqual(self.store.collect_due(late), ())
        self.assertEqual(self.store.get_reminder(daily.id).next_at, instant("2027-01-03", 1))
        weekly = self.store.create_reminder("weekly", Schedule.weekly(time(9), (0, 4), date(2026, 10, 31)), "UTC")
        self.assertEqual(weekly.next_at, instant("2026-11-02", 9))
        event, = self.store.collect_due(instant("2026-11-06", 10))
        self.assertEqual(event.occurrence.scheduled_at, instant("2026-11-02", 9))
        self.assertEqual(self.store.get_reminder(weekly.id).next_at, instant("2026-11-09", 9))

    def test_update_cancel_complete_invalidate_only_pending(self):
        first = self.store.create_reminder("old", Schedule.daily(time(8), date(2026, 10, 31)), "UTC")
        event, = self.store.collect_due(instant("2026-10-31", 8))
        self.store.update_reminder(first.id, schedule=Schedule.daily(time(10), date(2026, 11, 1)))
        self.assertEqual(self.store.get_event(event.id).status, "invalidated")
        self.assertEqual(self.store.list_pending_events(), ())
        with self.assertRaisesRegex(ReminderError, "EVENT_STALE"):
            self.store.acknowledge_event(event.id)
        event2, = self.store.collect_due(instant("2026-11-01", 10))
        self.store.acknowledge_event(event2.id)
        self.store.complete_reminder(first.id)
        self.assertEqual(self.store.get_event(event2.id).status, "acknowledged")
        self.assertEqual(self.store.collect_due(instant("2026-11-02", 10)), ())
        other = self.store.create_reminder("other", Schedule.once(self.now))
        pending, = self.store.collect_due(self.now)
        self.store.cancel_reminder(other.id)
        self.assertEqual(self.store.get_event(pending.id).status, "invalidated")

    def test_content_edit_with_pending_event_invalidates_old_snapshot(self):
        reminder = self.store.create_reminder("old text", Schedule.once(self.now), "UTC")
        event, = self.store.collect_due(self.now)
        changed = self.store.update_reminder(reminder.id, content="new text")
        self.assertEqual(changed.revision, 2)
        self.assertEqual(self.store.get_event(event.id).content, "old text")
        self.assertEqual(self.store.get_event(event.id).status, "invalidated")
        self.assertEqual(self.store.list_pending_events(), ())
        replacement, = self.store.collect_due(self.now)
        self.assertEqual(replacement.content, "new text")
        self.assertEqual(replacement.occurrence.revision, 2)
        self.assertEqual(self.store.collect_due(self.now), ())

    def test_dst_offset_changes_utc_interval_and_long_gap_is_bounded(self):
        before = instant("2026-03-07", 13)  # 08:00 New York before spring DST
        with ReminderStore(self.root / "dst", clock=lambda: before - timedelta(minutes=1)) as store:
            reminder = store.create_reminder("daily", Schedule.daily(time(8), date(2026, 3, 7)),
                                             "America/New_York")
            self.assertEqual(reminder.next_at, before)
            store.collect_due(before)
            after = store.get_reminder(reminder.id).next_at
            self.assertEqual(after, instant("2026-03-08", 12))
            self.assertEqual(after - before, timedelta(hours=23))
        old = self.store.create_reminder("old", Schedule.daily(time(8), date(2026, 10, 31)), "UTC")
        with self.assertRaisesRegex(ReminderError, "SCHEDULE_RANGE_UNSUPPORTED"):
            self.store.collect_due(self.now + timedelta(days=3661))
        self.assertEqual(self.store.get_reminder(old.id).next_at, instant("2026-10-31", 8))

    def test_two_connections_one_occurrence_and_transaction_rollback(self):
        reminder = self.store.create_reminder("test", Schedule.once(self.now), "UTC")
        def poll(_):
            with ReminderStore(self.root, clock=lambda: self.now) as store:
                return store.collect_due(self.now)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(poll, range(2)))
        self.assertEqual(sum(map(len, results)), 1)
        self.assertEqual(len(self.store.list_pending_events()), 1)
        second = self.store.create_reminder("rollback", Schedule.once(self.now), "UTC")
        self.store.db.execute("""CREATE TRIGGER block_event BEFORE INSERT ON events
            WHEN NEW.reminder_id='""" + second.id + "' BEGIN SELECT RAISE(ABORT,'blocked'); END")
        with self.assertRaisesRegex(ReminderError, "DATABASE_ERROR"):
            self.store.collect_due(self.now)
        self.assertEqual(self.store.get_reminder(second.id).next_at, self.now)
        count = self.store.db.execute("SELECT COUNT(*) FROM occurrences WHERE reminder_id=?", (second.id,)).fetchone()[0]
        self.assertEqual(count, 0)

    def test_cli_help_does_not_create_database(self):
        from scripts.check_reminders import main
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--data-dir", str(self.root / "new"), "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertFalse((self.root / "new").exists())


if __name__ == "__main__":
    unittest.main()
