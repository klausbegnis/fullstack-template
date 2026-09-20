#!/usr/bin/env python3
"""Print the path-scoped rules that apply to a set of repository paths.

Claude Code loads `.claude/rules/**` lazily by matching each rule's `paths`
frontmatter against the file being read. Codex has no such mechanism, so its
PostToolUse hook calls this script instead and injects the same bodies as
additional context. One glob implementation, so the two harnesses can never
disagree about which rule covers a file.

Usage:

    rules_for_path.py backend/app/routers/users.py
    rules_for_path.py --list frontend/src/features/users/model/user.ts

Always exits 0: a hook that fails closed on an unparseable rule file would stop
the agent from working for a documentation defect.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
BRACES = re.compile(r"\{([^{}]*)\}")


def parse_frontmatter(text: str) -> dict[str, list[str]]:
    """Return the `paths` list from a rule file's YAML frontmatter.

    Deliberately a tiny hand-rolled parser: hooks run on whatever Python the
    machine has and must not depend on PyYAML being installed.
    """
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    globs: list[str] = []
    collecting = False
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and collecting:
            globs.append(_unquote(stripped[2:]))
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key != "paths":
                collecting = False
                continue
            collecting = True
            if value.startswith("[") and value.endswith("]"):
                globs.extend(
                    _unquote(item) for item in value[1:-1].split(",") if item.strip()
                )
                collecting = False
            elif value:
                globs.append(_unquote(value))
                collecting = False
            continue
        collecting = False
    return {"paths": [glob for glob in globs if glob]}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def expand_braces(pattern: str) -> list[str]:
    """Expand `{a,b}` alternations, recursively, into plain globs."""
    match = BRACES.search(pattern)
    if not match:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end() :]
    results: list[str] = []
    for option in match.group(1).split(","):
        results.extend(expand_braces(head + option.strip() + tail))
    return results


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a repo-relative glob to a regex where `**` crosses separators."""
    out = ["\\A"]
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "*":
            if pattern.startswith("**/", index):
                out.append("(?:[^/]+/)*")
                index += 3
                continue
            if pattern.startswith("**", index):
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
            index += 1
            continue
        if char == "?":
            out.append("[^/]")
            index += 1
            continue
        out.append(re.escape(char))
        index += 1
    out.append("\\Z")
    return re.compile("".join(out))


def rule_files(rules_dir: Path) -> list[Path]:
    return sorted(rules_dir.rglob("*.md"))


def matches(path: str, globs: list[str]) -> bool:
    normalized = path.replace(os.sep, "/").lstrip("./")
    for raw in globs:
        for expanded in expand_braces(raw):
            if glob_to_regex(expanded).match(normalized):
                return True
    return False


def rules_for(paths: list[str], rules_dir: Path) -> list[Path]:
    """Return every rule file whose `paths` match at least one given path."""
    selected: list[Path] = []
    for rule in rule_files(rules_dir):
        try:
            text = rule.read_text(encoding="utf-8")
        except OSError:
            continue
        globs = parse_frontmatter(text).get("paths") or []
        if not globs:
            continue
        if any(matches(path, globs) for path in paths):
            selected.append(rule)
    return selected


def body_of(rule: Path) -> str:
    text = rule.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    return text[match.end() :] if match else text


def default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print rules matching a path.")
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--list", action="store_true", dest="names_only")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else default_root()
    rules_dir = root / ".agents" / "rules"
    if not args.paths or not rules_dir.is_dir():
        return 0

    relative: list[str] = []
    for path in args.paths:
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(root)
            except ValueError:
                continue
        relative.append(str(candidate))

    selected = rules_for(relative, rules_dir)
    for rule in selected:
        name = rule.relative_to(root).as_posix()
        if args.names_only:
            print(name)
        else:
            print(f"--- {name} ---")
            print(body_of(rule).rstrip())
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
