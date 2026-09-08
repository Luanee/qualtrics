# Prepare data for Power BI

Export five analysis tables from your parsed survey data, then connect them in Power BI. You can follow the export steps on any supported operating system; the import steps use Power BI Desktop.

You need the [installed project with Parquet support](../getting-started/installation.md) and a complete entity folder. The commands below use the folder from [your first report](../getting-started/first-report.md). Run them from the project folder; for an isolated CLI installation, replace `uv run qualtrics` with `qualtrics`.

## 1. Export the analysis tables

```text
uv run qualtrics semantic-model build data/first-report/entities --output data/first-report/power-bi --format parquet
```

The command checks the input collection and creates these files:

```text
data/first-report/power-bi/
├── fact_responses.parquet
├── fact_response_answers.parquet
├── dim_surveys.parquet
├── dim_questions.parquet
└── dim_answer_options.parquet
```

You should see `Wrote 5 parquet semantic tables to data/first-report/power-bi`.

Parquet is this command's default. For CSV output, use `--format csv` and a separate output folder such as `data/first-report/power-bi-csv`. The command refuses an output folder that already contains recognized semantic table files. Choose a fresh folder for a later export.

The input must be the folder containing the nine entity files. To prepare several surveys, [combine their entities](combine-surveys.md) first and use the combined entity folder as input.

## 2. Understand the five tables

A **fact table** holds the records you count or measure. A **dimension table** describes those records and supplies labels and filters.

| Table | One row represents… | Example use |
| --- | --- | --- |
| `fact_responses` | One survey response, including its available response metadata. | Count responses; filter by survey, date, or language. |
| `fact_response_answers` | One non-empty exported answer field. | Count answer rows or average a numeric answer. |
| `dim_surveys` | One survey. | Display survey names. |
| `dim_questions` | One exported question field, with its question and block details. | Label and filter the exact field you want to analyze. |
| `dim_answer_options` | One choice defined for one question field. | Show choice labels and definition order, including unused choices. |

A matrix question can have several fields, so it can have several rows in `dim_questions`. The same label, such as “Yes”, can appear in many option rows because each belongs to a particular field. Use the IDs to relate tables; do not join them by answer text.

If you parsed without a QSF, you will have no definition-based option records. Rebuild with the matching QSF if you need a complete choice list. See the [entity and semantic model contract](../entity-model.md) and [DBML file](../entity-model.dbml) for column and identity details.

## 3. Load each table into Power BI

1. In Power BI Desktop, open **Get data** and choose **Parquet**.
2. Enter the full local path to `fact_responses.parquet`, then load it or choose **Transform Data** to inspect it.
3. Repeat for the other four files. Keep the table names shown above so the measure examples work.
4. In Power Query, check column types. Keep IDs as text; use a decimal type for `answer_numeric` and a date/time type for timestamps such as `recorded_at`. The export writes timestamp columns as text, including in Parquet.
5. Apply the changes and open the model view to inspect relationships.

Microsoft documents the file connection in its [Parquet connector guide](https://learn.microsoft.com/en-us/power-query/connectors/parquet). For CSV exports, choose **Text/CSV** and load each file as a separate table; see the [Text/CSV connector guide](https://learn.microsoft.com/en-us/power-query/connectors/text-csv).

## 4. Create the relationships

Create these four **active**, **one-to-many** relationships. Set cross-filter direction to **Single**, from the table on the left to the table on the right. Inspect any relationships Power BI detected before adding yours.

| One side | Many side |
| --- | --- |
| `dim_surveys[survey_id]` | `fact_responses[survey_id]` |
| `fact_responses[response_id]` | `fact_response_answers[response_id]` |
| `dim_questions[question_field_id]` | `fact_response_answers[question_field_id]` |
| `dim_answer_options[answer_option_id]` | `fact_response_answers[answer_option_id]` |

A survey filter reaches responses, then their answers. Question and option filters reach the answer table. Keep this single route from surveys to answers; additional active routes can make filter behavior ambiguous. See [Microsoft's relationship explanation](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand) for the Power BI settings.

`dim_answer_options.question_field_id` tells you which field owns an option. Keep the relationship to the answer fact on `answer_option_id`. When presenting a field's full choice list, use `question_field_id` to restrict the option list to that field, including choices with zero answers.

For a date slicer, create a date table in your Power BI model. Convert `recorded_at` to a date for a daily relationship, or derive a separate date-only column from it; relate that column to the date table. Use the original timestamp when you need time-of-day analysis.

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

The answer table excludes empty fields. Use `Responses` when you need the number of survey response records; counting rows in the answer table would count a person several times and omit people with no answers in the selected fields.

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
| Respondents with a satisfaction answer | 3 |
| Respondents with a comment | 2 |
| Comment response rate | 2 ÷ 3, about 66.7% |
| Defined satisfaction options | 3, including Neutral with zero observed answers |

Keep a survey or question-field filter in place when comparing choice labels. Two choices with the same text can belong to different fields or surveys.

For missing tables, older entity formats, or output-folder errors, see [troubleshooting](../help/troubleshooting.md).
