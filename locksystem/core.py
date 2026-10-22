"""Small, local access controller. Credentials and lockouts survive restarts."""

import hashlib
import hmac
import math
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from .ownership import DatabaseOwner

ITERATIONS = 600_000
MAX_ATTEMPTS = 5
COOLDOWN = 30
OPEN_SECONDS = 15


def valid_pin(pin):
    return isinstance(pin, str) and 6 <= len(pin) <= 12 and pin.isascii() and pin.isdigit()


class DigitalLock:
    def __init__(self, database, *, wall_clock=time.time, clock=time.monotonic):
        self.wall_clock, self.clock = wall_clock, clock
        self.mutex = threading.RLock()
        self.open_until = 0.0
        self.cooldown_until = 0.0
        self.closed = False
        if str(database) != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.owner = DatabaseOwner(database)
        self.db = None
        try:
            self.db = sqlite3.connect(str(database), check_same_thread=False)
            self.db.execute("PRAGMA busy_timeout=3000")
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS credential (
                id INTEGER PRIMARY KEY CHECK(id=1), salt BLOB NOT NULL,
                digest BLOB NOT NULL, iterations INTEGER NOT NULL,
                failures INTEGER NOT NULL DEFAULT 0, blocked_until REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL);
            ''')
            self.db.commit()
            row = self._row()
            if row:
                salt, digest, iterations, failures, deadline = row
                if (not isinstance(salt, bytes) or len(salt) != 16
                        or not isinstance(digest, bytes) or len(digest) != 32
                        or type(iterations) is not int or not 1 <= iterations <= 10_000_000
                        or type(failures) is not int or not 0 <= failures <= MAX_ATTEMPTS
                        or not isinstance(deadline, (int, float)) or not math.isfinite(deadline)
                        or deadline < 0 or bool(deadline) != (failures == MAX_ATTEMPTS)):
                    raise ValueError("The credential record is invalid. Restore a trusted backup; no access was granted.")
                remaining = min(COOLDOWN, max(0, deadline - self.wall_clock()))
                if remaining:
                    self.cooldown_until = self.clock() + remaining
        except Exception:
            if self.db is not None:
                self.db.close()
            self.owner.close()
            raise

    def _row(self):
        return self.db.execute("SELECT salt,digest,iterations,failures,blocked_until FROM credential WHERE id=1").fetchone()

    def _event(self, action):
        self.db.execute("INSERT INTO events(at,action) VALUES (?,?)", (self.wall_clock(), action))
        self.db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 200)")

    def _tick(self):
        row = self._row()
        with self.db:
            if self.open_until and self.clock() >= self.open_until:
                self.open_until = 0
                self._event("auto_locked")
            if row and row[4] and self.clock() >= self.cooldown_until:
                self.db.execute("UPDATE credential SET failures=0,blocked_until=0 WHERE id=1")
                self.cooldown_until = 0
                self._event("cooldown_finished")

    def status(self):
        with self.mutex:
            self._tick()
            row = self._row()
            cooldown = max(0, math.ceil(self.cooldown_until - self.clock()))
            opened = max(0, math.ceil(self.open_until - self.clock()))
            return {"state": "UNCONFIGURED" if not row else "LOCKOUT" if cooldown else "UNLOCKED" if opened else "LOCKED",
                    "remaining": opened, "cooldown": cooldown,
                    "attempts_left": MAX_ATTEMPTS - row[3] if row else MAX_ATTEMPTS,
                    "events": [{"time": t, "action": a} for t, a in self.db.execute(
                        "SELECT at,action FROM events ORDER BY id DESC LIMIT 20")]}

    def setup(self, pin):
        with self.mutex:
            if self._row():
                raise ValueError("A PIN is already configured.")
            if not valid_pin(pin):
                raise ValueError("Use 6 to 12 ASCII digits.")
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, ITERATIONS)
            with self.db:
                self.db.execute("INSERT INTO credential(id,salt,digest,iterations) VALUES (1,?,?,?)", (salt, digest, ITERATIONS))
                self._event("configured")
            return self.status()

    def _verify(self, pin):
        self._tick()
        row = self._row()
        if not row:
            raise ValueError("Create a PIN first.")
        if self.clock() < self.cooldown_until:
            return False
        if not valid_pin(pin):
            raise ValueError("Use 6 to 12 ASCII digits.")
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), row[0], row[2])
        if hmac.compare_digest(digest, row[1]):
            with self.db:
                self.db.execute("UPDATE credential SET failures=0,blocked_until=0 WHERE id=1")
            return True
        failures = row[3] + 1
        blocked = self.wall_clock() + COOLDOWN if failures >= MAX_ATTEMPTS else 0
        self.open_until = 0
        with self.db:
            self.db.execute("UPDATE credential SET failures=?,blocked_until=? WHERE id=1", (failures, blocked))
            self._event("lockout_started" if blocked else "access_denied")
        if blocked:
            self.cooldown_until = self.clock() + COOLDOWN
        return False

    def unlock(self, pin):
        with self.mutex:
            ok = self._verify(pin)
            if ok:
                self.open_until = self.clock() + OPEN_SECONDS
                with self.db:
                    self._event("unlocked")
            return {"ok": ok, **self.status()}

    def lock(self):
        with self.mutex:
            self.open_until = 0
            with self.db:
                self._event("manually_locked")
            return self.status()

    def change_pin(self, current_pin, new_pin):
        with self.mutex:
            if not valid_pin(new_pin):
                raise ValueError("The new PIN must contain 6 to 12 ASCII digits.")
            if not self._verify(current_pin):
                return {"ok": False, **self.status()}
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", new_pin.encode(), salt, ITERATIONS)
            with self.db:
                self.db.execute("UPDATE credential SET salt=?,digest=?,iterations=? WHERE id=1", (salt, digest, ITERATIONS))
                self._event("pin_changed")
            self.open_until = 0
            return {"ok": True, **self.status()}

    def protected_content(self):
        with self.mutex:
            if self.status()["state"] != "UNLOCKED":
                raise PermissionError("Unlock the system first.")
            return {"message": "Access granted. This response passed the Python lock's authorization check."}

    def close(self):
        with self.mutex:
            if not self.closed:
                self.open_until = 0
                self.db.close()
                self.owner.close()
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
