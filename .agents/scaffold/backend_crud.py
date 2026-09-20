"""Render a complete backend CRUD slice from the templates that encode the rules.

The generated model, repository, service, schemas, router, dependency module and
both test modules already satisfy `.agents/rules/backend/*.md`: schema-pinned
tables, `.flush()`-only repositories, a `transaction()` boundary in the service,
an explicit auth dependency and response envelope on every route, and paired
test modules. Only the domain decisions — extra validation, RBAC nuance, extra
endpoints — are left for the implementer.

Run `--plan` first: it prints the exact artifact list as JSON and writes
nothing. Freeze that list to a file, then run `--apply --approved <file>`; every
path is checked by `validate_scaffold.py` and any path missing from the approved
list is refused.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_scaffold import validate  # noqa: E402

SCAFFOLD_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = SCAFFOLD_ROOT / "templates" / "backend"


def _detect_repo_root() -> Path:
    """Return the working tree the slice is written into."""
    result = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return SCAFFOLD_ROOT.parent.parent


REPO_ROOT = _detect_repo_root()

ENTITY_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
SCHEMA_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

COLUMN_TYPES = {
    "str": "String(255)",
    "int": "Integer",
    "float": "Float",
    "bool": "Boolean",
}
SAMPLE_VALUES = {
    "str": ('"Sample value"', '"Updated value"'),
    "int": ("1", "2"),
    "float": ("1.5", "2.5"),
    "bool": ("True", "False"),
}


class ScaffoldError(Exception):
    """Raised when the requested slice cannot be rendered."""


class Field:
    """One declared column, in every form the templates need it."""

    def __init__(self, name: str, kind: str, *, nullable: bool) -> None:
        self.name = name
        self.kind = kind
        self.nullable = nullable

    @property
    def annotation(self) -> str:
        """The Python annotation for a required value of this field."""
        return f"{self.kind} | None" if self.nullable else self.kind

    @property
    def column(self) -> str:
        """The SQLAlchemy column expression for this field."""
        parts = [COLUMN_TYPES[self.kind], f"nullable={self.nullable}"]
        if self.kind == "bool" and not self.nullable:
            parts.append("default=False")
            parts.append("server_default=false()")
        return f"mapped_column({', '.join(parts)})"


def parse_field(raw: str, nullable_names: set[str]) -> Field:
    """Turn a `name:type` argument into a `Field`, or explain why it is invalid."""
    if ":" not in raw:
        raise ScaffoldError(f"--field {raw!r} must be written as name:type")
    name, kind = raw.split(":", 1)
    name, kind = name.strip(), kind.strip()
    if not FIELD_NAME.match(name):
        raise ScaffoldError(f"field name {name!r} must be lower_snake_case")
    if kind not in COLUMN_TYPES:
        supported = ", ".join(sorted(COLUMN_TYPES))
        raise ScaffoldError(f"field type {kind!r} is not supported; use one of {supported}")
    if name in {"id", "created_at", "updated_at"}:
        raise ScaffoldError(f"field {name!r} is provided by the template already")
    return Field(name, kind, nullable=name in nullable_names)


def pluralize(word: str) -> str:
    """Return the table/module plural of a lower_snake_case entity stem."""
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def snake(name: str) -> str:
    """Convert a PascalCase entity name to lower_snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _indent(lines: list[str], spaces: int = 4) -> str:
    """Join pre-rendered lines with a fixed indent, or return an empty block."""
    pad = " " * spaces
    return "\n".join(pad + line for line in lines)


