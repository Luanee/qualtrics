# Troubleshooting

Start with the command's error message and the matching case below. If you are new to the toolkit, run the synthetic example in [your first report](../getting-started/first-report.md) to check your installation before investigating your own exports.

## The command is missing or an option is unknown

From the repository, run:

```bash
uv sync --extra cli --extra ui
uv run --extra cli --extra ui qualtrics --help
uv run --extra cli --extra ui qualtrics report --help
```

With a package installation, activate the environment containing `qualtrics` and run `qualtrics --help`. See [installation](../getting-started/installation.md).

Check the [CLI reference](../reference/cli.md) for current options. In particular, `report` accepts entity inputs and an output path; it has no style, theme, or template flags. Change the appearance with the **Theme** selector inside the generated report. `build` defaults to JSON, while `entities combine` and `semantic-model build` default to Parquet.

## The CSV fails to parse or contains no responses

**Messages:** `Qualtrics CSV must contain column and question-text rows`, a row-length error, or a report with no expected answers.

Use the original Qualtrics CSV export, encoded as UTF-8. Keep its column-name row, question-text row, and, when present, the third row containing JSON `ImportId` metadata. Spreadsheet edits that remove these rows or change the delimiter can break parsing. The parser reads comma-separated data, even if the file has a different extension.

Check that:

- Each header row has the same number of columns.
- The response identifier column is named `ResponseId`. The parser skips rows without a value in that column.
- Question identifiers remain available through the `ImportId` row, question metadata, or recognizable question column names. Removing them can prevent the parser from identifying question fields.
- You are using a response export as input to `build`, rather than a normalized entity CSV such as `responses.csv`.

Try a fresh export before editing the file by hand. See [parse exports](../guides/parse-exports.md) for expected inputs.

### The API downloaded a ZIP

`api export` requests compressed CSV by default. Pass the resulting ZIP directly:

```bash
uv run --extra cli --extra ui qualtrics build data/SV_EXAMPLE.zip \
  --qsf data/SV_EXAMPLE.qsf \
  --output output/example/entities
```

The ZIP must contain exactly one CSV, excluding macOS metadata entries. For `Qualtrics response ZIP must contain exactly one CSV`, extract the intended response CSV and pass that file. For `Invalid Qualtrics response ZIP`, check that you downloaded a complete ZIP file.

Use a `.zip` filename for compressed output. Passing `--output data/export.csv` to `api export` changes the filename, not the content. Rename that compressed file to `.zip` or extract its CSV. Directory input to `build` discovers only `*.csv`; pass ZIP paths explicitly.

## Questions, labels, or answer options are missing

A CSV can contain response values without the definition needed to interpret their question types and available choices. Supply the matching QSF or API definition JSON:

```bash
uv run --extra cli --extra ui qualtrics build data/customer.csv \
  --qsf data/customer.qsf \
  --output output/customer-rebuilt/entities
```

Without `--qsf`, the parser searches beside the input for a same-stem `.qsf`, then `.json`, ignoring filename case. `customer.csv` pairs with `customer.qsf`; it does not auto-discover `customer-definition.qsf`.

For multiple explicit inputs, definitions pair **by position**. Pass files in corresponding order, or place each definition next to its response export with the same filename stem. A single QSF cannot serve multiple CSVs. Directory discovery only includes `*.qsf`; pass definition JSON files explicitly or use same-stem discovery.

Use the definition that matches the exported survey version. Definitions from another survey or a changed question structure can produce missing or incorrect labels and domains. Rebuild the entities after correcting the pairing.

## An answer has no `answer_option_id`

This can be expected. Free text and numeric fields do not need choice options. For categorical answers, the parser matches a value against the field's choice IDs, labels, recodes, and export tags. Matching ignores case. It leaves `answer_option_id` null when the value matches no option or more than one option, and retains the original `answer_text`.

Compare the answer's `question_field_id` with the rows in `answer_options` for that field. Inspect `answer_external_id`, `answer_code`, `answer_text`, and `answer_export_tag`. Duplicate labels or a recode that conflicts with another option's ID can make a value ambiguous. Check the QSF version and export settings before rebuilding.

For exported multi-select fields that each represent a single defined choice, a nonempty value selects that field's choice. Do not treat those fields as a single shared list of labels.

The parser does not invent choices from observed response values. `answer_options` describes choices from the definition for supported exported fields, including choices with no responses. See [your data](../understand/your-data.md) and the [entity model](../entity-model.md).

## A command requests the CLI or UI extra

The base Python package includes the SDK and data functions. The command-line interface and report rendering are separate extras. For command-line reports in a package environment, install both:

```bash
python -m pip install 'qualtrics[cli,ui]'
```

From the repository, run `uv sync --extra cli --extra ui`. API and data commands need only `cli`; reports called directly from Python need only `ui`. A CLI-only installation can still show `qualtrics report --help`, but generating HTML requires `ui`.

## Parquet fails with `Install qualtrics[parquet]`

Install the optional dependency in the environment that runs the command:

```bash
uv sync --extra cli --extra ui --extra parquet
```

For an existing package environment:

