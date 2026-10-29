"""Per-task JSONL traces with safe projection, restricted permissions and bounded reading.

Initial filesystem implementation targets macOS/Linux. It does not make audit/tamper-proof guarantees.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import re
import stat
import sys

from elvion.storage.trace_privacy import SCHEMA_VERSION, sanitize_record, uuid_text

MAX_TRACE_BYTES = 1024 * 1024
MAX_RECORDS = 256
TRACE_NAME = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl\Z")


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/ELVION"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "ELVION"


class TraceStorageError(ValueError):
    """Only a fixed code escapes the storage boundary; never raw exception text."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _check_file(fd: int) -> None:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        raise TraceStorageError("TRACE_UNSAFE_FILE")


@dataclass
class TraceSession:
    fd: int
    path: Path
    task_id: str
    trace_id: str
    records_written: int = 0
    error_code: str | None = None
    finalized: bool = False

    def _fail(self, code: str) -> None:
        self.error_code = code
        self.close()

    def write(self, raw: dict, *, kind: str) -> None:
        if self.fd < 0 or self.error_code is not None:
            return
        try:
            record = sanitize_record(raw, kind=kind)
            if record["task_id"] != self.task_id or record["trace_id"] != self.trace_id:
                raise ValueError("Trace identity changed")
            if self.records_written >= MAX_RECORDS:
                self._fail("TRACE_RECORD_LIMIT")
                return
            payload = (json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
            if len(payload) > 16 * 1024:
                self._fail("TRACE_RECORD_TOO_LARGE")
                return
            offset = 0
            while offset < len(payload):
                written = os.write(self.fd, payload[offset:])
                if written == 0:
                    raise OSError(errno.EIO, "Trace write failed")
                offset += written
            os.fsync(self.fd)
            self.records_written += 1
            if kind == "task_result":
                self.finalized = True
        except (OSError, ValueError, TypeError, OverflowError):
            self._fail("TRACE_WRITE_FAILED")

    def close(self) -> None:
        if self.fd >= 0:
            fd, self.fd = self.fd, -1
            try:
                os.close(fd)
            except OSError:
                self.error_code = self.error_code or "TRACE_CLOSE_FAILED"

    def summary(self) -> dict:
        status = ("saved" if self.finalized and self.error_code is None else
                  "partial" if self.records_written else "failed")
        return {"status": status, "path": str(self.path), "records_written": self.records_written,
                "error_code": self.error_code}


class TraceStore:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir).expanduser().absolute() if data_dir is not None else default_data_dir()
        self.directory = self.data_dir / "traces"

    @contextmanager
    def _directory_fd(self, *, create: bool = False):
        fd = -1
        try:
            if create:
                self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                self.directory.mkdir(mode=0o700, exist_ok=True)
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise TraceStorageError("TRACE_UNSAFE_DIRECTORY")
            if create:
                os.fchmod(fd, 0o700)
            yield fd
        except TraceStorageError:
            raise
        except FileNotFoundError:
            raise TraceStorageError("TRACE_NOT_FOUND") from None
        except (OSError, AttributeError, ValueError):
            raise TraceStorageError("TRACE_STORAGE_UNAVAILABLE") from None
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    raise TraceStorageError("TRACE_CLOSE_FAILED") from None

    def start(self, *, task_id, trace_id) -> TraceSession:
        task, trace = uuid_text(task_id), uuid_text(trace_id)
        if task is None or trace is None:
            raise TraceStorageError("TRACE_INVALID_ID")
        fd = -1
        try:
            with self._directory_fd(create=True) as directory:
                fd = os.open(f"{trace}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
                _check_file(fd)
                os.fchmod(fd, 0o600)
                os.fsync(directory)
            return TraceSession(fd=fd, path=self.directory / f"{trace}.jsonl", task_id=task, trace_id=trace)
        except TraceStorageError:
            if fd >= 0:
                os.close(fd)
            raise
        except (OSError, AttributeError):
            if fd >= 0:
                os.close(fd)
            raise TraceStorageError("TRACE_STORAGE_UNAVAILABLE") from None

    def _read(self, directory: int, trace: str) -> dict:
        fd = -1
        try:
            fd = os.open(f"{trace}.jsonl", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            _check_file(fd)
            with os.fdopen(fd, "rb") as stream:
                fd = -1
                blob = stream.read(MAX_TRACE_BYTES + 1)
            if len(blob) > MAX_TRACE_BYTES:
                raise TraceStorageError("TRACE_TOO_LARGE")
            lines = blob.splitlines()
            if len(lines) > MAX_RECORDS:
                raise TraceStorageError("TRACE_RECORD_LIMIT")
            records, malformed = [], 0
            task_id = None
            for line in lines:
                try:
                    raw = json.loads(line)
                    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw["schema_version"] != SCHEMA_VERSION:
                        raise ValueError("Unsupported trace schema")
                    record = sanitize_record(raw, kind=raw.get("kind"))
                    if record["trace_id"] != trace or (task_id is not None and record["task_id"] != task_id):
                        raise ValueError("Inconsistent identity")
                    task_id = record["task_id"]
                    records.append(record)
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    malformed += 1
            # A truncated last line is incomplete even if it happens to be valid JSON.
            partial_tail = bool(blob and not blob.endswith(b"\n"))
            finalized = bool(records and records[-1]["kind"] == "task_result" and not partial_tail and not malformed)
            return {"trace_id": trace, "records": records, "finalized": finalized,
                    "malformed_records": malformed, "partial_tail": partial_tail}
        except FileNotFoundError:
            raise TraceStorageError("TRACE_NOT_FOUND") from None
        except OSError:
            raise TraceStorageError("TRACE_READ_FAILED") from None
        finally:
            if fd >= 0:
                os.close(fd)

    def show(self, trace_id: str) -> dict:
        trace = uuid_text(trace_id)
        if trace is None:
            raise TraceStorageError("TRACE_INVALID_ID")
        with self._directory_fd() as directory:
            return self._read(directory, trace)

    def recent(self, limit: int = 10) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise TraceStorageError("TRACE_INVALID_LIMIT")
        if not self.directory.exists() and not self.directory.is_symlink():
            return []
        with self._directory_fd() as directory:
            files = []
            for name in os.listdir(directory):
                if TRACE_NAME.fullmatch(name):
                    try:
                        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    if stat.S_ISREG(info.st_mode):
                        files.append((info.st_mtime_ns, name[:-6]))
            summaries = []
            for _, trace in sorted(files, reverse=True)[:limit]:
                try:
                    data = self._read(directory, trace)
                except TraceStorageError as error:
                    summaries.append({"trace_id": trace, "finalized": False, "error_code": error.code})
                    continue
                records = data["records"]
                latest = records[-1] if records else {}
                summaries.append({"trace_id": trace, "task_id": latest.get("task_id"),
                                  "status": latest.get("status"), "selected_method": latest.get("selected_method"),
                                  "capability": latest.get("capability"), "error_code": latest.get("error_code"),
                                  "created_at": records[0]["created_at"] if records else None,
                                  "duration_ms": latest.get("duration_ms"), "simulated": latest.get("simulated"),
                                  "finalized": data["finalized"], "malformed_records": data["malformed_records"]})
            return summaries
