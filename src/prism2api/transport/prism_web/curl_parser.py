"""cURL Parser: Extracts Prism credentials and session profile from DevTools Copy-as-cURL text."""

import re
import json
import os
import shlex
import argparse
from typing import Dict, Any, Optional
from pathlib import Path

from prism2api.transport.prism_web.live_profile import PrismLiveProfile
from prism2api.errors import AdmissionBlockedError


def parse_curl_command(curl_text: str) -> Dict[str, Any]:
    """Parse a DevTools 'Copy as cURL' text into extracted cookies, body json, and headers."""
    # Normalize multiline backslashes and whitespace
    clean = re.sub(r'\\\s*\n', ' ', curl_text).strip()

    cookie_header = ""

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

    # Extract fields from payload
    metadata = parsed_json.get("metadata", {}) if isinstance(parsed_json, dict) else {}
    turn_state = parsed_json.get("turn_state", {}) if isinstance(parsed_json, dict) else {}

    user_id = (
        metadata.get("userId")
        or turn_state.get("user_id")
        or parsed_json.get("user_id")
        or "user-default"
    )

    project_id = (
        metadata.get("projectId")
        or turn_state.get("project_id")
        or parsed_json.get("project_id")
        or ""
    )

    conversation_id = (
        parsed_json.get("conversationId")
        or turn_state.get("conversation_id")
        or parsed_json.get("conversation_id")
        or ""
    )

    sandbox_url = (
        metadata.get("sandbox_url")
        or turn_state.get("sandbox_url")
        or "https://prism.openai.com/s/sandboxes/proxy/"
    )

    sandbox_token = (
        metadata.get("sandbox_token")
        or turn_state.get("sandbox_token")
        or ""
    )

    return {
        "cookie_header": cookie_header,
        "user_id": user_id,
        "project_id": project_id,
        "conversation_id": conversation_id,
        "sandbox_url": sandbox_url,
        "sandbox_token": sandbox_token,
    }


def import_curl_to_profile(curl_text: str, target_path: Optional[Path] = None) -> PrismLiveProfile:
    """Extract profile credentials from cURL text and save to ~/.prism2api/live-profile.json with 0600 mode."""
    extracted = parse_curl_command(curl_text)

    if not extracted["cookie_header"]:
        raise AdmissionBlockedError("Failed to parse Cookie header from provided cURL command.")

    profile = PrismLiveProfile(
        user_id=extracted["user_id"],
        sandbox_url=extracted["sandbox_url"],
        sandbox_token=extracted["sandbox_token"],
        cookie_header=extracted["cookie_header"],
    )

    save_path = target_path or (Path.home() / ".prism2api" / "live-profile.json")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, indent=2)

    if os.name == "posix":
        save_path.chmod(0o600)

    return profile
