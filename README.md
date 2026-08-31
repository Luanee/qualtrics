# Qualtrics

[![Python](https://img.shields.io/pypi/pyversions/qualtrics?logo=python&logoColor=white)](https://pypi.org/project/qualtrics/)
[![Ruff](https://img.shields.io/badge/code%20style-Ruff-D7FF64?logo=ruff&logoColor=261230)](https://docs.astral.sh/ruff/)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A575%25-brightgreen)](#development)
[![PyPI](https://img.shields.io/pypi/v/qualtrics?logo=pypi&logoColor=white)](https://pypi.org/project/qualtrics/)
[![Tests](https://img.shields.io/github/actions/workflow/status/Luanee/qualtrics/ci.yml?branch=main&label=tests&logo=github)](https://github.com/Luanee/qualtrics/actions/workflows/ci.yml)

`qualtrics` is a typed Python SDK and Typer CLI for the Qualtrics API and
offline survey data. It can:

- list and update surveys through Qualtrics API v3;
- import and export survey responses;
- parse CSV or response-export ZIP files, with or without survey definitions;
- preserve questions, concrete fields, answer options, and survey blocks;
- write normalized JSON, CSV, or Parquet entities; and
- generate an interactive HTML report with data-quality and question analytics.

## Install

```bash
uv add qualtrics
```

Install Parquet support when needed:

```bash
uv add "qualtrics[parquet]"
```

For development from this repository:

```bash
uv sync --all-groups --extra parquet
```

## Configure the API

Create a `.env` file or export the same variables in your shell:

```dotenv
QUALTRICS_API_TOKEN=your-token
QUALTRICS_DATA_CENTER=ca1
```

Use `QUALTRICS_BASE_URL` instead of `QUALTRICS_DATA_CENTER` when your account
requires a custom API base URL. Explicit `QualtricsClient(...)` arguments take
precedence over environment settings.

## Export, parse, and report

The complete example accepts a survey ID, downloads its definition and
responses, extracts the original CSV, creates Parquet entities, and renders an
HTML report:

```bash
uv run python examples/export_parse_and_report.py SV_123
uv run python examples/export_parse_and_report.py SV_123 SV_456
```

It creates:

```text
data/
└── SV_123/
    ├── definition.qsf
    ├── export.zip
    ├── responses.csv
    ├── report.html
    └── entities/
        ├── surveys.parquet
        ├── sections.parquet
        ├── questions.parquet
        ├── question_fields.parquet
        ├── question_catalog.parquet
        ├── question_field_catalog.parquet
        ├── answer_options.parquet
        ├── responses.parquet
        └── response_answers.parquet
```

Parquet is the default. Select another entity format with `--format json` or
`--format csv`; export coded values with `--codes`.

## Parse existing exports

Parse a CSV and matching survey definition:

```bash
uv run qualtrics build responses.csv \
  --qsf definition.qsf \
  --output entities \
  --format parquet
```

Response-export ZIP files can be parsed directly:

```bash
uv run qualtrics build export.zip \
  --qsf definition.qsf \
  --output entities \
  --format parquet
```

When the response file and definition share a filename stem, the definition is
discovered automatically. For example, `SV_123.zip` matches `SV_123.qsf`.

Python usage:

```python
from qualtrics import parse_survey, render_report, write_entities

entities = parse_survey("responses.csv", "definition.qsf")
write_entities(entities, "entities", format="parquet")
render_report(entities, "report.html")
```

Wildcards support multiple surveys and lakehouse-style layouts:

```python
entities = parse_survey("/lakehouse/default/Files/qualtrics/run-1/*/*.csv")
```

## Why the survey definition matters

A Qualtrics CSV commonly starts with three header rows:

1. the exported field name;
2. the question and field text; and
3. metadata such as `{"ImportId":"QID30_4_TEXT"}`.

One logical question can produce many concrete CSV fields for choices, matrix
rows, loops, or text entries. The parser retains the complete field name,
ImportId, suffix, and column index instead of collapsing fields by normalized
question text.

A QSF or API survey definition is optional but recommended. It supplies the
survey name, question types, choices, blocks, and other metadata that cannot be
reliably reconstructed from response headers alone.

## Entity model

| Entity | Purpose |
| --- | --- |
| `surveys` | Survey identity and metadata |
| `sections` | Survey blocks and display order |
| `questions` | Survey-local questions, types, and block membership |
| `question_fields` | Concrete CSV fields and ImportIds |
| `answer_options` | Options defined for response questions |
| `responses` | Respondent and response metadata |
| `response_answers` | Values linked to responses, questions, and fields |
| `question_catalog` | Canonical questions shared across surveys |
| `question_field_catalog` | Canonical fields shared across surveys |

The primary relationship is:

```text
response_answer
  → (survey_id, response_id)
  → (survey_id, question_id, field_id)
  → question_catalog_id / question_field_catalog_id
```

Pipeline lineage such as an ingestion run ID belongs in the surrounding data
platform, not in the parser entities.

Each `responses` row contains the stable response metadata exported by
Qualtrics: status, IP address, progress, duration, recipient details, external
reference, distribution channel, language, and browser/device information.
Browser Meta Info fields are promoted to the response row and are not repeated
as answers. Repeating Timing fields remain in `response_answers`, where their
question and concrete field identities are preserved.

## SDK and CLI

```python
from qualtrics import QualtricsClient

with QualtricsClient() as client:
    for survey in client.surveys.iter():
        print(survey.id, survey.name)

    definition = client.survey_definitions.get("SV_123")
```

Common CLI commands:

```bash
uv run qualtrics api surveys
uv run qualtrics api export SV_123 --output exports --labels
uv run qualtrics api import SV_123 responses.csv
uv run qualtrics entities combine exports/run-1 exports/run-2 --output combined
uv run qualtrics report --folder entities --output report.html
uv run qualtrics report --folder data --output combined-report.html
```

`entities combine` accepts entity directories, survey directories containing an
`entities/` directory, and batch roots containing multiple `<survey-id>/entities/`
directories. Inputs may mix JSON, CSV, and Parquet files. Combined output uses
Parquet by default; select another format with `--format json` or `--format csv`.

The report command accepts repeated `--folder` options. It also discovers the
`<survey-id>/entities/` directories created by the complete export example when
its shared `data/` root is supplied.

`client.surveys` covers survey CRUD. `client.survey_definitions` handles survey
structure, `client.survey_quotas` reads quota progress and definitions, and
`client.responses` handles imports, exports, progress, and saved response
filters.

```python
with QualtricsClient() as client:
    page = client.survey_quotas.list("SV_123")
    for quota in client.survey_quotas.iter("SV_123"):
        print(quota.name, quota.count, quota.quota)
```

## Development

```bash
uv sync --all-groups --extra parquet
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run poe check
uv run poe build
```

CI tests Python 3.11–3.14. Ruff checks formatting and linting, `ty` checks
types, and pytest enforces at least 75% branch-aware coverage.

Releases are prepared through the **Prepare Release** GitHub workflow. See
[`release-notes.md`](release-notes.md) for version history and
[`examples/`](examples/) for runnable API and parsing examples.

## Acknowledgements

The workflow guidance was informed by the
[Qualtrics Report Generator](https://github.com/hihipy/qualtrics-report-generator).
Consult the [official Qualtrics API documentation](https://api.qualtrics.com/)
for features enabled on your account.
