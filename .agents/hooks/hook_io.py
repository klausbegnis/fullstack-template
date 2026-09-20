#!/usr/bin/env python3
"""Shared hook plumbing for both agent harnesses.

Claude Code and Codex hand a hook the same broad JSON shape on stdin, but they
name the editing tool differently (`Edit`/`Write` versus `apply_patch`) and they
accept different block responses. Every hook script in this directory reads its
event through this module so that difference is stated once.

Subcommands, all reading the event JSON on stdin:

    paths       print one repository-relative path per line
    harness     print `claude` or `codex`
    field <k>   print the raw value of a top-level field, or nothing
    post-block  build the Codex PostToolUse block response from two files
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
PATCH_TOOLS = {"apply_patch", "ApplyPatch"}
PATCH_HEADER = re.compile(
    r"^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$", re.MULTILINE
)


def read_event(stream=None) -> dict:
    """Return the hook event, or an empty mapping when stdin is not JSON."""
    raw = (stream or sys.stdin).read()
    try:
        event = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return event if isinstance(event, dict) else {}


def harness_of(event: dict) -> str:
    """Return which harness sent this event."""
    if event.get("tool_name") in PATCH_TOOLS:
        return "codex"
    if any(key.startswith("CODEX_") for key in os.environ):
        return "codex"
    return "claude"


def _patch_text(tool_input: dict) -> str:
    parts = []
    for key in ("command", "patch", "input", "content", "text"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def _normalize(path: str, cwd: str | None) -> str:
    path = path.strip().strip('"').strip("'")
    if not path:
        return ""
    root = repo_root(cwd)
    absolute = path if os.path.isabs(path) else os.path.join(cwd or root, path)
    absolute = os.path.normpath(absolute)
    try:
        return os.path.relpath(absolute, root)
    except ValueError:
        return absolute


def repo_root(cwd: str | None = None) -> str:
    """Return the repository root, falling back to this file's grandparent."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def paths_of(event: dict) -> list[str]:
    """Return the repository-relative paths this tool call writes to."""
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return []
    cwd = event.get("cwd")
    found: list[str] = []

    name = event.get("tool_name")
    if name in PATCH_TOOLS or PATCH_HEADER.search(_patch_text(tool_input)):
        found.extend(PATCH_HEADER.findall(_patch_text(tool_input)))
    if name in EDIT_TOOLS or "file_path" in tool_input:
        for key in ("file_path", "notebook_path", "path"):
            value = tool_input.get(key)
            if isinstance(value, str):
                found.append(value)

    seen: dict[str, None] = {}
    for candidate in found:
        normalized = _normalize(candidate, cwd)
        if normalized:
            seen.setdefault(normalized, None)
    return list(seen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("paths")
    sub.add_parser("harness")
    field = sub.add_parser("field")
    field.add_argument("key")
    block = sub.add_parser("post-block")
    block.add_argument("--reason-file", required=True)
    block.add_argument("--context-file")
    args = parser.parse_args(argv)

    if args.command == "post-block":
        with open(args.reason_file, encoding="utf-8") as handle:
            reason = handle.read().strip()
        context = ""
        if args.context_file and os.path.exists(args.context_file):
            with open(args.context_file, encoding="utf-8") as handle:
                context = handle.read().strip()
        payload = {
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            },
        }
        print(json.dumps(payload))
        return 0

    event = read_event()
    if args.command == "paths":
        for path in paths_of(event):
            print(path)
    elif args.command == "harness":
        print(harness_of(event))
    elif args.command == "field":
        value = event.get(args.key)
        if isinstance(value, bool):
            print("true" if value else "")
        elif value is not None:
            print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
