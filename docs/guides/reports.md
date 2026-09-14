# Read and share reports

One file, six views: turn parsed tables into a report you can open offline and share.

[Try the fictional report](../examples/question-types.md){ .md-button .md-button--primary }

The example includes its survey definition, response CSV, and a guide to each question family's presentation and limits.

## Generate the HTML file

```bash
uv run --extra cli --extra ui qualtrics report \
  --folder data/first-report/entities \
  --output data/first-report/report.html
```

Replace the two paths with your entity folder and desired report location. The output's parent folder must already exist. If an HTML file already exists at that path, the command replaces it.

You should see `Wrote HTML report to ...`. Open the resulting file in your browser. The file contains its styles, scripts, and report content, so the recipient does not need Python or the entity folder to read it.

??? info "Before you run the command"

    Install `qualtrics[cli,ui]` (`uv sync --extra cli --extra ui` in this repository). You need a parsed entity folder from [your first report](../getting-started/first-report.md) or [your own export](parse-exports.md). Run the example from the project folder; with a separate CLI installation, use `qualtrics` instead of `uv run --extra cli --extra ui qualtrics`.

## Read the report

Use the side navigation to move between six views. On a narrow screen, navigation wraps above the content. The views stay inside one HTML file, so you can move between them without an internet connection.

| View | Use it to |
| --- | --- |
| **Summary** | Explore response timing, compare surveys, and choose question charts before opening their details. |
| **Flow** | Explore a connected map of the survey, inspect a step, and try hypothetical routes through its conditions. |
| **Questions** | Find a question by text, section, or identifier and inspect one question at a time. |
| **Written answers** | Search comments, select a question, and open the response behind a comment. |
| **Responses** | Review individual response records and choose which questions to display. |
| **Codebook** | Look up export columns, field types, and answer codes; download the filtered dictionary. |

Use **Surveys** to choose the survey scope. **Respondent language** selects a `responses.user_language` cohort, including **Missing / unknown** for blank values. Summary totals, charts, question coverage, written answers, and response lists follow that cohort.

**Definition language** changes QSF question, field, and choice labels without changing counts. The report uses the base label where a translation is absent. Written answers keep their recorded text; a translated choice in a response shows its original under **Recorded**. The codebook shows the selected definition language and response properties. The [flow example](../examples/survey-flow.md) lets you try hypothetical routes; its answers do not affect response charts.

??? info "Navigation, theme, and flow controls"

    Moving between views keeps your survey selection. Use your browser's Back and Forward buttons to return to earlier views or question details.

    The **Theme** selector in the header offers **System**, **Light**, and **Dark**. System follows your browser's preferred appearance. A manual choice applies until you reload the file.

    The [survey flow guide](survey-flow.md) explains how to supply a definition and use the map and walkthrough. The fictional flow example compares Sales and Engineering routes, an early ending, and a randomizer.

    In Flow, select a card to read its settings and questions. Pan across the canvas, use the zoom controls to change scale, or select **Fit** for the full route. The **Show outline** control gives you the same structure as an expandable list. Printing uses that readable outline.

### Understand the totals

The top three totals count **Responses**, **Finished**, and **Not marked finished** in the selected surveys. They describe the exported records, not everyone invited. Expand **Coverage and data quality** below the charts for question and field counts.

??? info "What each total counts"

    | Report label | Meaning |
    | --- | --- |
    | **Responses** | Response records in the selected surveys, including records marked unfinished. |
    | **Finished** | Responses whose exported finished flag is `true` or `1`. The percentage beside the label is their share of the selected response records. |
    | **Not marked finished** | All other response records, including records with no finished flag. This does not establish that each record is a partial response. |
    | **Response questions** | Questions classified as respondent-facing questions in the selected surveys. |
    | **Respondent answers** | Response-and-question pairs with at least one answer. A matrix question with several filled fields counts once for that response here. |
    | **Unanswered questions** | Questions with no observed respondent answer in the export. |
    | **Unused fields** | Concrete exported fields with no observed respondent value. |

    The finished share is not the proportion of invited people who participated. The first three totals appear above the dashboard. Below the charts, expand **Coverage and data quality** for the other four totals and detailed diagnostics.

    If an older entity folder omits optional `questions.question_role`, the report infers each question's role from its saved question type and selector, then its related fields' ImportIds (`import_external_id`, or legacy `source_import_id`). A saved role takes precedence. Timing and browser metadata questions stay out of respondent-facing totals, coverage, spotlights, and unused-field diagnostics; their original rows and values remain in the entity folder. When no technical evidence survives, a question counts as a response question. Reparse the source export to recover evidence that was never saved.

### Explore the Summary dashboard

The dashboard follows the **Surveys** selector. It updates from the data inside the HTML file and works offline, including its chart controls and question links.

