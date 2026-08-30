# Qualtrics Toolkit

`qualtrics-toolkit` is a Python library and Typer CLI for working with
Qualtrics surveys end to end:

- list and update surveys through Qualtrics API v3;
- import responses and download response exports;
- parse one or many Qualtrics CSV exports, with or without QSF metadata;
- preserve survey, question, concrete field, block, and loop identities;
- build survey-local entities and cross-survey canonical catalogs;
- write JSON, CSV, or Parquet datasets;
- calculate question-type-aware analytics and data-quality signals; and
- create a self-contained, interactive HTML report.

It is useful for conventional surveys and for administrative data-intake
workflows where different people answer different sections—for example
institutional reporting, accreditation, compliance, annual collections, grant
reporting, and multi-stakeholder intake forms.

## Why CSV and QSF are both useful

A Qualtrics response CSV normally begins with three header rows:

1. exported field name, such as `4_cat_train`;
2. question and field text;
3. metadata such as `{"ImportId":"4_QID30"}`.

Multi-field, matrix, form, looped, and text-entry questions can create several
CSV fields for one logical survey question. The toolkit never identifies a
concrete answer using stripped question text. It retains the full field name,
ImportId, suffix, and column index.

QSF metadata is optional but strongly recommended. It supplies definitive
question types, complete question text, choices, survey blocks, and loop
configuration. Without QSF, the toolkit infers what it safely can from the CSV.
When `--qsf` is omitted, the toolkit automatically uses a `.qsf` file beside
the CSV when both files have the same filename stem. Extension matching is
case-insensitive, so `annual-survey.csv` can match `annual-survey.QSF`.

For a manual export in Qualtrics:

1. Open **Data & Analysis → Export & Import → Export Data**.
2. Choose CSV and, for readable reports, enable choice text rather than numeric
   codes.
3. Download the QSF from **Survey → Tools → Import/Export → Export Survey**.
4. Give matching CSV and QSF files the same sortable base name.

## Installation with uv

From this repository:

```bash
uv sync
```

Run the CLI without installing it globally:

```bash
uv run qualtrics-toolkit --help
```

Parquet support:

```bash
uv sync --extra parquet
```

## Build entity datasets

One survey:

```bash
uv run qualtrics-toolkit build \
  survey.csv --qsf survey.qsf --output entities --format json
```

With matching files such as `survey.csv` and `survey.qsf`, `--qsf` is optional:

```bash
uv run qualtrics-toolkit build \
  survey.csv --output entities --format json
```

Multiple surveys:

```bash
uv run qualtrics-toolkit build \
  survey-v1.csv survey-v2.csv \
  --qsf survey-v1.qsf --qsf survey-v2.qsf \
  --output entities --format parquet
```

Directories are supported too. CSV and QSF directory contents are sorted by
filename and paired in that order:

```bash
uv run qualtrics-toolkit build \
  ./exports/csv --qsf ./exports/qsf --output entities
```

The output contains:

| Entity | Identity and purpose |
|---|---|
| `surveys` | Survey/version metadata |
| `sections` | Survey-local Qualtrics blocks and their display order |
| `question_catalog` | Canonical logical questions shared across surveys |
| `question_field_catalog` | Canonical fields shared across surveys |
| `questions` | Survey-local question occurrences, types, blocks, and order |
| `question_fields` | Concrete CSV columns and ImportIds |
| `answer_options` | Defined respondent options—not Meta Info fields |
| `responses` | Response metadata |
| `response_answers` | Answers linked through survey, response, question, and field |

The central answer relationship is:

```text
response_answer
  → (survey_id, response_id)
  → (survey_id, question_id, field_id)
  → question_catalog_id / question_field_catalog_id
```

Entity records describe survey data only. Pipeline lineage such as ingestion
run IDs belongs in the surrounding platform manifest or control tables and is
therefore not added by the parser.

`parse_survey` also accepts wildcard paths. This is useful for run-oriented
lakehouse layouts where each survey has its own folder:

```python
from qualtrics_toolkit import parse_survey

entities = parse_survey("/lakehouse/default/Files/qualtrics/run-1/*/*.csv")
```

Each CSV is paired automatically with a same-stem `.qsf` or `.json` definition
in its directory. Prefer a single-level pattern like `*/*.csv`; recursive
patterns may also select translated CSV files stored below `translations/`.

## Generate an HTML report

```bash
uv run qualtrics-toolkit report \
  --folder entities --output report.html
```

The report is one portable HTML file with embedded styling and behavior. It
includes survey selection, response and question filters, blocks, metadata,
coverage, question-type-aware analytics, and per-survey data-quality findings.
All source values are HTML-escaped.

## Qualtrics API SDK

Set credentials without putting the token in shell history:

```bash
export QUALTRICS_API_TOKEN="..."
export QUALTRICS_DATA_CENTER="ca1"
```

