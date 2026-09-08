# Connect to the Qualtrics API

Use the API to download response exports from your Qualtrics account. You can skip this setup when working with existing CSV, ZIP, or QSF files.

You need the [installed project](../getting-started/installation.md), an API token with access to the surveys, and your account's data-center identifier or custom API base URL. Ask your Qualtrics administrator for the values and access your account permits. Keep your token private.

Run the examples from the `qualtrics` project folder. The example script in the last section requires the repository copy. For individual CLI commands, an isolated installation uses `qualtrics` in place of `uv run qualtrics`.

## 1. Set your connection details

Create a plain-text file named `.env` in the project folder, alongside `pyproject.toml`. On Windows, check that the editor has not added a `.txt` extension.

```dotenv
QUALTRICS_API_TOKEN=replace-with-your-token
QUALTRICS_DATA_CENTER=replace-with-your-data-center
```

Replace both placeholders. A data-center identifier looks like `ca1`; use the value for your account. Keep `.env` on your machine and out of shared documents or source-control commits. The repository's Git ignore file excludes it.

For a custom API endpoint, use `QUALTRICS_BASE_URL` instead of the data-center line:

```dotenv
QUALTRICS_API_TOKEN=replace-with-your-token
QUALTRICS_BASE_URL=https://your-api-host/API/v3
```

Use the complete API v3 base URL supplied for your account. If both a base URL and data center are set, the client uses the base URL.

### Alternative: set values for this terminal session

You can use environment variables instead of a `.env` file:

=== "Windows PowerShell"

    ```powershell
    $env:QUALTRICS_API_TOKEN = "replace-with-your-token"
    $env:QUALTRICS_DATA_CENTER = "replace-with-your-data-center"
    ```

=== "macOS / Linux"

    ```bash
    export QUALTRICS_API_TOKEN="replace-with-your-token"
    export QUALTRICS_DATA_CENTER="replace-with-your-data-center"
    ```

Environment variables override values in `.env`. Commands typed into a shell can remain in its history, including tokens, so use a local `.env` file if you need to avoid typing a token into the terminal. See [configuration](../reference/configuration.md) for all settings and precedence.

## 2. Check access by listing surveys

This command contacts Qualtrics and lists the surveys available to your token:

```text
uv run qualtrics api surveys
```

Each output line contains a survey ID and a survey name. For example:

```text
SV_123    Example feedback survey
```

Copy the ID of the survey you need. In the following commands, replace `SV_123` with that ID.

If you see an authentication or access error, check the token, endpoint, and account permissions with your administrator. [Troubleshooting](../help/troubleshooting.md) explains common failures.

## 3. Download a response export

```text
uv run qualtrics api export SV_123 --output data/api-exports --labels
```

The command starts a CSV export, waits for Qualtrics to finish, downloads the compressed result, and prints its local path. With the default filename strategy, the expected file is:

```text
data/api-exports/SV_123.zip
```

`--labels` requests answer labels such as “Satisfied” and is the default. Use `--codes` if you need Qualtrics answer codes. This command downloads responses; to get the definition and a report in one workflow, use the example below.

If you already have the matching QSF, parse the ZIP without extracting it:

```text
uv run qualtrics build data/api-exports/SV_123.zip --qsf data/my-survey/definition.qsf --output data/my-survey/entities --format csv
```

Replace the QSF path with your actual definition file. Use a new export folder when you want to retain earlier downloads; repeating an export to the same path replaces the local file.

## Export several surveys

List the survey IDs in the same command. The default runs one survey at a time. Increase `--batch-size` to set the maximum number of concurrent surveys:

```text
uv run qualtrics api export SV_123 SV_456 SV_789 --output data/api-exports --batch-size 2
```

This starts at most two surveys at once. A new survey starts when a slot becomes available. You can use the same command for one or two surveys; the effective concurrency never exceeds the number of surveys supplied. The default ID naming writes `SV_123.zip`, `SV_456.zip`, and `SV_789.zip` in the output directory. Other naming strategies use a separate subdirectory for each survey so equal survey names or download filenames cannot overwrite each other.

In a terminal, Rich displays an overall completed-survey count and a row for each survey, with a percentage bar, elapsed time, estimated remaining time, and stages for starting, exporting, and downloading. The overall counter advances after the download is saved. Download time has no percentage estimate. Redirected commands write simple stage messages to stderr instead of animated bars; `--no-progress` hides these progress messages. Saved paths go to stdout.

