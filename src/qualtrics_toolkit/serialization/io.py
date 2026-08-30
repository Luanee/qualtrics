from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models.entities import ENTITY_NAMES, EntitySet


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
                import pyarrow as pa  # ty: ignore[unresolved-import]
                import pyarrow.parquet as pq  # ty: ignore[unresolved-import]
            except ImportError as exc:
                raise RuntimeError("Install qualtrics-toolkit[parquet]") from exc
            pq.write_table(pa.Table.from_pylist(records), path)
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
                (
                    p
                    for ext in ("json", "csv", "parquet")
                    if folder and (p := folder / f"{name}.{ext}").exists()
                ),
                None,
            )
        )
        if not path:
            continue
        if path.suffix == ".json":
            records = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                records = list(csv.DictReader(handle))
        else:
            try:
                import pyarrow.parquet as pq  # ty: ignore[unresolved-import]
            except ImportError as exc:
                raise RuntimeError("Install qualtrics-toolkit[parquet]") from exc
            records = pq.read_table(path).to_pylist()
        setattr(result, name, records)
    return result
