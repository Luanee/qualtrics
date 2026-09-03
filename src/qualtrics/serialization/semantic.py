from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models.semantic import SEMANTIC_TABLE_NAMES, SemanticModel


def write_semantic_model(model: SemanticModel, folder: str | Path, format: str = "parquet") -> None:
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    for name in SEMANTIC_TABLE_NAMES:
        rows = getattr(model, name)
        path = destination / f"{name}.{format}"
        if format == "json":
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        elif format == "csv":
            keys = list(dict.fromkeys(key for row in rows for key in row))
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
            pq.write_table(pa.Table.from_pylist(rows), path)
        else:
            raise ValueError(f"Unsupported format: {format}")
