"""Bounded wall-clock scheduling and transactional SQLite outbox."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from elvion.storage.traces import default_data_dir

UTC = timezone.utc
MAX_CONTENT = 500
MAX_GAP_DAYS = 3660


class ReminderError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Schedule:
    kind: str
    at: datetime | None = None
    local_time: time | None = None
    weekdays: tuple[int, ...] = ()
    start_date: date | None = None

    @classmethod
    def once(cls, at: datetime):
        return cls("once", at=at)

    @classmethod
    def daily(cls, local_time: time, start_date: date):
        return cls("daily", local_time=local_time, start_date=start_date)

    @classmethod
    def weekly(cls, local_time: time, weekdays: tuple[int, ...], start_date: date):
        return cls("weekly", local_time=local_time, weekdays=weekdays, start_date=start_date)

    def __post_init__(self):
        if self.kind == "once":
            if type(self.at) is datetime and (self.at.tzinfo is None or self.at.utcoffset() is None):
                raise ReminderError("TIMEZONE_REQUIRED")
            if (type(self.at) is not datetime or self.local_time is not None or
                    self.weekdays or self.start_date is not None):
                raise ReminderError("SCHEDULE_INVALID")
            if isinstance(self.at.tzinfo, ZoneInfo):
                wall = self.at.replace(tzinfo=None)
                first = wall.replace(tzinfo=self.at.tzinfo, fold=0)
                second = wall.replace(tzinfo=self.at.tzinfo, fold=1)
                if (first.utcoffset() != second.utcoffset() or
                        self.at.astimezone(UTC).astimezone(self.at.tzinfo).replace(tzinfo=None) != wall):
                    raise ReminderError("SCHEDULE_DST_INVALID")
        elif self.kind in ("daily", "weekly"):
            if (self.at is not None or type(self.local_time) is not time or
                    self.local_time.tzinfo is not None or self.local_time.fold or
                    type(self.start_date) is not date or
                    (self.kind == "daily" and (type(self.weekdays) is not tuple or self.weekdays)) or
                    (self.kind == "weekly" and
                     (type(self.weekdays) is not tuple or not self.weekdays or
                      len(set(self.weekdays)) != len(self.weekdays) or
                      any(type(day) is not int or day not in range(7) for day in self.weekdays)))):
                raise ReminderError("SCHEDULE_INVALID")
        else:
            raise ReminderError("SCHEDULE_INVALID")


@dataclass(frozen=True)
class Reminder:
    id: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime
    timezone: str
    schedule: Schedule
    revision: int
    next_at: datetime | None


@dataclass(frozen=True)
class Occurrence:
    id: str
    reminder_id: str
    revision: int
    scheduled_at: datetime
    detected_at: datetime
    catch_up: bool


@dataclass(frozen=True)
class DueEvent:
    id: str
    occurrence: Occurrence
    content: str
    timezone: str
    status: str


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ReminderError("TIMEZONE_REQUIRED")
    return value.astimezone(UTC)


def _stamp(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse(value: str | None) -> datetime | None:
    return None if value is None else datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _zone(name: str) -> ZoneInfo:
    if type(name) is not str or not name or len(name) > 128:
        raise ReminderError("TIMEZONE_INVALID")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ReminderError("TIMEZONE_INVALID") from None


def _local_instant(day: date, wall: time, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, wall)
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)
    if (first.utcoffset() != second.utcoffset() or
            first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive):
        raise ReminderError("SCHEDULE_DST_INVALID")
    return first.astimezone(UTC)


def _next(schedule: Schedule, zone: ZoneInfo, lower: datetime, *, strict: bool = False) -> datetime | None:
    lower = _utc(lower)
    if schedule.kind == "once":
        at = _utc(schedule.at)
        return at if at > lower or (at == lower and not strict) else None
    local = lower.astimezone(zone)
    day = max(schedule.start_date, local.date())
    for offset in range(8):
        candidate = day + timedelta(days=offset)
        if schedule.kind == "weekly" and candidate.weekday() not in schedule.weekdays:
            continue
        if candidate == local.date() and (datetime.combine(candidate, schedule.local_time) <
                local.replace(tzinfo=None) or
                (strict and datetime.combine(candidate, schedule.local_time) == local.replace(tzinfo=None))):
            continue
        instant = _local_instant(candidate, schedule.local_time, zone)
        if instant > lower or (instant == lower and not strict):
            return instant
    raise ReminderError("SCHEDULE_INVALID")


def _next_after_gap(schedule: Schedule, zone: ZoneInfo, old: datetime, now: datetime) -> datetime:
    """Walk missed local dates with a hard bound so DST gaps cannot be skipped."""
    cursor = old.astimezone(zone).date()
    final = now.astimezone(zone).date()
    if (final - cursor).days > MAX_GAP_DAYS:
        raise ReminderError("SCHEDULE_RANGE_UNSUPPORTED")
    for offset in range((final - cursor).days + 9):
        day = cursor + timedelta(days=offset)
        if day < schedule.start_date or (schedule.kind == "weekly" and day.weekday() not in schedule.weekdays):
            continue
        instant = _local_instant(day, schedule.local_time, zone)
        if instant > now:
            return instant
    raise ReminderError("SCHEDULE_INVALID")


class ReminderStore:
    def __init__(self, data_dir: str | Path | None = None, *, clock=None):
        self.clock = clock if clock is not None else lambda: datetime.now(UTC)
        root = Path(data_dir).expanduser().absolute() if data_dir is not None else default_data_dir()
        self.directory = root / "reminders"
        self.path = self.directory / "reminders.sqlite3"
        self.db = None
        try:
            root.mkdir(parents=True, mode=0o700, exist_ok=True)
            root_info = root.lstat()
            if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid():
                raise ReminderError("DATABASE_UNSAFE_PATH")
            self.directory.mkdir(mode=0o700, exist_ok=True)
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise ReminderError("DATABASE_UNSAFE_PATH")
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                    raise ReminderError("DATABASE_UNSAFE_PATH")
                os.fchmod(fd, 0o600)
                self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
                self.db.row_factory = sqlite3.Row
                if os.fstat(fd).st_ino != self.path.stat().st_ino:
                    raise ReminderError("DATABASE_UNSAFE_PATH")
            finally:
                os.close(fd)
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA busy_timeout=5000")
            self._schema()
        except ReminderError:
            if self.db is not None:
                self.db.close()
            raise
        except (OSError, sqlite3.Error):
            if self.db is not None:
                self.db.close()
            raise ReminderError("DATABASE_ERROR") from None

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _transaction(self):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            yield
            self.db.execute("COMMIT")
        except BaseException as exc:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            if isinstance(exc, sqlite3.Error):
                raise ReminderError("DATABASE_ERROR") from None
            raise

    def _schema(self):
        with self._transaction():
            self.db.execute("CREATE TABLE IF NOT EXISTS meta (version INTEGER NOT NULL)")
            row = self.db.execute("SELECT version FROM meta").fetchone()
            if row is None:
                self.db.execute("INSERT INTO meta VALUES (1)")
            elif row["version"] != 1:
                raise ReminderError("SCHEMA_UNSUPPORTED")
            self.db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY, content TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, timezone TEXT NOT NULL,
                schedule_kind TEXT NOT NULL, at_utc TEXT, local_time TEXT, weekdays TEXT,
                start_date TEXT, revision INTEGER NOT NULL, next_at TEXT)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS occurrences (
                id TEXT PRIMARY KEY, reminder_id TEXT NOT NULL REFERENCES reminders(id),
                revision INTEGER NOT NULL, scheduled_at TEXT NOT NULL,
                detected_at TEXT NOT NULL, catch_up INTEGER NOT NULL,
                UNIQUE(reminder_id, revision, scheduled_at))""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, occurrence_id TEXT NOT NULL UNIQUE REFERENCES occurrences(id),
                reminder_id TEXT NOT NULL REFERENCES reminders(id), revision INTEGER NOT NULL,
                content TEXT NOT NULL, timezone TEXT NOT NULL, status TEXT NOT NULL)""")

    def _now(self, value=None):
        return _utc(self.clock() if value is None else value)

    @staticmethod
    def _content(value):
        if (type(value) is not str or not value.strip() or len(value) > MAX_CONTENT or
                any(ord(c) < 32 and c not in "\n\t" for c in value)):
            raise ReminderError("CONTENT_INVALID")
        return value

    @staticmethod
    def _schedule_fields(schedule):
        if type(schedule) is not Schedule:
            raise ReminderError("SCHEDULE_INVALID")
        return (schedule.kind, _stamp(schedule.at) if schedule.at is not None else None,
                schedule.local_time.isoformat() if schedule.local_time is not None else None,
                json.dumps(schedule.weekdays), schedule.start_date.isoformat() if schedule.start_date else None)

    @staticmethod
    def _reminder(row):
        schedule = Schedule(row["schedule_kind"], at=_parse(row["at_utc"]),
                            local_time=time.fromisoformat(row["local_time"]) if row["local_time"] else None,
                            weekdays=tuple(json.loads(row["weekdays"])),
                            start_date=date.fromisoformat(row["start_date"]) if row["start_date"] else None)
        return Reminder(row["id"], row["content"], row["status"], _parse(row["created_at"]),
                        _parse(row["updated_at"]), row["timezone"], schedule, row["revision"], _parse(row["next_at"]))

    def _row(self, reminder_id):
        row = self.db.execute("SELECT * FROM reminders WHERE id=?", (str(reminder_id),)).fetchone()
        if row is None:
            raise ReminderError("REMINDER_NOT_FOUND")
        return row

    def create_reminder(self, content: str, schedule: Schedule, timezone: str = "Asia/Ho_Chi_Minh") -> Reminder:
        content = self._content(content)
        fields = self._schedule_fields(schedule)
        zone = _zone(timezone)
        now = self._now()
        due = _utc(schedule.at) if schedule.kind == "once" else _next(schedule, zone, now)
        reminder_id = str(uuid4())
        with self._transaction():
            self.db.execute("INSERT INTO reminders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (reminder_id, content, "active", _stamp(now), _stamp(now), timezone,
                             *fields, 1, _stamp(due) if due else None))
        return self.get_reminder(reminder_id)

    def get_reminder(self, reminder_id) -> Reminder:
        try:
            return self._reminder(self._row(reminder_id))
        except sqlite3.Error:
            raise ReminderError("DATABASE_ERROR") from None

    def list_reminders(self, status: str | None = None) -> tuple[Reminder, ...]:
        if status is not None and status not in ("active", "completed", "cancelled"):
            raise ReminderError("STATUS_INVALID")
        try:
            rows = self.db.execute("SELECT * FROM reminders WHERE (? IS NULL OR status=?) ORDER BY created_at,id",
                                   (status, status)).fetchall()
            return tuple(self._reminder(row) for row in rows)
        except sqlite3.Error:
            raise ReminderError("DATABASE_ERROR") from None

    def update_reminder(self, reminder_id, *, content: str | None = None,
                        schedule: Schedule | None = None, timezone: str | None = None) -> Reminder:
        if content is None and schedule is None and timezone is None:
            raise ReminderError("UPDATE_EMPTY")
        now = self._now()
        with self._transaction():
            current = self._reminder(self._row(reminder_id))
            if current.status != "active":
                raise ReminderError("REMINDER_INACTIVE")
            new_content = self._content(content) if content is not None else current.content
            new_schedule = schedule if schedule is not None else current.schedule
            fields = self._schedule_fields(new_schedule)
            new_zone = timezone if timezone is not None else current.timezone
            zone = _zone(new_zone)
            changed_schedule = new_schedule != current.schedule or new_zone != current.timezone
            if new_content == current.content and not changed_schedule:
                return current
            due = ((_utc(new_schedule.at) if new_schedule.kind == "once" else _next(new_schedule, zone, now))
                   if changed_schedule else current.next_at)
            if not changed_schedule:
                pending = self.db.execute("""SELECT MIN(o.scheduled_at) AS scheduled_at
                    FROM events e JOIN occurrences o ON o.id=e.occurrence_id
                    WHERE e.reminder_id=? AND e.status='pending'""", (current.id,)).fetchone()["scheduled_at"]
                if pending is not None and (due is None or pending < _stamp(due)):
                    due = _parse(pending)
            revision = current.revision + 1
            self.db.execute("UPDATE events SET status='invalidated' WHERE reminder_id=? AND status='pending'",
                            (current.id,))
            self.db.execute("""UPDATE reminders SET content=?, updated_at=?, timezone=?,
                schedule_kind=?, at_utc=?, local_time=?, weekdays=?, start_date=?, revision=?, next_at=? WHERE id=?""",
                (new_content, _stamp(now), new_zone, *fields, revision,
                 _stamp(due) if due else None, current.id))
        return self.get_reminder(reminder_id)

    def _end(self, reminder_id, status):
        now = self._now()
        with self._transaction():
            current = self._reminder(self._row(reminder_id))
            if current.status == status:
                return current
            if current.status != "active":
                raise ReminderError("REMINDER_INACTIVE")
            self.db.execute("UPDATE events SET status='invalidated' WHERE reminder_id=? AND status='pending'",
                            (current.id,))
            self.db.execute("UPDATE reminders SET status=?, updated_at=?, next_at=NULL WHERE id=?",
                            (status, _stamp(now), current.id))
        return self.get_reminder(reminder_id)

    def cancel_reminder(self, reminder_id):
        return self._end(reminder_id, "cancelled")

    def complete_reminder(self, reminder_id):
        return self._end(reminder_id, "completed")

    def collect_due(self, now: datetime | None = None) -> tuple[DueEvent, ...]:
        now = self._now(now)
        created = []
        with self._transaction():
            rows = self.db.execute("SELECT * FROM reminders WHERE status='active' AND next_at<=? ORDER BY next_at,id",
                                   (_stamp(now),)).fetchall()
            for row in rows:
                reminder = self._reminder(row)
                scheduled = reminder.next_at
                next_at = (None if reminder.schedule.kind == "once" else
                           _next_after_gap(reminder.schedule, _zone(reminder.timezone), scheduled, now))
                occurrence_id, event_id = str(uuid4()), str(uuid4())
                self.db.execute("INSERT INTO occurrences VALUES (?,?,?,?,?,?)",
                                (occurrence_id, reminder.id, reminder.revision, _stamp(scheduled),
                                 _stamp(now), int(scheduled < now)))
                self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                                (event_id, occurrence_id, reminder.id, reminder.revision,
                                 reminder.content, reminder.timezone, "pending"))
                self.db.execute("UPDATE reminders SET next_at=? WHERE id=?",
                                (_stamp(next_at) if next_at else None, reminder.id))
                created.append(event_id)
        return tuple(self.get_event(event_id) for event_id in created)

    @staticmethod
    def _event(row):
        occurrence = Occurrence(row["occurrence_id"], row["reminder_id"], row["revision"],
                                _parse(row["scheduled_at"]), _parse(row["detected_at"]),
                                bool(row["catch_up"]))
        return DueEvent(row["id"], occurrence, row["content"], row["timezone"], row["status"])

    def get_event(self, event_id) -> DueEvent:
        try:
            row = self.db.execute("""SELECT e.*,o.scheduled_at,o.detected_at,o.catch_up
                FROM events e JOIN occurrences o ON o.id=e.occurrence_id WHERE e.id=?""",
                (str(event_id),)).fetchone()
            if row is None:
                raise ReminderError("EVENT_NOT_FOUND")
            return self._event(row)
        except sqlite3.Error:
            raise ReminderError("DATABASE_ERROR") from None

    def list_pending_events(self) -> tuple[DueEvent, ...]:
        try:
            rows = self.db.execute("""SELECT e.*,o.scheduled_at,o.detected_at,o.catch_up
                FROM events e JOIN occurrences o ON o.id=e.occurrence_id
                JOIN reminders r ON r.id=e.reminder_id
                WHERE e.status='pending' AND r.status='active' AND r.revision=e.revision
                ORDER BY o.scheduled_at,e.id""").fetchall()
            return tuple(self._event(row) for row in rows)
        except sqlite3.Error:
            raise ReminderError("DATABASE_ERROR") from None

    def acknowledge_event(self, event_id) -> DueEvent:
        with self._transaction():
            event = self.get_event(event_id)
            if event.status == "invalidated":
                raise ReminderError("EVENT_STALE")
            if event.status == "pending":
                current = self._reminder(self._row(event.occurrence.reminder_id))
                if current.status != "active" or current.revision != event.occurrence.revision:
                    raise ReminderError("EVENT_STALE")
                self.db.execute("UPDATE events SET status='acknowledged' WHERE id=?", (event.id,))
        return self.get_event(event_id)
