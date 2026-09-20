#!/usr/bin/env python3
"""Tests for the dockerless logic in task_env.py.

Run with `python3 .agents/skills/task/scripts/test_task_env.py`. Nothing here touches
docker, the network, or the developer's stack.
"""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parent / "task_env.py"
SPEC = importlib.util.spec_from_file_location("task_env", MODULE_PATH)
task_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task_env)


class SlugTests(unittest.TestCase):
    """slug_of turns arbitrary task text into a compose-safe identifier."""

    def test_lowercases_and_dashes(self):
        self.assertEqual(task_env.slug_of("Add User Search"), "add-user-search")

    def test_collapses_punctuation_runs(self):
        self.assertEqual(task_env.slug_of("fix:  the /health  endpoint!"), "fix-the-health-endpoint")

    def test_strips_leading_and_trailing_separators(self):
        self.assertEqual(task_env.slug_of("--wip--"), "wip")

    def test_truncates_on_a_word_boundary(self):
        slug = task_env.slug_of("add pagination to the users list endpoint and its tests", 30)
        self.assertLessEqual(len(slug), 30)
        self.assertEqual(slug, "add-pagination-to-the-users")
        self.assertFalse(slug.endswith("-"))

    def test_truncation_keeps_a_whole_word_when_the_cut_is_exact(self):
        self.assertEqual(task_env.slug_of("alpha-beta-gamma", 10), "alpha-beta")
        self.assertEqual(task_env.slug_of("alpha-beta-gamma", 12), "alpha-beta")

    def test_single_long_word_is_hard_truncated(self):
        self.assertEqual(task_env.slug_of("a" * 60, 12), "a" * 12)

    def test_non_ascii_only_text_falls_back_to_a_stable_hash(self):
        first = task_env.slug_of("日本語")
        second = task_env.slug_of("日本語")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertNotEqual(first, task_env.slug_of("한국어"))

    def test_every_slug_is_a_valid_project_suffix(self):
        for text in ["Add User Search", "--wip--", "日本語", "9 lives", ""]:
            task_env.validate_slug(task_env.slug_of(text))


class ProjectNameTests(unittest.TestCase):
    """Project names are the isolation boundary and the teardown scope."""

    def test_prefixes_the_slug(self):
        self.assertEqual(task_env.project_name("add-user-search"), "task-add-user-search")

    def test_rejects_an_invalid_slug(self):
        for bad in ["", "Add_User", "-leading", "has space", "UPPER"]:
            with self.assertRaises(ValueError):
                task_env.project_name(bad)

    def test_assert_scoped_accepts_task_projects(self):
        self.assertEqual(task_env.assert_scoped("task-x"), "task-x")

    def test_assert_scoped_refuses_the_main_stack(self):
        for foreign in ["build", "some-other-project", "", "task-", "mytask-x", None]:
            with self.assertRaises(ValueError):
                task_env.assert_scoped(foreign)

    def test_compose_cmd_cannot_be_built_for_an_unscoped_project(self):
        with self.assertRaises(ValueError):
            task_env.compose_cmd("build", ["down", "-v"])

    def test_compose_cmd_pins_project_file_and_env_file(self):
        cmd = task_env.compose_cmd(
            "task-demo", ["up", "-d"], worktree="/wt/demo", env_file="/state/env"
        )
        self.assertEqual(cmd[:4], ["docker", "compose", "-p", "task-demo"])
        self.assertIn("--project-directory", cmd)
        self.assertIn("/wt/demo/docker-compose.yml", cmd)
        self.assertIn("/state/env", cmd)
        self.assertEqual(cmd[-2:], ["up", "-d"])