If one survey fails, the remaining surveys continue. Successful files stay on disk, the command identifies failures on stderr, and its exit code is nonzero. Re-run the failed IDs to try them again. Pressing Ctrl+C stops scheduling further surveys and cancels active workflows at their next progress callback. An in-flight request, retry wait, or polling sleep may need to finish first; completed local files are retained.

### Recover from temporary errors

Safe requests have three retries by default (`--retries 3`), in addition to the original attempt. Read requests retry HTTP 408, 429, 500, 502, 503, and 504 and transport failures, with exponential backoff. The client honors a server's `Retry-After` delay. Use `--retries 0` to disable retries.

Authentication and permission failures do not retry. A mutation such as starting an export retries only connection failures known to occur before sending the request. It does not repeat a POST after a read timeout or error response, because Qualtrics might already have started the export. The retry count applies to each HTTP request, not the entire survey workflow. The polling deadline defaults to 900 seconds; an in-flight request and its retries can finish after that deadline.

### Select which responses and columns to export

For example, request January responses and two questions:

```text
uv run qualtrics api export SV_123 --output data/january --start-date 2026-01-01 --end-date 2026-02-01 --question-id QID1 --question-id QID2 --limit 5000
```

Dates and timestamps without an offset are interpreted as UTC; timestamps with an offset are converted to UTC. Repeat `--embedded-data-id` or `--metadata-id` to select additional embedded-data or survey metadata columns. `--filter-id` applies a saved filter to one survey. Qualtrics determines which options and fields your survey and export format support.

You can choose `--format csv`, `tsv`, `json`, `ndjson`, `xml`, or `spss`, and `--no-compress` downloads the uncompressed result. The toolkit's CSV/ZIP parsing workflow expects CSV data; the other formats are downloads for use in other tools. Other controls include `--display-order`, `--label-columns`, `--newline-replacement`, and `--sort-by-last-modified-date`. See the complete [CLI options](../reference/cli.md#api-export).

For incremental exports, `--allow-continuation` requests a continuation token. If Qualtrics returns one, the command prints it to stderr alongside its survey ID. Save it and pass `--continuation-token TOKEN` on a later export of that same survey. Tokens and saved filter IDs apply to one survey, so these options require a single-survey command. The toolkit does not automatically follow continuation tokens.

### Observe an export from Python

SDK callbacks contain no terminal-rendering dependencies:

```python
from qualtrics.api import ExportEvent, QualtricsClient


def show_progress(event: ExportEvent) -> None:
    print(event.survey_id, event.stage, event.percent_complete)


with QualtricsClient(max_retries=3, retry_backoff=1.0) as client:
    result = client.export_responses("SV_123", "data/api-exports", on_progress=show_progress)
```

The stages are `starting`, `exporting`, `downloading`, and `complete`. `percent_complete` is supplied during export polling and at completion. A `complete` event means the file was saved locally. Callbacks run in the thread making the export call; any callback exception is passed back to the caller.

## Download, parse, and report in one workflow

The repository includes `examples/export_parse_and_report.py`. With your connection configured, run:

```text
uv run python examples/export_parse_and_report.py SV_123 --output data/api-export
```

For several surveys, list their IDs:

```text
uv run python examples/export_parse_and_report.py SV_123 SV_456 SV_789 --output data/api-export --batch-size 2
```

The script defaults to one survey at a time. It uses the same progress display and retry policy as `api export`; `--batch-size`, `--retries`, and `--no-progress` control them. Its overall completed count includes parsing and report generation. If a survey fails, the other surveys continue and the command exits with an error after printing the successful results.

For each ID, the script downloads the survey definition and responses, extracts the CSV, writes entity tables, and renders a report:

```text
data/api-export/SV_123/
├── definition.qsf
├── export.zip
├── responses.csv
├── report.html
└── entities/
    └── ... nine Parquet files ...
```

This script uses Parquet by default, so keep the `parquet` extra installed. Add `--format csv` or `--format json` for another entity format. Its `--labels` default, optional `--codes`, and `--start-date` / `--end-date` export filters appear in:

```text
uv run python examples/export_parse_and_report.py --help
```

Choose a fresh output root for a new snapshot if you want to keep the previous files. Open each `report.html`, or follow [read and share reports](reports.md) to generate one report across the batch.

For Python integration or other API operations, use the [Python reference](../reference/python.md) and [CLI reference](../reference/cli.md).
