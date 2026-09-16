"""SDK Client for prism2api (embedded and daemon modes)."""

import fcntl
import os
import time
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

from prism2api.config import Settings
from prism2api.storage.journal import StorageJournal, GenerationResult
from prism2api.runtime.supervisor import RunSupervisor, RunRecord, RunState
from prism2api.provider.models import CapabilitySnapshot
from prism2api.runtime.context import ContextPolicy


class ClientMode(str, Enum):
    EMBEDDED = "embedded"
    DAEMON = "daemon"


class SingleInstanceLockError(Exception):
    """Raised when another process holds the single-instance OS file lock."""
    pass


class SDKClient:
    """Python SDK Client for prism2api."""

    def __init__(self, mode: ClientMode = ClientMode.EMBEDDED, settings: Optional[Settings] = None):
        self.mode = mode
        self.settings = settings or Settings()
        self.settings.ensure_directories()
        self._lock_fd: Optional[int] = None

        if self.mode == ClientMode.EMBEDDED:
            self._acquire_os_lock()
            self.journal = StorageJournal(self.settings)
            self.supervisor = RunSupervisor(self.settings, self.journal)
        else:
            # Daemon mode uses HTTP client (not holding local OS lock)
            self.journal = None
            self.supervisor = None

    def _acquire_os_lock(self) -> None:
        """Acquire OS file lock for embedded mode (T06 invariant)."""
        lock_path = self.settings.lock_file_path
        try:
            fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd = fd
        except (OSError, IOError) as exc:
            raise SingleInstanceLockError(
                f"Could not acquire OS lock on {lock_path}. Another process is running embedded mode."
            ) from exc

    def close(self) -> None:
        """Release OS lock and close storage journal."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except OSError:
                pass
            self._lock_fd = None

        if self.journal:
            self.journal.close()

    def submit(
        self,
        input_text: str,
        model_alias: str = "prism-default",
        context_policy: ContextPolicy = ContextPolicy.ISOLATED,
        idempotency_key: Optional[str] = None,
    ) -> RunRecord:
        """Submit generation run."""
        if self.mode == ClientMode.EMBEDDED:
            return self.supervisor.enqueue_run(
                principal_id="default_principal",
                input_text=input_text,
                model_alias=model_alias,
                context_policy=context_policy,
                idempotency_key=idempotency_key,
            )
        else:
            raise NotImplementedError("Daemon mode HTTP submit calls require running API server.")

    def execute_and_wait(self, input_text: str, model_alias: str = "prism-default") -> GenerationResult:
        """Submit and synchronously execute run."""
        if self.mode == ClientMode.EMBEDDED:
            record = self.submit(input_text, model_alias)
            return self.supervisor.execute_run(record.run_id, input_text, model_alias)
        else:
            raise NotImplementedError("Daemon mode requires API server.")

    def get_run(self, run_id: str) -> RunRecord:
        """Get run status."""
        if self.mode == ClientMode.EMBEDDED:
            return self.supervisor.get_run(run_id)
        else:
            raise NotImplementedError("Daemon mode requires API server.")

    def cancel(self, run_id: str) -> RunRecord:
        """Cancel run."""
        if self.mode == ClientMode.EMBEDDED:
            return self.supervisor.cancel_run(run_id)
        else:
            raise NotImplementedError("Daemon mode requires API server.")

    def capabilities(self) -> List[CapabilitySnapshot]:
        """List capabilities."""
        if self.mode == ClientMode.EMBEDDED:
            return self.supervisor.adapter.inspect_capabilities()
        else:
            raise NotImplementedError("Daemon mode requires API server.")
