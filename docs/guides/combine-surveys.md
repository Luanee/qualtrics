# Combine surveys

Combine parsed tables from different surveys into one collection. Use that collection for a shared report or a Power BI model.

You need at least two complete entity folders, with one file format per table. Current exports contain [ten entity files](../understand/your-data.md); older folders with the nine authoritative tables and no `comments` file are also accepted. Run the examples from the installed project folder; for an isolated CLI installation, replace `uv run --extra cli --extra ui qualtrics` with `qualtrics`.

## 1. Check which surveys you are combining

Use separate inputs for separate surveys, for example:

```text
data/
├── survey-a/entities/
│   └── ... ten entity files ...
└── survey-b/entities/
    └── ... ten entity files ...
```

The command rejects repeated `survey_id` values. It cannot append two response exports from the same survey or decide which response version to keep. To refresh one survey, rebuild its entity folder from the export you want to use.

Keep each input's table filenames intact. You may combine a CSV collection with a JSON or Parquet collection, but two formats for the same table in one folder are ambiguous.

## 2. Write a combined collection

Choose a new output folder, then run:

```text
uv run --extra cli --extra ui --extra parquet qualtrics entities combine data/survey-a/entities data/survey-b/entities --output data/combined/entities --format parquet
```

Parquet is the default for this command and requires the optional dependency from the [installation guide](../getting-started/installation.md). To produce tables for a spreadsheet, use a separate output path:

```text
uv run --extra cli --extra ui qualtrics entities combine data/survey-a/entities data/survey-b/entities --output data/combined-csv/entities --format csv
```

The command creates the output folder. It refuses an output location that already contains recognized entity files in CSV, JSON, or Parquet format. For a later run, choose a new folder such as `data/combined-v2/entities`.

You should see a message such as:

```text
Combined 2 survey(s) as parquet entities in data/combined/entities
```

## 3. Check the combined result

Generate a report:

```text
uv run --extra cli --extra ui --extra parquet qualtrics report --folder data/combined/entities --output data/combined/report.html
```

Open the HTML file and use **Surveys** to inspect each source survey. Check its response count against its individual report, then select all surveys to review the combined total.

The combined tables retain each survey's own questions, fields, and options. The two catalog tables group questions and fields that have matching normalized definitions across surveys. Similar-looking wording alone does not guarantee that two questions share a catalog entry, and shared entries do not establish that the survey populations are comparable. See [understand your data](../understand/your-data.md).

The combined `comments` table is regenerated from the original answer and response rows. Identical text from different responses remains separate, and each comment keeps its response's language or null. Comments still belong to `response_answers`; the derived table does not add responses or answers to your totals.

The `responses` table contains the union of response-property columns. If survey A exports `Region` and survey B exports `Country`, the combined table has both; a property absent from a survey is null for its responses. Original collections are unchanged. The codebook records any renamed columns needed to distinguish duplicate names, names that differ only by case, or names that collide with built-in response fields. Check this mapping before combining similarly named fields in an analysis.

## Use survey folders or a batch root

You can pass survey folders containing `entities/`:

```text
uv run --extra cli --extra ui --extra parquet qualtrics entities combine data/survey-a data/survey-b --output data/combined-v2/entities --format parquet
```

You can also pass the root created by the [API export example](api-access.md):

```text
data/api-export/
├── SV_123/entities/
└── SV_456/entities/
```

```text
uv run --extra cli --extra ui --extra parquet qualtrics entities combine data/api-export --output data/api-combined/entities --format parquet
```

Discovery checks the folder itself, its `entities/` subfolder, then immediate child folders containing `entities/`. It does not search through arbitrary nested directories. Put the output outside the input batch root so a later run does not discover it as another input.

For missing files, duplicate surveys, or incompatible older tables, see [troubleshooting](../help/troubleshooting.md). Continue with [Power BI export](power-bi.md) to build analysis tables from the combined collection.
