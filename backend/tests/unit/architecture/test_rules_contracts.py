"""Enforce the contracts that make the path-scoped rule files loadable and honest.

`.agents/rules/**` is the single source of the repo's coding standards: Claude Code
loads a file lazily when a path matching its `paths:` frontmatter is read, and the
Codex hook resolves the same globs to inject the same bodies. That only works while
the frontmatter parses, the globs match real files, and no rule is stated twice --
rule-file load order is undocumented, so a duplicated heading is a contradiction with
no tiebreaker. The nested guides and the root index are asserted here too, because a
rule nobody is pointed at is a rule that does not load.
"""

from pathlib import Path
import re

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
RULES_DIR = REPO_ROOT / ".agents" / "rules"
CLAUDE_RULES_LINK = REPO_ROOT / ".claude" / "rules"
ROOT_GUIDE = REPO_ROOT / "AGENTS.md"
BACKEND_GUIDE = REPO_ROOT / "backend" / "AGENTS.md"
FRONTEND_GUIDE = REPO_ROOT / "frontend" / "AGENTS.md"

EXPECTED_RULE_FILES = {
    "backend/layering.md",
    "backend/logging.md",
    "backend/persistence.md",
    "backend/api-crud.md",
    "backend/testing.md",
    "frontend/architecture.md",
    "frontend/server-client.md",
    "frontend/data-and-forms.md",
    "frontend/ui-components.md",
    "frontend/testing.md",
    "e2e.md",
    "harness.md",
}
IGNORED_DIRECTORIES = {"node_modules", ".venv", ".next", ".git", "__pycache__"}
BRACE_PATTERN = re.compile(r"\{([^{}]*)\}")
ROOT_GUIDE_MAX_BYTES = 12288
ROOT_GUIDE_MAX_LINES = 200


def _rule_files() -> list[Path]:
    return sorted(RULES_DIR.rglob("*.md"))


def _rule_ids() -> list[str]:
    return [path.relative_to(RULES_DIR).as_posix() for path in _rule_files()]


def _split_frontmatter(path: Path) -> tuple[dict, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path.name} does not open with frontmatter"
    closing = next(
        (index for index, line in enumerate(lines[1:], start=1) if line == "---"), None
    )
    assert closing is not None, f"{path.name} has an unterminated frontmatter block"
    document = yaml.safe_load("\n".join(lines[1:closing])) or {}
    return document, lines[closing + 1 :]


def _expand_braces(pattern: str) -> list[str]:
    match = BRACE_PATTERN.search(pattern)
    if match is None:
        return [pattern]
    expanded = []
    for option in match.group(1).split(","):
        candidate = pattern[: match.start()] + option.strip() + pattern[match.end() :]
        expanded.extend(_expand_braces(candidate))
    return expanded


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def _matches(pattern: str) -> list[Path]:
    found: list[Path] = []
    for expanded in _expand_braces(pattern):
        found.extend(
            match for match in REPO_ROOT.glob(expanded) if not _is_ignored(match)
        )
    return found


