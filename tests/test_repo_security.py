"""Deterministic repository security test scanning for leaked tokens, cookies, and real identifiers."""

import re
import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Generic secret patterns that MUST NOT appear in any tracked repository file or git blob
FORBIDDEN_REGEXES = [
    (re.compile(r"eyJ" + r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "Raw JWT literal"),
    (re.compile(r"prism_" + r"(?:session|oai_access)_token=\s*" + r"eyJ"), "Real session/access token cookie literal"),
    (re.compile(r"gAAAAA" + r"[A-Za-z0-9_-]{30,}"), "Real sandbox token literal"),
]

# SHA256 hashes of historical non-secret real identifiers (NO plaintext stored in code)
DENIED_SHA256_HASHES = {
    "f28547757ad93f3f65e69151b40be8594eba369b853e1e7e493d33187db5ba69",  # Historical project ID
    "0a4a9ec3775c1118dc635f996b55c9ce0558059f1405f469f5d1693848d62af6",  # Historical user ID
    "b433b7708cfae706a56d1fea14bb7d24dbeffc49203f8f5f307ae8cf7c5e3c20",  # Historical conversation ID
}

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,}")

# Directories and extensions to scan in current workspace
SCAN_DIRS = ["src", "docs", "tests", "Agent-init", "openspec"]
SCAN_EXTS = {".py", ".md", ".json", ".sh", ".toml", ".yml", ".yaml", ".txt"}


def test_repo_has_no_leaked_secrets_or_real_identifiers():
    """Scan all tracked source, doc, and test files in current workspace for secrets and real identifiers."""
    failures = []
    
    files_to_scan = []
    for scan_target in SCAN_DIRS:
        target_path = REPO_ROOT / scan_target
        if not target_path.exists():
            continue
        for path in target_path.rglob("*"):
            if path.is_file() and path.suffix in SCAN_EXTS:
                files_to_scan.append(path)

    for root_filename in ("README.md", "pyproject.toml"):
        root_path = REPO_ROOT / root_filename
        if root_path.exists():
            files_to_scan.append(root_path)

    for path in files_to_scan:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
            
        # 1. Generic regex secret scan
        for pattern, desc in FORBIDDEN_REGEXES:
            if pattern.search(content):
                failures.append(f"{path.relative_to(REPO_ROOT)}: Found forbidden {desc}")

        # 2. SHA256 hash matching against denylist
        for token in TOKEN_PATTERN.findall(content):
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if token_hash in DENIED_SHA256_HASHES:
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}: Found blacklisted historical identifier (SHA256: {token_hash[:8]}...)"
                )

    assert not failures, "Workspace security audit failed:\n" + "\n".join(failures)


def test_all_reachable_git_blobs_are_clean():
    """Traverse all reachable git commits and blobs scanning for secret patterns and identifier denylists."""
    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists():
        return  # Skip if not inside a git repository

    try:
        rev_out = subprocess.check_output(
            ["git", "rev-list", "--objects", "--all"],
            cwd=REPO_ROOT,
            text=True
        )
    except Exception as exc:
        pytest.fail(f"Failed to run git rev-list: {exc}")

    items = []
    for line in rev_out.strip().split("\n"):
        if not line:
            continue
        parts = line.split(maxsplit=1)
        sha = parts[0]
        path = parts[1] if len(parts) > 1 else ""
        items.append((sha, path))

    cat_proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )

    failures = []
    try:
        for sha, path in items:
            cat_proc.stdin.write(f"{sha}\n".encode("utf-8"))
            cat_proc.stdin.flush()
            header = cat_proc.stdout.readline().decode("utf-8").strip()
            if not header:
                continue
            h_parts = header.split()
            if len(h_parts) < 3:
                continue
            obj_sha, obj_type, size_str = h_parts[0], h_parts[1], h_parts[2]
            size = int(size_str)
            content_bytes = cat_proc.stdout.read(size)
            cat_proc.stdout.read(1)  # trailing newline

            if obj_type != "blob":
                continue

            try:
                content = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, desc in FORBIDDEN_REGEXES:
                if pattern.search(content):
                    failures.append(f"blob {obj_sha[:8]} (path: {path}): Found forbidden {desc}")

            for token in TOKEN_PATTERN.findall(content):
                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                if token_hash in DENIED_SHA256_HASHES:
                    failures.append(
                        f"blob {obj_sha[:8]} (path: {path}): Found blacklisted historical identifier (SHA256: {token_hash[:8]}...)"
                    )
    finally:
        cat_proc.terminate()

    assert not failures, "Reachable git history security audit failed:\n" + "\n".join(failures)


