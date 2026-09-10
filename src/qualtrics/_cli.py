"""Dependency-free console launcher for the optional command-line interface."""

import sys


def main() -> None:
    """Load the CLI only when invoked, with installation guidance if unavailable."""
    try:
        from .cli.app import app
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] not in {"typer", "rich"}:
            raise
        print(
            'The command-line interface requires optional dependencies. Install with: pip install "qualtrics[cli]"',
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    app()
