#!/usr/bin/env bash
# Run from the repository root after building exactly one wheel into dist/.
set -euo pipefail
unset PYTHONPATH
shopt -s nullglob
wheel_files=(dist/*.whl)
if [[ ${#wheel_files[@]} -ne 1 ]]; then
  echo "Expected exactly one built wheel in dist/." >&2
  exit 1
fi

uv venv --clear .wheel-venv
uv pip install --python .wheel-venv/bin/python "${wheel_files[0]}"
.wheel-venv/bin/python - <<'PYTHON'
import importlib.util
import qualtrics
from qualtrics.analytics import analyze_entities
assert analyze_entities(qualtrics.EntitySet()).response_count == 0
for dependency in ("typer", "rich", "jinja2", "markupsafe", "pyarrow"):
    assert importlib.util.find_spec(dependency) is None, dependency
PYTHON
uv venv --clear .wheel-cli-venv
uv pip install --python .wheel-cli-venv/bin/python "${wheel_files[0]}[cli]"
.wheel-cli-venv/bin/python -c "import importlib.util; assert importlib.util.find_spec('jinja2') is None"
.wheel-cli-venv/bin/qualtrics --help
.wheel-cli-venv/bin/qualtrics report --help
.wheel-cli-venv/bin/qualtrics build docs/assets/examples/feedback.csv --qsf docs/assets/examples/feedback.qsf --output .wheel-entities --format json
.wheel-cli-venv/bin/python - <<'PYTHON'
import subprocess
import sys
result = subprocess.run(
    [sys.executable, "-m", "qualtrics", "report", "--folder", ".wheel-entities", "--output", ".wheel-no-ui.html"],
    capture_output=True, text=True,
)
assert result.returncode == 2, result.stdout + result.stderr
assert "qualtrics[ui]" in result.stdout + result.stderr
PYTHON
uv venv --clear .wheel-ui-venv
uv pip install --python .wheel-ui-venv/bin/python "${wheel_files[0]}[ui]"
.wheel-ui-venv/bin/python - <<'PYTHON'
import importlib.util
from pathlib import Path
from qualtrics import EntitySet
from qualtrics.ui import render_report
assert importlib.util.find_spec("typer") is None
assert importlib.util.find_spec("rich") is None
render_report(EntitySet(), Path(".wheel-report.html"))
assert "id='overview'" in Path(".wheel-report.html").read_text()
PYTHON
uv pip install --python .wheel-venv/bin/python "${wheel_files[0]}[cli,ui]"
.wheel-venv/bin/qualtrics --help
printf '[{"survey_id":"smoke","survey_name":"Smoke"}]' > .wheel-surveys.json
.wheel-venv/bin/qualtrics report --surveys .wheel-surveys.json --output .wheel-cli-report.html
