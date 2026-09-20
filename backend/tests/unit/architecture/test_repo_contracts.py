"""Enforce the contracts that bind the agent harness together.

The issue forms, the label set, the `/task` parser and the PRD layout form one
machine-readable contract. When a form field is renamed and the parser is not, the
factory keeps running and quietly produces work against a section it can no longer
read. These tests are the only thing standing between that rename and a silent
failure, so they live with the architecture tests rather than in a linter.
"""

from pathlib import Path
import re
import tomllib

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
ISSUE_TEMPLATE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
LABELS_FILE = REPO_ROOT / ".github" / "labels.yml"
TASK_SKILL = REPO_ROOT / ".claude" / "skills" / "task" / "SKILL.md"
GROOM_SKILL = REPO_ROOT / ".claude" / "skills" / "groom" / "SKILL.md"
PRD_DIR = REPO_ROOT / "docs" / "prds"
PRD_TEMPLATE = PRD_DIR / "TEMPLATE.md"

AREA_LABELS = {"backend", "frontend", "full-stack", "devops", "security"}
REQUIRED_SECTIONS = {
    "bug.yml": {
        "What is it",
        "Observed behaviour",
        "Expected behaviour",
        "Reproduction",
        "Acceptance criteria",
    },
    "support.yml": {"What is it"},
}
DEFAULT_REQUIRED_SECTIONS = {"What is it", "Specs", "Acceptance criteria"}
PRD_NAME_PATTERN = re.compile(r"^\d{4}-[a-z0-9]+(-[a-z0-9]+)*\.md$")
HEX_COLOUR = re.compile(r"^[0-9A-Fa-f]{6}$")


def _issue_forms() -> list[Path]:
    return sorted(p for p in ISSUE_TEMPLATE_DIR.glob("*.yml") if p.name != "config.yml")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _declared_labels() -> dict[str, dict]:
    document = _load(LABELS_FILE)
    return {entry["name"]: entry for entry in document["labels"]}


def _rendered_headings(form: dict) -> list[str]:
    return [
        field["attributes"]["label"]
        for field in form["body"]
        if field["type"] != "markdown"
    ]


def _form_ids() -> list[str]:
    return [path.name for path in _issue_forms()]


@pytest.mark.parametrize("form_path", _issue_forms(), ids=_form_ids())
def test_issue_form_is_well_formed(form_path: Path) -> None:
    form = _load(form_path)

    assert form["name"], f"{form_path.name} has no name"
    assert form["description"], f"{form_path.name} has no description"
    assert form["body"], f"{form_path.name} has no body"

    for field in form["body"]:
        assert field["type"] in {
            "markdown",
            "input",
            "textarea",
            "dropdown",
            "checkboxes",
        }, f"{form_path.name} uses unknown field type {field['type']}"
        if field["type"] != "markdown":
            assert field.get("id"), f"{form_path.name} has a field without an id"


@pytest.mark.parametrize("form_path", _issue_forms(), ids=_form_ids())
def test_issue_form_ids_are_kebab_case_of_labels(form_path: Path) -> None:
    form = _load(form_path)

    for field in form["body"]:
        if field["type"] == "markdown":
            continue
        label = field["attributes"]["label"]
        expected = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        assert field["id"] == expected, (
            f"{form_path.name}: field id {field['id']!r} does not match "
            f"label {label!r}; expected {expected!r}"
        )


@pytest.mark.parametrize("form_path", _issue_forms(), ids=_form_ids())
def test_issue_form_declares_required_sections(form_path: Path) -> None:
    form = _load(form_path)
    headings = set(_rendered_headings(form))
    required = REQUIRED_SECTIONS.get(form_path.name, DEFAULT_REQUIRED_SECTIONS)

    missing = required - headings
    assert not missing, f"{form_path.name} is missing sections {sorted(missing)}"

    for field in form["body"]:
        if field["type"] == "markdown":
            continue
        label = field["attributes"]["label"]
        if label in required:
            assert field.get("validations", {}).get("required") is True, (
                f"{form_path.name}: section {label!r} is required by the contract "
                f"but the form lets it be submitted empty"
            )


@pytest.mark.parametrize("form_path", _issue_forms(), ids=_form_ids())
def test_issue_form_area_dropdown_matches_label_set(form_path: Path) -> None:
    form = _load(form_path)
    area_fields = [field for field in form["body"] if field.get("id") == "area"]

    assert area_fields, f"{form_path.name} has no area dropdown"
    options = set(area_fields[0]["attributes"]["options"])
    assert options == AREA_LABELS, (
        f"{form_path.name} area options {sorted(options)} do not match the "
        f"declared area labels {sorted(AREA_LABELS)}"
    )


