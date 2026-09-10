# Python reference

Use the Python API to add parsing, reports, or Qualtrics API calls to your own scripts. Install the package first, following [installation](../getting-started/installation.md). Run scripts from this repository with `uv run python your_script.py`.

## Public imports

The package root exports the offline workflow and the API client:

```python
from qualtrics import (
    EntitySet,
    QualtricsClient,
    __version__,
    load_entities,
    merge_entity_sets,
    parse_survey,
    parse_surveys,
    render_report,
    write_entities,
)
```

The canonical report interface is `from qualtrics.ui import render_report`; install `qualtrics[ui]` before generating a report. The root import above and existing `qualtrics.reporting` imports remain compatible. Base SDK/data imports do not load Jinja, Typer, or Rich; UI rendering does not require CLI dependencies.

For semantic tables, use the defining modules:

```python
from qualtrics.models.semantic import SemanticModel, build_semantic_model
from qualtrics.serialization.semantic import write_semantic_model
```

Importing these names does not read credentials or make API calls. The client reads connection settings when you construct it; service methods make requests when you call them.

## Offline functions

The signatures below use `Path` from `pathlib` and `Sequence` from `collections.abc`.

```text
parse_survey(
    source_path: str | Path,
    qsf_path: str | Path | None = None,
    survey_id: str | None = None,
    *,
    flow_path: str | Path | None = None,
) -> EntitySet

parse_surveys(
    source_paths: Sequence[str | Path],
    qsf_paths: Sequence[str | Path] | None = None,
) -> EntitySet

merge_entity_sets(entity_sets: list[EntitySet]) -> EntitySet

write_entities(entities: EntitySet, folder: str | Path, format: str = "json") -> None

load_entities(folder: str | Path | None = None, **paths: str | Path) -> EntitySet

render_report(entities: EntitySet, output: str | Path) -> None

build_semantic_model(entities: EntitySet) -> SemanticModel

write_semantic_model(
    model: SemanticModel,
    folder: str | Path,
    format: str = "parquet",
) -> None
```

| Function | Behavior and constraints |
| --- | --- |
| `parse_survey` | Accepts a CSV, a ZIP containing one CSV, or a wildcard pattern matching several inputs. Discovers a same-stem `.qsf` then `.json` definition if you omit `qsf_path`. A `survey_id` override applies to one input only. |
| `parse_surveys` | Expands wildcard patterns in each supplied path, sorting each pattern's matches. Explicit definitions pair with inputs by position; supply one per input or omit them for adjacent discovery. |
| `merge_entity_sets` | Combines distinct survey IDs and deduplicates identical records in the two catalogs. Raises `ValueError` for repeated survey IDs or conflicting records with the same catalog ID. |
| `write_entities` | Writes all nine entities as `json`, `csv`, or `parquet`. Creates the folder and overwrites matching files. |
| `load_entities` | Loads entity files named for their tables. Explicit keyword paths use table names, such as `responses="responses.json"`. Validates the full contract when you supply a folder; without a folder, validates the supplied subset's keys and relationships. Rejects multiple formats for the same entity in a folder. |
| `render_report` | Writes a self-contained HTML report with the built-in design. The output's parent directory must exist. Overwrites the target file. |
| `build_semantic_model` | Requires a complete, valid entity collection. Returns five tables in a `SemanticModel`. |
| `write_semantic_model` | Writes all five tables as `json`, `csv`, or `parquet`. Creates the folder and overwrites matching files. |

The Python writers do not apply the CLI combine and semantic commands' occupied-output checks. Choose a fresh output directory for each run or format. Both reading and writing Parquet require the `parquet` extra.

### Parse, save, and report

```python
from pathlib import Path

from qualtrics import load_entities, parse_survey, render_report, write_entities
from qualtrics.models.semantic import build_semantic_model
from qualtrics.serialization.semantic import write_semantic_model


def main() -> None:
    output = Path("output/customer")
    output.mkdir(parents=True, exist_ok=True)

    entities = parse_survey("data/customer.csv", "data/customer.qsf")
    write_entities(entities, output / "entities")  # JSON by default.
    saved = load_entities(output / "entities")
    render_report(saved, output / "report.html")

    semantic = build_semantic_model(saved)
    write_semantic_model(semantic, output / "semantic", format="csv")
    print(f"Wrote a report for {len(saved.responses)} responses")


if __name__ == "__main__":
    main()
```

