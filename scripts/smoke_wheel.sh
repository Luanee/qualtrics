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

wheel_smoke_output=$(mktemp -d .wheel-smoke-XXXXXX)
export QUALTRICS_WHEEL_SMOKE_OUTPUT="$wheel_smoke_output"
trap 'rm -rf -- "$wheel_smoke_output"' EXIT

uv venv --clear .wheel-venv
uv pip install --python .wheel-venv/bin/python "${wheel_files[0]}"
.wheel-venv/bin/python - <<'PYTHON'
import importlib.util
import os
import pkgutil
import sqlite3
from pathlib import Path

import qualtrics
from qualtrics import (
    EntitySet,
    QualtricsClient,
    ReportAnalytics,
    SemanticModel,
    __version__,
    analyze_entities,
    build_semantic_model,
    load_entities,
    merge_entity_sets,
    parse_survey,
    parse_surveys,
    render_report,
    write_entities,
    write_semantic_model,
)

package_path = Path(qualtrics.__file__).parent
assert "site-packages" in package_path.parts, package_path
assert (package_path / "py.typed").is_file()
packages = {module.name for module in pkgutil.iter_modules(qualtrics.__path__) if module.ispkg}
assert packages == {"_common", "api", "cli", "ui"}, packages
analytics = analyze_entities(EntitySet())
assert isinstance(analytics, ReportAnalytics)
assert analytics.response_count == 0
entities = parse_survey("docs/assets/examples/feedback.csv", "docs/assets/examples/feedback.qsf")
semantic = build_semantic_model(entities)
assert isinstance(semantic, SemanticModel)
assert len(semantic.fact_responses) == len(entities.responses) > 0
assert len(semantic.dim_questions) == len(entities.question_fields) > 0
assert len(entities.comments) == 2
assert semantic.fact_comments == entities.comments
responses = {row["response_id"]: row for row in entities.responses}
for comment in entities.comments:
    assert comment["user_language"] == responses[comment["response_id"]].get("user_language")
smoke_output = Path(os.environ["QUALTRICS_WHEEL_SMOKE_OUTPUT"])
write_entities(entities, smoke_output / "base-entities", "json")
assert load_entities(smoke_output / "base-entities").comments == entities.comments
write_semantic_model(semantic, smoke_output / "base-model", "sqlite")
with sqlite3.connect(smoke_output / "base-model/semantic_model.sqlite") as connection:
    assert connection.execute("SELECT count(*) FROM fact_comments").fetchone() == (2,)
for dependency in ("typer", "rich", "jinja2", "markupsafe", "pyarrow"):
    assert importlib.util.find_spec(dependency) is None, dependency
PYTHON
uv venv --clear .wheel-cli-venv
uv pip install --python .wheel-cli-venv/bin/python "${wheel_files[0]}[cli]"
.wheel-cli-venv/bin/python -c "import importlib.util; assert importlib.util.find_spec('jinja2') is None"
.wheel-cli-venv/bin/qualtrics --help
.wheel-cli-venv/bin/qualtrics report --help
.wheel-cli-venv/bin/qualtrics build docs/assets/examples/feedback.csv --qsf docs/assets/examples/feedback.qsf --output .wheel-entities --format json
.wheel-cli-venv/bin/qualtrics semantic-model build .wheel-entities --output "$wheel_smoke_output/cli-model" --format sqlite
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
