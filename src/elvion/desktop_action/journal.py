"""Durable at-most-one dispatch reservation; no raw AX data or display values."""
from pathlib import Path
from contextlib import closing
import os
import sqlite3
import threading


class AttemptJournal:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def reserve(self, key, digest):
        # A reservation is deliberately never released, including after a crash.
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.path,os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,0o600)
            os.close(fd)
            with closing(sqlite3.connect(self.path, timeout=1)) as db:
                self.path.chmod(0o600)
                db.execute('PRAGMA synchronous=FULL')
                db.execute('CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, digest TEXT NOT NULL)')
                try:
                    db.execute('INSERT INTO attempts VALUES (?, ?)', (str(key), digest))
                except sqlite3.IntegrityError:
                    return False
                db.commit()
                return True
