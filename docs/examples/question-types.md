---
hide:
  - toc
---

# Explore a report with every supported question family

Try the report with a fictional survey designed to exercise the toolkit's question types. The data and report are regenerated together whenever this documentation is built.

{{ showcase_counts }}

<p class="showcase-links">
  <a class="md-button md-button--primary" href="{{ showcase_report_url }}" target="_blank" rel="noopener">Open full report</a>
  <a class="md-button" href="{{ showcase_survey_url }}" download>Download survey QSF</a>
  <a class="md-button" href="{{ showcase_responses_url }}" download>Download responses CSV</a>
</p>

<iframe class="showcase-report" src="{{ showcase_report_url }}" title="Interactive report from fictional question-type survey responses" loading="lazy"></iframe>

## What to try

1. In **Summary**, group response counts by week, month, or year. Enable **Cumulative** to follow the running total. Choose different question spotlights to compare answer distributions.
2. Open **Questions** to compare multiple choice, matrix, numeric, and written-answer presentations.
3. Search for a question or a fictional answer using **Search this report**, then follow the result to its detail view.
4. Open **Codebook** to connect exported columns to their question, field type, and answer codes. Download its filtered dictionary to inspect the column mapping.

The embedded report has its own navigation and theme selector. Use **Open full report** for more room, especially on a phone. The full report is a self-contained HTML file that you can save and open offline. The [report guide](../guides/reports.md) explains chart denominators, search, and data-quality indicators.

## What this example covers

The survey definition includes all 32 canonical question families recognized by this toolkit, plus selected multiple-choice, text, matrix, and compound-field variants. The cases below identify the exact QSF type, selector, and sub-selector used. They cover useful export layouts; they do not enumerate every possible Qualtrics configuration.

The responses are entirely fictional. They include incomplete records, optional blanks, unused choices, attached written answers, and compound fields so you can see how those cases appear in the report. A missing answer does not establish whether a question was shown to a respondent.

!!! note "A coverage fixture, not an import-tested survey"

    The QSF is a synthetic definition for exercising the parser and report. It has not been imported into Qualtrics and is not a promise that every included type or selector is available in your account. Some advanced question types depend on product features or licensing. See the [Qualtrics question-type overview](https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/question-types-guide/question-types-overview/) and [survey import and export guide](https://www.qualtrics.com/support/survey-platform/survey-module/survey-tools/import-and-export-surveys/).

Multiple choice, matrix, numeric, and written answers have specific presentations. File, location, and other structured values use generic value displays; the example does not provide media playback or interactive maps. Descriptive text and CAPTCHA occur only in the definition because they produce no respondent answer fields. Timing and browser metadata remain technical information rather than survey-answer charts.

The table is generated from the same case manifest as the downloadable fixture. **Exported fields** counts CSV question fields for that case, not the number of possible choices or responses. Definition-only cases therefore have zero fields and do not appear in the report's question or codebook views.

<a href="{{ showcase_coverage_url }}" download>Download the coverage manifest</a>

{{ showcase_coverage }}

## Generate the same example locally

From a repository checkout, run:

```bash
uv run --extra ui python -m scripts.question_type_showcase --output data/question-type-showcase
```

Open `data/question-type-showcase/report.html`. The folder also contains `survey.qsf`, `responses.csv`, and `coverage.json`. The generator uses fixed fictional data and the production parser and report renderer; running it again with the same code produces the same example.

To try a smaller example first, follow [Your first report](../getting-started/first-report.md). To change or rebuild this embedded example, see [Maintain the documentation](../contributing/documentation.md#maintain-the-report-showcase).
