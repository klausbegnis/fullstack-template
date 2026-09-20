"""Unit tests for the scaffold artifact-list validator."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_scaffold import check_path, validate  # noqa: E402

BACKEND_SLICE = [
    "backend/app/models/widget.py",
    "backend/app/repositories/widgets.py",
    "backend/app/services/widgets.py",
    "backend/app/schemas/api/widgets.py",
    "backend/app/routers/widgets.py",
    "backend/app/dependencies/widgets.py",
    "backend/tests/unit/services/test_widgets.py",
    "backend/tests/integration/api/test_widgets.py",
]

FRONTEND_SLICE = [
    "frontend/src/features/widgets/model/widget.ts",
    "frontend/src/features/widgets/api/widget-mapper.ts",
    "frontend/src/app/(app)/widgets/page.tsx",
]


class CheckPathTests(unittest.TestCase):
    def test_backend_slice_paths_are_allowed(self) -> None:
        for path in BACKEND_SLICE:
            self.assertEqual(check_path(path), "", path)

    def test_frontend_slice_paths_are_allowed(self) -> None:
        for path in FRONTEND_SLICE:
            self.assertEqual(check_path(path, feature="widgets"), "", path)

    def test_patch_targets_are_allowed(self) -> None:
        for path in ("backend/app/main.py", "backend/app/models/__init__.py"):
            self.assertEqual(check_path(path), "", path)

    def test_absolute_path_is_rejected(self) -> None:
        self.assertIn("absolute", check_path("/etc/passwd"))

    def test_windows_absolute_path_is_rejected(self) -> None:
        self.assertIn("absolute", check_path("C:/windows/system32"))

    def test_traversal_is_rejected(self) -> None:
        self.assertIn("traversal", check_path("backend/app/models/../../../etc/x.py"))

    def test_backslash_is_rejected(self) -> None:
        self.assertIn("separators", check_path("backend\\app\\models\\widget.py"))

    def test_empty_path_is_rejected(self) -> None:
        self.assertIn("empty", check_path(""))

    def test_backend_path_outside_the_slice_is_rejected(self) -> None:
        self.assertIn("not one of", check_path("backend/app/core/database.py"))

    def test_backend_test_module_must_be_named_test(self) -> None:
        self.assertIn("not a test module", check_path("backend/tests/unit/services/widgets.py"))

    def test_backend_module_name_must_be_snake_case(self) -> None:
        self.assertIn("snake_case", check_path("backend/app/models/Widget.py"))

    def test_frontend_path_outside_a_feature_is_rejected(self) -> None:
        self.assertIn("only features", check_path("frontend/src/lib/api/mutator.ts"))

    def test_frontend_path_of_another_feature_is_rejected(self) -> None:
        reason = check_path("frontend/src/features/users/model/user.ts", feature="widgets")
        self.assertIn("does not belong", reason)

    def test_frontend_non_module_is_rejected(self) -> None:
        reason = check_path("frontend/src/features/widgets/model/notes.md", feature="widgets")
        self.assertIn("not a .ts", reason)

    def test_path_outside_both_stacks_is_rejected(self) -> None:
        self.assertIn("only writes under", check_path("docs/prds/0001-widgets.md"))


class ValidateTests(unittest.TestCase):
    def test_a_matching_plan_and_approval_pass(self) -> None:
        result = validate(BACKEND_SLICE, BACKEND_SLICE)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["checked"], len(BACKEND_SLICE))

    def test_a_path_missing_from_the_approved_list_fails(self) -> None:
        result = validate(BACKEND_SLICE, BACKEND_SLICE[:-1])
        self.assertFalse(result["ok"])
        self.assertIn("not present in the approved artifact list", result["errors"][0])

    def test_strict_requires_every_approved_path_to_be_produced(self) -> None:
        result = validate(BACKEND_SLICE[:-1], BACKEND_SLICE, strict=True)
        self.assertFalse(result["ok"])
        self.assertIn("approved but not produced", result["errors"][0])

    def test_non_strict_tolerates_an_unused_approved_path(self) -> None:
        result = validate(BACKEND_SLICE[:-1], BACKEND_SLICE)
        self.assertTrue(result["ok"], result["errors"])

    def test_a_duplicate_path_fails(self) -> None:
        duplicated = [*BACKEND_SLICE, BACKEND_SLICE[0]]
        result = validate(duplicated, duplicated)
        self.assertFalse(result["ok"])
        self.assertIn("listed twice", result["errors"][0])

    def test_an_unsafe_path_fails_even_when_approved(self) -> None:
        result = validate(["/etc/passwd"], ["/etc/passwd"])
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
