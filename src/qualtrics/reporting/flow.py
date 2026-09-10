"""Offline survey flow map and walkthrough markup."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from ..models import EntitySet
from .components.primitives import page_heading

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


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


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


def _render_node(
    item: dict[str, Any],
    definition: dict[str, Any],
    index: int,
    anchors: dict[str, str],
    targets: dict[str, str],
) -> str:
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
        text = _escape(question.get("text") or qid or "Question")
        target = targets.get(qid)
        question_label = f"<a href='#{_escape(target)}'>{text}</a>" if target else text
        flags = "; ".join(
            name
            for key, name in (("display_logic", "Display logic"), ("skip_logic", "Skip logic"))
            if question.get(key)
        )
        questions.append(f"<li>{question_label}<small>{_escape(qid)}{' · ' + flags if flags else ''}</small></li>")
    question_html = (
        (
            f"<details class='flow-questions'><summary>{len(questions)} "
            f"{'question' if len(questions) == 1 else 'questions'} in this block</summary>"
            f"<ol>{''.join(questions)}</ol></details>"
        )
        if questions
        else ""
    )
    children = "".join(
        f"<li>{_render_node(child, definition, index, anchors, targets)}</li>" for child in item["children"]
    )
    children_html = f"<ol class='flow-children'>{children}</ol>" if children else ""
    identifiers = " · ".join(
        str(value) for value in (item.get("external_id"), config.get("ID"), f"Step {nid}") if value
    )
    return (
        f"<details id='{anchor}' class='flow-node' data-flow-node='{_escape(nid)}' open>"
        f"<summary><span class='flow-node-type'>{_escape(_TYPES.get(kind, kind))}</span>"
        f"<span class='flow-node-title'>{_escape(title)}</span><span class='flow-state'>Configured</span></summary>"
        f"<div class='flow-node-body'><p class='flow-node-ids'>{_escape(identifiers)}</p>"
        + "".join(f"<p class='flow-setting'>{_escape(setting)}</p>" for setting in settings)
        + question_html
        + children_html
        + "</div></details>"
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
        nodes = []
        if definition:
            nodes.append(_render_node(definition["root"], definition, index, anchors, targets))
            if not definition["root"]["children"]:
                nodes.append("<p class='flow-empty'>This flow definition contains no steps.</p>")
            surveys.append({"id": sid, "label": label, "definition": definition, "targets": targets, "nodes": anchors})
        else:
            nodes.append(f"<p class='flow-empty'>{message}</p>")
        maps.append(
            f"<section class='flow-survey' data-survey='{_escape(sid)}' aria-label='{_escape(label)} flow'>"
            f"<h3>{_escape(label)}</h3>{''.join(nodes)}</section>"
        )
    if not maps:
        maps.append("<p class='flow-empty'>No surveys are available.</p>")
    payload = json.dumps({"surveys": surveys}, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return (
        "<section id='survey-flow' class='report-section report-view' aria-labelledby='flow-heading'>"
        + page_heading("Survey flow", heading_id="flow-heading")
        + "<p class='flow-intro'>Explore the configured route, then try hypothetical answers. "
        "This scenario uses the supplied definition; it does not show observed respondent routing "
        "or reproduce a Qualtrics preview.</p>"
        "<div class='flow-layout'><div class='flow-map'><div class='flow-map-head'><h3>Configured route</h3>"
        "<div class='flow-map-controls' hidden><button id='flow-outline-toggle' type='button' "
        "aria-expanded='false' aria-controls='flow-outline' hidden>Show outline</button></div></div>"
        "<div id='flow-canvas-shell' class='flow-canvas-shell' hidden>"
        "<div class='flow-canvas-toolbar'><h4 id='flow-canvas-title'>Configured route</h4>"
        "<div class='flow-zoom-controls'><button id='flow-zoom-out' type='button' aria-label='Zoom out'>−</button>"
        "<output id='flow-zoom-value' aria-label='Canvas zoom'>100%</output>"
        "<button id='flow-zoom-in' type='button' aria-label='Zoom in'>+</button>"
        "<button id='flow-fit' type='button'>Fit</button>"
        "<button id='flow-move-toggle' class='flow-move-toggle' type='button' aria-pressed='false'>Move map</button>"
        "<button id='flow-center' type='button'>Selected step</button></div></div>"
        "<p id='flow-canvas-help' class='flow-canvas-help'>Drag or scroll to pan · Ctrl/⌘ + scroll to zoom. "
        "Tab to a card to inspect it. Focus the canvas for arrow keys, +/− zoom, or Home to fit. "
        "On touch screens, swipe to scroll the page; choose Move map to pan, then Done moving to scroll again.</p>"
        "<div id='flow-canvas' class='flow-canvas' tabindex='0' role='region' "
        "aria-label='Survey route canvas' aria-describedby='flow-canvas-help'>"
        "<div id='flow-canvas-layer' class='flow-canvas-layer'></div></div>"
        "<p id='flow-canvas-empty' class='flow-empty' hidden>"
        "No flow definition is available for the selected scope.</p>"
        "</div>"
        "<div id='flow-outline' class='flow-outline'><div class='flow-outline-head'><h4>Accessible route outline</h4>"
        "<div class='flow-map-controls' hidden><button id='flow-expand' type='button'>Expand outline</button>"
        "<button id='flow-collapse' type='button'>Collapse outline</button></div></div>"
        "<p class='flow-legend'><span>Reached</span><span>Skipped</span>"
        "<span>Pending</span><span>Not reached</span></p>"
        "<p id='flow-scope-empty' class='flow-empty' hidden>Select a survey to see its flow.</p>"
        + "".join(maps)
        + "</div></div><aside class='flow-walkthrough' aria-labelledby='flow-walkthrough-heading'>"
        "<h3 id='flow-walkthrough-heading'>Explore this route</h3>"
        "<noscript>Enable JavaScript to use the walkthrough. The configured map remains readable.</noscript>"
        "<div id='flow-interactive' hidden><label for='flow-survey-select'>Map and walkthrough survey</label>"
        "<select id='flow-survey-select'></select>"
        "<div id='flow-panel-controls' class='flow-panel-controls' hidden aria-label='Flow panels'>"
        "<button id='flow-panel-details' type='button' aria-pressed='false' "
        "aria-controls='flow-selection'>Step details</button>"
        "<button id='flow-panel-scenario' type='button' aria-pressed='true' "
        "aria-controls='flow-scenario-panel'>What if</button>"
        "</div><section id='flow-selection' class='flow-selection' aria-label='Selected step details' hidden></section>"
        "<div id='flow-scenario-panel'><h4>Try a scenario</h4>"
        "<p class='flow-walkthrough-intro'>Your hypothetical answers stay in this page. "
        "Choose one survey and follow its route step by step.</p>"
        "<p id='flow-walkthrough-status' role='status' aria-live='polite'></p>"
        "<div id='flow-current'></div><p id='flow-error' role='alert' hidden></p>"
        "<div class='flow-actions'><button id='flow-back' type='button'>Back</button>"
        "<button id='flow-continue' type='button' class='flow-primary'>Start walkthrough</button>"
        "<button id='flow-reset' type='button'>Reset</button></div>"
        "<details id='flow-assumptions' class='flow-assumptions' hidden open><summary>Scenario assumptions</summary>"
        "<ol id='flow-assumption-list'></ol></details></div></div></aside></div></section>"
        f"<script id='flow-data' type='application/json'>{payload}</script>"
    )
