#!/usr/bin/env python3
"""Per-task Docker Compose isolation for the /task pipeline.

Every task gets its own compose project (``task-<slug>``), its own dynamically
allocated host ports, and its own state directory outside the git worktree.
Teardown is structurally scoped to a ``task-`` project name and therefore cannot
reach the developer's main stack.

Stdlib only. Usage:

    python3 task_env.py slug   <free text description>
    python3 task_env.py path   --task <slug> [--mkdir]
    python3 task_env.py up     --task <slug> --worktree <abs-path> [--services db,api,frontend] [--build]
    python3 task_env.py env    --task <slug> [--export]
    python3 task_env.py status [--task <slug>]
    python3 task_env.py logs   --task <slug> [--service api] [-n 200]
    python3 task_env.py down   --task <slug> [--keep-state]
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys

PROJECT_PREFIX = "task-"
STATE_ROOT_ENV = "TASK_ENV_ROOT"
STATE_FILE = "state.json"
ENV_FILE = "env"

DEFAULT_SERVICES = ("db", "api", "frontend")
SERVICE_PORT_BASE = {"db": 55432, "api": 58000, "frontend": 53000}
SERVICE_PORT_VAR = {"db": "POSTGRES_PORT", "api": "API_PORT", "frontend": "FRONTEND_PORT"}

PORT_SCAN_LIMIT = 400
SLUG_MAX = 40
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

POSTGRES_DB = "app"
POSTGRES_USER = "app"
POSTGRES_PASSWORD = "app"


def slug_of(text, max_len=SLUG_MAX):
    """Turn free text into a compose-safe slug, truncated on a word boundary."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if not cleaned:
        return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:8]
    if len(cleaned) <= max_len:
        return cleaned
    head = cleaned[:max_len]
    if cleaned[max_len] != "-" and "-" in head:
        head = head[: head.rindex("-")]
    head = head.strip("-")
    return head or cleaned[:max_len].strip("-")


def validate_slug(slug):
    """Raise unless the slug is a usable compose project suffix."""
    if not slug or not SLUG_PATTERN.match(slug):
        raise ValueError(
            "invalid task slug %r: expected lowercase alphanumerics and dashes, "
            "starting with an alphanumeric" % (slug,)
        )
    return slug


def project_name(slug):
    """Return the compose project name that owns this task's containers."""
    return PROJECT_PREFIX + validate_slug(slug)


def assert_scoped(project):
    """Raise unless the compose project belongs to the /task namespace."""
    if not isinstance(project, str) or not project.startswith(PROJECT_PREFIX):
        raise ValueError(
            "refusing to act on compose project %r: only %r* projects are in scope"
            % (project, PROJECT_PREFIX)
        )
    if len(project) <= len(PROJECT_PREFIX):
        raise ValueError("refusing to act on the bare prefix %r" % (project,))
    return project


def state_root():
    """Return the directory holding every task's state, outside any worktree."""
    override = os.environ.get(STATE_ROOT_ENV)
    if override:
        return Path(override)
    return Path(os.environ.get("TMPDIR", "/tmp")) / "task-qa"


def state_dir(slug, root=None):
    """Return this task's state directory."""
    return (root or state_root()) / validate_slug(slug)


def port_is_free(port):
    """Return True when the port can be bound on all interfaces right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def next_free_port(base, used, probe=port_is_free, limit=PORT_SCAN_LIMIT):
    """Return the first port at or above base that is neither used nor bound."""
    for candidate in range(base, base + limit):
        if candidate in used:
            continue
        if probe(candidate):
            return candidate
    raise RuntimeError(
        "no free port found in range %d-%d" % (base, base + limit - 1)
    )


def allocate_ports(services=DEFAULT_SERVICES, taken=(), probe=port_is_free, bases=None):
    """Allocate one distinct host port per service, skipping ports already taken."""
    bases = bases or SERVICE_PORT_BASE
    used = set(taken)
    ports = {}
    for service in services:
        if service not in bases:
            raise ValueError("unknown service %r" % (service,))
        port = next_free_port(bases[service], used, probe)
        ports[service] = port
        used.add(port)
    return ports


def reserved_ports(root=None):
    """Return every port already reserved by another task's state file."""
    root = root or state_root()
    taken = set()
    if not root.is_dir():
        return taken
    for entry in sorted(root.iterdir()):
        state_path = entry / STATE_FILE
        if not state_path.is_file():
            continue
        try:
            payload = json.loads(state_path.read_text())
        except (OSError, ValueError):
            continue
        for value in (payload.get("ports") or {}).values():
            if isinstance(value, int):
                taken.add(value)
    return taken


