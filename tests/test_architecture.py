import ast
import importlib
from pathlib import Path

from sp_farms.application.context import ApplicationContext
from sp_farms.bootstrap import create_application
from sp_farms.domain.result import AppError, Result
from sp_farms.infrastructure.clock import SystemClock

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("app", "domain", "application", "infrastructure", "modules", "plugins")


def test_top_level_packages_import() -> None:
    for package in PACKAGES:
        importlib.import_module(f"sp_farms.{package}")


def test_bootstrap_creates_application_context(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[sp_farms]\n"
        f'database_path = "{(tmp_path / "data.db").as_posix()}"\n'
        f'log_path = "{(tmp_path / "app.log").as_posix()}"\n',
        encoding="utf-8",
    )
    context = create_application(config_path)
    assert isinstance(context, ApplicationContext)
    assert context.clock.now().tzinfo is not None
    assert context.unit_of_work is not None
    context.close()


def test_shutdown_hooks_run_once_in_reverse_order() -> None:
    calls: list[int] = []
    context = ApplicationContext(clock=SystemClock())
    context.add_shutdown_hook(lambda: calls.append(1))
    context.add_shutdown_hook(lambda: calls.append(2))

    context.close()
    context.close()

    assert calls == [2, 1]


def test_result_holds_value_or_error() -> None:
    success = Result.success("ready")
    failure = Result[str].failure(AppError("unavailable", "Provider unavailable"))

    assert success.value == "ready"
    assert failure.error.code == "unavailable"


def test_domain_does_not_import_outer_layers() -> None:
    forbidden = {"sp_farms.app", "sp_farms.application", "sp_farms.infrastructure"}
    for source in (ROOT / "sp_farms" / "domain").glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        assert not any(
            imported == boundary or imported.startswith(f"{boundary}.")
            for imported in imports
            for boundary in forbidden
        )


def test_app_only_uses_infrastructure_through_composition_root() -> None:
    for source in (ROOT / "sp_farms" / "app").glob("*.py"):
        assert "sp_farms.infrastructure" not in source.read_text(encoding="utf-8")