Your data-center identifier is the first part of the Qualtrics host used by
your account. You may instead set `QUALTRICS_BASE_URL` for a custom API base.
Explicit constructor arguments override matching environment variables:

```python
from qualtrics_toolkit import QualtricsClient

client = QualtricsClient()  # reads QUALTRICS_API_TOKEN and connection settings
client = QualtricsClient(api_token="...", data_center="ca1")
```

List surveys:

```bash
uv run qualtrics-toolkit api surveys
```

Export labeled CSV responses and name the ZIP after the survey ID:

```bash
uv run qualtrics-toolkit api export SV_123 --output exports --labels \
  --naming survey_id
```

Import a UTF-8 CSV response file and wait for processing:

```bash
uv run qualtrics-toolkit api import SV_123 responses.csv
```

Naming strategies are `qualtrics`, `survey_id`, `survey_name`, and `custom`.
For custom naming, add `--filename my-export`. An explicit output file path
always takes precedence.

Python usage:

```python
from pathlib import Path

from qualtrics_toolkit import QualtricsClient
from qualtrics_toolkit.api import FilenameStrategy, ResponseExportRequest

# With no arguments, credentials are read from QUALTRICS_* variables.
with QualtricsClient() as client:
    surveys = list(client.surveys.iter())
    result = client.responses.export(
        surveys[0].id,
        Path("exports"),
        options=ResponseExportRequest(format="csv", use_labels=True),
        naming=FilenameStrategy.SURVEY_NAME,
        survey_name=surveys[0].name,
    )
    print(result.path)
```

The context manager is recommended because it closes the underlying HTTPX
connection pool deterministically. Long-lived applications can instead create
one client, reuse it, and call `client.close()` during application shutdown.

The export workflow starts an asynchronous job, polls its `progressId`, obtains
the resulting `fileId`, and downloads the binary file. The low-level
`client.request(...)` method provides access to API v3 endpoints not yet covered
by a typed resource method.

The API client uses domain resources rather than placing every endpoint on the
root client:

```python
with QualtricsClient() as client:
    survey = client.surveys.get("SV_123")
    client.surveys.update("SV_123", {"name": "Annual survey"})
    filters = list(client.responses.iter_filters("SV_123"))
    job = client.responses.start("SV_123")
    progress = client.responses.wait("SV_123", job.progress_id)
```

`client.responses` covers local-file and hosted-file imports, import progress,
saved filters, export creation/progress, and export download. The older
`client.response_exports` attribute remains as an alias. Survey structure
operations such as definitions and metadata are intentionally exposed through
`client.survey_definitions`, separate from the `/surveys` CRUD resource.

The root client owns authentication, error handling, and HTTP transport. Domain
packages own endpoint paths and workflows. Compatibility delegates such as
`client.iter_surveys()` remain available for existing callers.

Qualtrics currently documents CSV, TSV, JSON, NDJSON, XML, and SPSS response
exports. Large exports should use filters, date ranges, selected questions, or
continuation tokens where appropriate.

## Python API

```python
from qualtrics_toolkit import parse_surveys, render_report, write_entities

entities = parse_surveys(
    ["survey-v1.csv", "survey-v2.csv"],
    ["survey-v1.qsf", "survey-v2.qsf"],
)
write_entities(entities, "entities", format="json")
render_report(entities, "report.html")
```

## Source layout

```text
src/qualtrics_toolkit/
├── api/
├── analytics/
├── cli/
├── models/
├── parsers/
├── reporting/
├── serialization/
└── services/
```

The API and offline data tooling are equal package capabilities. The `api/`
domain owns HTTP resources and API models; parsing, analytics, reporting, and
serialization remain independent and never require network credentials.

The distribution and CLI are named `qualtrics-toolkit`; the Python import is
`qualtrics_toolkit`.

## Development

```bash
uv sync --group dev --group test --extra parquet
uv run poe check
uv run poe build
```

## Examples

Runnable examples live in [`examples/`](examples/):

```bash
# Parse one CSV; a matching QSF is discovered automatically.
uv run python examples/parse_survey.py survey.csv

# Parse all CSV files in a directory into one multi-survey report.
uv run python examples/parse_multiple_surveys.py exports

# List surveys, or add --survey-id SV_123 to export responses.
uv run python examples/api_list_and_export.py

# Import responses into an existing survey.
uv run python examples/api_import_responses.py \
  SV_123 responses.csv
```

API examples read `QUALTRICS_API_TOKEN` and `QUALTRICS_DATA_CENTER` from the
environment. Importing responses changes data in the target survey, so verify
the survey ID before running that example.

## Acknowledgements

The usage guidance and administrative-survey examples were informed by the
[Qualtrics Report Generator](https://github.com/hihipy/qualtrics-report-generator)
README. API behavior should be checked against the
[official Qualtrics API documentation](https://api.qualtrics.com/) for the
features enabled on your account.
