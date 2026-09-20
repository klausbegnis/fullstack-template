#!/usr/bin/env python3
"""Tests for the hook scripts, in both harness shapes.

Run with `python3 .agents/hooks/test_hooks.py`. Every case pipes a sample event
into a real script and asserts on the exit code and the response, because the
exit code *is* the contract: Claude Code blocks on 2, Codex blocks on the JSON
response, and a hook that silently exits 0 is a guardrail that is not there.

Nothing here runs docker, a formatter, or a linter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
ROOT = HOOKS.parents[1]
GUARD = HOOKS / "guard_paths.py"
RULES = HOOKS / "rules_for_path.py"
POST_EDIT = HOOKS / "post_edit_check.sh"
STOP = HOOKS / "stop_check.sh"
CHANGED = HOOKS / "changed_checks.sh"
HOOK_IO = HOOKS / "hook_io.py"

sys.path.insert(0, str(HOOKS))

import hook_io
import rules_for_path


def claude_edit(path: str, **extra: str) -> dict:
    event = {
        "session_id": "test",
        "cwd": str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": "a", "new_string": "b"},
    }
    event["tool_input"].update(extra)
    return event


def claude_bash(command: str) -> dict:
    return {
        "session_id": "test",
        "cwd": str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def codex_patch(*paths: str, verb: str = "Update") -> dict:
    body = "\n".join(f"*** {verb} File: {path}\n@@\n-old\n+new" for path in paths)
    return {
        "session_id": "test",
        "cwd": str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {"command": f"*** Begin Patch\n{body}\n*** End Patch"},
    }


def run(script: Path, event: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.pop("CLAUDE_PROJECT_DIR", None)
    for key in [k for k in environment if k.startswith("CODEX_")]:
        environment.pop(key)
    environment.update(env or {})
    return subprocess.run(
        [str(script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=environment,
    )


class GuardPathsClaudeShape(unittest.TestCase):
    def assert_denied(self, result: subprocess.CompletedProcess, fragment: str) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(fragment, result.stderr)

    def test_generated_client_is_denied(self) -> None:
        result = run(GUARD, claude_edit("frontend/src/lib/api/generated/users.ts"))
        self.assert_denied(result, "orval output")

    def test_absolute_path_into_generated_client_is_denied(self) -> None:
        target = str(ROOT / "frontend/src/lib/api/generated/users.ts")
        self.assert_denied(run(GUARD, claude_edit(target)), "orval output")

    def test_ordinary_source_file_is_allowed(self) -> None:
        result = run(GUARD, claude_edit("backend/app/routers/users.py"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_new_migration_is_allowed(self) -> None:
        result = run(GUARD, claude_edit("backend/alembic/versions/9999_brand_new.py"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_commit_no_verify_is_denied(self) -> None:
        self.assert_denied(run(GUARD, claude_bash('git commit --no-verify -m "x"')), "--no-verify")
        self.assert_denied(run(GUARD, claude_bash('git commit -n -m "x"')), "--no-verify")

    def test_ordinary_commit_is_allowed(self) -> None:
        result = run(GUARD, claude_bash('git commit -m "feat: x"'))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_force_push_to_main_is_denied(self) -> None:
        self.assert_denied(run(GUARD, claude_bash("git push --force origin main")), "Force-push")
        self.assert_denied(run(GUARD, claude_bash("git push -f origin main")), "Force-push")

    def test_force_push_to_a_branch_is_allowed(self) -> None:
        result = run(GUARD, claude_bash("git push --force-with-lease origin task/x"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_raw_alembic_revision_is_denied(self) -> None:
        self.assert_denied(
            run(GUARD, claude_bash('uv run alembic revision --autogenerate -m "x"')),
            "create_migration",
        )

    def test_create_migration_command_is_allowed(self) -> None:
        result = run(
            GUARD,
            claude_bash('uv run python -m app.commands.create_migration -m "add x"'),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_alembic_upgrade_is_allowed(self) -> None:
        result = run(GUARD, claude_bash("uv run alembic upgrade head"))
        self.assertEqual(result.returncode, 0, result.stderr)


class GuardPathsCodexShape(unittest.TestCase):
    def decision(self, result: subprocess.CompletedProcess) -> dict:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        return payload["hookSpecificOutput"]

    def test_patch_into_generated_client_is_denied_as_json(self) -> None:
        result = run(GUARD, codex_patch("frontend/src/lib/api/generated/users.ts"))
        output = self.decision(result)
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("orval output", output["permissionDecisionReason"])

    def test_added_file_header_is_parsed(self) -> None:
        result = run(
            GUARD, codex_patch("frontend/src/lib/api/generated/new.ts", verb="Add")
        )
        self.assertEqual(self.decision(result)["permissionDecision"], "deny")

    def test_deleted_file_header_is_parsed(self) -> None:
        result = run(
            GUARD, codex_patch("frontend/src/lib/api/generated/old.ts", verb="Delete")
        )
        self.assertEqual(self.decision(result)["permissionDecision"], "deny")

    def test_ordinary_patch_is_allowed(self) -> None:
        result = run(GUARD, codex_patch("backend/app/services/users.py"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_bash_denial_uses_codex_json_when_codex_env_is_set(self) -> None:
        result = run(
            GUARD,
            claude_bash('git commit --no-verify -m "x"'),
            env={"CODEX_HOME": "/tmp/codex"},
        )
        self.assertEqual(self.decision(result)["permissionDecision"], "deny")


class MergedMigrationGuard(unittest.TestCase):
    def test_a_migration_on_origin_main_is_denied(self) -> None:
        listing = subprocess.run(
            ["git", "ls-tree", "--name-only", "origin/main", "backend/alembic/versions/"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        merged = [
            line
            for line in listing.stdout.splitlines()
            if line.endswith(".py") and not line.endswith("__init__.py")
        ]
        if not merged:
            self.skipTest("no merged migration reachable from origin/main")
        result = run(GUARD, claude_edit(merged[0]))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("immutable", result.stderr)


class HookIoShapes(unittest.TestCase):
    def test_harness_detection(self) -> None:
        self.assertEqual(hook_io.harness_of(claude_edit("a.py")), "claude")
        self.assertEqual(hook_io.harness_of(codex_patch("a.py")), "codex")

    def test_paths_from_both_shapes(self) -> None:
        self.assertEqual(
            hook_io.paths_of(claude_edit("backend/app/main.py")), ["backend/app/main.py"]
        )
        self.assertEqual(
            hook_io.paths_of(codex_patch("backend/app/main.py", "frontend/src/a.ts")),
            ["backend/app/main.py", "frontend/src/a.ts"],
        )

    def test_unparseable_stdin_is_not_fatal(self) -> None:
        result = subprocess.run(
            [str(HOOK_IO), "paths"], input="not json", capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_post_block_response_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reason = Path(directory, "reason")
            context = Path(directory, "context")
            reason.write_text("E501 line too long\n", encoding="utf-8")
            context.write_text("--- .agents/rules/backend/layering.md ---\n", encoding="utf-8")
            result = subprocess.run(
                [
                    str(HOOK_IO),
                    "post-block",
                    "--reason-file",
                    str(reason),
                    "--context-file",
                    str(context),
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("E501", payload["reason"])
        self.assertEqual(
            payload["hookSpecificOutput"]["hookEventName"], "PostToolUse"
        )
        self.assertIn("layering.md", payload["hookSpecificOutput"]["additionalContext"])


class RulesForPath(unittest.TestCase):
    def test_frontmatter_list_forms(self) -> None:
        block = rules_for_path.parse_frontmatter(
            '---\npaths:\n  - "backend/app/**"\n  - backend/tests/**\n---\nbody\n'
        )
        self.assertEqual(block["paths"], ["backend/app/**", "backend/tests/**"])

        inline = rules_for_path.parse_frontmatter(
            "---\npaths: [frontend/src/**, frontend/vitest.*]\n---\nbody\n"
        )
        self.assertEqual(inline["paths"], ["frontend/src/**", "frontend/vitest.*"])

    def test_brace_expansion(self) -> None:
        self.assertEqual(
            rules_for_path.expand_braces("frontend/src/features/*/{api,model}/**"),
            [
                "frontend/src/features/*/api/**",
                "frontend/src/features/*/model/**",
            ],
        )

    def test_glob_semantics(self) -> None:
        self.assertTrue(rules_for_path.matches("backend/app/routers/users.py", ["backend/app/**"]))
        self.assertFalse(rules_for_path.matches("backend/tests/unit/a.py", ["backend/app/**"]))
        self.assertTrue(rules_for_path.matches("frontend/src/a.ts", ["frontend/src/*.ts"]))
        self.assertFalse(
            rules_for_path.matches("frontend/src/deep/a.ts", ["frontend/src/*.ts"])
        )
        self.assertTrue(
            rules_for_path.matches("frontend/src/deep/a.ts", ["frontend/src/**/*.ts"])
        )
        self.assertTrue(rules_for_path.matches("frontend/src/a.ts", ["frontend/src/**/*.ts"]))

    def test_matching_bodies_are_printed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rules = root / ".agents" / "rules" / "backend"
            rules.mkdir(parents=True)
            (rules / "layering.md").write_text(
                '---\npaths:\n  - "backend/app/**"\n---\n\n### Routers are HTTP only\n',
                encoding="utf-8",
            )
            (rules / "testing.md").write_text(
                '---\npaths:\n  - "backend/tests/**"\n---\n\n### Two tiers only\n',
                encoding="utf-8",
            )
            bodies = subprocess.run(
                [str(RULES), "--root", str(root), "backend/app/routers/users.py"],
                capture_output=True,
                text=True,
            )
            names = subprocess.run(
                [str(RULES), "--root", str(root), "--list", "backend/app/routers/users.py"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(bodies.returncode, 0, bodies.stderr)
        self.assertIn("Routers are HTTP only", bodies.stdout)
        self.assertNotIn("Two tiers only", bodies.stdout)
        self.assertEqual(names.stdout.strip(), ".agents/rules/backend/layering.md")

    def test_unknown_path_exits_zero_with_no_output(self) -> None:
        result = subprocess.run(
            [str(RULES), "README.md"], capture_output=True, text=True, cwd=str(ROOT)
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class PostEditCheck(unittest.TestCase):
    def test_no_relevant_path_exits_zero(self) -> None:
        result = run(POST_EDIT, claude_edit("docs/architecture/backend.md"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_stdin_exits_zero(self) -> None:
        result = subprocess.run(
            [str(POST_EDIT)], input="", capture_output=True, text=True, cwd=str(ROOT)
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class StopCheck(unittest.TestCase):
    def test_reentry_is_suppressed(self) -> None:
        event = {"hook_event_name": "Stop", "stop_hook_active": True}
        result = run(STOP, event)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ScriptsAreExecutable(unittest.TestCase):
    def test_every_hook_script_is_executable(self) -> None:
        for script in (GUARD, RULES, POST_EDIT, STOP, CHANGED, HOOK_IO):
            self.assertTrue(script.is_file(), script)
            self.assertTrue(os.access(script, os.X_OK), f"{script} is not executable")

    def test_shell_scripts_parse(self) -> None:
        for script in (POST_EDIT, STOP, CHANGED):
            result = subprocess.run(["sh", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
