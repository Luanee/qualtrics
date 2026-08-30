from __future__ import annotations

import glob
from collections.abc import Sequence
from pathlib import Path


def _expand_paths(paths: Sequence[str | Path]) -> list[Path]:
    expanded: list[Path] = []
    for value in paths:
        pattern = str(value)
        matches = (
            sorted(glob.glob(pattern, recursive=True)) if glob.has_magic(pattern) else [pattern]
        )
        if not matches:
            raise FileNotFoundError(f"Path pattern matched no files: {pattern}")
        expanded.extend(Path(match) for match in matches)
    return expanded
