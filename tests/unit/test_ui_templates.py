"""Behavior of canonical installed-resource UI templates."""

import pytest


def test_environment_uses_strict_autoescaped_package_templates():
    from jinja2 import PackageLoader, StrictUndefined, UndefinedError

    from qualtrics.ui.templating import get_environment

    environment = get_environment()
    assert get_environment() is environment
    assert environment.autoescape is True
    assert environment.undefined is StrictUndefined
    assert isinstance(environment.loader, PackageLoader)
    with pytest.raises(UndefinedError):
        environment.from_string("{{ missing }}").render()
    assert environment.from_string("{{ value }}").render(value='<x a="\'">&') == "&lt;x a=&quot;&#x27;&quot;&gt;&amp;"


def test_shared_templates_escape_labels_and_preserve_trusted_components():
    from qualtrics.ui.components.primitives import page_heading
    from qualtrics.ui.templating import get_environment, trusted_html

    markup = page_heading("<script>'\"</script>", heading_id="' onclick='bad")
    assert "<script>" not in markup
    assert "&#x27;" in markup and "&quot;" in markup
    assert "id='&#x27; onclick=&#x27;bad'" in markup
    assert get_environment().from_string("{{ component }}").render(component=trusted_html(markup)) == markup


@pytest.mark.parametrize("page", ["overview", "questions", "written", "responses"])
def test_page_templates_are_packaged_and_compiled(page):
    from qualtrics.ui.templating import get_environment

    template = get_environment().get_template(f"pages/{page}.html.jinja")
    assert template.name == f"pages/{page}.html.jinja"


def test_canonical_report_preserves_whitespace_links_and_escapes_hostile_values(tmp_path):
    from html import escape

    from qualtrics.models.entities import EntitySet
    from qualtrics.ui import render_report

    value = "  first\n<script>'\"&</script>\n last  "
    entities = EntitySet(
        surveys=[{"survey_id": "s'", "survey_name": "<Survey>"}],
        questions=[{"survey_id": "s'", "question_id": "q", "question_text": "<Question>", "question_type": "TE"}],
        question_fields=[{"survey_id": "s'", "question_id": "q", "field_id": "f'", "field_text": "Written field"}],
        responses=[{"survey_id": "s'", "response_id": "r", "user_agent": "<Agent>"}],
        response_answers=[
            {
                "survey_id": "s'",
                "question_id": "q",
                "field_id": "f'",
                "response_id": "r",
                "answer_text": value,
            }
        ],
    )
    output = tmp_path / "canonical.html"
    render_report(entities, output)
    document = output.read_text()
    assert f"class='written-value'>{escape(value)}</p>" in document
    assert "data-field-id='f&#x27;'" in document
    assert "data-survey='s&#x27;'" in document
    assert "data-response-target='response-1'" in document
    assert "<b>User Agent</b> &lt;Agent&gt;" in document
    assert "<script>'\"&</script>" not in document
    assert document.count("class='written-answer'") == 1
    assert document.count("class='respondent'") == 1
    assert "<style>" in document and "<script>" in document


def test_canonical_empty_report_retains_empty_dom_contract(tmp_path):
    from qualtrics.models.entities import EntitySet
    from qualtrics.ui import render_report

    output = tmp_path / "empty.html"
    render_report(EntitySet(), output)
    document = output.read_text()
    assert "id='response-list'></div>" in document
    assert "id='written-empty'>No written answers" in document
    assert "id='findings-empty'>No observed highlights" in document


def test_importing_ui_and_its_renderer_does_not_import_template_dependencies():
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import qualtrics.ui; from qualtrics.ui import render_report; "
            "assert callable(render_report); "
            "assert 'jinja2' not in sys.modules; assert 'markupsafe' not in sys.modules",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
