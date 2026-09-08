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

## Download, parse, and report in one workflow

The repository includes `examples/export_parse_and_report.py`. With your connection configured, run:

```text
uv run python examples/export_parse_and_report.py SV_123 --output data/api-export
```

For several surveys, list their IDs:

```text
uv run python examples/export_parse_and_report.py SV_123 SV_456 --output data/api-export
```

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

This script uses Parquet by default, so keep the `parquet` extra installed. Add `--format csv` or `--format json` for another entity format. Its `--labels` default, optional `--codes`, and `--start-date` export filter appear in:

```text
uv run python examples/export_parse_and_report.py --help
```

Choose a fresh output root for a new snapshot if you want to keep the previous files. Open each `report.html`, or follow [read and share reports](reports.md) to generate one report across the batch.

For Python integration or other API operations, use the [Python reference](../reference/python.md) and [CLI reference](../reference/cli.md).
