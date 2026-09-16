"""Configuration settings for prism2api."""

import os
from pathlib import Path
import math
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class TimeoutsConfig(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def positive_finite(cls, value):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Timeout must be positive and finite")
        return value

    queue_wait_seconds: float = 30.0
    preparation_seconds: float = 15.0
    submit_ack_seconds: float = 10.0
    first_output_seconds: float = 20.0
    inter_event_seconds: float = 15.0
    total_run_seconds: float = 300.0
    cleanup_seconds: float = 10.0


class LimitsConfig(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def nonnegative(cls, value):
        if value < 0:
            raise ValueError("Limit must be nonnegative")
        return value

    max_queue_size: int = 100
    max_text_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_event_count: int = 10000
    max_event_bytes: int = 1024 * 1024
    max_total_event_bytes: int = 16 * 1024 * 1024
    max_created_contexts: int = 100
    max_http_body_bytes: int = 12 * 1024 * 1024
    idempotency_tombstone_days: int = 7


class Settings(BaseModel):
    home_dir: Path = Field(
        default_factory=lambda: Path(
            os.getenv("PRISM2API_HOME", Path.home() / ".prism2api")
        ).resolve()
    )
    api_key: str = Field(
        default_factory=lambda: os.getenv("PRISM2API_KEY", "")
    )
    loopback_only: bool = True
    allowed_hosts: List[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "::1", "testserver"])
    allowed_origins: List[str] = Field(default_factory=list)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    secret_salt: str = ""
    transport_mode: Literal["unconfigured", "mock"] = "unconfigured"

    @field_validator("home_dir")
    @classmethod
    def resolve_home(cls, value):
        return value.expanduser().resolve()


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
        self.home_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            os.chmod(self.home_dir, 0o700)
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
                os.chmod(d, 0o700)

    def load_local_secrets(self):
        # Called only after the home lock is held. No secrets printed or returned by API.
        import secrets
        for attr, filename in (("api_key", "gateway.key"), ("secret_salt", "fingerprint.key")):
            if getattr(self, attr):
                continue
            path = self.credentials_dir / filename
            if path.is_symlink():
                raise RuntimeError("Refusing symlinked secret file")
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if not value:
                    raise RuntimeError("Empty local secret file")
            else:
                value = secrets.token_urlsafe(32)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(value + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            if os.name == "posix":
                os.chmod(path, 0o600)
            setattr(self, attr, value)
