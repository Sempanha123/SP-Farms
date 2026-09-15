from pathlib import Path

import yaml


def test_ci_workflow_structure_and_syntax() -> None:
    root = Path(__file__).resolve().parent.parent
    ci_path = root / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), "CI workflow file must exist"

    with ci_path.open("r", encoding="utf-8") as stream:
        ci_doc = yaml.safe_load(stream)

    assert "jobs" in ci_doc
    jobs = ci_doc["jobs"]

    expected_jobs = {
        "lint-and-typecheck",
        "unit-and-regression-tests",
        "migration-verification",
        "package-smoke-test",
    }
    assert expected_jobs.issubset(jobs.keys())

    # Verify no embedded secrets in CI definition
    raw_text = ci_path.read_text(encoding="utf-8")
    assert "password:" not in raw_text.lower()
    assert "secret_key:" not in raw_text.lower()
    assert "bearer" not in raw_text.lower()


def test_release_workflow_structure_and_syntax() -> None:
    root = Path(__file__).resolve().parent.parent
    release_path = root / ".github" / "workflows" / "release.yml"
    assert release_path.exists(), "Release workflow file must exist"

    with release_path.open("r", encoding="utf-8") as stream:
        rel_doc = yaml.safe_load(stream)

    assert "jobs" in rel_doc
    assert "build-and-release" in rel_doc["jobs"]

    # Verify trigger includes tags
    on_trigger = rel_doc.get("on") or rel_doc.get(True, {})
    assert "push" in on_trigger
    assert "tags" in on_trigger["push"]

    # Verify secrets are accessed strictly via GitHub secret context
    raw_text = release_path.read_text(encoding="utf-8")
    assert "${{ secrets." in raw_text


def test_documentation_files_exist() -> None:
    root = Path(__file__).resolve().parent.parent
    checklist = root / "docs" / "RELEASE_CHECKLIST.md"
    contributing = root / "CONTRIBUTING.md"

    assert checklist.exists()
    assert contributing.exists()
    assert "Pre-Release Verification" in checklist.read_text(encoding="utf-8")
    assert "Ruff" in contributing.read_text(encoding="utf-8")