class PortAllocationTests(unittest.TestCase):
    """Ports are allocated dynamically so concurrent tasks never collide."""

    @staticmethod
    def probe_excluding(blocked):
        """Return a probe that reports every port free except the blocked ones."""
        return lambda port: port not in blocked

    def test_defaults_to_the_service_bases_when_everything_is_free(self):
        ports = task_env.allocate_ports(probe=self.probe_excluding(set()))
        self.assertEqual(ports, {"db": 55432, "api": 58000, "frontend": 53000})

    def test_skips_bound_ports(self):
        blocked = {55432, 55433, 58000}
        ports = task_env.allocate_ports(probe=self.probe_excluding(blocked))
        self.assertEqual(ports["db"], 55434)
        self.assertEqual(ports["api"], 58001)
        self.assertEqual(ports["frontend"], 53000)

    def test_skips_ports_reserved_by_another_task(self):
        ports = task_env.allocate_ports(
            taken={55432, 53000}, probe=self.probe_excluding(set())
        )
        self.assertEqual(ports["db"], 55433)
        self.assertEqual(ports["frontend"], 53001)

    def test_never_hands_out_the_same_port_twice(self):
        bases = {"db": 40000, "api": 40000, "frontend": 40000}
        ports = task_env.allocate_ports(bases=bases, probe=self.probe_excluding(set()))
        self.assertEqual(sorted(ports.values()), [40000, 40001, 40002])

    def test_raises_when_the_scan_window_is_exhausted(self):
        with self.assertRaises(RuntimeError):
            task_env.next_free_port(40000, set(), probe=lambda port: False, limit=5)

    def test_rejects_an_unknown_service(self):
        with self.assertRaises(ValueError):
            task_env.allocate_ports(["redis"], probe=self.probe_excluding(set()))

    def test_reserved_ports_reads_every_sibling_task(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            for name, db_port in (("alpha", 55432), ("beta", 55433)):
                directory = root_path / name
                directory.mkdir()
                (directory / task_env.STATE_FILE).write_text(
                    json.dumps({"ports": {"db": db_port, "api": db_port + 100}})
                )
            (root_path / "junk").mkdir()
            self.assertEqual(
                task_env.reserved_ports(root_path), {55432, 55532, 55433, 55533}
            )

    def test_reserved_ports_tolerates_a_corrupt_state_file(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "alpha"
            directory.mkdir()
            (directory / task_env.STATE_FILE).write_text("{not json")
            self.assertEqual(task_env.reserved_ports(Path(root)), set())


class EnvRenderingTests(unittest.TestCase):
    """The compose env file and the host env file are deliberately different."""

    PORTS = {"db": 55440, "api": 58010, "frontend": 53010}

    def test_compose_env_carries_ports_and_the_required_secret(self):
        text = task_env.render_env(self.PORTS, "s" * 40)
        self.assertIn("POSTGRES_PORT=55440", text)
        self.assertIn("API_PORT=58010", text)
        self.assertIn("FRONTEND_PORT=53010", text)
        self.assertIn("AUTH_JWT_SECRET=" + "s" * 40, text)

    def test_compose_env_never_sets_database_url(self):
        text = task_env.render_env(self.PORTS, "s" * 40)
        self.assertNotIn("DATABASE_URL", text)

    def test_host_env_points_at_the_allocated_host_port(self):
        values = task_env.host_env(self.PORTS, "s" * 40)
        self.assertEqual(
            values["DATABASE_URL"],
            "postgresql+asyncpg://app:app@127.0.0.1:55440/app",
        )
        self.assertEqual(values["API_BASE_URL"], "http://127.0.0.1:58010")

    def test_host_env_omits_services_that_were_not_allocated(self):
        values = task_env.host_env({"db": 55440}, "s" * 40)
        self.assertNotIn("API_BASE_URL", values)


class ServiceParsingTests(unittest.TestCase):
    """--services is a whitelist, in compose dependency order."""

    def test_empty_means_all(self):
        self.assertEqual(task_env.parse_services(""), ["db", "api", "frontend"])

    def test_preserves_dependency_order(self):
        self.assertEqual(task_env.parse_services("frontend,db"), ["db", "frontend"])

    def test_rejects_unknown_services(self):
        with self.assertRaises(ValueError):
            task_env.parse_services("db,postgres")


class StateDirTests(unittest.TestCase):
    """State lives outside the worktree so it is never committed."""

    def test_state_dir_is_per_task(self):
        with tempfile.TemporaryDirectory() as root:
            directory = task_env.state_dir("demo", Path(root))
            self.assertEqual(directory, Path(root) / "demo")

    def test_state_round_trips(self):
        with tempfile.TemporaryDirectory() as root:
            task_env.write_state("demo", {"slug": "demo", "ports": {"db": 1}}, Path(root))
            self.assertEqual(
                task_env.read_state("demo", Path(root)),
                {"slug": "demo", "ports": {"db": 1}},
            )

    def test_missing_state_reads_as_none(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(task_env.read_state("demo", Path(root)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