```bash
python -m pip install 'qualtrics[parquet]'
```

Or select `--format json` or `--format csv` when writing. Reading existing Parquet files still needs the dependency. A fresh entity folder in JSON or CSV lets you use the full offline workflow without Parquet.

## The output already contains files

**Messages:** `output already contains entity files` or `output already contains semantic tables`.

`entities combine` and `semantic-model build` refuse to overwrite recognized output tables, even when the existing files use another format. Choose a new destination:

```bash
uv run --extra cli --extra ui qualtrics semantic-model build output/customer/entities \
  --output output/customer/semantic-v2 --format csv
```

`build`, Python writers, and `report` overwrite their matching target files. Writing a second format into the same entity directory leaves both versions behind. Use one directory per format.

For a report error mentioning a missing output path, create the parent directory before running `report`. The renderer writes the file but does not create its parent folders.

## The toolkit cannot find an entity collection

**Message:** `no entity files or survey entity folders found under ...`.

`report --folder` and `entities combine` recognize entity files in the supplied folder, in its `entities/` child, or in each immediate child's `entities/` folder. They do not search deeper. Point the command at the actual entity folder if your layout differs.

`semantic-model build` requires the entity folder itself:

```bash
uv run --extra cli --extra ui qualtrics semantic-model build output/customer/entities \
  --output output/customer/semantic --format json
```

## An entity folder is incomplete or has multiple formats

**Messages:** `missing entity files`, `Incomplete strict entity contract`, `Multiple formats found`, or `has multiple formats for entities`.

A complete collection contains all nine entity files, including `sections`, even when some tables have no rows. Use the collection that `build` writes. An HTML report or a semantic model folder is not an entity collection.

Keep exactly one file per entity name: for example, `surveys.json` or `surveys.csv`, not both in the same folder. Store alternative formats in separate folders. An explicit report file override does not bypass the loader's multiple-format check on its folder.

### Older entity files fail current validation

**Messages:** missing `question_field_id`, `answer_order`, or other required columns; mismatched lineage; invalid parent references.

Rebuild from the original response exports and their matching definitions using the installed version:

```bash
uv run --extra cli --extra ui qualtrics build data/customer.csv \
  --qsf data/customer.qsf \
  --output output/customer-current/entities
uv run --extra cli --extra ui qualtrics semantic-model build output/customer-current/entities \
  --output output/customer-current/semantic --format csv
```

Current validation checks the schema of empty tables as well as populated rows. Adding empty files or renaming an old column will not reconstruct identities, option domains, or relationships. Keep the old collection for comparison and regenerate the full set. The [entity contract](../entity-model.md) and [DBML schema](../entity-model.dbml) define the current structure.

## Combining fails with duplicate survey IDs

**Message:** `Duplicate survey_id values: ...`.

Combining supports distinct surveys, not successive exports of the same survey. Check for duplicate copies of an export, a QSF paired with the wrong CSV, or several definitions carrying the same `SurveyID`.

When a standalone input has no definition, the parser uses its filename stem as the survey ID. Distinct surveys with the same input filename may therefore need explicit IDs when you build them one at a time. Use `--survey-id` only when it represents the intended survey identity; changing IDs to append duplicate exports would count those responses again.

For a catalog collision, rebuild all inputs with the same current package version and matching definitions, then try a new combined output folder. See [combine surveys](../guides/combine-surveys.md).

## API credentials or requests fail

| Symptom | Next step |
| --- | --- |
| `api_token is required` | Set `QUALTRICS_API_TOKEN`, or put the token and connection setting together in the current directory's `.env`. Check the CLI mixed-source caveat in [configuration](../reference/configuration.md#cli-overrides). |
| `provide data_center or base_url` | Supply `QUALTRICS_DATA_CENTER` or a complete `QUALTRICS_BASE_URL`. |
| Changing the data center does not change the destination | Check `QUALTRICS_BASE_URL` in the environment and `.env`; a base URL takes precedence. |
| HTTP error from Qualtrics | Read the returned message. Check the token, account data center, survey ID, and the token's access to that survey. In Python, retain the exception's `status_code` and `request_id` for investigation. |
| Import or export did not finish within 900 seconds | With Python, check the existing job's progress by its `progress_id`; polling methods accept a longer timeout. Check import progress before uploading the same data again. |
| Connection timeout or transport error | Check network access to the configured API URL. Python HTTP requests use a 30-second timeout by default; import/export polling has a separate timeout. |

Use [API access](../guides/api-access.md) for the working workflow and the [Python reference](../reference/python.md#errors) for exception types.

## Report totals differ from your expectations

A response is one respondent record; an answer is one nonempty exported field value. Multi-part questions and multi-select exports can contribute several answers per response. Blank cells do not produce answer rows. Browser metadata fields populate response metadata instead of answer rows.

Check the report's survey selection and filters, then compare its totals with `responses` and `response_answers`. Use [create reports](../guides/reports.md) for report controls and the [glossary](../understand/glossary.md) for data terms. For Power BI, follow the [documented relationships](../guides/power-bi.md) to avoid multiplying rows in joins.
