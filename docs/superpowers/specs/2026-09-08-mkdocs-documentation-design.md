# MkDocs documentation design

## Outcome

Rebuild `docs/` as a Material for MkDocs site for people who use survey data, including readers who do not write Python. Keep a separate reference for CLI and Python users. Work from the current implementation on `main`, including field-scoped answer options.

## Structure

- Home: choose a task and understand the CSV → tables → report workflow.
- Start here: installation, a synthetic downloadable example, and a first report without API credentials.
- Guides: parse existing exports again, read and share reports, combine surveys, connect to the API, and export a Power BI model.
- Understand your data: explain the nine output tables and survey terminology before introducing technical IDs.
- Reference: CLI options and defaults, Python entry points, configuration, and the existing entity/DBML contract.
- Help: troubleshooting and a contributor guide covering preview, strict builds, and plugin maintenance.

## Presentation and dependencies

Use the requested `material` theme with search, light/dark palettes, copyable commands, clear navigation, and responsive layouts. Prefer Material's built-in support for diagrams and Markdown tables. Evaluate catalog plugins against primary release and maintenance evidence; install only plugins used by the actual pages. Put documentation dependencies in a separate locked `docs` group.

Preserve `docs/entity-model.md` and `docs/entity-model.dbml`, which existing links and contract tests use. Exclude `docs/superpowers/` from the rendered site and search. Keep all example survey data synthetic. Include prose equivalents for diagrams.

## Verification

Build with `mkdocs build --strict`, verify local links and navigation, run the beginner CSV/QSF → entities → report → semantic-model workflow, and inspect the rendered site at desktop and narrow widths. Add a strict documentation build to CI. Verify existing model documentation tests and relevant CLI integration tests. Keep deployment as documented instructions; this task does not require publishing to a live service.
