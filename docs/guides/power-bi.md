# Prepare data for Power BI

Export nine analysis and display-label tables as Parquet files or one SQLite database, then connect the tables you need in Power BI. You can follow the export steps on any supported operating system; the import steps use Power BI Desktop.

You need the [installed project](../getting-started/installation.md) and a complete entity folder. The base package supports Parquet and SQLite output. The commands below use the folder from [your first report](../getting-started/first-report.md). Run them from the project folder; for an isolated CLI installation, replace `uv run --extra cli --extra ui qualtrics` with `qualtrics`.

## 1. Export the analysis tables

### Parquet files (default)

```text
uv run --extra cli --extra ui qualtrics semantic-model build data/first-report/entities --output data/first-report/power-bi --format parquet
```

The command checks the input collection and creates these files:

```text
data/first-report/power-bi/
├── fact_responses.parquet
├── fact_response_answers.parquet
├── dim_surveys.parquet
├── dim_questions.parquet
├── dim_answer_options.parquet
├── fact_comments.parquet
├── dim_display_languages.parquet
├── dim_question_labels.parquet
├── dim_answer_option_labels.parquet
└── manifest.json
```

You should see `Wrote 9 parquet semantic tables to data/first-report/power-bi`.

### SQLite database

To keep all nine tables in one file, choose SQLite:

```text
uv run --extra cli --extra ui qualtrics semantic-model build data/first-report/entities --output data/first-report/power-bi-sqlite --format sqlite
```

This creates `data/first-report/power-bi-sqlite/semantic_model.sqlite` and a sibling `manifest.json`. The `--output` value is a directory for both formats. The database contains the same tables, columns, and identifiers as the Parquet export, including the schema for tables with no rows. Numeric answers use `REAL`, booleans use `INTEGER` values `0` and `1`, and IDs and timestamps remain text. Missing values are SQL `NULL`.

The command refuses an output folder that already contains recognized semantic table files or `semantic_model.sqlite`. Choose a fresh folder for a later export. SQLite writes complete before the final database appears; a failed build does not leave a partial database. CSV and JSON remain available with `--format csv` or `--format json`.

The input must be a complete entity folder: nine core tables, derived `comments`, and `manifest.json`. Prepared translation columns, when present, are stored on `comments` rather than in another table. To prepare several surveys, [combine their entities](combine-surveys.md) first. The manifest keeps flow, source-column, and language descriptors for each survey ID; it is not a semantic table.

## 2. Understand the nine tables

A **fact table** holds the records you count or measure. A **dimension table** describes those records and supplies labels and filters.

| Table | One row represents… | Example use |
| --- | --- | --- |
| `fact_responses` | One survey response, including its available response metadata. | Count responses; filter by survey, date, or language. |
| `fact_response_answers` | One non-empty exported answer field. | Count answer rows or average a numeric answer. |
| `dim_surveys` | One survey. | Display survey names. |
| `dim_questions` | One exported base-language question field, with its question and block details. | Label and filter the exact field you want to analyze without multiplying answer facts by language. |
| `dim_answer_options` | One choice defined for one question field. | Show choice labels and definition order, including unused choices. |
| `fact_comments` | One nonblank text answer field, with optional prepared target-language columns. | Read original or current translated comments without multiplying rows. |
| `dim_display_languages` | One display-language code across the combined model. | Populate a single-select label-language slicer. |
| `dim_question_labels` | One exported base question field × display language. | Show translated question and field labels with base fallback. |
| `dim_answer_option_labels` | One exported base option × display language. | Show translated choice labels without changing option IDs. |

A matrix question can have several fields, so it can have several rows in `dim_questions`. The same label, such as “Yes”, can appear in many option rows because each belongs to a particular field. Use the IDs to relate tables; do not join them by answer text.

QSF-only questions stay in the entity codebook. They have no answer facts and are excluded from the active `dim_questions` and `dim_answer_options` tables; do not interpret them as questions that respondents saw and skipped. Localized label tables likewise contain only exported base fields and options.

`fact_comments` contains the same text answers already present in `fact_response_answers`. It reuses each `response_answer_id` and keeps `answer_text` and available `raw_value` unchanged. Two matching comments remain two records; multiple text boxes in one response remain separate. Do not append the subset to all answers or add their row counts together.

