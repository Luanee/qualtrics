"""Versioned, folder-level metadata for one or more exported surveys."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "manifest.json"
MANIFEST_VERSION = 1


def validate_manifests(survey_ids: set[str], manifests: dict[str, dict[str, Any]]) -> None:
    extra = manifests.keys() - survey_ids
    if extra:
        raise ValueError(f"Manifest has unknown survey IDs: {', '.join(sorted(extra))}")
    for survey_id, entry in manifests.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Manifest entry for {survey_id} must be an object")
        if not isinstance(entry.get("source_columns_json"), list):
            raise ValueError(f"Manifest source_columns_json for {survey_id} must be a list")
        if any(not isinstance(column, dict) for column in entry["source_columns_json"]):
            raise ValueError(f"Manifest source_columns_json for {survey_id} must contain objects")
        flow = entry.get("flow_definition_json")
        if flow is not None and not isinstance(flow, dict):
            raise ValueError(f"Manifest flow_definition_json for {survey_id} must be an object or null")
        languages = entry.get("languages")
        if languages is None:
            continue
        if not isinstance(languages, dict):
            raise ValueError(f"Manifest languages for {survey_id} must be an object")
        base = languages.get("base_language")
        if base is not None and (not isinstance(base, str) or not base.strip()):
            raise ValueError(f"Manifest languages base_language for {survey_id} must be a code or null")
        for key in ("available_languages", "all_languages", "prepared_languages"):
            codes = languages.get(key)
            if key == "prepared_languages" and codes is None:
                continue
            if not isinstance(codes, list) or any(not isinstance(code, str) or not code.strip() for code in codes):
                raise ValueError(f"Manifest languages {key} for {survey_id} must be a list of codes")
            if len(set(codes)) != len(codes):
                raise ValueError(f"Manifest languages {key} for {survey_id} contains duplicate codes")
        all_codes = set(languages["all_languages"])
        if (base is not None and base not in all_codes) or not set(languages["available_languages"]) <= all_codes:
            raise ValueError(f"Manifest languages for {survey_id} has codes missing from all_languages")


def write_manifest(folder: Path, surveys: list[dict[str, Any]], manifests: dict[str, dict[str, Any]]) -> None:
    survey_ids = {str(row["survey_id"]) for row in surveys}
    completed = {
        survey_id: manifests.get(survey_id, {"flow_definition_json": None, "source_columns_json": []})
        for survey_id in sorted(survey_ids)
    }
    validate_manifests(survey_ids, manifests)
    payload = {"schema_version": MANIFEST_VERSION, "surveys": completed}
    (folder / MANIFEST_FILENAME).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(path: Path, surveys: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid survey manifest: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != MANIFEST_VERSION:
        raise ValueError(f"Unsupported survey manifest version in {path}")
    manifests = payload.get("surveys")
    if not isinstance(manifests, dict):
        raise ValueError(f"Manifest surveys must be an object in {path}")
    survey_ids = {str(row["survey_id"]) for row in surveys}
    if set(manifests) != survey_ids:
        raise ValueError(f"Manifest survey IDs do not match surveys table in {path}")
    validate_manifests(survey_ids, manifests)
    return manifests