def build_substitutions(entity: str, schema: str, fields: list[Field]) -> dict[str, str]:
    """Compute every placeholder the backend templates reference."""
    stem = snake(entity)
    plural = pluralize(stem)
    sa_names = {"DateTime", "func"} | {
        COLUMN_TYPES[field.kind].split("(")[0] for field in fields
    }
    if any(field.kind == "bool" and not field.nullable for field in fields):
        sa_names.add("false")
    upper = sorted(name for name in sa_names if name[0].isupper())
    lower = sorted(name for name in sa_names if not name[0].isupper())

    create_literal = ", ".join(
        f"{field.name}={SAMPLE_VALUES[field.kind][0]}" for field in fields
    )
    update_literal = f"{fields[0].name}={SAMPLE_VALUES[fields[0].kind][1]}"
    create_dict = (
        "{"
        + ", ".join(f'"{f.name}": {SAMPLE_VALUES[f.kind][0]}' for f in fields)
        + "}"
    )
    update_dict = f'{{"{fields[0].name}": {SAMPLE_VALUES[fields[0].kind][1]}}}'

    return {
        "{{Entity}}": entity,
        "{{entity}}": stem,
        "{{entities}}": plural,
        "{{table}}": plural,
        "{{schema}}": schema,
        "{{schema_const}}": f"{schema.upper()}_SCHEMA",
        "{{model_sa_imports}}": ", ".join(upper + lower),
        "{{model_columns}}": _indent(
            [f"{f.name}: Mapped[{f.annotation}] = {f.column}" for f in fields]
        ),
        "{{schema_create_fields}}": _indent(_create_schema_lines(fields)),
        "{{schema_update_fields}}": _indent(
            [f"{f.name}: {f.kind} | None = None" for f in fields]
        ),
        "{{schema_read_fields}}": _indent(
            [f"{f.name}: {f.annotation}" for f in fields]
        ),
        "{{repository_create_params}}": ", ".join(
            f"{f.name}: {f.annotation}" for f in fields
        ),
        "{{repository_create_kwargs}}": ", ".join(f"{f.name}={f.name}" for f in fields),
        "{{repository_update_params}}": _indent(
            [f"{f.name}: {f.kind} | None = None," for f in fields], spaces=8
        ),
        "{{repository_update_assignments}}": "\n".join(
            f"        if {f.name} is not None:\n            record.{f.name} = {f.name}"
            for f in fields
        ),
        "{{service_read_kwargs}}": _indent(
            [f"{f.name}=record.{f.name}," for f in fields], spaces=8
        ),
        "{{service_create_kwargs}}": _indent(
            [f"{f.name}=payload.{f.name}," for f in fields], spaces=20
        ),
        "{{service_update_kwargs}}": _indent(
            [f"{f.name}=payload.{f.name}," for f in fields], spaces=20
        ),
        "{{fake_record_values}}": _indent(
            [f'"{f.name}": {SAMPLE_VALUES[f.kind][0]},' for f in fields], spaces=8
        ),
        "{{fake_create_overrides}}": ", ".join(f"{f.name}={f.name}" for f in fields),
        "{{create_payload_literal}}": create_literal,
        "{{update_payload_literal}}": update_literal,
        "{{update_assertion}}": (
            f"result.{fields[0].name} == {SAMPLE_VALUES[fields[0].kind][1]}"
        ),
        "{{create_payload_dict}}": create_dict,
        "{{update_payload_dict}}": update_dict,
        "{{update_response_assertion}}": (
            f'updated.json()["data"]["{fields[0].name}"] '
            f"== {SAMPLE_VALUES[fields[0].kind][1]}"
        ),
    }


def _create_schema_lines(fields: list[Field]) -> list[str]:
    """Render the create schema's field declarations without an ellipsis default."""
    lines = []
    for field in fields:
        if field.kind == "str" and not field.nullable:
            lines.append(f"{field.name}: str = Field(min_length=1, max_length=255)")
        elif field.kind == "str":
            lines.append(f"{field.name}: str | None = Field(default=None, max_length=255)")
        elif field.nullable:
            lines.append(f"{field.name}: {field.kind} | None = None")
        else:
            lines.append(f"{field.name}: {field.kind}")
    return lines


def render(template_name: str, substitutions: dict[str, str]) -> str:
    """Fill one template, replacing the longest placeholders first."""
    text = (TEMPLATE_ROOT / template_name).read_text(encoding="utf-8")
    for key in sorted(substitutions, key=len, reverse=True):
        text = text.replace(key, substitutions[key])
    return text


def artifact_plan(entity: str, schema: str, fields: list[Field]) -> dict[str, str]:
    """Map every repo-relative artifact path to its rendered content."""
    values = build_substitutions(entity, schema, fields)
    stem = values["{{entity}}"]
    plural = values["{{entities}}"]
    return {
        f"backend/app/models/{stem}.py": render("model.py.tmpl", values),
        f"backend/app/repositories/{plural}.py": render("repository.py.tmpl", values),
        f"backend/app/services/{plural}.py": render("service.py.tmpl", values),
        f"backend/app/schemas/api/{plural}.py": render("schemas.py.tmpl", values),
        f"backend/app/routers/{plural}.py": render("router.py.tmpl", values),
        f"backend/app/dependencies/{plural}.py": render("dependencies.py.tmpl", values),
        f"backend/tests/unit/services/test_{plural}.py": render(
            "test_service.py.tmpl", values
        ),
        f"backend/tests/integration/api/test_{plural}.py": render(
            "test_router.py.tmpl", values
        ),
    }


