#!/usr/bin/env python3
"""Validate every SKILL.md's frontmatter and required sections.

    python scripts/check_frontmatter.py

Exits non-zero on the first problem found, so it works as a pre-commit hook.
The same checks run inside `tests/test_instruction_integrity.py`; this script
exists so a contributor can check one file without running the suite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
REQUIRED_HEADINGS = ("When to use", "Required inputs", "Workflow",
                     "Output format", "Failure handling", "Safety requirements",
                     "Examples")


def check(path: Path, *, is_root: bool) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    if not m:
        return [f"{path}: no YAML frontmatter"]
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        return [f"{path}: frontmatter does not parse ({str(exc).splitlines()[0]})"]
    if not isinstance(data, dict):
        return [f"{path}: frontmatter is not a mapping"]

    for key in ("name", "description"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            problems.append(f"{path}: '{key}' is missing or empty")

    name = data.get("name", "")
    if not is_root and name != path.parent.name:
        problems.append(f"{path}: name {name!r} does not match folder {path.parent.name!r}")
    if not re.fullmatch(r"[a-z0-9-]+", name or ""):
        problems.append(f"{path}: name {name!r} should be lowercase and hyphenated")

    desc = data.get("description", "")
    if len(desc) > 1024:
        problems.append(f"{path}: description is {len(desc)} chars, over 1024")
    if len(desc) < 120:
        problems.append(f"{path}: description is {len(desc)} chars; too short to trigger well")
    if "Use when" not in desc and "Use this" not in desc:
        problems.append(f"{path}: description does not say when to use the skill")

    if not is_root:
        if data.get("license") != "MIT":
            problems.append(f"{path}: license should be MIT")
        if data.get("metadata", {}).get("bundle") != "linkedin-network-intelligence":
            problems.append(f"{path}: metadata.bundle is missing or wrong")
        for heading in REQUIRED_HEADINGS:
            if not re.search(rf"^#+ .*{re.escape(heading)}", text, re.M | re.I):
                problems.append(f"{path}: no '{heading}' section")
    return problems


def main() -> int:
    docs = [(p, False) for p in sorted((ROOT / "skills").glob("*/SKILL.md"))]
    docs.append((ROOT / "SKILL.md", True))
    problems: list[str] = []
    for path, is_root in docs:
        problems.extend(check(path, is_root=is_root))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print(f"\n{len(problems)} problem(s) in {len(docs)} document(s)", file=sys.stderr)
        return 1
    print(f"{len(docs)} documents valid ({len(docs) - 1} skills + root)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
