"""Fixed-oracle reminder regression; never waits or sends notifications."""

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from elvion.reminders import ReminderStore, Schedule

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _case(name, store):
    """Return observed/expected scheduled instants and stale pending expectation."""
    if name == "once-before":
        store.create_reminder("synthetic", Schedule.once(START + timedelta(hours=1)), "UTC")
        actual = store.collect_due(START)
        expected, stale = (), 0
    elif name == "once-exact":
        store.create_reminder("synthetic", Schedule.once(START), "UTC")
        actual = store.collect_due(START)
        expected, stale = (START,), 0
    elif name == "once-overdue":
        store.create_reminder("synthetic", Schedule.once(START - timedelta(days=3)), "UTC")
        actual = store.collect_due(START)
        expected, stale = (START - timedelta(days=3),), 0
    elif name == "daily-long-gap":
        store.create_reminder("synthetic", Schedule.daily(time(8), date(2026, 1, 1)), "UTC")
        actual = store.collect_due(START + timedelta(days=100, hours=9))
        expected, stale = (START + timedelta(hours=8),), 0
    elif name == "weekly-selected":
        store.create_reminder("synthetic", Schedule.weekly(time(9), (0, 4), date(2026, 1, 1)), "UTC")
        actual = store.collect_due(START + timedelta(days=5))
        expected, stale = (START + timedelta(days=1, hours=9),), 0
    elif name == "poll-repeat":
        store.create_reminder("synthetic", Schedule.once(START), "UTC")
        actual = store.collect_due(START) + store.collect_due(START)
        expected, stale = (START,), 0
    elif name == "update-invalidates":
        reminder = store.create_reminder("synthetic", Schedule.daily(time(0), date(2026, 1, 1)), "UTC")
        actual = store.collect_due(START)
        store.update_reminder(reminder.id, schedule=Schedule.daily(time(8), date(2026, 1, 2)))
        expected, stale = (START,), 0
    elif name in ("cancel-invalidates", "complete-invalidates"):
        reminder = store.create_reminder("synthetic", Schedule.once(START), "UTC")
        actual = store.collect_due(START)
        (store.cancel_reminder if name.startswith("cancel") else store.complete_reminder)(reminder.id)
        expected, stale = (START,), 0
    else:
        raise AssertionError(name)
    observed = tuple(event.occurrence.scheduled_at for event in actual)
    pending = store.list_pending_events()
    invalid = sum(1 for event in actual if store.get_event(event.id).status == "invalidated")
    expected_invalid = 1 if name.endswith("invalidates") else 0
    duplicate = store.db.execute("""SELECT COUNT(*) - COUNT(DISTINCT reminder_id || '/' || revision || '/' || scheduled_at)
        FROM occurrences""").fetchone()[0]
    return observed, expected, len(pending), invalid, expected_invalid, duplicate


CASES = ("once-before", "once-exact", "once-overdue", "daily-long-gap",
         "weekly-selected", "poll-repeat", "update-invalidates",
         "cancel-invalidates", "complete-invalidates")


def score():
    rows = []
    totals = dict(missed_expected_events=0, unexpected_events=0, duplicate_occurrences_events=0,
                  invalid_events_still_pending=0, external_actions=0)
    for name in CASES:
        try:
            with TemporaryDirectory() as root, ReminderStore(root, clock=lambda: START) as store:
                observed, expected, pending, invalid, expected_invalid, duplicate = _case(name, store)
                missed = len(set(expected) - set(observed))
                unexpected = len(set(observed) - set(expected))
                duplicate += len(observed) - len(set(observed))
                stale = pending if name.endswith("invalidates") else 0
                passed = (not missed and not unexpected and not duplicate and not stale and
                          invalid == expected_invalid and len(observed) == len(expected))
                totals["missed_expected_events"] += missed
                totals["unexpected_events"] += unexpected
                totals["duplicate_occurrences_events"] += duplicate
                totals["invalid_events_still_pending"] += stale
        except Exception:
            passed = False
            totals["missed_expected_events"] += 1
        rows.append({"case": name, "passed": passed})
    return {"synthetic_only": True, "scenarios": len(CASES),
            "passed": sum(row["passed"] for row in rows),
            "failed": sum(not row["passed"] for row in rows), **totals, "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/benchmarks/reminders"))
    args = parser.parse_args(argv)
    result = score()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "latest.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), **{key: result[key] for key in
                     ("scenarios", "passed", "failed", "missed_expected_events",
                      "unexpected_events", "duplicate_occurrences_events",
                      "invalid_events_still_pending", "external_actions")}}))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
