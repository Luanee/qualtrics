# CLI reference

Run these commands from the repository with `uv run qualtrics`. If you installed the package into another environment, use `qualtrics` in place of `uv run qualtrics`. See [installation](../getting-started/installation.md) for setup.

| Command | Input | Output | Default format |
| --- | --- | --- | --- |
| `build` | Qualtrics CSV or response ZIP, with an optional definition | Nine entity files | JSON |
| `report` | Entity files | One HTML report | HTML |
| `entities combine` | Entity collections for distinct surveys | Nine combined entity files | Parquet |
| `semantic-model build` | One complete entity collection | Five analysis tables | Parquet |
| `api surveys` | API credentials | Survey IDs and names in the terminal | Tab-separated text |
| `api export` | Survey ID and API credentials | Response export | CSV inside a ZIP |
| `api import` | Survey ID, UTF-8 CSV, and API credentials | Import job ID and status in the terminal | Tab-separated text |

Use `--help` after any command or command group. At the top level, `--install-completion` installs shell completion and `--show-completion` prints the completion script.

## `build`

```bash
uv run qualtrics build data/customer.csv \
  --qsf data/customer.qsf \
  --output output/customer/entities
```

| Argument or option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `CSV_PATHS...` | Yes | — | One or more readable files or directories. A directory expands to its sorted `*.csv` files, without recursion. An explicit response ZIP path also works. |
| `--output`, `-o` | Yes | — | Destination directory; the command creates it if needed. |
| `--qsf PATH` | No | Same-stem definition beside each input | Repeat for multiple definitions. A directory expands to its sorted `*.qsf` files. An explicit API definition JSON path also works. |
| `--format`, `-f` | No | `json` | `json`, `csv`, or `parquet`. |
| `--survey-id TEXT` | No | Definition `SurveyID`, then input filename stem | Override the survey ID when building from one input file. |

Without `--qsf`, the parser checks for a same-stem `.qsf`, then `.json`, next to the CSV or ZIP. Filename matching ignores case. With multiple explicit definitions, the parser pairs inputs and definitions **by position**. Pass both lists in matching order.

```bash
uv run qualtrics build data/north.csv data/south.csv \
  --qsf data/north.qsf --qsf data/south.qsf \
  --output output/all/entities --format csv
```

Supply at most one definition for one CSV. For several CSVs, provide one definition per CSV or let the parser find adjacent definitions. You cannot apply one definition or one `--survey-id` override to several input files.

The command writes `surveys`, `sections`, `question_catalog`, `question_field_catalog`, `questions`, `answer_options`, `question_fields`, `responses`, and `response_answers`, each with the selected extension. It overwrites matching filenames. Use a separate directory for each format to avoid leaving conflicting copies.

See [parse exports](../guides/parse-exports.md), [your data](../understand/your-data.md), and the [entity model](../entity-model.md) for input requirements and table meanings.

## `report`

```bash
uv run qualtrics report \
  --folder output/customer/entities \
  --output output/customer/report.html
```

| Option | Required | Meaning |
| --- | --- | --- |
| `--output`, `-o` | Yes | HTML file to write. Its parent directory must exist. An existing file will be overwritten. |
| `--folder DIRECTORY` | Unless you supply entity paths | Repeat to include multiple surveys. Accepts the directory layouts below. |
| `--surveys PATH` | No | Explicit `surveys` file. |
| `--question-catalog PATH` | No | Explicit `question_catalog` file. |
| `--question-field-catalog PATH` | No | Explicit `question_field_catalog` file. |
| `--questions PATH` | No | Explicit `questions` file. |
| `--answer-options PATH` | No | Explicit `answer_options` file. |
| `--question-fields PATH` | No | Explicit `question_fields` file. |
| `--responses PATH` | No | Explicit `responses` file. |
| `--response-answers PATH` | No | Explicit `response_answers` file. |

All input options default to unset. Entity files may use JSON, CSV, or Parquet. The renderer uses a fixed built-in design; the command has no style, theme, or template options.

Prefer `--folder` for a complete collection. Explicit paths can override files in one collection, or load a subset without a folder, subject to relationship validation. You cannot combine explicit paths with multiple resolved folders. The CLI has no `--sections` option; load sections through `--folder`.

For multiple surveys, repeat `--folder` or pass a batch root:

```bash
uv run qualtrics report \
  --folder output/north/entities --folder output/south/entities \
  --output output/comparison.html
```

