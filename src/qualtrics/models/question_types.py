from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionTypeDefinition:
    canonical_question_type: str
    answer_value_type: str
    raw: tuple[object, object, object]


_TYPES: dict[str, tuple[str, str]] = {
    "te": ("text_entry", "text"),
    "db": ("descriptive_text", "non_response"),
    "textgraphic": ("descriptive_text", "non_response"),
    "matrix": ("matrix", "categorical"),
    "form": ("form_field", "text"),
    "formfield": ("form_field", "text"),
    "calendar": ("calendar", "datetime"),
    "slider": ("slider", "numeric"),
    "ro": ("rank_order", "numeric"),
    "sbs": ("side_by_side", "structured"),
    "nps": ("nps", "numeric"),
    "timing": ("timing", "numeric"),
    "graphicslider": ("graphic_slider", "numeric"),
    "cs": ("constant_sum", "numeric"),
    "constantsum": ("constant_sum", "numeric"),
    "fileupload": ("file_upload", "file"),
    "pgr": ("pick_group_rank", "structured"),
    "dd": ("drill_down", "categorical"),
    "drilldown": ("drill_down", "categorical"),
    "signature": ("signature", "file"),
    "heatmap": ("heat_map", "coordinate"),
    "hotspot": ("hot_spot", "structured"),
    "meta": ("metadata", "metadata"),
    "metadata": ("metadata", "metadata"),
    "captcha": ("captcha", "non_response"),
    "highlight": ("highlight", "structured"),
    "screencapture": ("screen_capture", "file"),
    "videoresponse": ("video_response", "file"),
    "unmoderatedusertesting": ("unmoderated_user_testing", "structured"),
    "location": ("location_selector", "coordinate"),
    "locationselector": ("location_selector", "coordinate"),
    "arcgis": ("arcgis_map", "coordinate"),
    "arcgismap": ("arcgis_map", "coordinate"),
    "solicitreviews": ("solicit_reviews", "structured"),
    "treetest": ("tree_testing", "structured"),
    "treetesting": ("tree_testing", "structured"),
    "numberscale": ("number_scale", "numeric"),
    "orghierarchy": ("org_hierarchy", "categorical"),
}


def _normalized(value: object) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def resolve_question_type(
    question_type: object, selector: object = None, sub_selector: object = None
) -> QuestionTypeDefinition:
    normalized_type = _normalized(question_type)
    normalized_selector = _normalized(selector)
    if normalized_type == "mc":
        if normalized_selector == "nps":
            resolved = ("nps", "numeric")
        elif normalized_selector in {"mavr", "macol", "mabox"}:
            resolved = ("multiple_choice_multiple", "categorical")
        else:
            resolved = ("multiple_choice_single", "categorical")
    elif normalized_type == "te" and normalized_selector == "form":
        resolved = ("form_field", "text")
    elif normalized_type == "te" and normalized_selector == "calendar":
        resolved = ("calendar", "datetime")
    elif normalized_type == "matrix" and normalized_selector in {"cs", "constantsum", "te"}:
        resolved = ("matrix", "numeric" if normalized_selector != "te" else "text")
    else:
        resolved = _TYPES.get(normalized_type, ("unsupported", "unsupported"))
    return QuestionTypeDefinition(*resolved, raw=(question_type, selector, sub_selector))
