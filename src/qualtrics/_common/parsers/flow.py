from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .identity import _clean

_NODE_CONFIG_KEYS = (
    "ID",
    "Description",
    "BranchLogic",
    "SubSet",
    "EvenPresentation",
    "EmbeddedData",
    "EndingType",
)
_EMBEDDED_DATA_KEYS = ("Field", "Value", "Type", "Description")
_BLOCK_OPTION_KEYS = ("Looping", "RandomizeQuestions")


def _unwrap(data: Mapping[str, Any]) -> Mapping[str, Any]:
    current = data
    for _ in range(4):
        wrapped = next(
            (
                current.get(key)
                for key in ("result", "SurveyDefinition", "survey_definition", "payload")
                if isinstance(current.get(key), Mapping)
            ),
            None,
        )
        if wrapped is None:
            return current
        current = wrapped
    return current


def _source_format(data: Mapping[str, Any], source: Mapping[str, Any]) -> str:
    current = data
    for _ in range(4):
        if any(key in current for key in ("SurveyDefinition", "survey_definition", "payload")):
            return "survey_definition"
        wrapped_result = current.get("result")
        if not isinstance(wrapped_result, Mapping):
            break
        current = wrapped_result
    if isinstance(source.get("SurveyElements"), list):
        return "qsf"
    if "Blocks" in source or "Questions" in source:
        return "survey_definition"
    return "flow"


