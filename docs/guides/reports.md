# Read and share reports

Create one HTML file from a folder of parsed tables. You can open it in a browser, search answers, inspect question patterns, and review individual responses.

You need a parsed entity folder from [your first report](../getting-started/first-report.md) or [your own export](parse-exports.md). Run the examples from the project folder; for an isolated CLI installation, replace `uv run qualtrics` with `qualtrics`.

## Generate the HTML file

```text
uv run qualtrics report --folder data/first-report/entities --output data/first-report/report.html
```

Replace the two paths with your entity folder and desired report location. The output's parent folder must already exist. If an HTML file already exists at that path, the command replaces it.

You should see `Wrote HTML report to ...`. Open the resulting file in your browser. The file contains its styles, scripts, and report content, so the recipient does not need Python or the entity folder to read it.

## Read the report

| Report label | Meaning |
| --- | --- |
| **Responses** | Response records in the selected surveys, including records marked unfinished. |
| **Response questions** | Questions classified as respondent-facing questions in the selected surveys. |
| **Respondent answers** | Response-and-question pairs with at least one answer. A matrix question with several filled fields counts once for that response here. |
| **Finished responses** | Responses whose exported finished flag is `true` or `1`. |
| **Completion rate** | Finished responses divided by all response records in the selected surveys. |
| **Unanswered questions** | Questions with no observed respondent answer in the export. |
| **Unused fields** | Concrete exported fields with no observed respondent value. |

These counts describe the export you provided. They do not count everyone invited to the survey. Completion rate is not the proportion of invited people who participated.

## Inspect questions and data quality

1. Expand **Question coverage** to see how many response records contain an answer to each question.
2. Expand **Question analytics**, then a question, to inspect its field-level distributions, numeric summaries, or text answers.
3. Expand **Data quality** to see fields without values and defined options nobody selected.

Question coverage uses all response records for that survey as its denominator. A skipped question, optional question, or branching rule can lower coverage; low coverage alone does not establish an export error.

With a QSF, the report can show defined choices with zero observations. Without a QSF, it cannot tell you which unselected choices existed. A data-quality flag is a prompt to inspect the source survey and export.

## Review individual responses

Under **By responses**:

- Type in the search box to find response IDs, question text, or answer text.
- Use **Questions** to choose which answers appear within each response.
- Click a response to expand it, or use **Expand all** and **Collapse**.
- Use **Surveys** to choose which surveys appear in a combined report.

The survey selector updates the overview totals. Text search filters the response cards, and the question selector controls the displayed answers; those two controls do not recalculate the overview or question analytics. Search also examines the response's full searchable text, including answers hidden by the question selector.

## Include several surveys

Pass one `--folder` option per input:

```text
uv run qualtrics report --folder data/survey-a/entities --folder data/survey-b/entities --output data/combined-report.html
```

For the batch layout made by the [API example](api-access.md), you can pass its shared root:

```text
uv run qualtrics report --folder data/api-export --output data/api-export/report.html
```

The command discovers immediate `<survey-id>/entities/` folders. It also accepts a survey folder containing `entities/`. Inputs must represent different surveys; overlapping survey IDs cause an error. See [combine surveys](combine-surveys.md) if you also want a combined table collection.

## Share or print a report

Share the HTML file through your usual approved channel. Anyone with the file can read its included answers and response identifiers. Hiding questions or filtering responses in the browser does not remove them from the file, so choose the source data before generating a report for a particular audience.

For a paper or PDF copy, select the surveys and questions you need, expand the relevant sections, and use your browser's **Print** command. Check the print preview before saving or printing.

The report is a snapshot. To include new responses, rebuild the entity folder and regenerate the HTML file.
