"""cURL Parser: Extracts Prism credentials and session profile from DevTools Copy-as-cURL text."""

import re
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

from prism2api.transport.prism_web.live_profile import PrismLiveProfile
from prism2api.errors import AdmissionBlockedError

REQUIRED_PURE_HTTP_FIELDS = [
    "cookie_header",
    "user_id",
    "project_id",
    "conversation_id",
    "sandbox_url",
    "sandbox_token",
]


def parse_curl_command(curl_text: str) -> Dict[str, Optional[str]]:
    """Parse a DevTools 'Copy as cURL' text into extracted cookies, body json, and headers.

    Strictly refrains from supplying synthetic or default fallbacks; missing fields remain None.
    """
    clean = re.sub(r'\\\s*\n', ' ', curl_text).strip()

    cookie_header: Optional[str] = None

    # Match -b 'cookie_str' or -b "cookie_str" or -H 'cookie: cookie_str' or -H 'Cookie: cookie_str'
    cookie_match = re.search(r"(?:-b|-H\s+['\"]cookie:\s*)\s*['\"]([^'\"]+)['\"]", clean, re.IGNORECASE)
    if not cookie_match:
        cookie_match = re.search(r"-b\s+['\"]([^'\"]+)['\"]", clean)

    if cookie_match:
        cookie_header = cookie_match.group(1).strip()

    # Match --data-raw 'json_str' or -d 'json_str' or --data 'json_str'
    data_match = re.search(r"(?:--data-raw|-d|--data)\s+['\"]({.*})['\"]", clean, re.DOTALL)
    if not data_match:
        data_match = re.search(r"(?:--data-raw|-d|--data)\s+['\"]([^'\"]+)['\"]", clean, re.DOTALL)

    parsed_json: Dict[str, Any] = {}
    if data_match:
        raw_json_str = data_match.group(1).strip()
        try:
            parsed_json = json.loads(raw_json_str)
        except Exception:
            pass

    metadata = parsed_json.get("metadata", {}) if isinstance(parsed_json, dict) else {}
    turn_state = parsed_json.get("turn_state", {}) if isinstance(parsed_json, dict) else {}

    user_id = metadata.get("userId") or turn_state.get("user_id") or parsed_json.get("user_id")
    project_id = metadata.get("projectId") or turn_state.get("project_id") or parsed_json.get("project_id")
    conversation_id = parsed_json.get("conversationId") or turn_state.get("conversation_id") or parsed_json.get("conversation_id")
    sandbox_url = metadata.get("sandbox_url") or turn_state.get("sandbox_url")
    sandbox_token = metadata.get("sandbox_token") or turn_state.get("sandbox_token")

    return {
        "cookie_header": cookie_header,
        "user_id": user_id,
        "project_id": project_id,
        "conversation_id": conversation_id,
        "sandbox_url": sandbox_url,
        "sandbox_token": sandbox_token,
    }


def import_curl_to_profile(
    curl_text: str,
    profile_path: Optional[Path] = None,
    context_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extract profile credentials from cURL text and save:

    - live-profile.json: user_id, sandbox_url, sandbox_token, cookie_header
    - fixed-context.json: project_id, conversation_id
    Enforces mode 0600 on both files.
    """
    extracted = parse_curl_command(curl_text)

    # Check presence of required fields
    presence = {field: bool(extracted.get(field)) for field in REQUIRED_PURE_HTTP_FIELDS}
    is_complete = all(presence.values())
    status_str = "imported" if is_complete else "incomplete"

    if not extracted.get("cookie_header") or not extracted.get("user_id") or not extracted.get("sandbox_url") or not extracted.get("sandbox_token"):
        # We still save available secret fields to profile if user_id and cookie_header exist
        if not extracted.get("cookie_header"):
            raise AdmissionBlockedError("Failed to parse required Cookie header from provided cURL command.")

    profile = PrismLiveProfile(
        user_id=extracted.get("user_id") or "missing-user-id",
        sandbox_url=extracted.get("sandbox_url") or "",
        sandbox_token=extracted.get("sandbox_token") or "",
        cookie_header=extracted.get("cookie_header"),
    )

    save_profile_path = profile_path or (Path.home() / ".prism2api" / "live-profile.json")
    save_profile_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_profile_path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, indent=2)

    if os.name == "posix":
        save_profile_path.chmod(0o600)

    # Save fixed-context.json separately outside repo
    save_context_path = context_path or (Path.home() / ".prism2api" / "fixed-context.json")
    save_context_path.parent.mkdir(parents=True, exist_ok=True)

    context_data = {
        "project_id": extracted.get("project_id"),
        "conversation_id": extracted.get("conversation_id"),
    }

    with open(save_context_path, "w", encoding="utf-8") as f:
        json.dump(context_data, f, indent=2)

    if os.name == "posix":
        save_context_path.chmod(0o600)

    return {
        "status": status_str,
        "is_complete": is_complete,
        "presence": presence,
        "profile": profile,
        "context": context_data,
    }
