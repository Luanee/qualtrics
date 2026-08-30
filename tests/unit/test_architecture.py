from pathlib import Path

import qualtrics_toolkit
from qualtrics_toolkit.analytics import analyze_entities


def test_public_api_is_implemented_by_domain_modules() -> None:
    assert qualtrics_toolkit.EntitySet.__module__ == "qualtrics_toolkit.models.entities"
    assert qualtrics_toolkit.parse_survey.__module__ == "qualtrics_toolkit.parsers.survey"
    assert qualtrics_toolkit.write_entities.__module__ == "qualtrics_toolkit.serialization.io"
    assert qualtrics_toolkit.render_report.__module__ == "qualtrics_toolkit.reporting.report"
    assert analyze_entities.__module__ == "qualtrics_toolkit.analytics.report"


def test_catch_all_core_module_is_removed() -> None:
    package_root = Path(qualtrics_toolkit.__file__).parent
    assert not (package_root / "_core.py").exists()