@pytest.mark.parametrize("form_path", _issue_forms(), ids=_form_ids())
def test_issue_form_preseeded_labels_exist(form_path: Path) -> None:
    form = _load(form_path)
    declared = _declared_labels()

    for label in form.get("labels", []):
        assert label in declared, (
            f"{form_path.name} preseeds label {label!r} which is absent "
            f"from .github/labels.yml"
        )


def test_label_file_is_internally_consistent() -> None:
    document = _load(LABELS_FILE)
    entries = document["labels"]
    names = [entry["name"] for entry in entries]

    assert len(names) == len(set(names)), "duplicate label names in labels.yml"

    for entry in entries:
        assert entry.get("description"), f"label {entry['name']!r} has no description"
        assert HEX_COLOUR.match(entry["color"]), (
            f"label {entry['name']!r} has colour {entry['color']!r}; "
            f"expected six hex digits with no leading '#'"
        )

    assert set(names) >= AREA_LABELS, (
        f"area labels missing from labels.yml: {sorted(AREA_LABELS - set(names))}"
    )


EXECUTABLE_FORMS = ("feature.yml", "chore.yml", "spike.yml", "bug.yml")


def test_task_skill_parses_every_section_the_forms_render() -> None:
    skill = TASK_SKILL.read_text(encoding="utf-8")
    rendered: set[str] = set()
    for form_path in _issue_forms():
        if form_path.name not in EXECUTABLE_FORMS:
            continue
        rendered.update(_rendered_headings(_load(form_path)))

    unhandled = sorted(heading for heading in rendered if f"`{heading}`" not in skill)
    assert not unhandled, (
        f"issue forms render sections the /task parser never mentions: {unhandled}. "
        f"Rename in one place and the factory reads a section that is no longer there."
    )


GROOMABLE_FORMS = ("feature.yml", "chore.yml", "spike.yml")


def test_groom_skill_writes_every_section_the_forms_render() -> None:
    skill = GROOM_SKILL.read_text(encoding="utf-8")
    rendered: set[str] = set()
    for form_path in _issue_forms():
        if form_path.name not in GROOMABLE_FORMS:
            continue
        rendered.update(_rendered_headings(_load(form_path)))

    unhandled = sorted(heading for heading in rendered if f"`{heading}`" not in skill)
    assert not unhandled, (
        f"/groom creates issues without sections the forms declare: {unhandled}"
    )


def _prd_files() -> list[Path]:
    return sorted(p for p in PRD_DIR.glob("*.md") if p.name[0].isdigit())


def test_prd_directory_has_a_template() -> None:
    assert PRD_TEMPLATE.is_file(), "docs/prds/TEMPLATE.md is missing"
    assert (PRD_DIR / "README.md").is_file(), "docs/prds/README.md is missing"


@pytest.mark.parametrize("prd_path", _prd_files(), ids=lambda path: path.name)
def test_prd_follows_the_template(prd_path: Path) -> None:
    assert PRD_NAME_PATTERN.match(prd_path.name), (
        f"{prd_path.name} does not match NNNN-kebab-slug.md"
    )

    template_sections = re.findall(
        r"^## (.+)$", PRD_TEMPLATE.read_text(encoding="utf-8"), re.MULTILINE
    )
    prd_sections = re.findall(
        r"^## (.+)$", prd_path.read_text(encoding="utf-8"), re.MULTILINE
    )

    assert prd_sections == template_sections, (
        f"{prd_path.name} sections {prd_sections} do not match "
        f"TEMPLATE.md sections {template_sections}"
    )


@pytest.mark.parametrize("prd_path", _prd_files(), ids=lambda path: path.name)
def test_prd_declares_a_status(prd_path: Path) -> None:
    text = prd_path.read_text(encoding="utf-8")
    statuses = ("Draft", "Accepted", "In progress", "Shipped", "Superseded")

    match = re.search(r"^Status:\s*(.+)$", text, re.MULTILINE)
    assert match, f"{prd_path.name} has no 'Status:' line"
    assert match.group(1).strip() in statuses, (
        f"{prd_path.name} has status {match.group(1).strip()!r}; "
        f"expected one of {list(statuses)}"
    )