def render_env(ports, secret):
    """Render the compose --env-file contents for this task."""
    lines = [
        "POSTGRES_DB=%s" % POSTGRES_DB,
        "POSTGRES_USER=%s" % POSTGRES_USER,
        "POSTGRES_PASSWORD=%s" % POSTGRES_PASSWORD,
        "AUTH_JWT_SECRET=%s" % secret,
    ]
    for service in DEFAULT_SERVICES:
        if service in ports:
            lines.append("%s=%d" % (SERVICE_PORT_VAR[service], ports[service]))
    return "\n".join(lines) + "\n"


def host_env(ports, secret):
    """Return the host-side environment for running repo checks against this task."""
    values = {"AUTH_JWT_SECRET": secret}
    if "db" in ports:
        values["DATABASE_URL"] = (
            "postgresql+asyncpg://%s:%s@127.0.0.1:%d/%s"
            % (POSTGRES_USER, POSTGRES_PASSWORD, ports["db"], POSTGRES_DB)
        )
    if "api" in ports:
        values["API_BASE_URL"] = "http://127.0.0.1:%d" % ports["api"]
    if "frontend" in ports:
        values["FRONTEND_BASE_URL"] = "http://127.0.0.1:%d" % ports["frontend"]
    return values


def compose_cmd(project, args, worktree=None, env_file=None):
    """Build a docker compose argument vector scoped to one task project."""
    assert_scoped(project)
    cmd = ["docker", "compose", "-p", project]
    if worktree:
        cmd += ["--project-directory", str(worktree)]
        cmd += ["-f", str(Path(worktree) / "docker-compose.yml")]
    if env_file:
        cmd += ["--env-file", str(env_file)]
    return cmd + list(args)


def parse_services(raw):
    """Parse a comma-separated service list, rejecting unknown services."""
    if not raw:
        return list(DEFAULT_SERVICES)
    wanted = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in wanted if item not in DEFAULT_SERVICES]
    if unknown:
        raise ValueError("unknown service(s): %s" % ", ".join(unknown))
    return [service for service in DEFAULT_SERVICES if service in wanted]


