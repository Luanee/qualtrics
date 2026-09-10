"""Reconcile flat response-property columns across surveys without losing their source identity."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .entities import EntitySet
from .response_columns import RESPONSE_SYSTEM_COLUMNS, allocate_response_column, read_source_columns

PropertyIdentity = tuple[str, int]


def merge_response_columns(
    entity_sets: list[EntitySet],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    surveys = [dict(survey) for item in entity_sets for survey in item.surveys]
    source_rows = [row for item in entity_sets for row in item.responses]
    canonical = set(RESPONSE_SYSTEM_COLUMNS)
    manifests = {str(survey["survey_id"]): read_source_columns(survey) for survey in surveys}
    identities: dict[str, dict[str, PropertyIdentity]] = {}
    present_keys: set[str] = set(RESPONSE_SYSTEM_COLUMNS) if entity_sets else set()
    for survey_id, columns in manifests.items():
        mapping: dict[str, PropertyIdentity] = {}
        occurrences: Counter[str] = Counter()
        for column in columns:
            if column.get("storage_table") != "responses":
                continue
            key = str(column.get("storage_column") or "")
            if not key:
                continue
            present_keys.add(key)
            if key in canonical:
                continue
            source = str(column["source_column"]) if column.get("source_column") is not None else key
            occurrences[source] += 1
            mapping[key] = (source, occurrences[source])
        identities[survey_id] = mapping
    described_keys = set(present_keys)
    for item in entity_sets:
        schema = item._present_columns.get("responses", set())
        present_keys.update(schema)
        for survey in item.surveys:
            mapping = identities[str(survey["survey_id"])]
            for key in schema - canonical - described_keys:
                mapping.setdefault(key, (key, 1))
    for row in source_rows:
        mapping = identities.setdefault(str(row.get("survey_id", "")), {})
        present_keys.update(row)
        for key in row.keys() - canonical:
            if row[key] is None and key in described_keys and key not in mapping:
                continue
            mapping.setdefault(key, (key, 1))

    # Reserve all canonical names even if this particular collection has no values for them.
    # Sorting source identities makes allocation independent of the order of input surveys.
    used = {key.casefold() for key in canonical}
    property_ids = {identity for mapping in identities.values() for identity in mapping.values()}
    names = {
        identity: allocate_response_column(identity[0], used)
        for identity in sorted(property_ids, key=lambda identity: (identity[0].casefold(), *identity))
    }
    keys = [key for key in RESPONSE_SYSTEM_COLUMNS if key in present_keys]
    keys.extend(names.values())
    responses = []
    for row in source_rows:
        mapping = identities[str(row.get("survey_id", ""))]
        normalized = dict.fromkeys(keys)
        normalized.update({
            names[mapping[key]] if key in mapping else key: value
            for key, value in row.items()
            if key in mapping or key in canonical
        })
        responses.append(normalized)

    for survey in surveys:
        survey_id = str(survey["survey_id"])
        columns = manifests[survey_id]
        for column in columns:
            key = str(column.get("storage_column") or "")
            if column.get("storage_table") == "responses" and key in identities[survey_id]:
                column["storage_column"] = names[identities[survey_id][key]]
        if columns:
            survey["source_columns_json"] = json.dumps(columns, ensure_ascii=False)
    return surveys, responses, set(keys)
