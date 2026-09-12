# Qualtrics

Start with the [documentation](docs/index.md), [first-report tutorial](docs/getting-started/first-report.md), or [guide to parsing an export again](docs/guides/parse-exports.md). The docs cover command-line use without Python code, reports, and Power BI.

Explore the [question-type showcase](docs/examples/question-types.md) for an interactive report built from a synthetic survey and 100 fictional responses, with downloadable QSF and CSV files.

Preview the Material for MkDocs site from this repository:

```bash
uv run --group docs --extra ui mkdocs serve
```

Open `http://127.0.0.1:8000` in your browser. Build the site with `uv run --group docs --extra ui mkdocs build --strict`. See [documentation setup and plugin choices](docs/contributing/documentation.md) and [publishing to GitHub Pages](docs/contributing/documentation.md#publish-the-site) for details, and the [entity model](docs/entity-model.md) and [DBML contract](docs/entity-model.dbml) for analytical relationships.

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
- write normalized JSON, CSV, or Parquet entities, including a derived comments table with response language; and
- generate an offline HTML report with summary highlights, question charts, searchable written answers, individual responses, and a codebook.

## Install

```bash
uv add qualtrics
```

The base installation provides the SDK, parsing, analytics, and JSON/CSV serialization.
Install the command-line tools and HTML reports together:

```bash
uv add "qualtrics[cli,ui]"
```

Use `qualtrics[cli]` for API/data commands without reports, or `qualtrics[ui]`
for reports from Python without Typer/Rich. Add Parquet support when needed:

```bash
uv add "qualtrics[parquet]"
```

For development from this repository:

```bash
uv sync --all-groups --all-extras
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
HTML report. It needs the `ui` and `parquet` extras:

```bash
uv run --extra ui --extra parquet python examples/export_parse_and_report.py SV_123
uv run --extra ui --extra parquet python examples/export_parse_and_report.py SV_123 SV_456
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
        ├── response_answers.parquet
        └── comments.parquet
```

Parquet is the default. Select another entity format with `--format json` or
`--format csv`; export coded values with `--codes`.

## Parse existing exports

Parse a CSV and matching survey definition:

```bash
uv run --extra cli --extra ui --extra parquet qualtrics build responses.csv \
  --qsf definition.qsf \
  --output entities \
  --format parquet
```

Response-export ZIP files can be parsed directly:

```bash
uv run --extra cli --extra ui --extra parquet qualtrics build export.zip \
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

Use the root API for analytics and semantic tables too:

```python
from qualtrics import analyze_entities, build_semantic_model, write_semantic_model

analytics = analyze_entities(entities)
print(analytics.response_count)
semantic = build_semantic_model(entities)
write_semantic_model(semantic, "semantic", format="csv")
```

The root also exports `EntitySet`, `SemanticModel`, and `ReportAnalytics` for
type annotations. Earlier deep imports such as `qualtrics.models`,
`qualtrics.serialization`, and `qualtrics.reporting` have been removed; see the
[Python import migration](docs/reference/python.md#migrate-earlier-deep-imports)
for replacements.

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
| `comments` | Nonblank text answers derived from the original answer rows, with response language |
| `question_catalog` | Canonical questions shared across surveys |
| `question_field_catalog` | Canonical fields shared across surveys |

Exports contain ten tables: the nine authoritative entities and `comments`.
Comments reuse the original `response_answer_id` and preserve the text. Their
nullable `user_language` comes only from the linked response. All comments remain
in `response_answers`; use the subset for text analysis without adding its counts
to all-answer totals. Older nine-table folders remain readable and reconstruct
comments from their available metadata. See the [comments contract](docs/entity-model.md#comments).

The [Power BI export](docs/guides/power-bi.md) provides six semantic tables,
including `fact_comments`, as Parquet files or one SQLite database.

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
uv run --extra cli qualtrics api surveys
uv run --extra cli qualtrics api export SV_123 --output exports --labels
uv run --extra cli qualtrics api import SV_123 responses.csv
uv run --extra cli --extra ui --extra parquet qualtrics entities combine exports/run-1 exports/run-2 --output combined
uv run --extra cli --extra ui --extra parquet qualtrics report --folder entities --output report.html
uv run --extra cli --extra ui --extra parquet qualtrics report --folder data --output combined-report.html
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
uv sync --all-groups --all-extras
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run --all-extras poe check
uv run --all-extras poe build
```

CI tests Python 3.11–3.14. Ruff checks formatting and linting, `ty` checks
types, and pytest enforces at least 75% branch-aware coverage.

Implementation code has four packages: `api` for the remote SDK, `cli` for
terminal commands, `ui` for HTML reports, and `_common` for shared models,
parsers, analytics, and serialization. Use the root public API for shared data
operations; `_common` is private. The base SDK dependencies and `cli`, `ui`, and
`parquet` extras are unchanged. See the [package architecture](docs/contributing/documentation.md#package-architecture)
for contributor boundaries.

Releases are prepared through the **Prepare Release** GitHub workflow. See
[`release-notes.md`](release-notes.md) for version history and
[`examples/`](examples/) for runnable API and parsing examples.

## Acknowledgements

The workflow guidance was informed by the
[Qualtrics Report Generator](https://github.com/hihipy/qualtrics-report-generator).
Consult the [official Qualtrics API documentation](https://api.qualtrics.com/)
for features enabled on your account.
