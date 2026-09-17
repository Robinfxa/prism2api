"""PrismLiveProfile: Local execution profile for Prism web transport endpoints."""

import os
import json
import stat
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from prism2api.errors import AdmissionBlockedError


class PrismLiveProfile(BaseModel):
    """Local execution profile containing live user identity and sandbox credentials.

    Loaded directly by PrismHttpTransport from ~/.prism2api/live-profile.json with 0600 permissions.
    NEVER stored in ContextBinding, RemoteHandle, or journal evidence.
    """

    user_id: str = Field(..., description="Remote user ID on prism.openai.com")
    sandbox_url: str = Field(..., description="Proxy URL for code execution sandbox")
    sandbox_token: str = Field(..., description="Authorization token for code execution sandbox")
    cookie_header: Optional[str] = Field(None, description="Raw Prism session cookie header string")

    @classmethod
    def load(cls, profile_path: Optional[Path] = None) -> "PrismLiveProfile":
        """Load live profile from file (~/.prism2api/live-profile.json by default) with 0600 permissions."""
        path_str = os.getenv("PRISM_LIVE_PROFILE")
        if profile_path:
            target_path = Path(profile_path)
        elif path_str:
            target_path = Path(path_str)
        else:
            target_path = Path.home() / ".prism2api" / "live-profile.json"

        if not target_path.exists():
            raise AdmissionBlockedError(f"PrismLiveProfile file not found at {target_path}")

        # Enforce POSIX file permission 0600 (not readable/writable by group or others)
        if os.name == "posix":
            st_mode = target_path.stat().st_mode
            if st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                try:
                    target_path.chmod(0o600)
                except Exception:
                    pass
                st_mode = target_path.stat().st_mode
                if st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                    raise AdmissionBlockedError(
                        f"PrismLiveProfile file {target_path} must have 0600 permissions (current mode: {oct(st_mode)})"
                    )

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        except AdmissionBlockedError:
            raise
        except Exception as exc:
            raise AdmissionBlockedError(f"Failed to load or parse PrismLiveProfile from {target_path}: {exc}") from exc
