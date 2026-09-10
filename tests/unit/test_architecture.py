import ast
import importlib.machinery
import importlib.util
import py_compile
import sys
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
    _assert_four_implementation_packages(package_root)


def _assert_four_implementation_packages(package_root: Path) -> None:
    packages = {path.name for path in package_root.iterdir() if (path / "__init__.py").is_file()}
    assert packages == {"_common", "api", "cli", "ui"}


@pytest.mark.parametrize("name", ["models", "parsers", "analytics", "serialization", "reporting", "services"])
def test_removed_deep_imports_have_no_implementation(name: str) -> None:
    _assert_legacy_module_removed(f"qualtrics.{name}")


def _assert_legacy_module_removed(module: str) -> None:
    spec = importlib.util.find_spec(module)
    if spec is None:
        return
    assert spec.origin is None, f"Legacy implementation: {spec.origin}"
    assert spec.submodule_search_locations is not None, f"Legacy module is not an empty namespace: {module}"
    implementations = [
        path
        for location in spec.submodule_search_locations
        for path in Path(location).rglob("*")
        if path.is_file()
        and (
            path.suffix == ".py"
            or (
                "__pycache__" not in path.relative_to(location).parts
                and path.name.endswith(tuple(importlib.machinery.all_suffixes()))
            )
        )
    ]
    assert not implementations, f"Legacy implementation files: {implementations}"


@pytest.fixture
def cached_package_layout(tmp_path, monkeypatch):
    package_root = tmp_path / "architecture_cache_probe"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("")
    for name in ("_common", "api", "cli", "ui"):
        (package_root / name).mkdir()
        (package_root / name / "__init__.py").write_text("")
    for name in ("models", "parsers", "analytics", "serialization", "reporting", "services"):
        legacy = package_root / name
        legacy.mkdir()
        source = legacy / "__init__.py"
        source.write_text("raise RuntimeError('Stale legacy code must not execute')\n")
        py_compile.compile(str(source), doraise=True)
        source.unlink()
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        yield package_root
    finally:
        for name in list(sys.modules):
            if name == package_root.name or name.startswith(package_root.name + "."):
                del sys.modules[name]


def test_architecture_checks_allow_cache_only_legacy_directories(cached_package_layout) -> None:
    _assert_four_implementation_packages(cached_package_layout)
    for name in ("models", "parsers", "analytics", "serialization", "reporting", "services"):
        _assert_legacy_module_removed(f"{cached_package_layout.name}.{name}")


@pytest.mark.parametrize(
    "filename",
    [
        "models.py",
        "models/__init__.py",
        "models/entities.py",
        "models/nested/entities.py",
        "models/nested/legacy.pyc",
        "models/__pycache__/legacy.py",
    ],
)
def test_legacy_check_rejects_implementation_files(cached_package_layout, filename: str) -> None:
    implementation = cached_package_layout / filename
    implementation.parent.mkdir(parents=True, exist_ok=True)
    if implementation.suffix == ".pyc":
        py_compile.compile(str(cached_package_layout / "__init__.py"), cfile=str(implementation), doraise=True)
    else:
        implementation.write_text("from qualtrics._common.models import EntitySet\n")
    with pytest.raises(AssertionError, match="Legacy implementation"):
        _assert_legacy_module_removed(f"{cached_package_layout.name}.models")


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