def _harness_yaml_files() -> list[Path]:
    return sorted(ISSUE_TEMPLATE_DIR.glob("*.yml")) + [LABELS_FILE]


@pytest.mark.parametrize("path", _harness_yaml_files(), ids=lambda path: path.name)
def test_harness_yaml_carries_no_explanatory_comments(path: Path) -> None:
    offenders = [
        (number, line.rstrip())
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if line.lstrip().startswith("#")
    ]

    assert not offenders, (
        f"{path.name} carries explanatory comments: {offenders}. "
        f"YAML descriptions are content; comments are not."
    )


def _documents_citing_code() -> list[Path]:
    documents = sorted(ISSUE_TEMPLATE_DIR.glob("*.yml"))
    documents.append(REPO_ROOT / "CONTRIBUTING.md")
    documents.extend(sorted(PRD_DIR.glob("*.md")))
    return documents


BACKTICKED = re.compile(r"`([^`\n]+)`")
CODE_PATH_PATTERN = re.compile(
    r"^(?:app|tests|src|features|alembic|scripts|docs)/[A-Za-z0-9_./-]+"
    r"\.(?:py|ts|tsx|md|sh|yml|mako)$"
)
CODE_PATH_BASES = ("", "backend", "frontend", "backend/app", "frontend/src")


def _cited_code_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for span in BACKTICKED.findall(text):
        for token in span.split():
            candidate = token.split("::")[0].strip("`,;()[]")
            if CODE_PATH_PATTERN.match(candidate):
                paths.add(candidate)
    return sorted(paths)


@pytest.mark.parametrize(
    "document", _documents_citing_code(), ids=lambda path: path.name
)
def test_cited_code_paths_exist(document: Path) -> None:
    cited = _cited_code_paths(document.read_text(encoding="utf-8"))

    missing = [
        path
        for path in cited
        if not any((REPO_ROOT / base / path).exists() for base in CODE_PATH_BASES)
    ]

    assert not missing, (
        f"{document.name} cites paths that do not exist: {missing}. "
        f"An example that points at a renamed module teaches every future agent "
        f"to look in the wrong place."
    )


def test_task_skill_refuses_the_one_form_it_cannot_execute() -> None:
    skill = TASK_SKILL.read_text(encoding="utf-8")
    support_form = ISSUE_TEMPLATE_DIR / "support.yml"
    support_label = _load(support_form)["labels"][0]

    assert f"`{support_label}`" in skill, (
        f"support.yml preseeds {support_label!r} but /task never mentions it. "
        f"A support ticket is a question, not a change: /task must refuse it "
        f"rather than plan an implementation for it."
    )


CODEX_SKILLS = ("groom", "task", "orchestrate")
CODEX_REVIEWERS = ("backend-reviewer", "frontend-reviewer", "uncle-bob")


def test_agents_md_is_the_shared_project_guide() -> None:
    assert (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip() == (
        "@AGENTS.md"
    )


@pytest.mark.parametrize("name", CODEX_SKILLS)
def test_codex_skill_points_to_maintained_workflow(name: str) -> None:
    path = REPO_ROOT / ".agents" / "skills" / name / "SKILL.md"
    assert path.is_file(), f"Codex cannot discover {name}: {path} is missing"

    contents = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", contents, re.DOTALL)
    assert match, f"{path} lacks YAML frontmatter"
    metadata = yaml.safe_load(match.group(1))
    assert metadata["name"] == name
    assert metadata["description"].strip()
    assert (REPO_ROOT / ".claude" / "skills" / name / "SKILL.md").is_file()
    assert f".claude/skills/{name}/SKILL.md" in contents
    assert "AGENTS.md" in contents


@pytest.mark.parametrize("name", CODEX_REVIEWERS)
def test_codex_reviewer_uses_maintained_rubric(name: str) -> None:
    path = REPO_ROOT / ".codex" / "agents" / f"{name}.toml"
    assert path.is_file(), f"Codex cannot discover {name}: {path} is missing"

    config = tomllib.loads(path.read_text(encoding="utf-8"))
    assert config["name"] == name
    assert config["description"].strip()
    instructions = config["developer_instructions"]
    assert "AGENTS.md" in instructions
    assert f".claude/agents/{name}.md" in instructions
    assert "Do not edit files or commit" in instructions
    assert (REPO_ROOT / ".claude" / "agents" / f"{name}.md").is_file()
