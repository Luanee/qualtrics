# Your first report

Turn a small example survey into an HTML report you can open in a browser. You will create nine data tables along the way. The example uses invented responses and needs no Qualtrics account or API token.

Before you start, complete [installation](installation.md) and open a terminal in the `qualtrics` project folder.

## 1. Find the example files

The repository includes both files in `docs/assets/examples/`:

| File | What it contains |
| --- | --- |
| [Download feedback.csv](../assets/examples/feedback.csv) | Three survey responses, with the original Qualtrics-style header rows. |
| [Download feedback.qsf](../assets/examples/feedback.qsf) | The survey definition: its questions, answer choices, and block. |

You already have these files if you cloned the repository. You do not need to download them again.

The survey asks one satisfaction question and one free-text question. The three satisfaction answers are **Satisfied**, **Satisfied**, and **Dissatisfied**. Two people leave a comment; one leaves it blank. The definition also includes **Neutral**, which nobody chose.

## 2. Create the data tables

Run this command as one line:

```text
uv run qualtrics build docs/assets/examples/feedback.csv --qsf docs/assets/examples/feedback.qsf --output data/first-report/entities --format csv
```

The `build` command reads the responses and the definition. It creates the output folders for you. `--format csv` makes the resulting tables easy to inspect; the command's default is JSON if you omit that option.

You should see:

```text
Wrote 1 survey(s) as csv entities to data/first-report/entities
```

Inside the new folder, you should find:

```text
data/first-report/entities/
├── surveys.csv
├── sections.csv
├── questions.csv
├── question_fields.csv
├── question_catalog.csv
├── question_field_catalog.csv
├── answer_options.csv
├── responses.csv
└── response_answers.csv
```

You can leave these files together and proceed to the report. [Understand your data](../understand/your-data.md) explains each table.

## 3. Generate the report

```text
uv run qualtrics report --folder data/first-report/entities --output data/first-report/report.html
```

You should see:

```text
Wrote HTML report to data/first-report/report.html
```

## 4. Open and check it

Find `data/first-report/report.html` inside your project folder and open it with a browser. You can double-click it in your file manager or use one of these commands:

=== "Windows PowerShell"

    ```powershell
    Start-Process "data/first-report/report.html"
    ```

=== "macOS"

    ```bash
    open data/first-report/report.html
    ```

=== "Linux"

    ```bash
    xdg-open data/first-report/report.html
    ```

Check these results:

1. **Summary** shows **3 Responses**, **3 Finished · 100%**, and **0 Not marked finished**. The dashboard places all three responses in the same week in September 2026 and shows all three as finished in the survey comparison. Switch the timeline to monthly counts or expand its table to check the values.
2. The satisfaction question appears in **Question spotlights**: two Satisfied answers, one Dissatisfied answer, and zero Neutral answers. Follow its link, or open **Questions**, for the full analysis. The coverage chart shows that two of the three responses contain a comment and all three contain a satisfaction answer.
3. Return to **Summary** and expand **Coverage and data quality**, then **Data quality**. Neutral appears under **Defined options not observed**. This is expected: the QSF lists Neutral as a possible answer even though nobody chose it.
4. Open **Written answers** to read the two comments. Follow a comment's response link, or open **Responses** to inspect a complete record. One response has no comment.

The blank comment contributes no row to `response_answers.csv`. That gives you five answer rows: three satisfaction answers plus two comments. In a survey with matrix or multiple-selection questions, one question can produce several answer rows; the report's **Respondent answers** count groups those by response and question.

Below the dashboard, expand **Observed highlights** for a brief account of the answers, or **Coverage and data quality** to see **2 Response questions** and **5 Respondent answers**. The dashboard and its controls work offline. In a combined report, the **Surveys** selector updates all dashboard charts; each question keeps its own survey's denominator.

## Repeat or use your own data

You can repeat the two commands to regenerate this example. `build` replaces entity files of the selected format in its output folder, and `report` replaces the HTML file at its output path.

For your own survey, follow [parse existing exports](../guides/parse-exports.md). To explore the report controls or share a report, use [read and share reports](../guides/reports.md).

## If you installed only the CLI

Download both example files into a folder you choose, open a terminal in that folder, and run:

```text
qualtrics build feedback.csv --qsf feedback.qsf --output data/first-report/entities --format csv
qualtrics report --folder data/first-report/entities --output data/first-report/report.html
```

Open the HTML file as described above. All paths in these two commands start from your download folder.
