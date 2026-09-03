import pytest

from qualtrics.models.question_types import resolve_question_type


@pytest.mark.parametrize(
    ("question_type", "selector", "canonical", "value_type"),
    [
        ("MC", "SAVR", "multiple_choice_single", "categorical"),
        ("MC", "MAVR", "multiple_choice_multiple", "categorical"),
        ("MC", "MAHR", "multiple_choice_multiple", "categorical"),
        ("MC", "NPS", "nps", "numeric"),
        ("TE", "SL", "text_entry", "text"),
        ("TE", "FORM", "form_field", "text"),
        ("TE", "Calendar", "calendar", "datetime"),
        ("DB", None, "descriptive_text", "non_response"),
        ("Matrix", "Likert", "matrix", "categorical"),
        ("Matrix", "CS", "matrix", "numeric"),
        ("SBS", None, "side_by_side", "structured"),
        ("Slider", None, "slider", "numeric"),
        ("RO", None, "rank_order", "numeric"),
        ("NPS", None, "nps", "numeric"),
        ("Timing", None, "timing", "numeric"),
        ("CS", None, "constant_sum", "numeric"),
        ("DD", None, "drill_down", "categorical"),
        ("Meta", "Browser", "metadata", "metadata"),
        ("FileUpload", None, "file_upload", "file"),
        ("HeatMap", None, "heat_map", "coordinate"),
        ("HotSpot", None, "hot_spot", "structured"),
        ("Highlight", None, "highlight", "structured"),
        ("Signature", None, "signature", "file"),
        ("Calendar", None, "calendar", "datetime"),
        ("PGR", None, "pick_group_rank", "structured"),
        ("Captcha", None, "captcha", "non_response"),
        ("GraphicSlider", None, "graphic_slider", "numeric"),
        ("NumberScale", None, "number_scale", "numeric"),
        ("Location", None, "location_selector", "coordinate"),
        ("ArcGIS", None, "arcgis_map", "coordinate"),
        ("TreeTest", None, "tree_testing", "structured"),
        ("OrgHierarchy", None, "org_hierarchy", "categorical"),
    ],
)
def test_resolves_documented_question_types(
    question_type: str, selector: str | None, canonical: str, value_type: str
) -> None:
    result = resolve_question_type(question_type, selector, None)
    assert result.canonical_question_type == canonical
    assert result.answer_value_type == value_type


def test_unknown_type_is_lossless_and_unsupported() -> None:
    result = resolve_question_type("FutureType", "NewSelector", "NewSub")
    assert result.raw == ("FutureType", "NewSelector", "NewSub")
    assert result.canonical_question_type == "unsupported"
    assert result.answer_value_type == "unsupported"


def test_unknown_multiple_choice_selector_is_not_guessed() -> None:
    result = resolve_question_type("MC", "FutureSelector")
    assert result.canonical_question_type == "unsupported"
    assert result.raw == ("MC", "FutureSelector", None)