def _items(value: object) -> Iterable[tuple[str | None, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(item, Mapping):
                yield str(key), item
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                yield None, item


def _qsf_parts(data: Mapping[str, Any]) -> tuple[object | None, object, object, str | None]:
    flow: object | None = None
    blocks: object = {}
    questions: dict[str, Any] = {}
    flow_external_id: str | None = None
    elements = data.get("SurveyElements")
    if not isinstance(elements, list):
        return flow, blocks, questions, flow_external_id
    for element in elements:
        if not isinstance(element, Mapping):
            continue
        kind = element.get("Element")
        payload = element.get("Payload")
        if kind == "FL" and isinstance(payload, (Mapping, list)):
            flow = payload
            primary = element.get("PrimaryAttribute")
            flow_external_id = str(primary) if primary is not None else None
        elif kind == "BL" and isinstance(payload, (Mapping, list)):
            blocks = payload
        elif kind == "SQ" and isinstance(payload, Mapping):
            question_id = payload.get("QuestionID") or element.get("PrimaryAttribute")
            if question_id is not None:
                questions[str(question_id)] = payload
    return flow, blocks, questions, flow_external_id


def _safe_embedded_data(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {key: item[key] for key in _EMBEDDED_DATA_KEYS if key in item} for item in value if isinstance(item, Mapping)
    ]


def _node(raw: Mapping[str, Any], path: str) -> dict[str, Any]:
    raw_children = raw.get("Flow", raw.get("Children", []))
    if raw_children is None:
        raw_children = []
    if not isinstance(raw_children, list):
        raise ValueError(f"Invalid survey flow children at {path}: expected a list")
    children = []
    for index, child in enumerate(raw_children):
        if not isinstance(child, Mapping):
            raise ValueError(f"Invalid survey flow node at {path}.{index}: expected an object")
        children.append(_node(child, f"{path}.{index}"))
    config: dict[str, Any] = {}
    for key in _NODE_CONFIG_KEYS:
        if key not in raw:
            continue
        config[key] = _safe_embedded_data(raw[key]) if key == "EmbeddedData" else raw[key]
    external_id = raw.get("FlowID")
    if external_id is None and str(raw.get("Type") or "").casefold() == "root":
        external_id = raw.get("ID")
    return {
        "node_id": path,
        "external_id": str(external_id) if external_id is not None else None,
        "type": str(raw.get("Type") or "Unknown"),
        "config": config,
        "children": children,
    }


def _blocks(value: object) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for fallback_id, block in _items(value):
        block_id = block.get("ID") or fallback_id
        if block_id is None:
            continue
        elements = []
        has_skip_logic = False
        raw_elements = block.get("BlockElements", [])
        if isinstance(raw_elements, list):
            for order, element in enumerate(raw_elements, start=1):
                if not isinstance(element, Mapping):
                    continue
                has_skip_logic = has_skip_logic or bool(element.get("SkipLogic"))
                question_id = element.get("QuestionID")
                if question_id is not None and str(element.get("Type") or "Question").casefold() == "question":
                    elements.append({
                        "type": "question",
                        "question_external_id": str(question_id),
                        "order": order,
                    })
        raw_options = block.get("Options")
        options_source = raw_options if isinstance(raw_options, Mapping) else block
        options = {key: options_source[key] for key in _BLOCK_OPTION_KEYS if key in options_source}
        if has_skip_logic:
            options["skip_logic"] = True
        result[str(block_id)] = {
            "name": _clean(block.get("Description")),
            "type": str(block.get("Type") or "Unknown"),
            "elements": elements,
            "options": options,
        }
    return result


def _choice_label(value: object) -> str:
    if isinstance(value, Mapping):
        return _clean(value.get("Display"))
    return _clean(value)


def _questions(value: object) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for fallback_id, question in _items(value):
        question_id = question.get("QuestionID") or fallback_id
        if question_id is None:
            continue
        raw_choices = question.get("Choices")
        choices = (
            {str(choice_id): _choice_label(choice) for choice_id, choice in raw_choices.items()}
            if isinstance(raw_choices, Mapping)
            else {}
        )
        raw_order = question.get("ChoiceOrder")
        choice_order = [str(item) for item in raw_order] if isinstance(raw_order, list) else list(choices)
        result[str(question_id)] = {
            "text": _clean(question.get("QuestionText")),
            "type": str(question.get("QuestionType") or "Unknown"),
            "selector": str(question.get("Selector") or ""),
            "choices": choices,
            "choice_order": choice_order,
            "display_logic": bool(question.get("DisplayLogic")),
            "skip_logic": bool(question.get("SkipLogic")),
        }
    return result


def extract_flow_definition(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the bounded report-safe survey flow envelope from a Qualtrics definition."""
    if not isinstance(data, dict):
        raise ValueError("Invalid survey flow definition: expected an object")
    source = _unwrap(data)
    source_format = _source_format(data, source)
    qsf_flow, qsf_blocks, qsf_questions, qsf_external_id = _qsf_parts(source)
    blocks = source.get("Blocks", qsf_blocks)
    questions = source.get("Questions", qsf_questions)

    if "Type" in source and ("Flow" in source or "Children" in source):
        raw_flow = source
    elif "Flow" in source:
        raw_flow = source["Flow"]
    elif "SurveyFlow" in source:
        raw_flow = source["SurveyFlow"]
    elif qsf_flow is not None:
        raw_flow = qsf_flow
    else:
        return None

    if isinstance(raw_flow, list):
        raw_root: Mapping[str, Any] = {"Type": "Root", "Flow": raw_flow}
    elif isinstance(raw_flow, Mapping):
        raw_root = raw_flow
    else:
        raise ValueError("Invalid survey flow: expected a root object or flow list")
    root = _node(raw_root, "0")
    raw_root_type = str(raw_root.get("Type") or "").casefold()
    if raw_root_type in {"", "standard"} and isinstance(raw_root.get("Flow"), list):
        root = {
            "node_id": "0",
            "external_id": (str(raw_root["FlowID"]) if raw_root.get("FlowID") is not None else qsf_external_id),
            "type": "Root",
            "config": {},
            "children": [
                _node(child, f"0.{index}") for index, child in enumerate(raw_root["Flow"]) if isinstance(child, Mapping)
            ],
        }
    elif root["type"].casefold() != "root":
        root = {
            "node_id": "0",
            "external_id": qsf_external_id,
            "type": "Root",
            "config": {},
            "children": [_node(raw_root, "0.0")],
        }
    elif root["external_id"] is None and qsf_external_id is not None:
        root["external_id"] = qsf_external_id
    return {
        "schema_version": 1,
        "source_format": source_format,
        "root": root,
        "blocks": _blocks(blocks),
        "questions": _questions(questions),
    }
