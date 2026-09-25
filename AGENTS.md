# Agent guide

Use this guide when changing the Qualtrics Python toolkit. Start from the requested scope and preserve unrelated working-tree changes.

## Before editing

1. Check `git status --short --branch` and the diff. Continue on an explicitly selected branch; otherwise use a short, single-purpose branch.
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing package structure, dependencies, public interfaces, parsing, or data contracts. Read the relevant [ADRs](docs/adr/index.md) for the reasons behind those boundaries.
3. For survey terminology, use [CONTEXT.md](CONTEXT.md). For table grains, IDs, and serialization changes, read [the entity contract](docs/entity-model.md) and its linked DBML schemas.

Keep plans, research, issue drafts, and local verification results under ignored `knowledge/` subfolders. Commit maintained project documentation under `docs/`, plus these root guides. Use synthetic fixtures in tests and examples; keep private survey exports and credentials out of commits and logs.

## Setup and commands

The project supports Python 3.11–3.14. It uses uv, Poe, Ruff, ty, and pytest. Install the locked contributor environment from the repository root:

```bash
uv sync --locked --all-groups --all-extras
```

Node.js is also needed for browser-logic tests. The CLI extra supplies Typer/Rich; the UI extra supplies Jinja/MarkupSafe. Documentation builds need the UI extra because their hooks render example reports.

Use the tasks in [pyproject.toml](pyproject.toml) and keep this table aligned when they change:

| Action | Command |
| --- | --- |
| Full Python quality gate | `uv run poe check` |
| Lint | `uv run poe lint` |
| Format | `uv run poe format` |
| Check formatting | `uv run poe format-check` |
| Type check with ty | `uv run poe type` |
| Python tests with coverage | `uv run poe test` |
| Focused regression tests | `uv run pytest --no-cov tests/unit/test_architecture.py` |
| Browser-logic tests | `node --test tests/js/*.test.cjs` |
| Strict documentation build | `uv run poe docs-build` |
| Documentation preview | `uv run poe docs-serve` |
| Build wheel and source distribution | `uv run poe build` |
| Pre-commit checks | `uv run poe pre-commit` |

`poe check` runs lint, format-check, type checking, and Python tests. Focused pytest runs may use `--no-cov` because the configured 75% threshold applies to the whole package; the full test run must retain coverage. CI also checks Python 3.11–3.14 and optional-dependency installations; a local run on one interpreter does not cover that matrix.

## Implement and verify

- Keep domain rules in the modules assigned by [ARCHITECTURE.md](ARCHITECTURE.md). Use the existing package-relative import style and let Ruff sort imports. Use documented public imports in examples and application code.
- Add parameter and return annotations to new or changed functions. Prefer concrete types, `TypedDict`, or a `Protocol` for known contracts. The [dynamic-data exception](ARCHITECTURE.md#typing-and-dynamic-data) permits `Any` at Qualtrics payload and entity-row boundaries; narrow values before applying domain rules.
- Put focused Python checks in `tests/unit/`, cross-layer and round-trip checks in `tests/integration/`, and browser behavior in `tests/js/`. Follow nearby tests rather than creating a second test layout.
- Reproduce a bug with a regression test, then verify the fix. Cover changed behavior, failure paths, and relevant data invariants. Documentation-only changes use the strict docs build and existing checks.
- Run `uv run poe check` before committing. Format touched files as needed; inspect any edits from the repository-wide formatter.
- Run `uv run poe docs-build` for documentation, navigation, or showcase changes. Follow [the contributor guide](docs/contributing/documentation.md) for UI checks. For package, dependency, or public-import changes, also run `uv run poe build` and `bash scripts/smoke_wheel.sh` with exactly one wheel in `dist/`.
- Stage the intended files, including new files, then run `uv run poe pre-commit`. Its `--all-files` check uses Git-tracked files. Inspect and re-stage hook edits, rerun affected checks, and review `git diff --cached --check` before committing. Keep hooks enabled; report an environment failure instead of bypassing it.

## Git, commits, and PRs

Use `feat/short-description`, `fix/short-description`, or `docs/short-description` without a `codex/` prefix. Keep each branch focused on one reviewable change. For new independent work, update `main` with `git pull --ff-only` while on a clean `main` checkout, then create the branch. Continue an existing branch or build an approved stack from its specified parent without merging `main` into it as a setup step.

Use Conventional Commits: `type(scope): description`. Choose the affected area, such as `parser`, `entities`, `semantic`, `translations`, `api`, `cli`, `report`, or `docs`. Commitizen is not configured; use `git commit -m "docs(architecture): document package boundaries"` for a non-interactive commit. Prefer cohesive commits over a fixed line-count limit.

For an authorized PR, use [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md), a scoped title, and exactly one release category from the template. Record checks that actually ran. For stacked PRs, target the immediate parent and record the dependency and merge order. Push, open PRs, merge, publish, and delete branches only when the user requests those actions.

## Keep the design record current

Update `ARCHITECTURE.md` in the same change whenever module responsibilities, allowed dependencies, public interfaces, data flow, schema invariants, or optional-dependency boundaries change. Update the entity contract and DBML when table contracts change; keep `CONTEXT.md` focused on vocabulary.

Record a consequential architectural choice in `docs/adr/NNNN-name.md` using the [ADR convention](docs/adr/index.md). Capture the context, decision, alternatives, and consequences that a future maintainer needs. Link it from the index and architecture guide. Supersede an accepted decision with a new ADR rather than replacing its rationale.

## Completion checklist

- [ ] The requested change is implemented, and unrelated edits are preserved.
- [ ] The required checks passed, with any unrun checks or blockers stated in the handoff.
- [ ] Architecture, ADRs, schema references, and user documentation reflect any changed contracts.
- [ ] Staged files contain no private exports, generated reports, credentials, or `knowledge/` content.
- [ ] If committing was requested, the commit uses the relevant Conventional Commit scope and hooks pass.
- [ ] The handoff names the branch, summarizes the behavior, and reports validation and publication status.