def _all_names(source: str) -> tuple[list[str], int, int] | None:
    """Locate the module's `__all__` assignment and return its names and span."""
    tree = ast.parse(source)
    for node in tree.body:
        targets = getattr(node, "targets", [])
        if not targets or not isinstance(targets[0], ast.Name):
            continue
        if targets[0].id != "__all__" or not isinstance(node.value, ast.List):
            continue
        names = [
            element.value
            for element in node.value.elts
            if isinstance(element, ast.Constant)
        ]
        return names, node.lineno, node.end_lineno or node.lineno
    return None


def _with_all_entries(source: str, new_names: list[str]) -> str:
    """Return the module with `new_names` added to a sorted `__all__` list."""
    located = _all_names(source)
    if located is None:
        raise ScaffoldError("module has no __all__ list to extend")
    names, start, end = located
    merged = sorted(set(names) | set(new_names))
    body = "\n".join(f'    "{name}",' for name in merged)
    lines = source.splitlines(keepends=True)
    replacement = f"__all__ = [\n{body}\n]\n"
    return "".join(lines[: start - 1]) + replacement + "".join(lines[end:])


def _with_import(source: str, statement: str) -> str:
    """Insert an import statement after the module's last import, idempotently."""
    if statement in source:
        return source
    tree = ast.parse(source)
    last = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = max(last, node.end_lineno or node.lineno)
    lines = source.splitlines(keepends=True)
    return "".join(lines[:last]) + statement + "\n" + "".join(lines[last:])


def _with_router_registration(source: str, alias: str) -> str:
    """Add the router to `main.py`'s routers import and its `include_router` calls."""
    call = f"app.include_router({alias}, responses=ERROR_RESPONSES)"
    if alias not in source:
        source = re.sub(
            r"from \.routers import ([^\n]+)\n",
            lambda match: "from .routers import "
            + ", ".join(sorted({*match.group(1).split(", "), alias}))
            + "\n",
            source,
            count=1,
        )
    if call not in source:
        includes = list(
            re.finditer(r"^app\.include_router\([^\n]*\)\n", source, re.MULTILINE)
        )
        if not includes:
            raise ScaffoldError("main.py has no include_router call to follow")
        cut = includes[-1].end()
        source = source[:cut] + call + "\n" + source[cut:]
    return source


def _with_schema_constant(source: str, schema: str) -> str:
    """Declare a new bounded-context schema and add it to `DOMAIN_SCHEMAS`."""
    constant = f"{schema.upper()}_SCHEMA"
    if f"{constant} =" not in source:
        source = source.replace(
            "DOMAIN_SCHEMAS:",
            f'{constant} = "{schema}"\n\nDOMAIN_SCHEMAS:',
            1,
        )
    source = re.sub(
        r"DOMAIN_SCHEMAS: tuple\[str, \.\.\.\] = \(([^)]*)\)",
        lambda match: "DOMAIN_SCHEMAS: tuple[str, ...] = ("
        + ", ".join(
            sorted(
                {
                    part.strip()
                    for part in match.group(1).split(",")
                    if part.strip()
                }
                | {constant}
            )
        )
        + ")",
        source,
        count=1,
    )
    return _with_all_entries(source, [constant])


def patch_plan(
    entity: str, schema: str, fields: list[Field], *, add_schema: bool
) -> dict[str, str]:
    """Map every repo-relative patch target to its rewritten content."""
    values = build_substitutions(entity, schema, fields)
    stem = values["{{entity}}"]
    plural = values["{{entities}}"]
    patches: dict[str, str] = {}

    models_init = (REPO_ROOT / "backend/app/models/__init__.py").read_text()
    models_init = _with_import(models_init, f"from .{stem} import {entity}")
    patches["backend/app/models/__init__.py"] = _with_all_entries(models_init, [entity])

    deps_init = (REPO_ROOT / "backend/app/dependencies/__init__.py").read_text()
    deps_init = _with_import(
        deps_init,
        f"from .{plural} import {entity}ServiceDep, get_{stem}_service",
    )
    patches["backend/app/dependencies/__init__.py"] = _with_all_entries(
        deps_init, [f"{entity}ServiceDep", f"get_{stem}_service"]
    )

    routers_init = (REPO_ROOT / "backend/app/routers/__init__.py").read_text()
    routers_init = _with_import(
        routers_init, f"from .{plural} import router as {plural}_router"
    )
    patches["backend/app/routers/__init__.py"] = _with_all_entries(
        routers_init, [f"{plural}_router"]
    )

    main = (REPO_ROOT / "backend/app/main.py").read_text()
    patches["backend/app/main.py"] = _with_router_registration(main, f"{plural}_router")

    if add_schema:
        schemas = (REPO_ROOT / "backend/app/models/db_schemas.py").read_text()
        patches["backend/app/models/db_schemas.py"] = _with_schema_constant(
            schemas, schema
        )
    return patches


