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

Use the side navigation to move between five views. On a narrow screen, navigation wraps above the content. The views stay inside one HTML file, so you can move between them without an internet connection.

| View | Use it to |
| --- | --- |
| **Summary** | Read totals and factual highlights, then follow a finding to its supporting question. |
| **Questions** | Find a question by text, section, or identifier and inspect one question at a time. |
| **Written answers** | Search comments, select a question, and open the response behind a comment. |
| **Responses** | Review individual response records and choose which questions to display. |
| **Codebook** | Look up export columns, field types, and answer codes; download the filtered dictionary. |

The **Surveys** selector applies across all views. Moving between views keeps your survey selection. Use your browser's Back and Forward buttons to return to earlier views or question details.

The **Theme** selector in the header offers **System**, **Light**, and **Dark**. System follows your browser's preferred appearance. A manual choice applies until you reload the file.

### Understand the totals

| Report label | Meaning |
| --- | --- |
| **Responses** | Response records in the selected surveys, including records marked unfinished. |
| **Finished** | Responses whose exported finished flag is `true` or `1`. The percentage beside the label is their share of the selected response records. |
| **Not marked finished** | All other response records, including records with no finished flag. This does not establish that each record is a partial response. |
| **Response questions** | Questions classified as respondent-facing questions in the selected surveys. |
| **Respondent answers** | Response-and-question pairs with at least one answer. A matrix question with several filled fields counts once for that response here. |
| **Unanswered questions** | Questions with no observed respondent answer in the export. |
| **Unused fields** | Concrete exported fields with no observed respondent value. |

These counts describe the export you provided. They do not count everyone invited to the survey. The finished share is not the proportion of invited people who participated.

The first three totals appear above the findings. Expand **Coverage and data quality** beneath the findings for the question, answer, unanswered-question, and unused-field totals, followed by the detailed diagnostics.

### Follow a finding to the evidence

Summary highlights describe observed answers, such as the most selected option or a median for a declared numeric field. Each highlight names the question and links to its analysis. Counts and denominators accompany the observations; ties remain explicit. A field containing numeric-looking text, such as an employee ID, stays text.

Treat these highlights as a starting point for reading the charts. They do not infer sentiment, causes, or whether a score is good or bad. Question types without a suitable factual summary remain available under **Questions**.

### Search across the report

Use **Search this report** in the header to find questions, written answers, responses, and codebook fields. Enter several words or an identifier. Results show their type and a highlighted excerpt; select a result to open the matching question, comment, response answer, or dictionary row.

Search matches are case-insensitive and accent-insensitive. Searching changes what you can find, not the population used for statistics. Totals and charts continue to describe the selected surveys.

Results replace the current view while you search. **Clear** restores that view; selecting a view in the sidebar clears the global search and opens it.

Written answers, responses, search results, and codebook rows use page controls. The count shows the full matching total. Filtering resets the page so matches do not remain hidden on a previous page.

## Inspect questions and data quality

1. Open **Questions**, use the question finder, and select a question to inspect its distributions, numeric summaries, or text answers.
2. In **Summary**, expand **Coverage and data quality**, then **Question coverage**, to see how many response records contain an answer to each question.
3. In the same area, expand **Data quality** to see fields without values and defined options nobody selected.

Question coverage uses all response records for that survey as its denominator. A skipped question, optional question, or branching rule can lower coverage; low coverage alone does not establish an export error.

With a QSF, the report can show defined choices with zero observations. Without a QSF, it cannot tell you which unselected choices existed. A data-quality flag is a prompt to inspect the source survey and export.

### Read question-specific summaries

The question and field types determine how answers appear:

| Answer type | Presentation |
| --- | --- |
| **Multiple choice** | Counts and percentages for each option, in definition order when a QSF is available. Defined options with no selections remain visible. |
| **Matrix or Likert** | One compact table: statements down the rows, answer options across the columns. Each cell contains a count, a percentage, and a small comparison bar. |
| **Numeric** | A value distribution alongside minimum, average, median, maximum, and sample standard deviation for each numeric field. |
| **Written response** | Number of responses, number of unique values, and the most frequent values. Read individual comments under **Written answers**, or inspect a complete record under **Responses**. |

Multiple-choice percentages use respondents who answered the question. The report counts each respondent once per option, so selecting several options can produce percentages that add up to more than 100%. The selection total uses the same deduplicated counts. Attached written answers appear separately.

Matrix percentages use **Answered (n)** for each statement. For example, if 20 people answer the delivery row and 10 choose “Good,” that cell shows **10 / 50%**. If only 8 answer the support row and all choose “Good,” its cell shows **8 / 100%**. Each statement therefore has its own denominator. Multiple-answer matrix fields belonging to the same statement share one row. A dash means there are no responses for that row or the option was not exported for it. A missing answer does not establish whether someone saw the question.

Numeric summaries use the declared question or field type. A text field containing employee numbers such as `000123` stays text. Numeric fields with no usable values show an empty-state message; non-numeric and infinite values are excluded with a count. Standard deviation describes the spread of the observed values and uses the sample formula, dividing by `n − 1`. It appears as a dash when fewer than two numeric values are available.

Numeric charts show up to 12 distinct values individually. Larger domains use up to eight equal-width intervals, with counts and percentages of usable numeric values. Interval labels show which boundaries they include; the final interval includes the maximum value.

Option codes are translated only when the mapping is unambiguous for that field. Unknown or ambiguous values remain as recorded in the export.

## Review individual responses

Under **Responses**:

- Use the local search box to filter response records by their identifiers, metadata, or displayed answer text.
- Use **Questions** to choose which answers appear within each response.
- Click a response to expand it, or use **Expand all** for the current page and **Collapse**.
- Use **Surveys** to choose which surveys appear in a combined report.

The survey selector updates the summary totals. Local search and the question selector do not recalculate summary totals or question analytics. A global search result points to the matching answer and reveals that question when you open it.

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

For a paper or PDF copy, open the view you need, choose surveys and local filters, and use your browser's **Print** command. The report prints the active view, including matching rows beyond the current page, and opens its detail sections for printing. Browser navigation and controls stay out of the printout. Check the print preview before saving or printing.

The report is a snapshot. To include new responses, rebuild the entity folder and regenerate the HTML file.

## Look up exported columns in the codebook

Open **Codebook** to connect a column in your CSV to its question, specific field or matrix row, section, question type, and answer codes. For example, a field called `QID8_2` might represent the working-hours row of a satisfaction matrix.

The codebook contains one row for each exported question field. It includes the original export column and ImportId when available. Response metadata columns such as `ResponseId` and `RecordedDate` are outside this view.

- Use **Find a field** to search question text, column names, sections, codes, and labels.
- Use the report's **Surveys** selector to limit the codebook to particular surveys.
- Click **Download CSV** to save all rows matching the codebook search and selected surveys as `codebook.csv`, including matches on other pages.

Codes and labels come from the survey definition, including options nobody selected. Where a recode differs from the choice ID, both are shown. Without a QSF, the codebook still shows the available export headers and field metadata, but it does not invent missing choices. Text that could be interpreted as a spreadsheet formula is exported as literal text.

Codebook search is independent of response search. It changes which dictionary rows appear and are downloaded; it does not change response statistics. A codebook match from global search opens the relevant row.
