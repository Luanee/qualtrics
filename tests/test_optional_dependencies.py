"""Exercise public operations with optional distributions unavailable to imports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


def isolated(code: str, blocked: tuple[str, ...], *arguments: Path) -> subprocess.CompletedProcess[str]:
    prefix = f"""
import importlib.abc
import sys
class UnavailableOptionalDependency(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {blocked!r}:
            raise ModuleNotFoundError('Optional distribution unavailable: ' + fullname, name=fullname)
sys.meta_path.insert(0, UnavailableOptionalDependency())
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(prefix) + textwrap.dedent(code), *map(str, arguments)],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_base_sdk_and_data_roundtrip_without_interface_dependencies(survey_files, tmp_path):
    result = isolated(
        """
        from pathlib import Path
        import httpx
        from qualtrics import QualtricsClient, parse_survey, write_entities, load_entities, render_report
        from qualtrics._common.analytics import analyze_entities
        page = {'result': {'elements': [], 'nextPage': None}}
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=page))
        with QualtricsClient(api_token='test', base_url='https://example.test/API/v3', transport=transport) as client:
            assert client.list_surveys().elements == []
        entities = parse_survey(Path(sys.argv[1]), Path(sys.argv[2]))
        write_entities(entities, Path(sys.argv[3]), 'json')
        assert load_entities(Path(sys.argv[3])).responses == entities.responses
        assert analyze_entities(entities).response_count > 0
        assert render_report.__module__ == 'qualtrics.ui.report'
        assert not {'typer', 'rich', 'jinja2', 'markupsafe', 'pyarrow'}.intersection(sys.modules)
    """,
        ("typer", "rich", "jinja2", "markupsafe", "pyarrow"),
        *survey_files,
        tmp_path / "entities",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_root_semantic_and_analytics_workflow_without_optional_dependencies(survey_files, tmp_path):
    result = isolated(
        """
        import json
        from pathlib import Path
        from qualtrics import (
            ReportAnalytics, SemanticModel, analyze_entities, build_semantic_model,
            parse_survey, write_semantic_model,
        )
        entities = parse_survey(Path(sys.argv[1]), Path(sys.argv[2]))
        analytics = analyze_entities(entities)
        assert isinstance(analytics, ReportAnalytics)
        assert analytics.response_count == 2
        assert analytics.survey_name == 'Sample'
        model = build_semantic_model(entities)
        assert isinstance(model, SemanticModel)
        assert [row['response_external_id'] for row in model.fact_responses] == ['R_1', 'R_2']
        output = Path(sys.argv[3])
        write_semantic_model(model, output, 'json')
        responses = json.loads((output / 'fact_responses.json').read_text())
        assert [row['response_external_id'] for row in responses] == ['R_1', 'R_2']
        assert not {'typer', 'rich', 'jinja2', 'markupsafe', 'pyarrow'}.intersection(sys.modules)
    """,
        ("typer", "rich", "jinja2", "markupsafe", "pyarrow"),
        *survey_files,
        tmp_path / "semantic",
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("missing", [("typer",), ("rich",)])
def test_console_entrypoint_explains_missing_cli_extra(missing):
    result = isolated(
        """
        from qualtrics._cli import main
        sys.argv = ['qualtrics', '--help']
        main()
    """,
        missing,
    )
    assert result.returncode == 2
    assert "qualtrics[cli]" in result.stderr
    assert "Traceback" not in result.stderr


def test_module_entrypoint_explains_missing_cli_extra():
    result = isolated(
        """
        import runpy
        sys.argv = ['qualtrics', '--help']
        runpy.run_module('qualtrics', run_name='__main__')
    """,
        ("typer", "rich"),
    )
    assert result.returncode == 2
    assert "qualtrics[cli]" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_help_and_build_do_not_import_ui(survey_files, tmp_path):
    result = isolated(
        """
        from typer.testing import CliRunner
        from qualtrics.cli import app
        from qualtrics import load_entities
        from pathlib import Path
        runner = CliRunner()
        for command in [[], ['build'], ['api'], ['entities'], ['report'], ['semantic-model']]:
            result = runner.invoke(app, [*command, '--help'])
            assert result.exit_code == 0, result.output
        result = runner.invoke(app, ['build', sys.argv[1], '--qsf', sys.argv[2], '--output', sys.argv[3]])
        assert result.exit_code == 0, result.output
        assert load_entities(Path(sys.argv[3])).responses
        assert not {'jinja2', 'markupsafe'}.intersection(sys.modules)
    """,
        ("jinja2", "markupsafe"),
        *survey_files,
        tmp_path / "built",
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("missing", [("jinja2",), ("markupsafe",)])
def test_report_command_explains_missing_ui_extra(missing, tmp_path):
    surveys = tmp_path / "surveys.json"
    surveys.write_text(json.dumps([{"survey_id": "s", "survey_name": "Survey"}]))
    result = isolated(
        """
        from typer.testing import CliRunner
        from qualtrics.cli import app
        result = CliRunner().invoke(app, ['report', '--surveys', sys.argv[1], '--output', sys.argv[2]])
        assert result.exit_code == 2, result.output
        assert 'qualtrics[ui]' in result.output, result.output
        assert not __import__('pathlib').Path(sys.argv[2]).exists()
    """,
        missing,
        surveys,
        tmp_path / "report.html",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ui_rendering_does_not_import_cli(tmp_path):
    result = isolated(
        """
        from pathlib import Path
        from qualtrics import EntitySet
        from qualtrics.ui import render_report
        render_report(EntitySet(), Path(sys.argv[1]))
        assert "id='overview'" in Path(sys.argv[1]).read_text()
        assert not {'typer', 'rich'}.intersection(sys.modules)
    """,
        ("typer", "rich"),
        tmp_path / "report.html",
    )
    assert result.returncode == 0, result.stdout + result.stderr