def _diff(path: str, updated: str) -> str:
    """Render a unified diff between the file on disk and its patched content."""
    current = (REPO_ROOT / path).read_text().splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            current, updated.splitlines(keepends=True), f"a/{path}", f"b/{path}"
        )
    )


def known_schemas() -> set[str]:
    """Read the bounded-context schemas already declared by the backend."""
    source = (REPO_ROOT / "backend/app/models/db_schemas.py").read_text()
    constants = dict(
        re.findall(r'^([A-Z_]+_SCHEMA) = "([a-z_]+)"$', source, re.MULTILINE)
    )
    domain = re.search(r"DOMAIN_SCHEMAS: tuple\[str, \.\.\.\] = \(([^)]*)\)", source)
    if domain is None:
        return set()
    return {
        constants[part.strip()]
        for part in domain.group(1).split(",")
        if part.strip() in constants
    }


def _run(command: list[str], cwd: Path) -> None:
    """Run a fixed developer tool from a directory, reporting a failure but not raising."""
    result = subprocess.run(  # noqa: S603
        command, cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)


def main(argv: list[str] | None = None) -> int:
    """Plan or apply one backend CRUD slice."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entity")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--field", action="append", default=[])
    parser.add_argument("--nullable", action="append", default=[])
    parser.add_argument("--add-schema", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved")
    args = parser.parse_args(argv)

    if args.plan == args.apply:
        sys.stderr.write("choose exactly one of --plan or --apply\n")
        return 2
    if not ENTITY_NAME.match(args.entity):
        sys.stderr.write(f"entity {args.entity!r} must be PascalCase\n")
        return 2
    if not SCHEMA_NAME.match(args.schema):
        sys.stderr.write(f"schema {args.schema!r} must be lower_snake_case\n")
        return 2
    if not args.field:
        sys.stderr.write("at least one --field name:type is required\n")
        return 2

    try:
        fields = [parse_field(raw, set(args.nullable)) for raw in args.field]
    except ScaffoldError as error:
        sys.stderr.write(f"{error}\n")
        return 2

    existing = known_schemas()
    if args.schema not in existing and not args.add_schema:
        constant = f"{args.schema.upper()}_SCHEMA"
        sys.stderr.write(
            f"{args.schema!r} is not a declared bounded context "
            f"(have: {', '.join(sorted(existing))}).\n"
            "Add it to backend/app/models/db_schemas.py:\n"
            f'    {constant} = "{args.schema}"\n'
            f"    DOMAIN_SCHEMAS: tuple[str, ...] = (..., {constant})\n"
            "or re-run with --add-schema to have this command make that edit.\n"
        )
        return 2

    add_schema = args.add_schema and args.schema not in existing
    artifacts = artifact_plan(args.entity, args.schema, fields)
    patches = patch_plan(args.entity, args.schema, fields, add_schema=add_schema)
    stem = snake(args.entity)
    plural = pluralize(stem)
    follow_up = [
        f'cd backend && uv run python -m app.commands.create_migration -m "add {plural}"',
        "cd backend && uv run python -m app.commands.export_openapi",
    ]

    if args.plan:
        print(
            json.dumps(
                {
                    "entity": args.entity,
                    "schema": args.schema,
                    "add_schema": add_schema,
                    "artifacts": sorted(artifacts),
                    "patches": [
                        {"path": path, "diff": _diff(path, content)}
                        for path, content in sorted(patches.items())
                    ],
                    "approved_list": sorted([*artifacts, *patches]),
                    "follow_up": follow_up,
                },
                indent=2,
            )
        )
        return 0

    if not args.approved:
        sys.stderr.write("--apply requires --approved <path-list-file>\n")
        return 2
    approved = [
        line.strip()
        for line in Path(args.approved).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    proposed = sorted([*artifacts, *patches])
    verdict = validate(proposed, approved)
    if not verdict["ok"]:
        sys.stderr.write(json.dumps(verdict, indent=2) + "\n")
        return 1

    written: list[str] = []
    for path, content in sorted({**artifacts, **patches}.items()):
        target = REPO_ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(path)

    backend = REPO_ROOT / "backend"
    relative = [path[len("backend/") :] for path in written]
    _run(["uv", "run", "ruff", "format", *relative], backend)
    _run(["uv", "run", "ruff", "check", "--fix", *relative], backend)
    _run(["uv", "run", "ruff", "format", *relative], backend)

    print(json.dumps({"written": written, "follow_up": follow_up}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
