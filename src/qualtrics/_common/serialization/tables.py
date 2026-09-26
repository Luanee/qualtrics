"""File-format mechanics; callers retain their column and value contracts."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

ScalarType = type[bool] | type[int] | type[float]


def write_table(
    path: Path,
    rows: list[dict[str, Any]],
    format: str,
    columns: list[str],
    field_types: Mapping[str, ScalarType],
    *,
    normalize: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> None:
    """Write ordered, nullable columns; unspecified Parquet types are strings.

    The optional normalizer is a caller-owned Parquet policy. JSON and CSV
    retain original values. Import Arrow only for Parquet, before normalizing.
    """
    if format == "json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif format == "csv":
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    elif format == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("PyArrow is required for Parquet output") from exc
        types = {bool: pa.bool_(), int: pa.int64(), float: pa.float64()}
        fields = [pa.field(key, types.get(field_types.get(key), pa.string()), nullable=True) for key in columns]
        records = normalize(rows) if normalize is not None else rows
        normalized = [
            {
                field.name: str(row[field.name])
                if row.get(field.name) is not None and pa.types.is_string(field.type)
                else row.get(field.name)
                for field in fields
            }
            for row in records
        ]
        pq.write_table(pa.Table.from_pylist(normalized, schema=pa.schema(fields)), path)
    else:
        raise ValueError(f"Unsupported format: {format}")
