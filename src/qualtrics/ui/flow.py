"""Offline survey flow map and walkthrough markup."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..models import EntitySet
from .components.primitives import page_heading
from .templating import render_template, trusted_html

_TYPES = {
    "Root": "Survey start",
    "Block": "Question block",
    "Standard": "Question block",
    "Branch": "Branch",
    "Group": "Group",
    "Randomizer": "Randomizer",
    "BlockRandomizer": "Randomizer",
    "EmbeddedData": "Embedded data",
    "EndSurvey": "Survey ending",
    "WebService": "Web service",
    "Authenticator": "Authenticator",
    "Quota": "Quota",
    "ReferenceSurvey": "Referenced survey",
}
_CONFIG = {"ID", "Description", "BranchLogic", "SubSet", "EvenPresentation", "EmbeddedData", "EndingType"}


def _safe_definition(raw: Any) -> dict[str, Any]:
    """Allowlist a stored envelope again before sending it to a report browser."""
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Unsupported flow definition")
    count = 0
    seen: set[str] = set()

    def node(item: Any, depth: int = 0) -> dict[str, Any]:
        nonlocal count
        count += 1
        if count > 5000 or depth > 100 or not isinstance(item, dict):
            raise ValueError("Invalid flow tree")
        node_id = item.get("node_id")
        if not isinstance(node_id, str) or node_id in seen or not isinstance(item.get("type"), str):
            raise ValueError("Invalid flow occurrence")
        seen.add(node_id)
        children = item.get("children", [])
        config = item.get("config", {})
        if not isinstance(children, list) or not isinstance(config, dict):
            raise ValueError("Invalid flow node")
        safe = {key: value for key, value in config.items() if key in _CONFIG}
        if "EmbeddedData" in safe:
            entries = safe["EmbeddedData"]
            safe["EmbeddedData"] = (
                [
                    {key: value for key, value in entry.items() if key in {"Field", "Value", "Type", "Description"}}
                    for entry in entries
                    if isinstance(entry, dict)
                ]
                if isinstance(entries, list)
                else []
            )
        return {
            "node_id": node_id,
            "type": item["type"],
            "external_id": str(item.get("external_id") or ""),
            "config": safe,
            "children": [node(child, depth + 1) for child in children],
        }

    blocks = raw.get("blocks", {})
    questions = raw.get("questions", {})
    if not isinstance(blocks, dict) or not isinstance(questions, dict):
        raise ValueError("Invalid flow references")
    return {
        "schema_version": 1,
        "source_format": str(raw.get("source_format") or ""),
        "root": node(raw.get("root")),
        "blocks": {
            key: {
                "name": str(value.get("name") or key),
                "type": str(value.get("type") or ""),
                "elements": [
                    {k: v for k, v in element.items() if k in {"type", "question_external_id", "order"}}
                    for element in value.get("elements", [])
                    if isinstance(element, dict)
                ],
                "options": {
                    k: v
                    for k, v in value.get("options", {}).items()
                    if k in {"Looping", "RandomizeQuestions", "skip_logic"}
                },
            }
            for key, value in blocks.items()
            if isinstance(value, dict)
        },
        "questions": {
            key: {
                k: v
                for k, v in value.items()
                if k in {"text", "type", "selector", "choices", "choice_order", "display_logic", "skip_logic"}
            }
            for key, value in questions.items()
            if isinstance(value, dict)
        },
    }


def _condition_text(logic: Any, questions: dict[str, Any], depth: int = 0) -> str:
    if not isinstance(logic, dict) or depth > 30:
        return "Condition needs an explicit assumption in the walkthrough."
    if logic.get("LogicType") == "Question":
        qid = str(logic.get("QuestionID") or "Question")
        question = questions.get(qid, {})
        label = str(question.get("text") or qid)
        locator = re.fullmatch(r"q://[^/]+/SelectableChoice/([^/]+)", str(logic.get("ChoiceLocator") or ""))
        operator = logic.get("Operator")
        if locator and operator in {"Selected", "NotSelected"}:
            choice = question.get("choices", {}).get(locator[1], locator[1])
            return f"{label}: {choice} is {'not selected' if operator == 'NotSelected' else 'selected'}"
    if logic.get("LogicType") == "EmbeddedField":
        field = logic.get("LeftOperand") or logic.get("Field") or "Embedded field"
        operators = {
            "EqualTo": "equals",
            "NotEqualTo": "does not equal",
            "GreaterThan": "is greater than",
            "LessThan": "is less than",
            "GreaterThanOrEqual": "is at least",
            "LessThanOrEqual": "is at most",
        }
        operator = operators.get(str(logic.get("Operator")))
        if operator:
            return f"{field} {operator} {logic.get('RightOperand', '')}"
    terms = [logic[key] for key in sorted((key for key in logic if str(key).isdigit()), key=int)]
    if terms:
        parts = [_condition_text(term, questions, depth + 1) for term in terms]
        if len(parts) == 1:
            return parts[0]
        description = parts[0]
        for term, part in zip(terms[1:], parts[1:], strict=True):
            connector = term.get("Conjuction") or term.get("Conjunction") if isinstance(term, dict) else None
            conjunction = str(connector or logic.get("Conjunction") or logic.get("Operator") or "").lower()
            if conjunction not in {"and", "or"}:
                return "Conditions: " + "; ".join(parts) + ". Combination requires verification."
            description = f"({description}) {conjunction} ({part})"
        return description
    return "Condition needs an explicit assumption in the walkthrough."


@dataclass(frozen=True)
class FlowQuestionView:
    question_id: str
    text: str
    target: str | None
    flags: str


@dataclass(frozen=True)
class FlowNodeView:
    node_id: str
    anchor: str
    type_label: str
    title: str
    identifiers: str
    settings: list[str]
    questions: list[FlowQuestionView]
    children: list[FlowNodeView]


@dataclass(frozen=True)
class FlowSurveyView:
    survey_id: str
    label: str
    root: FlowNodeView | None
    message: str


def _node_view(
    item: dict[str, Any],
    definition: dict[str, Any],
    index: int,
    anchors: dict[str, str],
    targets: dict[str, str],
) -> FlowNodeView:
    nid = item["node_id"]
    anchor = f"flow-{index}-node-{len(anchors) + 1}"
    anchors[nid] = anchor
    kind = item["type"]
    config = item["config"]
    block = definition["blocks"].get(str(config.get("ID")), {})
    title = str(block.get("name") or config.get("Description") or _TYPES.get(kind, kind))
    settings = []
    if kind == "Branch":
        settings.append(
            "Continue into this branch when " + _condition_text(config.get("BranchLogic"), definition["questions"])
        )
    elif kind in {"Randomizer", "BlockRandomizer"}:
        count = config.get("SubSet", "the configured number of")
        noun = "step" if str(count) == "1" else "steps"
        settings.append(f"Select {count} eligible {noun} in an explicit scenario order.")
        if str(config.get("EvenPresentation", "")).lower() in {"true", "1"}:
            settings.append("Even presentation is configured; this offline scenario does not use allocation history.")
    elif kind == "EmbeddedData":
        for entry in config.get("EmbeddedData", []):
            field = entry.get("Field") or entry.get("Description") or "Unnamed field"
            settings.append(f"{field} = {entry['Value']}" if "Value" in entry else f"{field}: supplied at runtime")
    elif kind == "EndSurvey":
        settings.append("End the whole survey route here.")
        if config.get("EndingType"):
            settings.append(f"Ending: {config['EndingType']}")
    elif kind not in {"Root", "Block", "Standard", "Group"}:
        settings.append("This step needs an explicit assumption to proceed in the walkthrough.")
    for option, value in block.get("options", {}).items():
        if value and str(value).lower() not in {"false", "none", "0"}:
            settings.append(
                f"{'Question skip logic' if option == 'skip_logic' else option} is configured; "
                "the walkthrough may need an assumption."
            )
    questions = []
    for element in block.get("elements", []):
        if element.get("type") != "question":
            continue
        qid = str(element.get("question_external_id") or "")
        question = definition["questions"].get(qid, {})
        flags = "; ".join(
            name
            for key, name in (("display_logic", "Display logic"), ("skip_logic", "Skip logic"))
            if question.get(key)
        )
        questions.append(
            FlowQuestionView(
                qid,
                str(question.get("text") or qid or "Question"),
                targets.get(qid),
                flags,
            )
        )
    identifiers = " · ".join(
        str(value) for value in (item.get("external_id"), config.get("ID"), f"Step {nid}") if value
    )
    return FlowNodeView(
        node_id=nid,
        anchor=anchor,
        type_label=_TYPES.get(kind, kind),
        title=title,
        identifiers=identifiers,
        settings=settings,
        questions=questions,
        children=[_node_view(child, definition, index, anchors, targets) for child in item["children"]],
    )


def render_flow(entities: EntitySet, question_targets: dict[tuple[str, str], str]) -> str:
    surveys: list[dict[str, Any]] = []
    maps = []
    for index, survey in enumerate(entities.surveys, 1):
        sid = str(survey["survey_id"])
        label = str(survey.get("survey_name") or sid)
        encoded = survey.get("flow_definition_json")
        definition = None
        message = "No flow definition is available. Re-parse with a survey definition that includes its flow."
        if encoded:
            try:
                definition = _safe_definition(json.loads(str(encoded)))
            except (ValueError, TypeError, RecursionError, AttributeError):
                message = "This flow definition could not be read. Re-parse it from the source definition."
        targets = {qid: target for (survey_id, qid), target in question_targets.items() if survey_id == sid}
        anchors: dict[str, str] = {}
        root = None
        if definition:
            root = _node_view(definition["root"], definition, index, anchors, targets)
            message = "" if root.children else "This flow definition contains no steps."
            surveys.append({"id": sid, "label": label, "definition": definition, "targets": targets, "nodes": anchors})
        maps.append(FlowSurveyView(sid, label, root, message))
    payload = json.dumps({"surveys": surveys}, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return render_template(
        "flow/page.html.jinja",
        maps=maps,
        payload=trusted_html(payload),
        heading=trusted_html(page_heading("Survey flow", heading_id="flow-heading")),
    )
