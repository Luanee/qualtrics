# Qualtrics Entity and Semantic Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the beta entity schema with stable identities and complete question typing, make response answers analysis-ready, validate all formats, and export a Power BI star projection.

**Architecture:** Parsing always produces the nine normalized entities. Four stacked branches progressively add identity, the answer fact, validation, and a separate five-table semantic projection.

**Tech Stack:** Python 3.11+, Typer, SHA-256, JSON/QSF, pytest, CSV/JSON/Parquet, Markdown, DBML

**Spec:** `docs/superpowers/specs/2026-09-03-qualtrics-entity-and-semantic-model-design.md`

## Global Constraints

- Keep exactly nine parser entities.
- Replace the beta schema directly; do not migrate legacy folders.
- Preserve raw Qualtrics type metadata and unsupported data.
- Use domain-scoped, length-delimited hashes.
- Default semantic exports to Parquet.
- Every branch is based on and targets its predecessor.

---

### Task 1: Identity and complete question types

**Branch:** `feat/entity-identity-contract`

**Files:**
- Create: `src/qualtrics/models/identity.py`
- Create: `src/qualtrics/models/question_types.py`
- Modify: `src/qualtrics/parsers/survey.py`
- Modify: `src/qualtrics/parsers/qsf.py`
- Test: `tests/unit/test_entity_identity.py`
- Test: `tests/unit/test_question_types.py`
- Test: `tests/integration/test_package.py`

**Interfaces:**
- Produces: `entity_id(domain: str, *parts: object) -> str`
- Produces: `semantic_id(domain: str, content: object) -> str`
- Produces: `resolve_question_type(...) -> QuestionTypeDefinition`

- [ ] Write identity tests and verify they fail.
- [ ] Implement canonical serialization and domain-scoped hashing.
- [ ] Write tests for every documented type, compound fields, and unknown tuples; verify failure.
- [ ] Implement the type registry and lossless unsupported fallback.
- [ ] Write parser-contract tests for occurrence and catalog stability; verify failure.
- [ ] Apply IDs and raw/canonical type fields to the nine entities.
- [ ] Run focused and complete checks.
- [ ] Commit identity, typing, and parser changes in reviewable batches.

### Task 2: Analytical response-answer fact

**Branch:** `feat/response-answer-fact`, based on Task 1

**Files:**
- Modify: `src/qualtrics/parsers/survey.py`
- Modify: `src/qualtrics/analytics/report.py`
- Modify: `src/qualtrics/reporting/report.py`
- Modify executive reporting modules if present
- Test: `tests/integration/test_package.py`
- Test: `tests/integration/test_export_parse_and_report.py`

**Interfaces:**
- Produces: typed answer values and all fact foreign IDs from the spec

- [ ] Write failing fact-grain, ID, typed-value, and option-mapping tests.
- [ ] Build the full field lookup and populate fact IDs.
- [ ] Update analytics and reports to internal IDs without legacy fallbacks.
- [ ] Verify distinct-response denominators and mixed question types.
- [ ] Run all checks and commit in parser then consumer batches.

### Task 3: Contract validation and round trips

**Branch:** `feat/entity-contract-validation`, based on Task 2

**Files:**
- Modify: `src/qualtrics/models/entity_set.py`
- Modify: `src/qualtrics/serialization/io.py`
- Test: `tests/unit/test_entity_set.py`
- Create: `tests/integration/test_serialization.py`
- Modify: `tests/integration/test_cli_entities.py`

**Interfaces:**
- Produces: `validate_entity_set(entities: EntitySet, *, strict: bool = False) -> None`

- [ ] Write failing uniqueness, relationship, schema, and collision tests.
- [ ] Implement partial and strict validation.
- [ ] Write failing JSON, CSV, Parquet, and mixed-combine round-trip tests.
- [ ] Preserve exact field types and validate loaded folders.
- [ ] Run all checks and commit validation then serialization batches.

### Task 4: Power BI semantic projection and documentation

**Branch:** `feat/powerbi-semantic-model`, based on Task 3

**Files:**
- Create: `src/qualtrics/models/semantic.py`
- Create: `src/qualtrics/serialization/semantic.py`
- Create: `src/qualtrics/cli/semantic_model.py`
- Modify: `src/qualtrics/cli/app.py`
- Create: `docs/entity-model.md`
- Create: `docs/entity-model.dbml`
- Modify: `README.md`
- Test: `tests/unit/test_semantic_model.py`
- Test: `tests/integration/test_cli_semantic_model.py`
- Test: `tests/unit/test_model_documentation.py`

**Interfaces:**
- Produces: `build_semantic_model(entities: EntitySet) -> SemanticModel`
- Produces CLI: `qualtrics semantic-model build`

- [ ] Write failing projection-grain and flattened-dimension tests.
- [ ] Implement the five-table semantic projection.
- [ ] Write failing CLI tests for Parquet default and JSON/CSV selection.
- [ ] Implement strict source validation and safe output behavior.
- [ ] Document nine normalized entities, star relationships, Date table, and DAX.
- [ ] Run complete checks and package build.
- [ ] Commit projection, CLI, and documentation batches.

### Task 5: Final stacked verification

- [ ] Parse representative CSV/QSF fixtures into all nine entities.
- [ ] Round-trip JSON, CSV, and Parquet.
- [ ] Build all five semantic tables.
- [ ] Render reports from the new contract.
- [ ] Run `uv run poe check` and `uv run poe build`.
- [ ] Review each branch diff against its parent and record PR order.