| Chart | How to read it |
| --- | --- |
| **Recorded responses over time** | Group counts by week, month, or year. Enable **Cumulative** to see the running total. Expand the count table for exact values. |
| **Responses by survey** | Compare response volumes and each survey's finished share. The bars distinguish records marked finished from all other records. |
| **Question spotlights** | Choose up to two question distributions to inspect together, then follow a question link to its full analysis. |
| **Questions with little recorded data** | Inspect the eight questions with the lowest answer coverage across the selected surveys. Each link opens that question's details. |

Coverage is a clue, not proof that a question was shown: optional questions and branches also produce missing answers. Open a question or **Coverage and data quality** to investigate.

??? info "Chart dates, denominators, and selection behavior"

    The timeline uses calendar dates as written in the exported recorded-date field; it does not convert timestamps to your browser's time zone. Missing or invalid dates are excluded from this chart and counted in its note. Those records still contribute to response totals and the other charts. A period without recorded responses appears as zero between the first and last usable dates. Very long spans group adjacent periods to keep the chart within 260 points; the note identifies the grouping and the table retains exact counts for each interval.

    **Cumulative** adds each period's responses to the preceding total across the selected surveys. It stays flat through periods with no responses and continues across year boundaries. In this mode, the table shows both the period count and its cumulative total. Changing the survey selection recalculates the running total; missing or invalid dates remain excluded.

    Spotlight menus list available NPS questions first, then declared numeric fields, then categorical questions, with larger answer counts first within each type. The first chart defaults to the first available choice; the second prefers a different answer type when available. Changing the survey selection keeps a choice when it is still available and selects another when necessary. Questions from different surveys retain their own labels, answer counts, and denominators; the report does not combine their distributions. For categorical questions with more than 12 options, the spotlight shows the 12 most selected and links to the full distribution.

    An NPS spotlight shows the recorded score distribution. Numeric charts use usable numeric values and state any excluded values. Categorical percentages use the question's or field's answering respondents; multiple selections can make percentages add up to more than 100%. Written answers remain in their own view.

    Coverage divides respondents with an answer by all response records for that survey. Use the chart to decide what to inspect, then open **Coverage and data quality** for the full coverage list.

### Follow a finding to the evidence

Expand **Observed highlights** below the Summary dashboard to read factual observations, such as the most selected option or a median for a declared numeric field. Each highlight names the question and links to its analysis. Counts and denominators accompany the observations; ties remain explicit. A field containing numeric-looking text, such as an employee ID, stays text.

Treat these highlights as a starting point for reading the charts. They do not infer sentiment, causes, or whether a score is good or bad. Question types without a suitable factual summary remain available under **Questions**.

### Search across the report

Use **Search this report** in the header to find questions, written answers, responses, flow steps, and codebook fields. Enter several words or an identifier. Results show their type and a highlighted excerpt; select a result to open the matching question, comment, response answer, flow card, or dictionary row.

Search matches are case-insensitive and accent-insensitive. It searches the selected surveys and respondent cohort; the definition-language choice controls which codebook translation rows appear. Search itself does not recalculate statistics.

Results replace the current view while you search. **Clear** restores that view; selecting a view in the sidebar clears the global search and opens it.

Written answers, responses, search results, and codebook rows use page controls. The count shows the full matching total. Filtering resets the page so matches do not remain hidden on a previous page.

### Work with written answers

**Written answers** uses the same membership rule as the exported `comments` table and Power BI's `fact_comments`: one nonblank answer in a supported text field. It includes form and matrix text and attached “Other” text fields. Choice labels, numeric fields, technical data, and response properties are excluded. Whitespace-only cells remain in the original answer table but do not appear in this view.