See [create reports](../guides/reports.md) for the report controls and sharing workflow.

## Folder discovery

`report --folder` and `entities combine` check each supplied directory in this order:

1. Entity files in the supplied directory, identified by a `surveys.json`, `surveys.csv`, or `surveys.parquet` file.
2. Entity files in its `entities/` subdirectory.
3. Entity files in each immediate child's `entities/` subdirectory, sorted by child name.

Discovery stops at the first matching layout. It does not search deeper. Repeated paths to the same resolved collection count once.

## `entities combine`

```bash
uv run qualtrics entities combine output/north output/south \
  --output output/combined/entities --format json
```

| Argument or option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `FOLDERS...` | Yes | — | One or more directories using the discovery layouts above. |
| `--output`, `-o` | Yes | — | Destination directory. It must contain no existing entity filenames in any supported format. |
| `--format`, `-f` | No | `parquet` | `json`, `csv`, or `parquet`. |

Each input must contain all nine entity files, with one format per entity and valid keys and relationships. You can combine collections stored in different formats. The command rejects duplicate survey IDs and conflicting catalog records; it deduplicates matching question and field catalog records.

Use this command for distinct surveys. It does not append successive exports from the same survey. See [combine surveys](../guides/combine-surveys.md).

## `semantic-model build`

```bash
uv run qualtrics semantic-model build output/combined/entities \
  --output output/combined/semantic --format parquet
```

| Argument or option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `FOLDER` | Yes | — | Directory containing all nine entity files. This command does not discover nested folders. |
| `--output`, `-o` | Yes | — | Destination directory. It must contain no existing semantic table filenames or `semantic_model.sqlite`. |
| `--format`, `-f` | No | `parquet` | `parquet`, `sqlite`, `json`, or `csv`. SQLite stores all five tables in one database. |

The command validates the entity collection and writes `fact_responses`, `fact_response_answers`, `dim_surveys`, `dim_questions`, and `dim_answer_options`. See [Power BI](../guides/power-bi.md) for relationships and loading instructions, or download the [DBML schema](../entity-model.dbml).

For SQLite, use `--format sqlite`; the command writes `semantic_model.sqlite` inside the output directory. It preserves IDs as text, represents booleans as `0`/`1`, and includes typed columns even for empty tables. The database becomes available only after all five tables have been written successfully. Existing output is never replaced.

!!! note "Parquet requires an extra dependency"
    `entities combine` and `semantic-model build` default to Parquet. Install the extra with `uv sync --extra parquet`, or select `--format json` or `--format csv`. The semantic-model command also supports `--format sqlite` without an extra dependency. See [installation](../getting-started/installation.md).

## API commands

These commands connect to Qualtrics. Configure a token and data center or API base URL as described in [configuration](configuration.md). Offline commands above need no credentials.

All three API commands accept `--data-center TEXT`, with `QUALTRICS_DATA_CENTER` as its environment fallback. They also accept `--api-token TEXT`, a hidden option with `QUALTRICS_API_TOKEN` as its environment fallback. Keep tokens in the environment or `.env` to avoid putting them in shell history. There is no CLI `--base-url`; use `QUALTRICS_BASE_URL`.

### `api surveys`

```bash
uv run qualtrics api surveys
```

List all survey pages available to the token. Print one survey ID and name per line, separated by a tab. There are no positional arguments or extra options beyond credentials and `--help`.

### `api export`

```bash
uv run qualtrics api export SV_EXAMPLE --output data
uv run qualtrics api export SV_FIRST SV_SECOND SV_THIRD --output data --batch-size 2
```

