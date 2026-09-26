# Architecture

The Qualtrics toolkit has two entry paths: a typed SDK for the remote Qualtrics API, and an offline pipeline for existing survey exports. Both support workflows that produce entity folders, HTML reports, and Power BI tables. The CLI coordinates those operations through the same implementations used by Python callers.

This document owns the package boundaries and cross-cutting invariants. Use [CONTEXT.md](CONTEXT.md) for domain vocabulary, the [entity contract](docs/entity-model.md) for column-level details, and [ADRs](docs/adr/index.md) for the reasons behind durable decisions. Update this document in the same change as the architecture it describes.

## Package map and public interfaces

Implementation code lives in four packages under `src/qualtrics/`:

| Package | Owns | Main entry points |
| --- | --- | --- |
| `api/` | HTTP transport, retries, API settings, typed requests/responses, endpoint domains, response export polling | `QualtricsClient` and documented `qualtrics.api` types |
| `cli/` | Typer commands, command validation, terminal output and export progress | `qualtrics` command |
| `ui/` | Report context, page composition, Jinja templates, browser controllers and bundled assets | `render_report` |
| `_common/` | Entity models, parsing, analytics, and serialization shared by consumers | Root-level Python operations listed below |

The package root exposes public functions and types through [`__init__.py`](src/qualtrics/__init__.py), alongside entry-point shims, version information, and `py.typed`. Examples and application code import shared operations from `qualtrics`; `_common` is private implementation.

| Operation | Public interface | Implementation owner |
| --- | --- | --- |
| Read raw exports | `parse_survey`, `parse_surveys` | `_common/parsers` |
| Read or write entity folders | `load_entities`, `write_entities` | `_common/serialization` |
| Combine entity collections | `merge_entity_sets` | `_common/models` |
| Prepare translations | `prepare_translations`, `TranslationRequest` | `_common/models/translations.py` |
| Compute report analytics | `analyze_entities`, `ReportAnalytics` | `_common/analytics` |
| Build or write analysis tables | `build_semantic_model`, `SemanticModel`, `write_semantic_model` | `_common/models/semantic.py` and `_common/serialization/semantic.py` |
| Render an offline report | `render_report` | `ui/report.py` |

The [Python reference](docs/reference/python.md) documents signatures and usage. Keep root exports small and deliberate; importing the root must not initialize CLI or template dependencies.

## Dependency direction

`cli` coordinates the SDK and offline operations. `ui` consumes shared models and analytics. Inside `_common`, dependencies point from parsers, analytics, and serialization toward models:

```text
_common/parsers       ─┐
_common/analytics     ─┼──> _common/models
_common/serialization ─┘
```

- `models` owns entity validation, merging, question classification, localization after parsing, translation preparation, and semantic projections. It must not import parser internals.
- `parsers` interprets QSF and CSV/ZIP source evidence and creates model rows. A transformation that operates on an existing `EntitySet` belongs in models when multiple consumers need it.
- `analytics` computes metrics from model rows without importing parsers or inspecting raw QSF files.
- `serialization` owns table formats and round-trips. Survey-manifest validation and its JSON read/write helpers currently live together in `models/survey_manifest.py`.
- Raw parsers and entity loaders share the platform-safe CSV field-limit policy in `_common/csv_support.py`. Both raise Python's process-global limit without lowering an existing limit; the helper depends only on the standard library.
- `_common` must not import `api`, `cli`, `ui`, the package-root facade, Typer, Rich, Jinja, or MarkupSafe. Keep `_common/__init__.py` minimal.

These rules prevent adapter dependencies and import cycles in shared operations. [ADR 0001](docs/adr/0001-protect-the-domain-model-from-adapters.md) records the decision. [Architecture tests](tests/unit/test_architecture.py) enforce the four-package layout, root export ownership, shared-package isolation, and the model/analytics-to-parser restrictions.

## Data flow and ownership

```text
Qualtrics API ──> exported files ──┐
Local CSV or ZIP + optional QSF ──┴──> parse ──> EntitySet
                                                  │
                             prepare translations / combine
                                                  │
                       ┌──────────────────────────┼───────────────────────┐
                       ▼                          ▼                       ▼
                 entity folder              report analytics       semantic model
                       │                          │                       │
                       ▼                          ▼                       ▼
                  load_entities              offline HTML         analysis tables
```

`EntitySet` holds nine authoritative tables and derived `comments`. Definitions describe surveys, blocks, questions, fields, and options; response tables record observed submissions and answers. The [entity model and DBML](docs/entity-model.md) define their grain and relationships.

