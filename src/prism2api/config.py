"""Configuration settings for prism2api."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class TimeoutsConfig(BaseModel):
    queue_wait_seconds: float = 30.0
    preparation_seconds: float = 15.0
    submit_ack_seconds: float = 10.0
    first_output_seconds: float = 20.0
    inter_event_seconds: float = 15.0
    total_run_seconds: float = 300.0
    cleanup_seconds: float = 10.0


class LimitsConfig(BaseModel):
    max_queue_size: int = 100
    max_text_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_event_count: int = 10000
    idempotency_tombstone_days: int = 7


class Settings(BaseModel):
    home_dir: Path = Field(
        default_factory=lambda: Path(
            os.getenv("PRISM2API_HOME", Path.home() / ".prism2api")
        ).resolve()
    )
    api_key: str = Field(
        default_factory=lambda: os.getenv("PRISM2API_KEY", "prism-local-key")
    )
    loopback_only: bool = True
    allowed_hosts: List[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "testserver"])
    allowed_origins: List[str] = Field(default_factory=list)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    secret_salt: str = Field(default="prism2api-local-secret-salt")

    @property
    def db_path(self) -> Path:
        return self.home_dir / "runtime.db"

    @property
    def inputs_dir(self) -> Path:
        return self.home_dir / "inputs"

    @property
    def results_dir(self) -> Path:
        return self.home_dir / "results"

    @property
    def evidence_dir(self) -> Path:
        return self.home_dir / "evidence"

    @property
    def credentials_dir(self) -> Path:
        return self.home_dir / "credentials"

    @property
    def browser_profile_dir(self) -> Path:
        return self.home_dir / "browser-profile"

    @property
    def logs_dir(self) -> Path:
        return self.home_dir / "logs"

    @property
    def locks_dir(self) -> Path:
        return self.home_dir / "locks"

    @property
    def lock_file_path(self) -> Path:
        return self.locks_dir / "prism2api.lock"

    def ensure_directories(self) -> None:
        """Create necessary home directories with proper permissions."""
        self.home_dir.mkdir(parents=True, exist_ok=True)
        for d in [
            self.inputs_dir,
            self.results_dir,
            self.evidence_dir,
            self.credentials_dir,
            self.browser_profile_dir,
            self.logs_dir,
            self.locks_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
            # Secure POSIX permissions for credential & data directories
            if os.name == "posix":
                try:
                    os.chmod(d, 0o700)
                except OSError:
                    pass