def _rule_blocks(body: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    heading: str | None = None
    collected: list[str] = []
    for line in body:
        if line.startswith("### "):
            if heading is not None:
                blocks.append((heading, collected))
            heading = line[4:].strip()
            collected = []
        elif heading is not None:
            collected.append(line)
    if heading is not None:
        blocks.append((heading, collected))
    return blocks


def _declared_globs(path: Path) -> list[str]:
    document, _ = _split_frontmatter(path)
    return list(document["paths"])


@pytest.mark.parametrize("rule_path", _rule_files(), ids=_rule_ids())
def test_rule_frontmatter_declares_string_paths(rule_path: Path) -> None:
    document, body = _split_frontmatter(rule_path)

    assert set(document) == {"paths"}, (
        f"{rule_path.name} frontmatter must declare `paths` and nothing else, "
        f"got {sorted(document)}"
    )
    globs = document["paths"]
    assert isinstance(globs, list) and globs, f"{rule_path.name} has no `paths` entries"
    for glob in globs:
        assert isinstance(glob, str) and glob.strip(), (
            f"{rule_path.name} declares a non-string path entry {glob!r}"
        )
    assert any(line.strip() for line in body), f"{rule_path.name} has no body"


@pytest.mark.parametrize("rule_path", _rule_files(), ids=_rule_ids())
def test_rule_globs_match_existing_paths(rule_path: Path) -> None:
    for glob in _declared_globs(rule_path):
        assert _matches(glob), (
            f"{rule_path.name} declares `{glob}`, which matches nothing in the repo; "
            "a rule scoped to a path that does not exist never loads"
        )


def test_rule_files_are_exactly_the_declared_set() -> None:
    assert set(_rule_ids()) == EXPECTED_RULE_FILES


def test_rule_headings_are_unique_across_every_file() -> None:
    seen: dict[str, str] = {}
    for rule_path in _rule_files():
        _, body = _split_frontmatter(rule_path)
        for heading, _lines in _rule_blocks(body):
            origin = seen.get(heading)
            assert origin is None, (
                f"`{heading}` is stated in both {origin} and "
                f"{rule_path.relative_to(RULES_DIR).as_posix()}"
            )
            seen[heading] = rule_path.relative_to(RULES_DIR).as_posix()
    assert seen, "no rules were found"


@pytest.mark.parametrize("rule_path", _rule_files(), ids=_rule_ids())
def test_every_incorrect_example_is_paired_with_a_correct_one(rule_path: Path) -> None:
    _, body = _split_frontmatter(rule_path)

    for heading, lines in _rule_blocks(body):
        incorrect = [i for i, line in enumerate(lines) if line == "**Incorrect:**"]
        correct = [i for i, line in enumerate(lines) if line == "**Correct:**"]
        for position in incorrect:
            assert any(other > position for other in correct), (
                f"`{heading}` in {rule_path.name} shows an incorrect example with no "
                "correct one after it"
            )


@pytest.mark.parametrize("rule_path", _rule_files(), ids=_rule_ids())
def test_every_rule_names_its_enforcement_mechanism(rule_path: Path) -> None:
    _, body = _split_frontmatter(rule_path)
    blocks = _rule_blocks(body)

    assert blocks, f"{rule_path.name} declares no rules"
    for heading, lines in blocks:
        content = [line for line in lines if line.strip()]
        assert content and content[-1].startswith("Enforced by:"), (
            f"`{heading}` in {rule_path.name} does not end with an `Enforced by:` line"
        )


def test_claude_rules_is_a_symlink_to_the_maintained_tree() -> None:
    assert CLAUDE_RULES_LINK.is_symlink(), ".claude/rules must be a symlink"
    assert CLAUDE_RULES_LINK.resolve() == RULES_DIR.resolve(), (
        ".claude/rules must resolve to .agents/rules so both harnesses read one copy"
    )


def test_root_guide_indexes_every_rule_file() -> None:
    index = ROOT_GUIDE.read_text(encoding="utf-8")

    for relative in sorted(EXPECTED_RULE_FILES):
        assert f".agents/rules/{relative}" in index, (
            f"root AGENTS.md does not point at .agents/rules/{relative}"
        )


@pytest.mark.parametrize(
    ("guide_path", "prefix"),
    [(BACKEND_GUIDE, "backend/"), (FRONTEND_GUIDE, "frontend/")],
    ids=["backend", "frontend"],
)
def test_nested_guide_points_at_its_sides_rules(guide_path: Path, prefix: str) -> None:
    guide = guide_path.read_text(encoding="utf-8")

    assert "## Code Review Rules" in guide, (
        f"{guide_path.parent.name}/AGENTS.md has no `## Code Review Rules` section, "
        "which is the only part Codex PR review reads per changed file"
    )
    for relative in sorted(EXPECTED_RULE_FILES):
        if relative.startswith(prefix):
            assert f".agents/rules/{relative}" in guide, (
                f"{guide_path.parent.name}/AGENTS.md does not point at "
                f".agents/rules/{relative}"
            )


def test_frontend_guide_leaves_the_nextjs_block_to_next_dev() -> None:
    guide = FRONTEND_GUIDE.read_text(encoding="utf-8")

    assert "BEGIN:nextjs-agent-rules" not in guide
    assert "END:nextjs-agent-rules" not in guide


def test_root_guide_stays_within_the_always_on_budget() -> None:
    raw = ROOT_GUIDE.read_bytes()

    assert len(raw) <= ROOT_GUIDE_MAX_BYTES, (
        f"root AGENTS.md is {len(raw)} bytes, over the {ROOT_GUIDE_MAX_BYTES} budget; "
        "move scoped guidance into .agents/rules"
    )
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) <= ROOT_GUIDE_MAX_LINES, (
        f"root AGENTS.md is {len(lines)} lines, over the {ROOT_GUIDE_MAX_LINES} budget"
    )
