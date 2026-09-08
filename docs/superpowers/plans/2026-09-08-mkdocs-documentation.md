# MkDocs documentation implementation plan

> **For agentic workers:** Use the parallel-agents and verification-before-completion skills. Independent writing tasks may run concurrently; configuration, integration, and verification stay with the coordinating agent.

**Goal:** Deliver a usable Material for MkDocs documentation site with beginner workflows and evidence-based plugin choices.

**Architecture:** Task-oriented Markdown pages under `docs/`, a root `mkdocs.yml`, a locked documentation dependency group, and a strict build in CI. Preserve the entity contract and isolate internal planning notes from the public site.

**Tech stack:** MkDocs, Material for MkDocs, PyMdown Extensions, and maintained catalog plugins that serve actual page content.

**Spec:** `docs/superpowers/specs/2026-09-08-mkdocs-documentation-design.md`

## Global constraints

- Match current CLI flags and defaults, including JSON for `build` and Parquet for semantic export and combining.
- Start without API credentials or real respondent data.
- Preserve `docs/entity-model.md` and `docs/entity-model.dbml`.
- Exclude `docs/superpowers/` from build and search.
- Use primary upstream evidence for plugin maintenance; record the check date.

## Tasks

- [x] Research catalog candidates and Material compatibility; record decisions in `docs/contributing/documentation.md`.
- [x] Write `docs/getting-started/` and practical guides under `docs/guides/`, checking each command against `src/qualtrics/cli/`.
- [x] Write `docs/reference/` and `docs/help/troubleshooting.md`; preserve and link the existing model contract.
- [x] Add home, data explanations, synthetic `docs/assets/examples/` downloads, and an accessible workflow illustration.
- [x] Configure `mkdocs.yml`, add the `docs` dependency group and preview/build tasks to `pyproject.toml`, resolve `uv.lock`, and add a strict build step in CI.
- [x] Run `uv run --group docs mkdocs build --strict`; inspect all local links and internal-document exclusions.
- [x] Run the published sample commands in a temporary output directory and the CLI/model-documentation integration checks.
- [x] Inspect desktop and narrow browser views, navigation, search, diagrams, and plugin output. Fix defects and request an independent final review.
- [x] Add a documentation entry point to `README.md` and report exact preview/build commands and verified plugin choices.


## Completion evidence

- `uv run --locked --group docs mkdocs build --strict` succeeds with 16 public Markdown pages. Material prints an upstream MkDocs 2 announcement; the project resolves MkDocs 1.6.1 and the strict build reports no site warnings.
- `uv lock --check --offline` resolves the locked 71-package environment; pre-existing locked package versions are unchanged.
- All 695 local references in built HTML (page links, scripts, stylesheets, and image assets) resolve. No `superpowers/` output or search entries exist. The first-report tutorial is indexed.
- The synthetic survey produced the documented counts for all nine tables. CLI smoke checks covered CSV, JSON, and Parquet entity output, report generation, five semantic tables, ZIP input, adjacent definition discovery, and combining distinct surveys. Outputs are in a temporary directory outside source control.
- The 33 focused CLI, definition-answer-option, and model-documentation tests passed.
- Browser checks covered desktop and 390-pixel mobile views, both themes, search results and navigation, code-copy confirmation, GLightbox enlargement, and Mermaid rendering. The mobile guide has no page-wide horizontal overflow. Browser console reported no errors in these checks.
- An independent source and documentation review reported no actionable findings. Live Qualtrics access, Power BI Desktop, and fresh Windows/Linux installation were not executed.

Implementation branch: `codex/mkdocs-documentation`. Publishing the site and merging the branch are separate steps from the initial documentation rebuild.
