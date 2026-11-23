#!/usr/bin/env python3
"""Refuse to ship credentials or personal data.

    python scripts/check_no_secrets.py

Checks three things, each of which has shipped from somebody's repository
before:

1. No API keys, tokens or session cookies anywhere in the package.
2. No filled personal configuration — `config/profile.yaml` must ship blank.
3. No business-identifying strings the author's own setup would leave behind.

The practice is borrowed from `scripts/check_no_secrets.py` in the
company-page bundle, where it guards a filled confidential template.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

SECRET_PATTERNS = {
    "OpenAI-style key": r"sk-[A-Za-z0-9]{20,}",
    "Stripe live key": r"sk_live_[A-Za-z0-9]{10,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "generic api key assignment": r"api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{16,}",
    "LinkedIn session cookie": r"li_at\s*=\s*[A-Za-z0-9]{10,}",
    "bearer token": r"Bearer\s+[A-Za-z0-9._-]{30,}",
    "private key block": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
}

# Strings that would mean the author's own configuration leaked into a public
# release. Extend this for your own fork.
PERSONAL_PATTERNS = {
    "author's company": r"cybercore",
    "author's city": r"nagpur",
    "author's email": r"dnyanesh@",
}

SKIP_DIRS = {".git", "data", "__pycache__", ".pytest_cache", ".ruff_cache",
             ".mypy_cache", "node_modules", ".venv", "venv"}
SKIP_SUFFIXES = {".db", ".pyc", ".png", ".jpg", ".gif", ".zip", ".gz"}

#: Files that state the forbidden patterns in order to search for them, and so
#: would match themselves. Any checker added here must be the same kind of
#: thing: a scanner, not content.
PATTERN_DEFINING_FILES = {
    "tests/test_instruction_integrity.py",
}


def files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.resolve() == SELF:
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS or p.suffix in SKIP_SUFFIXES:
            continue
        if rel.as_posix() in PATTERN_DEFINING_FILES:
            continue
        yield p


def main() -> int:
    problems: list[str] = []

    for p in files():
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT)
        for label, pattern in SECRET_PATTERNS.items():
            if re.search(pattern, text):
                problems.append(f"{rel}: looks like a {label}")
        for label, pattern in PERSONAL_PATTERNS.items():
            if re.search(pattern, text, re.I):
                problems.append(f"{rel}: contains {label}")

    profile_path = ROOT / "config/profile.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))["profile"]
    for key in ("display_name", "headline", "profile_url", "primary_objective",
                "industry", "geography", "notes"):
        if profile.get(key) is not None:
            problems.append(f"config/profile.yaml: ships a value for {key!r}")
    for key in ("secondary_objectives", "languages", "content_topics",
                "services_offered"):
        if profile.get(key):
            problems.append(f"config/profile.yaml: ships entries in {key!r}")

    env = ROOT / ".env"
    if env.is_file():
        problems.append(".env exists; it must never be committed (see .gitignore)")

    if problems:
        print("\n".join(problems), file=sys.stderr)
        print(f"\n{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("no credentials, no personal data, profile.yaml is blank")
    return 0


if __name__ == "__main__":
    sys.exit(main())