For each prepared target, `fact_comments` adds `translated_text__CODE`, `translation_source_hash__CODE`, `translation_source_language__CODE`, and `translation_is_current__CODE`. For example, English adds `__EN`. The last field verifies both the original-text hash and respondent-language lineage. Null or stale targets fall back to `answer_text`. No callback means no prepared target columns.

Comment membership follows the report's **Written answers** view. Supported text-entry, form, matrix-text, and attached “Other” text fields qualify; choice labels, numeric fields, response properties, and whitespace-only cells do not. `dim_questions.is_comment_field` records nullable classification evidence on new exports. Older folders fall back to their available types; incomplete side-by-side metadata is not guessed from labels. See [the comments contract](../entity-model.md#comments) for scope and compatibility.

`fact_comments.user_language` copies the code on the linked response. It stays null if that response has no language, even when a survey default exists. It does not detect the language of the text. For a slicer that filters both answers and comments, use `fact_responses.user_language`; use the comment copy to display the code beside its text.

Response properties are additional columns in `fact_responses`. For example, if your export contains embedded `Department`, `Region`, or `Country` values, use those columns in slicers or chart axes. With the relationships below, selecting `Department = Sales` filters those responses and their question answers. There is no extra property table to join. Custom values remain text, including numeric-looking codes and permission flags; choose analytical types deliberately in Power Query.

The report's codebook shows each original source name and its actual storage column. A name can be changed to prevent collisions with built-in columns or other source fields. A property missing from one survey is null in the combined table. A real question about department stays in the answer table; its name alone does not turn it into response metadata.

If you parsed without a QSF, you will have no definition-based option records. Rebuild with the matching QSF if you need a complete choice list. See the [entity and semantic model contract](../entity-model.md) and [Power BI DBML file](../power-bi-model.dbml) for column and identity details.

## 3. Load each table into Power BI

### From Parquet

1. In Power BI Desktop, open **Get data** and choose **Parquet**.
2. Enter the full local path to `fact_responses.parquet`, then load it or choose **Transform Data** to inspect it.
3. Repeat for the other eight files. Keep the table names shown above so the measure examples work.

