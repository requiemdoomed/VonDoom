"""Keep two controllers from changing the same database at once."""

import os
from pathlib import Path


class DatabaseOwner:
    def __init__(self, database):
        self.file = None
        if str(database) == ":memory:":
            return
        path = Path(database).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(str(path) + ".lock", "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0, os.SEEK_END)
                if self.file.tell() == 0:
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise OSError("This database is already in use, or its ownership file cannot be locked. Stop the other controller first.") from exc

    def close(self):
        if self.file is not None:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None
