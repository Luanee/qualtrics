# Parse existing exports

Convert a Qualtrics response CSV or response-export ZIP into ten related tables. You can then generate a report, combine different surveys, or prepare a Power BI model.

You need the [installed project](../getting-started/installation.md), a response export, and, if available, its matching survey definition (`.qsf`). Run the commands from the `qualtrics` project folder. If you installed only the CLI, replace `uv run --extra cli --extra ui qualtrics` with `qualtrics`.

## 1. Prepare the files

Create a folder such as `data/my-survey` with your file manager. Place your export and definition there:

```text
data/my-survey/
├── responses.csv
└── definition.qsf
```

Use the original Qualtrics CSV export. Keep its header rows intact: field names, question text, and the metadata row containing values such as `{"ImportId":"QID1"}`. Saving a cleaned spreadsheet over the export can remove information the parser needs to identify questions and fields.

A QSF describes the survey. It supplies question types, blocks, and the complete set of answer choices, including choices nobody selected. Without a QSF, you can parse the export, but `answer_options` will be empty and some question details will be unavailable.

## 2. Choose an output format

| Format | Choose it when you want to… | Extra dependency |
| --- | --- | --- |
| `csv` | Open the tables in a spreadsheet or inspect them as text. | None |
| `json` | Read structured records or pass them to another program. This is the `build` default. | None |
| `parquet` | Store typed tables for an analysis tool or data platform. | Install with `--extra parquet` as in the setup guide. |

The report command reads all three formats. Use one format per entity folder.

## 3. Parse the export

For the file layout above:

```text
uv run --extra cli --extra ui qualtrics build data/my-survey/responses.csv --qsf data/my-survey/definition.qsf --output data/my-survey/entities --format csv
```

For a ZIP export, replace the input filename:

```text
uv run --extra cli --extra ui qualtrics build data/my-survey/export.zip --qsf data/my-survey/definition.qsf --output data/my-survey/entities --format csv
```

The ZIP must contain exactly one CSV response file. You do not need to extract it first.

To parse without a definition, omit `--qsf`:

```text
uv run --extra cli --extra ui qualtrics build data/my-survey/responses.csv --output data/my-survey/entities-without-definition --format csv
```

The parser still looks for a definition with the same filename stem in the same folder. For example, it pairs `feedback.csv` or `feedback.zip` with `feedback.qsf`; it also recognizes a matching `.json` definition. An explicit `--qsf` path removes any uncertainty about the pairing.

## 4. Check the output

Look for a success message naming the survey count, format, and destination. Open the output folder and confirm it contains the [ten entity files](../understand/your-data.md). Some tables can contain no records, but the parser still writes their files.

Generate a report to check the response count, question labels, and defined choices:

```text
uv run --extra cli --extra ui qualtrics report --folder data/my-survey/entities --output data/my-survey/report.html
```

Open `data/my-survey/report.html` in your browser. See [read and share reports](reports.md) for the controls and count definitions.

In **Responses**, expand **Response properties** to check embedded fields such as region, country, and permissions alongside standard response metadata. **Codebook** explains which source columns became question answers or response properties, why they were classified that way, and where their values are stored. Unknown columns are preserved as unclassified properties.

## Parse several different surveys

For a small set of surveys, list each response file and each matching QSF in the same order:

```text
uv run --extra cli --extra ui qualtrics build data/survey-a/responses.csv data/survey-b/responses.csv --qsf data/survey-a/definition.qsf --qsf data/survey-b/definition.qsf --output data/combined/entities --format csv
```

Each survey must have a distinct survey identity. The parser rejects two inputs with the same survey ID. You cannot apply one QSF to several survey files.

You can also pass a folder to `build`. The CLI reads the `.csv` files directly inside that folder; it does not walk through nested folders or discover ZIP files there. For nested survey folders, process each export first, then [combine their entity folders](combine-surveys.md).

## Rebuild after changing the input

Keep your raw CSV or ZIP and its QSF. Rerun `build` when the export or definition changes, then rerun `report`.

To recover response properties omitted by an older parser, rebuild from the original export with the matching QSF using the commands above. Regenerating HTML from an old entity folder cannot recover discarded values. Existing entity folders remain readable, but their codebooks may lack the new source-column dictionary.

`build` replaces the entity files of the selected format. If you change formats, choose a new output folder; old files in another format remain and can make later commands reject the collection as ambiguous.

Without a definition, the parser uses the input filename stem as the source survey identity. For one input file, you can supply a stable identity with `--survey-id SV_123`; replace `SV_123` with your survey's actual ID. Keep that choice consistent across rebuilds.

For missing headers, options, or files, see [troubleshooting](../help/troubleshooting.md). The [CLI reference](../reference/cli.md) lists the complete command options.
