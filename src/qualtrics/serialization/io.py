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


def _coerce_csv_records(name: str, records: list[dict[str, str]]) -> list[dict[str, object]]:
    field_types = CSV_FIELD_TYPES.get(name, {})
    coerced_records: list[dict[str, object]] = []
    for raw_record in records:
        record: dict[str, object] = dict(raw_record)
        for key, target_type in field_types.items():
            value = raw_record.get(key)
            if value in {None, ""}:
                continue
            record[key] = value.casefold() == "true" if target_type is bool else target_type(value)
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
            keys = list(dict.fromkeys(key for row in records for key in row))
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
            pq.write_table(pa.Table.from_pylist(_normalize_parquet_records(records)), path)
        else:
            raise ValueError(f"Unsupported format: {format}")


def load_entities(folder: str | Path | None = None, **paths: str | Path) -> EntitySet:
    folder = Path(folder) if folder else None
    result = EntitySet()
    for name in ENTITY_NAMES:
        path = (
            Path(paths[name])
            if name in paths
            else next(
                (p for ext in ("json", "csv", "parquet") if folder and (p := folder / f"{name}.{ext}").exists()),
                None,
            )
        )
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
    return result