Microsoft documents the file connection in its [Parquet connector guide](https://learn.microsoft.com/en-us/power-query/connectors/parquet).

### From SQLite through ODBC

Power BI uses an ODBC connection for this workflow. The toolkit creates the SQLite database; it does not install an ODBC driver.

1. Install a SQLite ODBC driver compatible with your Power BI Desktop installation and configure a data source name (DSN) pointing to the full path of `semantic_model.sqlite`. Follow your driver's instructions in Windows ODBC Data Source Administrator.
2. In Power BI Desktop, choose **Get data → ODBC** and select that DSN.
3. In Navigator, select the tables you need, then choose **Transform Data** or **Load**.

See Microsoft's [ODBC connector guide](https://learn.microsoft.com/en-us/power-query/connectors/odbc) for the connection and authentication options. If you prefer to avoid installing a database driver, use the Parquet files.

### Check types in either format

In Power Query, keep IDs as text; use a decimal type for `answer_numeric` and a date/time type for timestamps such as `recorded_at`. Both formats export timestamps as text. For SQLite, convert `answer_boolean`, `is_selected`, and `is_text_field` from `0`/`1` to the True/False type if needed. Keep null values as null. Apply the changes and open the model view to inspect relationships.

## 4. Create the relationships

Explore the nine exported tables below. The diagram's relationship symbols describe one-to-many cardinality; configure Power BI's cross-filter direction separately as explained below. The viewer needs an internet connection and requires no account or API key.

<iframe class="dbml-model" title="Nine-table Power BI semantic model" src="{{ dbml_power_bi_url }}" loading="lazy" referrerpolicy="no-referrer" allowfullscreen></iframe>

<p><a href="{{ dbml_power_bi_url }}" target="_blank" rel="noopener">Open the Power BI diagram at full size</a></p>

[Download the Power BI DBML schema](../power-bi-model.dbml) for a compatible schema tool. If the viewer cannot load, use the relationship table and instructions below.

Create these six **active**, **one-to-many** relationships. Set cross-filter direction to **Single**, from the table on the left to the table on the right. Inspect any relationships Power BI detected before adding yours.

| One side | Many side |
| --- | --- |
| `dim_surveys[survey_id]` | `fact_responses[survey_id]` |
| `fact_responses[response_id]` | `fact_response_answers[response_id]` |
| `dim_questions[question_field_id]` | `fact_response_answers[question_field_id]` |
| `dim_answer_options[answer_option_id]` | `fact_response_answers[answer_option_id]` |
| `fact_responses[response_id]` | `fact_comments[response_id]` |
| `dim_questions[question_field_id]` | `fact_comments[question_field_id]` |

A survey filter reaches responses, then both answer tables. Question filters reach both answer tables; option filters reach only `fact_response_answers`. Keep this single route from surveys to each answer table; additional active routes can make filter behavior ambiguous. Do not join `fact_response_answers` to `fact_comments`, or create a direct active `dim_surveys` → `fact_comments` relationship. See [Microsoft's relationship explanation](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand) for the Power BI settings.

Create two additional **label-only** relationships: `dim_display_languages[language_code]` → `dim_question_labels[language_code]` and `dim_display_languages[language_code]` → `dim_answer_option_labels[language_code]`. Both are one-to-many, active, and Single direction. Do **not** relate either label table directly to a fact table or to the active question/option dimensions: its ID columns are lookup keys used by measures, not new fact paths.

`dim_answer_options.question_field_id` tells you which field owns an option. Keep the relationship to the answer fact on `answer_option_id`. When presenting a field's full choice list, use `question_field_id` to restrict the option list to that field, including choices with zero answers.

New exports keep `source_choice_id`, `choice_value`, `recode_value`, `variable_name`, and `value` on `dim_answer_options`. Use `choice_value` for the respondent-visible label; `variable_name` records a configured multiple-choice export label when available. `recode_value` contains only explicit definition metadata, while `value` uses that recode or falls back to the choice text. These remain text columns, so `0` and `02` keep their source representation. Convert types deliberately for a particular analysis.

`fact_response_answers.raw_value` is the exact original CSV cell. For an option with native ID `1`, label `Yes`, and recode `2`, numeric `2` and label `Yes` can both link to the same `answer_option_id`. A configured export label can differ from both. Do not create a `raw_value` → `value` relationship: raw labels need not equal the normalized value, and duplicate recodes or values from different fields are not unique keys. The parser gives explicit recodes priority and leaves ambiguous links null.

Older entity folders can lack these provenance columns. Do not treat `answer_code` as evidence of an explicit recode; it may be a native-ID fallback. Reparse the original CSV/ZIP with the matching QSF and rebuild the semantic model when you need the additional metadata. See [answer value provenance](../entity-model.md#answer-value-provenance) for defaults and matrix scope.

For a date slicer, create a date table in your Power BI model; it is not one of the exported tables. Convert `recorded_at` to a date for a daily relationship, or derive a separate date-only column from it; relate that column to the date table. Use the original timestamp when you need time-of-day analysis.

### Display-language recipe

Use **two different slicers**: `fact_responses[user_language]` filters respondents and therefore changes all measures; `dim_display_languages[language_code]` changes labels only. Make the latter single-select and filter `dim_display_languages[is_available]` to True for the default picker. This includes codes with prepared comment translations even when the QSF has no labels for that code; those labels fall back to the survey's base language. Extra codes found only inside question translations remain in the table and can be exposed deliberately. Every base field and option has a label row for every display code across combined surveys; when a survey lacks that translation, the row uses its base label and records that fallback in `*_source_language`.

For a table or matrix keyed by one base field, this measure returns the selected question label without changing fact relationships:

```dax
Displayed Question =
VAR FieldId = SELECTEDVALUE(dim_questions[question_field_id])
VAR Language = SELECTEDVALUE(dim_display_languages[language_code])
RETURN COALESCE(
    LOOKUPVALUE(
        dim_question_labels[question_text],
        dim_question_labels[question_field_id], FieldId,
        dim_question_labels[language_code], Language
    ),
    SELECTEDVALUE(dim_questions[question_text])
)
```

Use the same pattern for `dim_question_labels[field_text]` and `dim_answer_option_labels[answer_text]`, looking up by base `question_field_id` or `answer_option_id`. For a chart axis built from `dim_answer_option_labels[answer_text]`, apply the axis's base IDs to the existing option dimension inside the measure:

When a label's `question_label_source_language`, `field_label_source_language`, or `label_source_language` differs from the selected display code, show an “Original · SOURCE” cue beside it. These source-language fields record both missing and stale prepared-label fallbacks; the exported label already contains the safe base text.

```dax
Localized Answer Rows =
CALCULATE(
    [Answer Rows],
    TREATAS(
        VALUES(dim_answer_option_labels[answer_option_id]),
        dim_answer_options[answer_option_id]
    )
)
```

This is a display measure, not a new relationship. Keep one display language selected so the axis has one label row per option. The respondent-language slicer remains independent: selecting German respondents never rewrites their raw answer text, and switching the display to French never changes answer counts. The [Microsoft DAX references for `SELECTEDVALUE`](https://learn.microsoft.com/en-us/dax/selectedvalue-function-dax) and [`LOOKUPVALUE`](https://learn.microsoft.com/en-us/dax/lookupvalue-function-dax) explain the single-selection and exact-key lookup behavior.

### Prepared written-answer translations

Prepared text lives on the same `fact_comments` row as its original. There is no translation lookup or extra relationship. In a table visual with one `response_answer_id` per row, use the display-language slicer and the freshness flag. This example assumes English (`__EN`) was prepared:

```dax
Displayed Comment =
VAR Original = SELECTEDVALUE(fact_comments[answer_text])
VAR Source = SELECTEDVALUE(fact_comments[user_language])
VAR Target = SELECTEDVALUE(dim_display_languages[language_code])
RETURN
    IF(
        Target = "EN" && Target <> Source
            && SELECTEDVALUE(fact_comments[translation_is_current__EN]) = TRUE(),
        COALESCE(SELECTEDVALUE(fact_comments[translated_text__EN]), Original),
        Original
    )
```

For another prepared language, add a `SWITCH` arm using that language's four columns; DAX cannot select a physical column by a string variable. Keep `fact_comments[answer_text]` for audit or drill-through. If `translation_is_current__EN` is False, show a visible “translation out of date” cue; if the target column is absent or null, show “translation unavailable.” Convert SQLite's `0`/`1` freshness values to Boolean in Power Query.

## 5. Add measures with the right denominator

Create each measure below as a separate Power BI measure:

```dax
Responses = DISTINCTCOUNT(fact_responses[response_id])
```

```dax
Respondents With Answer = DISTINCTCOUNT(fact_response_answers[response_id])
```

```dax
Answer Rows = COUNTROWS(fact_response_answers)
```

```dax
Comment Rows = COUNTROWS(fact_comments)
```

```dax
Responses With Comment = DISTINCTCOUNT(fact_comments[response_id])
```

The answer table excludes empty fields. Use `Responses` when you need the number of survey response records; counting rows in the answer table would count a person several times and omit people with no answers in the selected fields. `Comment Rows` counts text fields; `Responses With Comment` counts submissions with at least one qualifying text field. Both are already included in the all-answer measures.

Under the single-direction relationships above, a question filter does not filter `fact_responses`. For a report spanning multiple surveys, use a denominator limited to the surveys of the selected questions:

```dax
Question-scoped Responses =
CALCULATE(
    [Responses],
    TREATAS(VALUES(dim_questions[survey_id]), fact_responses[survey_id])
)
```

```dax
Question Response Rate =
DIVIDE([Respondents With Answer], [Question-scoped Responses])
```

Format `Question Response Rate` as a percentage. This measures the share of response records with an answer in the selected question fields. With several fields selected, a response counts in the numerator if it has an answer to any of them. The denominator includes the relevant surveys' response records even if branching skipped the question. It does not measure the proportion of invited people who responded, or the proportion eligible to see the question.

For the selected comment field or fields, use:

```dax
Comment Response Rate =
DIVIDE([Responses With Comment], [Question-scoped Responses])
```

This rate uses the same survey-scoped denominator and routing caveat. Filter to the intended text fields with `dim_questions`; a submission with several comments counts once in its numerator.

For a numeric field, filter to that field before using:

```dax
Numeric Answer Average = AVERAGE(fact_response_answers[answer_numeric])
```

## 6. Check the example numbers

With the first-report sample, confirm:

| Check | Expected value |
| --- | --- |
| All responses | 3 |
| All answer rows | 5 |
| Comment rows (already included in all answers) | 2 |
| Respondents with a satisfaction answer | 3 |
| Respondents with a comment | 2 |
| Comment response rate | 2 ÷ 3, about 66.7% |
| Defined satisfaction options | 3, including Neutral with zero observed answers |

Keep a survey or question-field filter in place when comparing choice labels. Two choices with the same text can belong to different fields or surveys.

For missing tables, older entity formats, or output-folder errors, see [troubleshooting](../help/troubleshooting.md).
