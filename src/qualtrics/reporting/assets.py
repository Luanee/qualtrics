from importlib.resources import files


def load_asset(name: str) -> str:
    """Load a report asset bundled inside the installed distribution."""
    return files("qualtrics.reporting").joinpath("static", name).read_text(encoding="utf-8")
