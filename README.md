# Qualtrics toolkit

[![PyPI](https://img.shields.io/pypi/v/qualtrics?logo=pypi&logoColor=white)](https://pypi.org/project/qualtrics/)
[![Python](https://img.shields.io/pypi/pyversions/qualtrics?logo=python&logoColor=white)](https://pypi.org/project/qualtrics/)
[![Tests](https://img.shields.io/github/actions/workflow/status/Luanee/qualtrics/ci.yml?branch=main&label=tests&logo=github)](https://github.com/Luanee/qualtrics/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/Luanee/qualtrics/blob/main/LICENSE)

**Turn Qualtrics exports into useful tables, offline reports, and Power BI models.**

Use the typed Python SDK or command-line tools to work with the Qualtrics API, or start with a CSV or ZIP you already have. Parsing and reporting work locally without an API token.

**[Documentation](https://luanee.github.io/qualtrics/)** · **[First report](https://luanee.github.io/qualtrics/getting-started/first-report/)** · **[Report demo](https://luanee.github.io/qualtrics/examples/question-types/)** · **[Flow demo](https://luanee.github.io/qualtrics/examples/survey-flow/)**

![A Qualtrics CSV or ZIP and optional QSF definition become organized tables, an HTML report, or a Power BI model.](https://luanee.github.io/qualtrics/assets/images/survey-workflow.svg)

## Features

| Capability | What you can do |
| --- | --- |
| **[Prepare survey data](https://luanee.github.io/qualtrics/guides/parse-exports/)** | Parse CSV/ZIP exports with optional QSF definitions. Preserve question fields, choices, recodes, and response properties; write JSON, CSV, or Parquet tables. |
| **[Explore offline reports](https://luanee.github.io/qualtrics/guides/reports/)** | Browse dashboard charts, question-specific visualizations, searchable written answers, individual responses, and a codebook in one HTML file. |
| **[Understand survey flow](https://luanee.github.io/qualtrics/guides/survey-flow/)** | Explore the configured flow map and try hypothetical paths with an interactive “what if” walkthrough. |
| **[Analyze comments](https://luanee.github.io/qualtrics/entity-model/#comments)** | Use dedicated text-answer tables with original answer IDs and the language recorded on each response. |
| **[Build Power BI models](https://luanee.github.io/qualtrics/guides/power-bi/)** | Export six analysis tables as Parquet files or one SQLite database, with relationship guides and interactive DBML diagrams. |
| **[Automate API workflows](https://luanee.github.io/qualtrics/guides/api-access/)** | Access surveys, definitions, flows, and response imports/exports through Python or the CLI. Export with retries, visible progress, and configurable survey concurrency. |

You can also [combine multiple surveys](https://luanee.github.io/qualtrics/guides/combine-surveys/) into one entity collection and report.

## Try your first report

With [uv and Git installed](https://luanee.github.io/qualtrics/getting-started/installation/), clone the repository and run the included example. It uses fictional responses and needs no Qualtrics account.

```bash
git clone https://github.com/Luanee/qualtrics.git
cd qualtrics
uv sync --locked --extra cli --extra ui
uv run --extra cli --extra ui qualtrics build docs/assets/examples/feedback.csv \
  --qsf docs/assets/examples/feedback.qsf \
  --output data/first-report/entities \
  --format csv
uv run --extra cli --extra ui qualtrics report \
  --folder data/first-report/entities \
  --output data/first-report/report.html
```

Open `data/first-report/report.html` in your browser. The [first-report tutorial](https://luanee.github.io/qualtrics/getting-started/first-report/) explains the results; [parse your own export](https://luanee.github.io/qualtrics/guides/parse-exports/) when you are ready.

## Use it in a Python project

In your own project, install the base package:

```bash
uv add qualtrics
```

The base package includes the SDK, parsing, analytics, and JSON/CSV data functions. Add `cli` for commands, `ui` for HTML reports, or `parquet` for Parquet files. Command-line reports need `qualtrics[cli,ui]`; SQLite output needs no extra dependency.

See [installation options](https://luanee.github.io/qualtrics/getting-started/installation/#choose-dependencies-for-python-projects) and the [Python reference](https://luanee.github.io/qualtrics/reference/python/) for examples, including `QualtricsClient`, `parse_survey`, and `render_report`.

## Find what you need

- **Commands and configuration:** [CLI reference](https://luanee.github.io/qualtrics/reference/cli/) · [API credentials](https://luanee.github.io/qualtrics/reference/configuration/)
- **Data and relationships:** [Output tables](https://luanee.github.io/qualtrics/understand/your-data/) · [Entity and Power BI models](https://luanee.github.io/qualtrics/entity-model/)
- **Help and development:** [Troubleshooting](https://luanee.github.io/qualtrics/help/troubleshooting/) · [Contributor guide](https://luanee.github.io/qualtrics/contributing/documentation/) · [Release notes](https://github.com/Luanee/qualtrics/blob/main/release-notes.md)

The report workflow was inspired by the [Qualtrics Report Generator](https://github.com/hihipy/qualtrics-report-generator).
