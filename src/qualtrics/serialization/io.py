from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models.entities import ENTITY_NAMES, EntitySet

CSV_FIELD_TYPES: dict[str, dict[str, type[object]]] = {
    "sections": {"section_order": int},
    "questions": {
        "block_order": int,
        "question_order_in_block": int,
    },
    "question_fields": {
        "source_column_index": int,
        "is_text_field": bool,
    },
    "response_answers": {
        "answer_numeric": float,
        "answer_boolean": bool,
        "is_selected": bool,
    },
}

ENTITY_COLUMNS: dict[str, tuple[str, ...]] = {
    "surveys": ("survey_id", "survey_name", "survey_status", "default_language"),
    "sections": ("section_id", "section_external_id", "survey_id", "section_name", "section_order"),
    "question_catalog": (
        "question_catalog_id",
        "question_text",
        "normalized_question_content",
        "canonical_question_type",
    ),
    "question_field_catalog": (
        "question_field_catalog_id",
        "question_catalog_id",
        "field_text",
        "normalized_field_content",
    ),
    "questions": (
        "question_id",
        "question_external_id",
        "survey_id",
        "section_id",
        "section_external_id",
        "question_catalog_id",
        "question_text",
        "question_description",
        "question_type",
        "selector",
        "sub_selector",
        "question_role",
        "canonical_question_type",
        "answer_value_type",
        "block_order",
        "question_order_in_block",
    ),
    "answer_options": (
        "answer_option_id",
        "answer_option_catalog_id",
        "answer_id",
        "answer_external_id",
        "answer_text",
        "answer_recode",
        "answer_export_tag",
        "question_id",
        "question_external_id",
        "survey_id",
    ),
    "question_fields": (
        "question_field_id",
        "field_id",
        "field_external_id",
        "question_id",
        "question_external_id",
        "survey_id",
        "question_catalog_id",
        "question_field_catalog_id",
        "field_text",
        "field_role",
        "answer_value_type",
        "is_text_field",
        "import_external_id",
        "source_field_suffix",
        "source_column_index",
    ),
    "responses": (
        "response_id",
        "response_external_id",
        "survey_id",
        "started_at",
        "ended_at",
        "recorded_at",
        "is_finished",
        "user_language",
        "status",
        "ip_address",
        "progress",
        "duration_seconds",
        "recipient_last_name",
        "recipient_first_name",
        "recipient_email",
        "external_reference",
        "distribution_channel",
        "browser",
        "browser_version",
        "operating_system",
        "screen_resolution",
        "user_agent",
    ),
    "response_answers": (
        "response_answer_id",
        "response_id",
        "response_external_id",
        "survey_id",
        "question_id",
        "question_external_id",
        "question_field_id",
        "field_id",
        "field_external_id",
        "question_catalog_id",
        "question_field_catalog_id",
        "answer_option_id",
        "answer_option_catalog_id",
        "answer_value_type",
        "answer_text",
        "answer_numeric",
        "answer_boolean",
        "is_selected",
        "user_language",
    ),
}


def _coerce_csv_records(name: str, records: list[dict[str, str]]) -> list[dict[str, object]]:
    field_types = CSV_FIELD_TYPES.get(name, {})
    coerced_records: list[dict[str, object]] = []
    for raw_record in records:
        record: dict[str, object] = dict(raw_record)
        for key, target_type in field_types.items():
            value = raw_record.get(key)
            if value in {None, ""}:
                record[key] = None
                continue
            record[key] = value.casefold() == "true" if target_type is bool else target_type(value)
        for key, value in tuple(record.items()):
            if value == "":
                record[key] = None
        coerced_records.append(record)
    return coerced_records


def _normalize_parquet_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = {key for record in records for key in record}
    conversions: dict[str, object] = {}
    for key in keys:
        values = [record[key] for record in records if record.get(key) is not None]
        types = {type(value) for value in values}
        if len(types) <= 1:
            continue
        if (
            types <= {bool, str}
            and bool in types
            and all(not isinstance(value, str) or value.casefold() in {"true", "false"} for value in values)
        ):
            conversions[key] = bool
        else:
            conversions[key] = str
    if not conversions:
        return records
    return [
        {
            key: (
                value.casefold() == "true"
                if conversions.get(key) is bool and isinstance(value, str)
                else str(value)
                if conversions.get(key) is str and value is not None
                else value
            )
            for key, value in record.items()
        }
        for record in records
    ]


def write_entities(entities: EntitySet, folder: str | Path, format: str = "json") -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name in ENTITY_NAMES:
        records = getattr(entities, name)
        path = folder / f"{name}.{format}"
        if format == "json":
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        elif format == "csv":
            keys = list(ENTITY_COLUMNS[name])
            keys.extend(key for row in records for key in row if key not in keys)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys)
                writer.writeheader()
                writer.writerows(records)
        elif format == "parquet":
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise RuntimeError("Install qualtrics[parquet]") from exc
            keys = list(ENTITY_COLUMNS[name])
            keys.extend(key for row in records for key in row if key not in keys)
            normalized_records = _normalize_parquet_records(records)
            fields = []
            for key in keys:
                target = CSV_FIELD_TYPES.get(name, {}).get(key)
                data_type = (
                    pa.bool_()
                    if target is bool
                    else pa.int64()
                    if target is int
                    else pa.float64()
                    if target is float
                    else pa.string()
                )
                fields.append(pa.field(key, data_type, nullable=True))
            normalized = []
            for record in normalized_records:
                normalized.append({
                    key: str(record.get(key))
                    if record.get(key) is not None and pa.types.is_string(fields[index].type)
                    else record.get(key)
                    for index, key in enumerate(keys)
                })
            pq.write_table(pa.Table.from_pylist(normalized, schema=pa.schema(fields)), path)
        else:
            raise ValueError(f"Unsupported format: {format}")


def load_entities(folder: str | Path | None = None, **paths: str | Path) -> EntitySet:
    from ..models.entity_set import validate_entity_set

    folder = Path(folder) if folder else None
    result = EntitySet()
    for name in ENTITY_NAMES:
        candidates = [
            folder / f"{name}.{ext}"
            for ext in ("json", "csv", "parquet")
            if folder and (folder / f"{name}.{ext}").exists()
        ]
        if len(candidates) > 1:
            raise ValueError(f"Multiple formats found for {name}: {', '.join(path.name for path in candidates)}")
        path = Path(paths[name]) if name in paths else candidates[0] if candidates else None
        if not path:
            continue
        if path.suffix == ".json":
            records = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                records = _coerce_csv_records(name, list(csv.DictReader(handle)))
        else:
            try:
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise RuntimeError("Install qualtrics[parquet]") from exc
            records = pq.read_table(path).to_pylist()
        setattr(result, name, records)
        result._present_entities.add(name)
    validate_entity_set(result, strict=folder is not None)
    return result
