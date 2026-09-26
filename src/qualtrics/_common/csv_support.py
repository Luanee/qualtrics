"""CSV reader policy shared by raw export and entity-folder adapters."""

import csv
import sys


def ensure_csv_field_size_limit() -> None:
    # This limit is process-global. Raise it monotonically and leave it raised so
    # another active CSV reader is never exposed to a lower limit after this load.
    candidate = sys.maxsize
    while candidate > csv.field_size_limit():
        try:
            csv.field_size_limit(candidate)
            return
        except OverflowError:
            # Some platforms represent C long with fewer bits than Py_ssize_t.
            candidate //= 2
