from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models.semantic import SEMANTIC_TABLE_NAMES, SemanticModel

SEMANTIC_COLUMNS = {
    "fact_responses": (
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
    "fact_response_answers": (
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
    "dim_surveys": ("survey_id", "survey_name", "survey_status", "default_language"),
    "dim_question_fields": (
        "question_field_id",
        "field_id",
        "field_external_id",
        "question_field_catalog_id",
        "question_id",
        "question_external_id",
        "question_catalog_id",
        "survey_id",
        "section_id",
        "section_external_id",
        "section_name",
        "section_order",
        "question_text",
        "question_description",
        "question_type",
        "selector",
        "sub_selector",
        "canonical_question_type",
        "question_role",
        "field_text",
        "field_role",
        "answer_value_type",
        "is_text_field",
        "import_external_id",
        "source_field_suffix",
        "source_column_index",
        "normalized_question_content",
        "normalized_field_content",
    ),
    "dim_answer_options": (
        "answer_option_id",
        "answer_option_catalog_id",
        "answer_external_id",
        "answer_id",
        "answer_text",
        "question_id",
        "question_external_id",
        "survey_id",
    ),
}

_FLOAT_COLUMNS = {"answer_numeric"}
_BOOL_COLUMNS = {"answer_boolean", "is_selected", "is_text_field"}
_INT_COLUMNS = {"source_column_index", "section_order"}


def write_semantic_model(model: SemanticModel, folder: str | Path, format: str = "parquet") -> None:
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    for name in SEMANTIC_TABLE_NAMES:
        rows = getattr(model, name)
        path = destination / f"{name}.{format}"
        if format == "json":
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        elif format == "csv":
            keys = list(SEMANTIC_COLUMNS[name])
            keys.extend(key for row in rows for key in row if key not in keys)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
        elif format == "parquet":
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise RuntimeError("Install qualtrics[parquet]") from exc
            keys = list(SEMANTIC_COLUMNS[name])
            keys.extend(key for row in rows for key in row if key not in keys)
            fields = []
            for key in keys:
                if key in _FLOAT_COLUMNS:
                    data_type = pa.float64()
                elif key in _BOOL_COLUMNS:
                    data_type = pa.bool_()
                elif key in _INT_COLUMNS:
                    data_type = pa.int64()
                else:
                    data_type = pa.string()
                fields.append(pa.field(key, data_type, nullable=True))
            normalized = []
            for row in rows:
                normalized_row = {}
                for field in fields:
                    value = row.get(field.name)
                    if value is not None and pa.types.is_string(field.type):
                        value = str(value)
                    normalized_row[field.name] = value
                normalized.append(normalized_row)
            pq.write_table(pa.Table.from_pylist(normalized, schema=pa.schema(fields)), path)
        else:
            raise ValueError(f"Unsupported format: {format}")