The view preserves separate responses and separate fields even when their text matches. Comments remain included in all-answer totals; exporting the subset does not add new answers. `comments.user_language` and `fact_comments.user_language` come only from the linked response, preserving missing language as null. For source-metadata limitations and older folders, see [the comments contract](../entity-model.md#comments).

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

??? info "Percentages, numeric rules, and recodes"

    Multiple-choice percentages use respondents who answered the question. The report counts each respondent once per option, so selecting several options can produce percentages that add up to more than 100%. The selection total uses the same deduplicated counts. Attached written answers appear separately.

    Matrix percentages use **Answered (n)** for each statement. For example, if 20 people answer the delivery row and 10 choose “Good,” that cell shows **10 / 50%**. If only 8 answer the support row and all choose “Good,” its cell shows **8 / 100%**. Each statement therefore has its own denominator. Multiple-answer matrix fields belonging to the same statement share one row. A dash means there are no responses for that row or the option was not exported for it. A missing answer does not establish whether someone saw the question.

    Numeric summaries use the declared question or field type. A text field containing employee numbers such as `000123` stays text. Numeric fields with no usable values show an empty-state message; non-numeric and infinite values are excluded with a count. Standard deviation describes the spread of the observed values and uses the sample formula, dividing by `n − 1`. It appears as a dash when fewer than two numeric values are available.

    Numeric charts show up to 12 distinct values individually. Larger domains use up to eight equal-width intervals, with counts and percentages of usable numeric values. Interval labels show which boundaries they include; the final interval includes the maximum value.

    Explicit recode values take priority over internal choice IDs when parsing answers. For example, if choice `1` (Yes) has recode `2`, an exported `2` links to Yes. Display labels and other identifiers still match when there is no explicit recode match. Duplicate recodes remain unresolved, and unknown values retain their original text. Rebuild the entities with the matching QSF to apply this rule to an older export; generating HTML alone does not repair stored option links.

    Charts and unused-option diagnostics follow the resolved option link. A raw value that happens to equal another choice's internal ID does not also mark that other choice as used. Older records without a valid link retain the existing raw-value fallback.

## Review individual responses

Under **Responses**:

- Use the local search box to filter response records by their identifiers, metadata, or displayed answer text.
- Use **Questions** to choose which answers appear within each response.
- Click a response to expand it, or use **Expand all** for the current page and **Collapse**.
- Use **Surveys** to choose which surveys appear in a combined report.

Expand **Response properties** inside a response to see available system metadata, embedded fields, and unclassified source columns. Both local and global search include property labels and values. Blank properties stay blank; the report does not infer a department or country from other answers. The codebook explains how each column was classified.

Survey and respondent-language selectors update summary totals. Local search and the question selector leave those totals unchanged. A global search result opens the matching answer.

## Include several surveys

Pass one `--folder` option per input:

```bash
uv run --extra cli --extra ui qualtrics report \
  --folder data/survey-a/entities \
  --folder data/survey-b/entities \
  --output data/combined-report.html
```

For the batch layout made by the [API example](api-access.md), you can pass its shared root:

```text
uv run --extra cli --extra ui qualtrics report --folder data/api-export --output data/api-export/report.html
```

The command discovers immediate `<survey-id>/entities/` folders. It also accepts a survey folder containing `entities/`. Inputs must represent different surveys; overlapping survey IDs cause an error. See [combine surveys](combine-surveys.md) if you also want a combined table collection.

## Share or print a report

Share the HTML file through your usual approved channel. Anyone with the file can read its included answers, response identifiers, and response properties, including any exported contact or location fields. Hiding questions, collapsing properties, or filtering responses in the browser does not remove them from the file, so choose the source data before generating a report for a particular audience.

For a paper or PDF copy, open the view you need, choose surveys and local filters, and use your browser's **Print** command. The report prints the active view, including matching rows beyond the current page, and opens its detail sections for printing. Browser navigation and controls stay out of the printout. Check the print preview before saving or printing.

The report is a snapshot. To include new responses, rebuild the entity folder and regenerate the HTML file.

## Look up exported columns in the codebook

Open **Codebook** to connect a column in your CSV to its question, specific field or matrix row, section, question type, and answer codes. For example, a field called `QID8_2` might represent the working-hours row of a satisfaction matrix.

- Use **Find a field** to search question text, column names, sections, codes, and labels.
- Use the report's **Surveys** selector to limit the codebook to particular surveys.
- Click **Download CSV** to save all rows matching the codebook search and selected surveys as `codebook.csv`, including matches on other pages.

??? info "Column classifications, recodes, and older folders"

    For newly parsed exports, the codebook includes question fields and response properties such as `ResponseId`, `RecordedDate`, and embedded `Region`. It shows the original export column, ImportId, classification, evidence, and storage table/column. Derived question outputs, such as an NPS group, are distinguished from direct answers. Unknown source fields are labeled **Unclassified**, so they remain inspectable without being counted as confirmed question answers. Older entity folders without the source dictionary still show their available question fields.

    Each newly parsed choice lists its respondent-visible label, native choice ID, explicit recode, and normalized value. A configured multiple-choice export label (`variable_name`) is shown separately from a compatibility export tag (`answer_export_tag`). For matrix options, the native choice ID refers to the scale answer, not the statement row. Search and the downloaded codebook CSV include this same choice text.

    **Explicit recode: unavailable** means the source did not provide that metadata; it does not rule out Qualtrics default numeric codes. The normalized value is the explicit recode when available, otherwise the choice text. Legacy options retain their existing code-and-label display, without claiming their old `answer_code` was an explicit recode. Reparse the original export with its matching definition to recover provenance; rebuilding HTML from an older folder cannot recreate it.

    Codes and labels come from the survey definition, including options nobody selected. Where a recode differs from the choice ID, both are shown. Without a QSF, the codebook still shows the available export headers and field metadata, but it does not invent missing choices. Text that could be interpreted as a spreadsheet formula is exported as literal text.

    Codebook search is independent of response search. It changes which dictionary rows appear and are downloaded; it does not change response statistics. A codebook match from global search opens the relevant row.
