"""Independent reminder-core CLI; does not run ELVION actions or notifications."""

import argparse
from dataclasses import asdict
from datetime import date, datetime, time
import json
import sys

from elvion.reminders import ReminderError, ReminderStore, Schedule


def _datetime(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ReminderError("TIME_INVALID") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ReminderError("TIMEZONE_REQUIRED")
    return result


def _schedule(args):
    if args.kind is None:
        return None
    if args.kind == "once":
        if not args.at or args.time or args.start_date or args.weekdays:
            raise ReminderError("SCHEDULE_INVALID")
        return Schedule.once(_datetime(args.at))
    if args.at or not args.time or not args.start_date or (args.kind == "weekly" and not args.weekdays):
        raise ReminderError("SCHEDULE_INVALID")
    try:
        wall = time.fromisoformat(args.time)
        start = date.fromisoformat(args.start_date)
        days = tuple(int(item) for item in args.weekdays.split(",")) if args.weekdays else ()
    except (TypeError, ValueError):
        raise ReminderError("SCHEDULE_INVALID") from None
    return (Schedule.daily(wall, start) if args.kind == "daily" else
            Schedule.weekly(wall, days, start))


def _print(value):
    print(json.dumps(asdict(value) if hasattr(value, "__dataclass_fields__") else value,
                     ensure_ascii=False, default=lambda item: item.isoformat(), allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", help="ELVION data-dir; database is under reminders/")
    commands = parser.add_subparsers(dest="command", required=True)

    def schedule_options(command):
        command.add_argument("--kind", choices=("once", "daily", "weekly"))
        command.add_argument("--at", help="ISO datetime with UTC offset, for once")
        command.add_argument("--time", help="Local HH:MM for daily/weekly")
        command.add_argument("--start-date", help="Local YYYY-MM-DD for daily/weekly")
        command.add_argument("--weekdays", help="Comma-separated 0=Mon..6=Sun for weekly")

    create = commands.add_parser("create", help="Create a reminder")
    create.add_argument("--content", required=True)
    create.add_argument("--timezone", default="Asia/Ho_Chi_Minh")
    schedule_options(create)
    listing = commands.add_parser("list", help="List reminders")
    listing.add_argument("--status", choices=("active", "completed", "cancelled"))
    show = commands.add_parser("show", help="Show one reminder")
    show.add_argument("id")
    update = commands.add_parser("update", help="Update content or schedule")
    update.add_argument("id")
    update.add_argument("--content")
    update.add_argument("--timezone")
    schedule_options(update)
    for name in ("cancel", "complete", "ack"):
        command = commands.add_parser(name, help=f"{name} by UUID")
        command.add_argument("id")
    poll = commands.add_parser("poll-due", help="Record due events in SQLite; no notification")
    poll.add_argument("--now", help="Optional aware ISO datetime; defaults to current UTC time")
    commands.add_parser("events", help="List pending outbox events")

    args = parser.parse_args(argv)
    try:
        schedule = _schedule(args) if args.command in ("create", "update") else None
        if args.command == "create" and schedule is None:
            raise ReminderError("SCHEDULE_INVALID")
        with ReminderStore(args.data_dir) as store:
            if args.command == "create":
                value = store.create_reminder(args.content, schedule, args.timezone)
            elif args.command == "list":
                value = [asdict(item) for item in store.list_reminders(args.status)]
            elif args.command == "show":
                value = store.get_reminder(args.id)
            elif args.command == "update":
                value = store.update_reminder(args.id, content=args.content,
                                              schedule=schedule, timezone=args.timezone)
            elif args.command == "cancel":
                value = store.cancel_reminder(args.id)
            elif args.command == "complete":
                value = store.complete_reminder(args.id)
            elif args.command == "poll-due":
                value = [asdict(item) for item in store.collect_due(_datetime(args.now) if args.now else None)]
            elif args.command == "events":
                value = [asdict(item) for item in store.list_pending_events()]
            else:
                value = store.acknowledge_event(args.id)
        _print(value)
        return 0
    except ReminderError as exc:
        print(json.dumps({"error_code": exc.code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
