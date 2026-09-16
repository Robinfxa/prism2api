"""POSIX home ownership. Not a remote fencing/exactly-once mechanism."""
import os
from pathlib import Path

class SingleInstanceLockError(RuntimeError):
    pass

class HomeLock:
    def __init__(self, path: Path):
        if os.name != "posix":
            raise RuntimeError("This release supports macOS/Linux runtime ownership only")
        import fcntl
        self.fd = None
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            os.close(fd)
            raise SingleInstanceLockError("Runtime home already has a writer") from exc
        self.fd = fd

    def close(self):
        if self.fd is not None:
            import fcntl
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