Survey manifests travel with the collection through `EntitySet.survey_manifests`. Each output folder has one `manifest.json` keyed by survey ID, including combined folders. It stores survey flow, source-column evidence, and language registries. Keep nested source descriptors in the manifest rather than adding serialized JSON columns to analytical tables.

Preserve these contracts across parsing, merging, and output:

- Occurrence IDs are survey-scoped; native `*_external_id` values retain source lineage. Catalog IDs describe normalized semantics across surveys. Parser and model identity helpers serve different contracts; changing or consolidating their algorithms requires an explicit identity decision and regression tests.
- Build option domains from definitions, including unobserved choices. Match response values within their field domain and preserve unresolved values with a nullable option link.
- Preserve raw answer text. Store non-question properties on `responses`, use source metadata to classify columns, and retain ambiguous columns with their evidence. Combined surveys use the union of property columns with nulls where absent.
- Keep definition-only and localized rows out of answer metrics and active semantic dimensions. They describe available content without inventing answer facts.
- Derive comments from eligible original answer rows. A comment keeps the original `response_answer_id` and question/field linkage; it is part of the answer fact set, so adding its count to all answers would double-count it.
- Preserve table schemas even for empty exports, and test nulls, identifiers, and dynamic columns through the affected serialization formats.

## Translation and language invariants

`prepare_translations` is the public preparation function. Callers supply a shared callback or callbacks for questions, fields, options, and comments. The package bundles no translation provider. A callback may perform network calls under the caller's control; parsing and reporting need none.

QSF labels in the target language take precedence. A callback fills missing definition labels using `SurveyLanguage` as the source; written answers use the response's `UserLanguage`, which may be unknown. The explicit target overrides each survey's default language. Qualtrics `AvailableLanguages` describes declared availability without limiting callback targets.

Preparation returns a separate collection and retains raw values, answer identities, catalog linkage, and option links. Generated option labels are display text and cannot become parser aliases. Translated QSF labels can resolve responses to base options under the parser's existing matching rules.

Each comment remains one row. A prepared target adds nullable text, source-hash, and source-language columns using the reversible encoding in `translation_columns.py`. Matching source and target languages keep the original text without a prepared translation. Shared freshness helpers detect source changes so both the report and semantic consumers fall back to the original. A failed callback must not publish a partial result or mutate the input collection.

## Consumer boundaries

Reports use a shared `ReportContext`, page renderers, reusable components, and a Jinja document layout. `assets.py` orders the CSS and JavaScript that the renderer embeds into one HTML file. Survey selection and respondent-language filtering recalculate views; display-language selection changes labels and prepared text without changing answer counts.

Keep survey text escaped in templates and browser DOM updates. Use script-safe serialization for inline JSON. Flow walkthroughs evaluate hypothetical routes separately from observed response facts. The [report contributor guide](docs/contributing/documentation.md#maintain-the-report-components) owns the module-by-module UI map and manual checks.

The semantic projection exports six tables on the fact path and three display-label tables. `dim_questions` has one row per analyzable base question field. Label tables provide language variants while facts retain their base IDs. `fact_comments` retains the comment grain and prepared target columns. See the [Power BI guide](docs/guides/power-bi.md) and [semantic DBML](docs/power-bi-model.dbml) before changing join grains or filter paths.

## Dependencies and import behavior

The base installation includes HTTPX, Pydantic, settings support, and PyArrow. Typer/Rich belong to the `cli` extra; Jinja/MarkupSafe belong to `ui`. Load PyArrow when a Parquet operation needs it, and defer template imports until report rendering. A base installation must support SDK and data operations, and importing `render_report` must remain possible before installing the UI extra.

[Optional-dependency tests](tests/test_optional_dependencies.py) exercise unavailable dependencies; the [wheel smoke script](scripts/smoke_wheel.sh) checks installed base, CLI, UI, and combined environments. Dependency changes must preserve those boundaries unless an accepted ADR changes the contract.

## Typing and dynamic data

Annotate new and changed function signatures and model known structures with concrete types, `TypedDict`, or `Protocol`. The current `EntitySet` and `SemanticModel` store heterogeneous dictionaries because exports can add response properties and target-language columns. `Any` is permitted at those row boundaries and in extensible Qualtrics payloads. Validate and narrow values before domain operations; do not spread `Any` through otherwise known interfaces or use it to silence a type error.

## Evolving the architecture

Update this document when responsibilities, dependency rules, public interfaces, data flow, or invariants change. Keep schema details in the entity contract and DBML. Add a numbered [ADR](docs/adr/index.md) for a durable trade-off, reference it here, and update the affected architecture tests. Routine implementation details and temporary investigation notes belong in code or ignored `knowledge/` files.