| Argument or option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `SURVEY_IDS...` | Yes | — | One or more distinct Qualtrics survey IDs. |
| `--output`, `-o` | Yes | — | Destination directory; an explicit file is allowed for one survey. |
| `--labels` / `--codes` | No | `--labels` | Export answer labels or codes. |
| `--naming` | No | `survey_id` | `survey_id`, `survey_name`, `qualtrics`, or `custom`. |
| `--filename TEXT` | With `--naming custom` | Unset | Custom filename stem. |
| `--survey-name TEXT` | No | Retrieved when needed | Name for the `survey_name` strategy; one survey only. |
| `--batch-size INTEGER` | No | `1` | Maximum concurrent surveys; at least 1. |
| `--no-progress` | No | Off | Hide progress on stderr. |
| `--retries INTEGER` | No | `3` | Additional attempts for each safe request; 0 disables retries. |
| `--format TEXT` | No | `csv` | `csv`, `tsv`, `json`, `ndjson`, `xml`, or `spss`. |
| `--compress` / `--no-compress` | No | `--compress` | Download a ZIP or uncompressed result. |
| `--start-date TEXT` | No | Unset | Recorded-response lower bound, ISO 8601. |
| `--end-date TEXT` | No | Unset | Recorded-response upper bound, ISO 8601. |
| `--question-id TEXT` | No | All | Select questions; repeat for more IDs. |
| `--embedded-data-id TEXT` | No | All | Select embedded-data fields; repeat for more IDs. |
| `--metadata-id TEXT` | No | All | Select survey metadata fields; repeat for more IDs. |
| `--filter-id TEXT` | No | Unset | Saved export filter; one survey only. |
| `--limit INTEGER` | No | Unset | Maximum responses; must be positive. |
| `--display-order` | No | Off | Include randomized display order. |
| `--label-columns` | No | Off | Include additional label columns. |
| `--newline-replacement TEXT` | No | Unset | Replacement for newlines in response values. |
| `--allow-continuation` | No | Off | Request a continuation token. |
| `--continuation-token TEXT` | No | Unset | Resume a previous export; one survey only. |
| `--sort-by-last-modified-date` | No | Off | Sort responses by last-modified date. |
| `--poll-interval FLOAT` | No | `1.0` | Seconds between status checks; at least 0.1. |
| `--timeout FLOAT` | No | `900.0` | Polling deadline in seconds; at least 0.1. In-flight requests and retries may finish later. |

The command starts exports, polls their status, downloads the results, and prints saved paths to stdout in the supplied survey order. The default CSV/compression settings write `data/SV_EXAMPLE.zip`. Dates without an explicit offset are interpreted as UTC. Selected fields and formats are passed to Qualtrics; support depends on the survey and API. The offline parser expects CSV or a ZIP containing CSV.

Interactive terminals show Rich progress on stderr: the overall completed count, per-survey export percentage, stages, elapsed time, and estimated remaining time. Downloading is indeterminate, and a survey counts as complete only after its file is saved. Redirected commands use simple stage lines. `--no-progress` suppresses progress, while errors and returned continuation tokens remain on stderr. Continuation tokens are reported with their survey IDs and are not followed automatically.

Safe reads retry temporary failures and honor `Retry-After`. Export creation only retries connection failures known to occur before sending; it never repeats an ambiguous POST response. Authentication and permission errors do not retry. See [retry behavior](../guides/api-access.md#recover-from-temporary-errors).

The naming strategies choose a filename from the survey ID, supplied or fetched survey name, Qualtrics download headers, or your custom filename. The Qualtrics strategy falls back to the survey ID if the response supplies no filename. Generated ID, survey-name, and custom names replace unsupported characters with underscores. For multiple surveys, non-ID naming uses `OUTPUT/SURVEY_ID/filename` to avoid collisions.

An explicit output file takes precedence over naming options. It does not change the downloaded content: naming a compressed export `.csv` will not unzip it. Existing directories containing a dot in their name remain directories. New output paths with a suffix are interpreted as files, so create such a directory first when needed. Parent directories are created automatically, and an existing export is replaced only after its replacement file is written successfully.

If one survey fails, completed outputs are retained and the others continue. The command reports failed survey IDs and exits nonzero after the batch finishes. Pressing Ctrl+C stops scheduling further surveys and cancels active workflows at their next progress callback. An in-flight request, retry wait, or polling sleep may need to finish first; completed local files are retained. Duplicate IDs, unsafe IDs, invalid dates, empty selected IDs, invalid numeric options, and incompatible multi-survey options are rejected before network requests.

### `api import`

```bash
uv run qualtrics api import SV_EXAMPLE data/responses-to-import.csv
```

| Argument | Required | Meaning |
| --- | --- | --- |
| `SURVEY_ID` | Yes | Destination survey ID. |
| `SOURCE` | Yes | Readable UTF-8 CSV file. |

This command uploads response data to the destination survey. It polls once per second for up to 900 seconds and prints the job ID and completion status, separated by a tab. The CLI supports CSV imports; the Python service also exposes JSON and URL imports. Follow the [API access guide](../guides/api-access.md) before working with a live survey.