Use the downloadable inputs in [your first report](../getting-started/first-report.md), or follow [parse exports](../guides/parse-exports.md) with your own data.

`render_report` selects presentations from the question and field metadata: choice distributions, matrix tables, numeric summaries, or text summaries. It does not infer numeric measurements from text values. Preserve the metadata from `parse_survey` or `load_entities` when constructing your own workflows. See [question-specific summaries](../guides/reports.md#read-question-specific-summaries) for the percentage denominators and numeric statistics.

### Collections and table names

`EntitySet` is a dataclass with lists of dictionaries named `surveys`, `sections`, `question_catalog`, `question_field_catalog`, `questions`, `answer_options`, `question_fields`, `responses`, and `response_answers`. Prefer `parse_survey` or `load_entities` to construct a collection with the metadata needed for strict validation.

`SemanticModel` is a dataclass with `fact_responses`, `fact_response_answers`, `dim_surveys`, `dim_questions`, and `dim_answer_options`, also lists of dictionaries. `dim_questions` has one row per exported question field.

Use the [entity model](../entity-model.md) and [DBML schema](../entity-model.dbml) for columns, keys, and relationships. The [glossary](../understand/glossary.md) explains the terminology.

## API client

```text
QualtricsClient(
    api_token: str | None = None,
    *,
    data_center: str | None = None,
    base_url: str | None = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    retry_backoff: float = 1.0,
    transport: httpx.BaseTransport | None = None,
)
```

Omit connection arguments to read environment variables and `.env`. See [configuration](configuration.md) for precedence, URL resolution, and timeouts. Use `with QualtricsClient() as client:` to close the HTTP connection on exit; otherwise call `client.close()`. `QualtricsClient.from_env(**kwargs)` is a compatibility alias for construction with the same keyword arguments.

### List surveys with error handling

```python
import httpx

from qualtrics import QualtricsClient
from qualtrics.api import QualtricsAPIError, QualtricsExportError


def main() -> None:
    try:
        with QualtricsClient() as client:
            for survey in client.surveys.iter():
                print(survey.id, survey.name)
    except QualtricsAPIError as error:
        print(f"Qualtrics HTTP {error.status_code}: {error}")
        if error.request_id:
            print(f"Request ID: {error.request_id}")
    except QualtricsExportError as error:
        print(f"Import or export job failed: {error}")
    except httpx.HTTPError as error:
        print(f"Connection failed: {error}")
    except ValueError as error:
        print(f"Check connection settings or request data: {error}")


if __name__ == "__main__":
    main()
```

The main guard keeps importing this script from making API calls. For response downloads and definitions, follow [API access](../guides/api-access.md).

## API services

Service attributes group endpoints by purpose. The signatures below omit `self`. `Any` comes from `typing`; `Iterator` comes from `collections.abc`. Response models below are Pydantic models: use their snake_case attributes, `.model_dump()`, or `.model_dump_json()`.

### `client.surveys`

```text
list(*, offset: int | None = None) -> SurveyPage
iter() -> Iterator[SurveySummary]
get(survey_id: str) -> dict[str, Any]
update(survey_id: str, changes: SurveyUpdateRequest | dict[str, Any]) -> dict[str, Any] | None
```

`list` returns one page; `iter` follows `nextPage` links. `update` sends changes to the live survey. `SurveyUpdateRequest` supports `name`, `is_active`, `expiration`, and `owner_id`; you can also pass API field names such as `isActive`.

### `client.survey_definitions`

```text
get(survey_id: str) -> SurveyDefinition
get_flow(survey_id: str) -> dict[str, Any]
create(definition: dict[str, Any]) -> dict[str, Any]
delete(survey_id: str) -> dict[str, Any] | None
get_metadata(survey_id: str) -> dict[str, Any]
update_metadata(survey_id: str, metadata: dict[str, Any]) -> None
```

`get` returns a wrapper with `survey_id`, `survey_name`, and the raw definition in `payload`. You can save `.model_dump_json()` as a `.json` definition and pass it to `parse_survey`. `create`, `delete`, and `update_metadata` change remote data.

`get_flow` reads the configured flow root with its ordered children through the existing retry transport. Save it as JSON and pass its path as `parse_survey(..., flow_path=...)` for one input. Flows already included in a QSF or API definition are preserved automatically. The parser stores report-safe flow metadata as optional `surveys.flow_definition_json`, retaining the existing entity-table contract. See [survey flow](../guides/survey-flow.md) for a complete example and supported walkthrough behavior.

### `client.survey_quotas`

```text
list(survey_id: str, *, offset: int | None = None) -> SurveyQuotaPage
iter(survey_id: str) -> Iterator[SurveyQuota]
```

`client.quotas` is an alias. `list` rejects negative offsets. A quota has `id`, `name`, `count`, `quota`, `logic_type`, and `combinations`; each combination has `count`, `quota`, and `description`.

### `client.responses`: exports

`client.response_exports` is an alias for the same service.

```text
start(survey_id: str, options: ResponseExportRequest | None = None) -> ExportProgress
progress(survey_id: str, progress_id: str) -> ExportProgress
wait(
    survey_id: str,
    progress_id: str,
    *,
    poll_interval: float = 1.0,
    timeout: float = 900.0,
    on_progress: ExportCallback | None = None,
) -> ExportProgress
download(survey_id: str, file_id: str) -> httpx.Response
export(
    survey_id: str,
    output: str | Path,
    *,
    options: ResponseExportRequest | None = None,
    naming: FilenameStrategy = FilenameStrategy.SURVEY_ID,
    filename: str | None = None,
    survey_name: str | None = None,
    poll_interval: float = 1.0,
    timeout: float = 900.0,
    on_progress: ExportCallback | None = None,
) -> ExportResult
```

`export` starts, waits for, downloads, and saves an export. It returns the saved `path`, `survey_id`, `progress_id`, `file_id`, `format`, and optional `continuation_token`. The default request uses labeled CSV with compression, resulting in a ZIP. Set `ResponseExportRequest(compress=False)` for an uncompressed export. See the [CLI naming rules](cli.md#api-export) for output path behavior.

`on_progress` receives an `ExportEvent` with `survey_id`, `stage`, and optional `percent_complete`. Import `ExportCallback` and `ExportEvent` from `qualtrics.api`. The full export emits `starting`, `exporting`, `downloading`, and `complete`; `wait` emits only polling updates. Completion is emitted after the local file is saved. Callbacks run in the calling thread. See [progress callbacks and safe retries](../guides/api-access.md#observe-an-export-from-python) for an example.

`wait` requires a completed status and file ID; failed or timed-out jobs raise `QualtricsExportError`. `download` returns the HTTP response without saving a file.

### `client.responses`: imports and filters

```text
import_file(
    survey_id: str,
    source: str | Path,
    *,
    format: ImportFormat = ImportFormat.CSV,
) -> ImportProgress
import_url(
    survey_id: str,
    file_url: str,
    *,
    format: ImportFormat = ImportFormat.CSV,
) -> ImportProgress
import_progress(survey_id: str, progress_id: str) -> ImportProgress
wait_for_import(
    survey_id: str,
    progress_id: str,
    *,
    poll_interval: float = 1.0,
    timeout: float = 900.0,
) -> ImportProgress
list_filters(survey_id: str, *, offset: int | None = None) -> SurveyFilterPage
iter_filters(survey_id: str) -> Iterator[SurveyFilter]
```

Imports add response data to a live survey. Pass `ImportFormat.CSV` or `ImportFormat.JSON`. `import_file` sends local file bytes; `import_url` sends a file URL for Qualtrics to fetch. Poll with the returned `progress_id`. Failed or timed-out imports also raise `QualtricsExportError`.

`list_filters` returns one page of saved filters; `iter_filters` follows pagination. Import `SurveyFilter` and `SurveyFilterPage` from `qualtrics.api.models` when you need their types; they are not re-exported from `qualtrics.api`.

## Request models and enums

Import the main request models from `qualtrics.api`:

```python
from qualtrics.api import (
    FilenameStrategy,
    ImportFormat,
    ResponseExportRequest,
    ResponseImportRequest,
    SurveyUpdateRequest,
)
```

`ResponseExportRequest` accepts the fields below. Both Python names and Qualtrics aliases work, for example `use_labels=False` and `useLabels=False`.

| Python field | API alias | Default |
| --- | --- | --- |
| `format` | `format` | `"csv"`; also `tsv`, `json`, `ndjson`, `xml`, `spss` |
| `compress` | `compress` | `True` |
| `use_labels` | `useLabels` | `True` |
| `new_line_replacement` | `newlineReplacement` | `None` |
| `include_display_order` | `includeDisplayOrder` | `False` |
| `include_label_columns` | `includeLabelColumns` | `False` |
| `start_date`, `end_date` | `startDate`, `endDate` | `None` |
| `filter_id` | `filterId` | `None` |
| `question_ids` | `questionIds` | `None` |
| `survey_metadata_ids` | `surveyMetadataIds` | `None` |
| `embedded_data_ids` | `embeddedDataIds` | `None` |
| `limit` | `limit` | `None` |
| `continuation_token` | `continuationToken` | `None` |
| `allow_continuation` | `allowContinuation` | `False` |
| `sort_by_last_modified_date` | `sortByLastModifiedDate` | `False` |

ID collections take lists of strings; date values and tokens take strings; `limit` takes an integer. The SDK passes these filters to Qualtrics. It does not automatically continue an export from a returned continuation token.

`ResponseImportRequest` requires `file_url` (alias `fileUrl`) and defaults to `format=ImportFormat.CSV`. `FilenameStrategy` provides `SURVEY_ID`, `SURVEY_NAME`, `QUALTRICS`, and `CUSTOM`. `ExportStatus` provides `IN_PROGRESS`, `COMPLETE`, and `FAILED`.

The API package also re-exports `ExportFormat`, `ExportProgress`, `ExportResult`, `ImportProgress`, `SurveyDefinition`, `SurveyPage`, `SurveySummary`, `SurveyQuota`, `SurveyQuotaCombination`, `SurveyQuotaPage`, `QualtricsSettings`, and the service classes. `ResponseExportsAPI` is the compatibility name for `ResponseImportsExportsAPI`.

## Low-level transport and compatibility methods

Use the services above for covered endpoints. For another JSON endpoint:

```text
client.request(
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> Any

client.download(path: str) -> httpx.Response
```

`request` returns the JSON `result` member when present, the full payload otherwise, and `None` for HTTP 204. Both methods use the configured token and raise `QualtricsAPIError` for HTTP error responses.

The client keeps these flat methods as delegates to the service API. They accept the same arguments and defaults as the corresponding service methods:

| Compatibility method | Service equivalent |
| --- | --- |
| `list_surveys` | `surveys.list` |
| `iter_surveys` | `surveys.iter` |
| `get_survey` | `surveys.get` |
| `list_survey_quotas` | `survey_quotas.list` |
| `iter_survey_quotas` | `survey_quotas.iter` |
| `start_response_export` | `response_exports.start` |
| `get_response_export_progress` | `response_exports.progress` |
| `wait_for_response_export` | `response_exports.wait` |
| `download_response_export` | `response_exports.download` |
| `export_responses` | `response_exports.export` |

## Errors

| Error | Meaning |
| --- | --- |
| `ValueError` | Invalid settings, a malformed input, or an invalid entity contract. Read the message for the missing field or conflict. |
| `FileNotFoundError` | Missing file, an unmatched wildcard, or a report destination whose parent does not exist. |
| `RuntimeError("Install qualtrics[parquet]")` | A Parquet operation needs the optional dependency. |
| `QualtricsAPIError` | Qualtrics returned an HTTP error. Inspect `status_code` and `request_id`. |
| `QualtricsExportError` | An import or export failed, timed out, or omitted a required job/file ID. |
| `httpx.HTTPError` | An HTTP transport failure, including timeouts. |

`QualtricsAPIError` and `QualtricsExportError` inherit from `QualtricsError`, a `RuntimeError` subclass. Import all three from `qualtrics.api`. See [troubleshooting](../help/troubleshooting.md) for recovery steps.
