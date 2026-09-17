"""POSIX-only local private files; no chmod-after-writing secret exposure window."""
import json
import os
import secrets
import stat
import tempfile
from pathlib import Path
from .errors import DirectError

MAX_FILE = 8 * 1024 * 1024


def private_dir(path: Path) -> Path:
    path = path.expanduser().absolute()
    if os.name != 'posix':
        raise DirectError('platform_unsupported', 'Direct runtime currently supports macOS and Linux.', 503)
    # Reject existing symlink ancestors, including the leaf (do not follow a swapped profile).
    for ancestor in [*reversed(path.parents), path]:
        if ancestor.is_symlink():
            raise DirectError('unsafe_path', 'Runtime path must not contain symbolic links.', 400)
    if any((ancestor / '.git').exists() for ancestor in [path, *path.parents]):
        raise DirectError('runtime_in_repository', 'Private runtime state must be stored outside a Git checkout.', 400)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = path.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise DirectError('unsafe_owner', 'Runtime directory must belong to the current user.', 400)
    path.chmod(0o700)
    return path


def read_private(path: Path, limit: int = MAX_FILE) -> bytes:
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise DirectError('unsafe_permissions', 'Private file must be owned by you and mode 0600 (or 0400).', 400)
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise DirectError('file_too_large', 'Private file exceeds the supported size limit.', 400)
        return data
    except DirectError:
        raise
    except OSError:
        raise DirectError('private_file_unavailable', 'Private file is missing or cannot be opened safely.', 400) from None
    finally:
        if fd is not None:
            os.close(fd)


def atomic_private(path: Path, data: bytes) -> None:
    private_dir(path.parent)
    if path.is_symlink():
        raise DirectError('unsafe_path', 'Refusing to replace a symbolic link.', 400)
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, data: dict) -> None:
    atomic_private(path, json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'))


class ProcessLock:
    """Shared by importer, CLI and daemon; never steals a live process lock."""
    def __init__(self, home: Path):
        import fcntl
        self.fd = None
        private_dir(home)
        fd = os.open(home / 'runtime.lock', os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            os.close(fd)
            raise DirectError('unsafe_lock', 'Runtime lock file is unsafe.', 400)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise DirectError('runtime_busy', 'Another direct runtime or import is active in this home.', 409) from None
        self.fd = fd

    def close(self):
        if self.fd is not None:
            import fcntl
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def gateway_key(home: Path) -> str:
    path = home / 'gateway.key'
    if not path.exists():
        atomic_private(path, secrets.token_urlsafe(32).encode())
    key = read_private(path, 512).decode('ascii').strip()
    if len(key) < 24 or any(c.isspace() for c in key):
        raise DirectError('invalid_gateway_key', 'Local API key is invalid.', 400)
    return key
