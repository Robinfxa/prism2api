"""Deterministic repository security test scanning for leaked tokens, cookies, and real identifiers."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Patterns that MUST NOT appear in any tracked repository file
FORBIDDEN_PATTERNS = [
    (re.compile(r"proj_fixture_001"), "Real project ID literal"),
    (re.compile(r"user_fixture_001"), "Real user ID literal"),
    (re.compile(r"cdx1_fixture_conv_001"), "Real conversation ID literal"),
    (re.compile(r"gAAAAABqqy"), "Real sandbox token literal"),
    (re.compile(r"eyJhbGciOi[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "Raw JWT literal"),
    (re.compile(r"prism_oai_access_token=REDACTED"), "Real OAuth access token cookie literal"),
    (re.compile(r"prism_session_token=REDACTED"), "Real session token cookie literal"),
]

# Directories and extensions to scan
SCAN_DIRS = ["src", "docs", "tests", "Agent-init", "openspec"]
SCAN_EXTS = {".py", ".md", ".json", ".sh", ".toml", ".yml", ".yaml", ".txt"}


def test_repo_has_no_leaked_secrets_or_real_identifiers():
    """Scan all tracked source, doc, and test files for leaked secrets and real identifiers."""
    failures = []
    
    for scan_target in SCAN_DIRS:
        target_path = REPO_ROOT / scan_target
        if not target_path.exists():
            continue
            
        for path in target_path.rglob("*"):
            if path.is_file() and path.suffix in SCAN_EXTS and path.name != "test_repo_security.py":
                try:
                    content = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                    
                for pattern, desc in FORBIDDEN_PATTERNS:
                    if pattern.search(content):
                        failures.append(f"{path.relative_to(REPO_ROOT)}: Found forbidden {desc}")

    # Check top-level files
    for root_file in (REPO_ROOT / "README.md", REPO_ROOT / "pyproject.toml"):
        if root_file.exists():
            content = root_file.read_text(encoding="utf-8")
            for pattern, desc in FORBIDDEN_PATTERNS:
                if pattern.search(content):
                    failures.append(f"{root_file.name}: Found forbidden {desc}")

    assert not failures, "Security audit failed:\n" + "\n".join(failures)
