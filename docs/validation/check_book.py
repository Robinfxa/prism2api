#!/usr/bin/env python3
"""Offline structural checks for this architecture book (standard library only).

This checks documentation, not Prism behavior, external URL availability,
production tests, licensing, or the completeness of secret detection.
Run from anywhere with: python /path/to/docs/validation/check_book.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
MODULES = [
    "01-api-and-client-contract.md",
    "02-prism-adapter-and-capabilities.md",
    "03-run-lifecycle-and-idempotency.md",
    "04-context-and-resource-ownership.md",
    "05-streaming-and-result-normalization.md",
    "06-journal-evidence-and-storage.md",
    "07-auth-security-and-deployment.md",
    "08-evaluation-and-workflow.md",
]
APPENDICES = [
    "a1-borrow-matrix.md", "a2-evidence-and-open-questions.md",
    "a3-delivery-and-acceptance.md", "a4-contract-index.md",
    "a5-decisions-and-source-differences.md",
]
REQUIRED = [
    "README.md", "DELIVERY.md", "Agent-init/PROJECT_OVERLAY.md", "docs/CONTEXT.md",
    "docs/architecture/00-master-design-book.md",
    "docs/research/prior-art-prb/README.md",
    "docs/research/prior-art-prb/sources.md",
    "docs/research/prior-art-prb/comparison-matrix.md",
    "docs/plans/active/architecture-and-protocol-readiness-prb.md",
    "docs/validation/architecture-book-prb-report.md",
] + [f"docs/architecture/modules/{p}" for p in MODULES] + [
    f"docs/architecture/appendices/{p}" for p in APPENDICES
]


def strip_fences(text: str, path: Path, errors: list[str]) -> tuple[str, int]:
    lines, fence, count = [], None, 0
    for number, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if match:
                fence = (match.group(1)[0], len(match.group(1)))
                count += 1
            else:
                lines.append(line)
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1] and not match.group(2).strip():
            fence = None
    if fence is not None:
        errors.append(f"Unclosed code fence: {path.relative_to(ROOT)}")
    return "\n".join(lines), count


def heading_slug(label: str) -> str:
    label = re.sub(r"<[^>]+>", "", label)
    label = re.sub(r"[`*_]", "", label).strip().lower()
    return re.sub(r"[^\w\- ]", "", label, flags=re.UNICODE).replace(" ", "-")


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"Missing required document: {relative}")
    texts: dict[Path, str] = {}
    clean: dict[Path, str] = {}
    anchors: dict[Path, set[str]] = {}
    fence_count = 0
    for path in sorted(ROOT.rglob("*.md")):
        if any(part in {".git", "__pycache__", ".agents", ".codex"} for part in path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as exc:
            errors.append(f"Unreadable UTF-8 file: {path.relative_to(ROOT)}: {exc}")
            continue
        texts[path] = text
        if not text.strip() or not re.search(r"^#\s+\S", text, re.MULTILINE):
            errors.append(f"Empty document or missing H1: {path.relative_to(ROOT)}")
        clean[path], count = strip_fences(text, path, errors)
        fence_count += count
        ids = set(re.findall(r'<a\s+id=[\"\']([^\"\']+)[\"\']', clean[path]))
        seen: Counter[str] = Counter()
        for label in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", clean[path], re.MULTILINE):
            slug = heading_slug(label)
            n = seen[slug]
            seen[slug] += 1
            ids.add(f"{slug}-{n}" if n else slug)
        anchors[path] = ids

    local_links = 0
    for path, text in clean.items():
        for target in re.findall(r"\[[^\]\n]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
            target = target.strip("<>")
            parts = urlsplit(target)
            if parts.scheme or parts.netloc:
                continue
            local_links += 1
            linked = (path.parent / unquote(parts.path)).resolve() if parts.path else path.resolve()
            if not linked.is_relative_to(ROOT):
                errors.append(f"Link leaves package: {path.relative_to(ROOT)} -> {target}")
                continue
            if not linked.exists():
                errors.append(f"Broken local link: {path.relative_to(ROOT)} -> {target}")
                continue
            if parts.fragment and linked.suffix == ".md" and unquote(parts.fragment) not in anchors.get(linked, set()):
                errors.append(f"Missing anchor: {path.relative_to(ROOT)} -> {target}")

    expected_ids = {"I": 12, "U": 15, "T": 52, "D": 14}
    canonical = {
        "I": ROOT / "docs/architecture/00-master-design-book.md",
        "U": ROOT / "docs/architecture/appendices/a2-evidence-and-open-questions.md",
        "T": ROOT / "docs/architecture/appendices/a3-delivery-and-acceptance.md",
        "D": ROOT / "docs/architecture/appendices/a5-decisions-and-source-differences.md",
    }
    for prefix, maximum in expected_ids.items():
        content = texts.get(canonical[prefix], "")
        found = Counter(re.findall(rf"^\|\s*(?:\*\*|`)?({prefix}\d{{2}})(?:\*\*|`)?\s*\|", content, re.MULTILINE))
        wanted = {f"{prefix}{n:02d}" for n in range(1, maximum + 1)}
        if set(found) != wanted or any(count != 1 for count in found.values()):
            errors.append(f"Canonical {prefix} table mismatch: expected {maximum} unique rows; got {dict(found)}")
        for path, content in texts.items():
            for identifier in re.findall(rf"\b{prefix}\d{{2}}\b", content):
                if identifier not in wanted:
                    errors.append(f"Undefined ID: {path.relative_to(ROOT)}: {identifier}")

    source_ids = {"w1", "w2", "v1", "v2", "v3", "r1", "r2", "r3", "r4", "r5", "o1", "o2", "o3"}
    source_file = ROOT / "docs/research/prior-art-prb/sources.md"
    if not source_ids.issubset(anchors.get(source_file, set())):
        errors.append("Source registry is missing one or more required explicit anchors")

    # Deliberately narrow checks: identifiers named in prose are not secrets.
    patterns = {
        "github_token": r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
        "api_key": r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}",
        "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "credential_url": r"[?&](?:access_token|token|api_key)=[A-Za-z0-9._~-]{24,}",
    }
    for path, text in texts.items():
        for name, pattern in patterns.items():
            if re.search(pattern, text):
                errors.append(f"Potential secret ({name}): {path.relative_to(ROOT)}")
    forbidden_parts = {"__MACOSX", "browser-profile", "credentials"}
    for path in ROOT.rglob("*"):
        if any(part in {".git", ".agents", ".codex", ".multi-subflow"} for part in path.relative_to(ROOT).parts):
            continue
        if any(part in forbidden_parts for part in path.relative_to(ROOT).parts):
            errors.append(f"Unexpected private/runtime path: {path.relative_to(ROOT)}")
        if path.is_file() and (path.name == ".env" or path.suffix in {".har", ".sqlite", ".sqlite3", ".db", ".pem"}):
            errors.append(f"Unexpected secret/runtime file: {path.relative_to(ROOT)}")
    if (ROOT / "src").exists() or (ROOT / "openspec/specs").exists():
        errors.append("Architecture-only package unexpectedly contains runtime code or live specs")

    summary = {
        "scope": "architecture-document-structure-only",
        "status": "pass" if not errors else "fail",
        "markdown_files": len(texts),
        "module_documents": len(MODULES),
        "appendix_documents": len(APPENDICES),
        "local_links_checked": local_links,
        "balanced_fenced_blocks": fence_count,
        "canonical_ids_checked": expected_ids,
        "source_anchors_checked": len(source_ids),
        "network_requests": 0,
        "runtime_tests_executed": False,
        "independent_architecture_audit": False,
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