def read_state(slug, root=None):
    """Load a task's state file, or None when the task has no environment."""
    path = state_dir(slug, root) / STATE_FILE
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def write_state(slug, payload, root=None):
    """Persist a task's state file and return its path."""
    directory = state_dir(slug, root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / STATE_FILE
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def run(cmd, dry_run=False):
    """Run a command, or print it when dry running."""
    print("+ %s" % " ".join(cmd), file=sys.stderr)
    if dry_run:
        return 0
    return subprocess.call(cmd)


def require_docker():
    """Exit unless the docker compose plugin is usable."""
    if shutil.which("docker") is None:
        sys.exit("docker is not installed; /task cannot provision an environment")
    if subprocess.call(
        ["docker", "compose", "version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ):
        sys.exit("`docker compose` is unavailable; install the compose plugin")


def cmd_up(args):
    """Bring this task's stack up on its own project name and ports."""
    slug = validate_slug(args.task)
    worktree = Path(args.worktree).resolve()
    compose_file = worktree / "docker-compose.yml"
    if not compose_file.is_file():
        sys.exit("no docker-compose.yml at %s" % compose_file)
    if not args.dry_run:
        require_docker()

    services = parse_services(args.services)
    state = read_state(slug)
    if state and state.get("ports"):
        ports = {name: int(value) for name, value in state["ports"].items()}
        secret = state["secret"]
    else:
        taken = reserved_ports()
        ports = allocate_ports(DEFAULT_SERVICES, taken=taken)
        secret = secrets.token_urlsafe(32)

    directory = state_dir(slug)
    directory.mkdir(parents=True, exist_ok=True)
    env_file = directory / ENV_FILE
    env_file.write_text(render_env(ports, secret))
    env_file.chmod(0o600)

    project = project_name(slug)
    write_state(
        slug,
        {
            "slug": slug,
            "project": project,
            "worktree": str(worktree),
            "ports": ports,
            "secret": secret,
            "services": services,
            "state_dir": str(directory),
        },
    )

    up_args = ["up", "-d", "--wait"]
    if args.build:
        up_args.append("--build")
    up_args += services
    code = run(compose_cmd(project, up_args, worktree, env_file), args.dry_run)
    if code:
        print(
            "stack failed to come up; run `task_env.py logs --task %s` then "
            "`task_env.py down --task %s`" % (slug, slug),
            file=sys.stderr,
        )
        return code

    print_env(ports, secret, export=True)
    return 0


def print_env(ports, secret, export=False):
    """Print the host-side environment, optionally as shell export lines."""
    prefix = "export " if export else ""
    for key, value in sorted(host_env(ports, secret).items()):
        print("%s%s=%s" % (prefix, key, value))


def cmd_slug(args):
    """Print the compose-safe slug for a free-text task description."""
    print(slug_of(" ".join(args.text)))
    return 0


def cmd_path(args):
    """Print this task's state directory, which lives outside any worktree."""
    directory = state_dir(validate_slug(args.task))
    if args.mkdir:
        directory.mkdir(parents=True, exist_ok=True)
    print(directory)
    return 0


def cmd_env(args):
    """Print the host-side environment for a provisioned task."""
    state = read_state(validate_slug(args.task))
    if not state:
        sys.exit("no environment for task %r; run `task_env.py up` first" % args.task)
    ports = {name: int(value) for name, value in state["ports"].items()}
    print_env(ports, state["secret"], export=args.export)
    return 0


def cmd_status(args):
    """Show one task's containers, or every provisioned task."""
    if args.task:
        state = read_state(validate_slug(args.task))
        if not state:
            sys.exit("no environment for task %r" % args.task)
        print(json.dumps(state, indent=2, sort_keys=True))
        return run(
            compose_cmd(state["project"], ["ps"], state.get("worktree")), args.dry_run
        )
    root = state_root()
    if not root.is_dir():
        print("no task environments under %s" % root)
        return 0
    for entry in sorted(root.iterdir()):
        state = read_state(entry.name, root)
        if state:
            print("%-42s %s" % (state["project"], state["ports"]))
    return 0


def cmd_logs(args):
    """Tail one task's container logs."""
    state = read_state(validate_slug(args.task))
    if not state:
        sys.exit("no environment for task %r" % args.task)
    log_args = ["logs", "--tail", str(args.tail)]
    if args.service:
        log_args += parse_services(args.service)
    return run(
        compose_cmd(state["project"], log_args, state.get("worktree")), args.dry_run
    )


def cmd_down(args):
    """Tear down exactly one task's stack. There is no --all."""
    slug = validate_slug(args.task)
    project = project_name(slug)
    assert_scoped(project)
    state = read_state(slug)
    worktree = state.get("worktree") if state else None
    env_file = state_dir(slug) / ENV_FILE
    code = run(
        compose_cmd(
            project,
            ["down", "-v", "--remove-orphans"],
            worktree,
            env_file if env_file.is_file() else None,
        ),
        args.dry_run,
    )
    if not args.keep_state and not args.dry_run:
        shutil.rmtree(state_dir(slug), ignore_errors=True)
    return code


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    slug = sub.add_parser("slug", help="print the slug for a task description")
    slug.add_argument("text", nargs="+")
    slug.set_defaults(func=cmd_slug)

    path = sub.add_parser("path", help="print this task's state directory")
    path.add_argument("--task", required=True)
    path.add_argument("--mkdir", action="store_true")
    path.set_defaults(func=cmd_path)

    up = sub.add_parser("up", help="provision this task's isolated stack")
    up.add_argument("--task", required=True)
    up.add_argument("--worktree", required=True)
    up.add_argument("--services", default="")
    up.add_argument("--build", action="store_true")
    up.set_defaults(func=cmd_up)

    env = sub.add_parser("env", help="print host-side env for this task")
    env.add_argument("--task", required=True)
    env.add_argument("--export", action="store_true")
    env.set_defaults(func=cmd_env)

    status = sub.add_parser("status", help="show provisioned tasks")
    status.add_argument("--task", default="")
    status.set_defaults(func=cmd_status)

    logs = sub.add_parser("logs", help="tail this task's logs")
    logs.add_argument("--task", required=True)
    logs.add_argument("--service", default="")
    logs.add_argument("-n", "--tail", type=int, default=200)
    logs.set_defaults(func=cmd_logs)

    down = sub.add_parser("down", help="tear down this task's stack (scoped)")
    down.add_argument("--task", required=True)
    down.add_argument("--keep-state", action="store_true")
    down.set_defaults(func=cmd_down)

    return parser


def main(argv=None):
    """Entry point."""
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as error:
        sys.exit(str(error))


if __name__ == "__main__":
    sys.exit(main())
