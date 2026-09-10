import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

import qualtrics
from qualtrics._common.analytics import analyze_entities


def test_public_api_is_implemented_by_domain_modules() -> None:
    assert qualtrics.EntitySet.__module__ == "qualtrics._common.models.entities"
    assert qualtrics.parse_survey.__module__ == "qualtrics._common.parsers.survey"
    assert qualtrics.write_entities.__module__ == "qualtrics._common.serialization.io"
    assert qualtrics.render_report.__module__ == "qualtrics.ui.report"
    assert analyze_entities.__module__ == "qualtrics._common.analytics.report"


def test_catch_all_core_module_is_removed() -> None:
    package_root = Path(qualtrics.__file__).parent
    assert not (package_root / "_core.py").exists()


def test_package_has_four_implementation_packages() -> None:
    package_root = Path(qualtrics.__file__).parent
    packages = {path.name for path in package_root.iterdir() if path.is_dir() and path.name != "__pycache__"}
    assert packages == {"_common", "api", "cli", "ui"}


@pytest.mark.parametrize("name", ["models", "parsers", "analytics", "serialization", "reporting", "services"])
def test_removed_deep_imports_are_unavailable(name: str) -> None:
    module = f"qualtrics.{name}"
    with pytest.raises(ModuleNotFoundError) as error:
        importlib.import_module(module)
    assert error.value.name == module


def _import_targets(path: Path, package_root: Path) -> set[str]:
    package = ".".join(("qualtrics", *path.relative_to(package_root).parent.parts))
    targets: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
            targets.add(module)
            targets.update(f"{module}.{alias.name}" for alias in node.names)
    return targets


def test_common_dependencies_point_toward_shared_code() -> None:
    package_root = Path(qualtrics.__file__).parent
    sources = list((package_root / "_common").rglob("*.py"))
    assert sources, "Shared implementation package is missing"
    forbidden = ("qualtrics.api", "qualtrics.cli", "qualtrics.ui", "typer", "rich", "jinja2", "markupsafe")
    violations = [
        f"{path.relative_to(package_root)} imports {target}"
        for path in sources
        for target in sorted(_import_targets(path, package_root))
        if target == "qualtrics" or any(target == name or target.startswith(name + ".") for name in forbidden)
    ]
    assert not violations, "\n".join(violations)


def test_analytics_does_not_depend_on_parsers() -> None:
    package_root = Path(qualtrics.__file__).parent
    sources = list((package_root / "_common" / "analytics").rglob("*.py"))
    assert sources, "Shared analytics package is missing"
    violations = [
        f"{path.relative_to(package_root)} imports {target}"
        for path in sources
        for target in sorted(_import_targets(path, package_root))
        if target == "qualtrics._common.parsers" or target.startswith("qualtrics._common.parsers.")
    ]
    assert not violations, "\n".join(violations)
