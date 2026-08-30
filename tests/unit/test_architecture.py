from pathlib import Path

import qualtrics
from qualtrics.analytics import analyze_entities


def test_public_api_is_implemented_by_domain_modules() -> None:
    assert qualtrics.EntitySet.__module__ == "qualtrics.models.entities"
    assert qualtrics.parse_survey.__module__ == "qualtrics.parsers.survey"
    assert qualtrics.write_entities.__module__ == "qualtrics.serialization.io"
    assert qualtrics.render_report.__module__ == "qualtrics.reporting.report"
    assert analyze_entities.__module__ == "qualtrics.analytics.report"


def test_catch_all_core_module_is_removed() -> None:
    package_root = Path(qualtrics.__file__).parent
    assert not (package_root / "_core.py").exists()
