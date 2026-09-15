# Survey Translation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare user-supplied translations of written answers and missing definition labels, retain them without duplicating facts, and teach the complete export-to-Power-BI workflow.

**Architecture:** Comments remain a derived one-row-per-answer projection with reversible, nullable target-language columns. One translation module chooses a shared callback or a kind-specific override, clones missing locale rows with base catalog links, and returns a new entity collection. Reports and the semantic export read the same freshness rules.

**Tech Stack:** Python 3.11+, Qualtrics SDK, pytest, PyArrow, Jinja, MkDocs, SQLite.

**Spec:** `docs/superpowers/specs/2026-09-15-survey-translation-workflow-design.md`

## Global Constraints

- Original `response_answers.answer_text`, `raw_value`, `response_answer_id`, `question_id`, and catalog IDs do not change.
- One comment row per written answer; each prepared target adds nullable text, source hash, and source-language columns.
- Survey-language defaults are per survey; an explicit `language` override applies across the collection, including undeclared targets.
- QSF target labels outrank callback labels; callback-generated option labels never resolve answer facts.
- No bundled provider or automatic network translation call. A failing callback leaves the input unchanged and publishes no partial translated survey.
- Reject repeated survey IDs while combining. No legacy migration, push, PR, or release.

---

### Task 1: Comment target columns and persistence

**Files:**
- Create: `src/qualtrics/_common/models/translation_columns.py`
- Modify: `src/qualtrics/_common/models/comments.py`, `src/qualtrics/_common/models/entities.py`, `src/qualtrics/_common/models/entity_set.py`, `src/qualtrics/_common/serialization/io.py`
- Test: `tests/integration/test_comment_translations.py`, `tests/integration/test_comments_persistence.py`

**Interfaces:**
- Produces: `translation_columns(code: str) -> tuple[str, str, str]`; `prepared_targets(columns: Iterable[str]) -> set[str]`; `build_comments(entities: EntitySet) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write a failing mixed-target test.** Use the existing `_parsed` fixture and assert that a prepared EN target survives `write_entities`/`load_entities`, then merging an untranslated second survey yields null EN fields for its comments. Assert unchanged response-answer rows and comment count.

```python
prepared = prepare_comment_translations(_parsed(tmp_path), ["EN"], lambda *_: "Greetings")
write_entities(prepared, tmp_path / "entities", "parquet")
loaded = load_entities(tmp_path / "entities")
assert loaded.comments[0]["translated_text__EN"] == "Greetings"
assert loaded.response_answers[0]["answer_text"] == " Grüße <tag> "
```

- [ ] **Step 2: Run the test and see an expected failure.** Run `uv run pytest tests/integration/test_comment_translations.py -k mixed_target -q`; it must fail because comments lack target columns.
- [ ] **Step 3: Add reversible language-code columns and preserve only recognized prepared keys when rebuilding comments.** The encoder keeps ASCII letters/digits and escapes every other UTF-8 byte as `_HH_`, so `ES-ES` becomes `ES_2D_ES` and literal underscores cannot collide.

```python
def translation_columns(code: str) -> tuple[str, str, str]:
    suffix = "".join(chr(byte) if 65 <= byte <= 90 or 48 <= byte <= 57 else f"_{byte:02X}_"
                     for byte in code.upper().encode("utf-8"))
    return (f"translated_text__{suffix}", f"translation_source_hash__{suffix}",
            f"translation_source_language__{suffix}")
```

- [ ] **Step 4: Replace fixed comment-column checks with fixed-plus-complete-target validation.** CSV/Parquet column discovery uses the union of prepared comment keys and present columns. Reject unknown extras, malformed hashes, and duplicate answer IDs; compare fixed columns against source rows.
- [ ] **Step 5: Run targeted tests and commit.** Run `uv run pytest tests/integration/test_comment_translations.py tests/integration/test_comments_persistence.py -q` and `git diff --check`; commit with `feat(entities): retain prepared targets on comment rows`.

### Task 2: Callback preparation and localized label rows

**Files:**
- Create: `src/qualtrics/_common/models/translations.py`
- Modify: `src/qualtrics/_common/models/comment_translations.py`, `src/qualtrics/_common/parsers/localization.py`, `src/qualtrics/_common/models/entity_set.py`, `src/qualtrics/__init__.py`
- Test: `tests/integration/test_comment_translations.py`, `tests/integration/test_semantic_language_labels.py`, `tests/integration/test_translations_preparation.py`

**Interfaces:**
- Consumes: `translation_columns`, `build_comments`.
- Produces: `TranslationRequest(kind, text, source_language, target_language, survey_id, question_id, question_field_id, answer_option_id, response_answer_id)`; `prepare_translations(entities, *, language=None, translate=None, question=None, field=None, answer_option=None, comment=None) -> EntitySet`.

- [ ] **Step 1: Write failing tests** for QSF-first partial labels, EN target absent from a Norwegian QSF, base catalog retention, all comment kinds, unknown `UserLanguage`, already-target skip, two-target retention, and callback failure leaving the input unchanged.

```python
prepared = prepare_translations(source, language="EN", translate=recording_callback)
assert len(prepared.response_answers) == len(source.response_answers)
assert any(row.get("language_code") == "EN" and row.get("is_localized") for row in prepared.questions)
assert source.comments == original_comments
```

- [ ] **Step 2: Verify red.** Run `uv run pytest tests/integration/test_translations_preparation.py -q`; imports or assertions must fail because the new interface is absent.
- [ ] **Step 3: Implement one callback-selection seam** using a structured request, with kind-specific overrides taking priority over the shared callback. Deep-copy input; resolve each survey's target; clone only missing locale rows; hash each callback-generated base label; prepare comments only when a comment callback exists and source differs from target. Add prepared target codes to per-survey manifest metadata, not `AvailableLanguages`.

```python
callback = {"question": question, "field": field, "answer_option": answer_option,
            "comment": comment}[kind] or translate
if callback is not None and source_language != target_language:
    translated = callback(request)
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError(f"Translator returned no text for {request.kind} in {target_language}")
```

- [ ] **Step 4: Verify green, strict validation, and commit.** Run the targeted tests, verify QSF aliases still resolve base options while callback labels do not, and commit `feat(translations): prepare missing definition and comment labels`.

### Task 3: Semantic and HTML consumers

**Files:**
- Modify: `src/qualtrics/_common/models/semantic.py`, `src/qualtrics/_common/serialization/semantic.py`, `src/qualtrics/cli/translations.py`, `src/qualtrics/ui/report_languages.py`, `src/qualtrics/ui/pages/written.py`, `src/qualtrics/ui/static/pages/written.js`, `docs/power-bi-model.dbml`, `docs/entity-model.dbml`
- Test: `tests/integration/test_report_comment_translations.py`, `tests/integration/test_semantic_language_labels.py`, `tests/integration/test_comment_translations.py`, `tests/integration/test_cli_comments.py`, `tests/js/report-written.test.cjs`

**Interfaces:**
- Consumes: target columns, source hashes, callback label provenance.
- Produces: `fact_comments` at one-row-per-written-answer grain with prepared target columns; no `fact_comment_translations` table.

- [ ] **Step 1: Write failing consumer tests.** Assert one fact comment for one original answer, no separate translation table, current target payload in HTML, stale fallback cue, and unchanged fact counts when display language changes.

```python
model = build_semantic_model(prepared)
assert len(model.fact_comments) == len(prepared.comments)
assert model.fact_comments[0]["translated_text__EN"] == "Greetings"
assert "fact_comment_translations" not in SEMANTIC_TABLE_NAMES
```

- [ ] **Step 2: Verify red.** Run the named Python tests and `node --test tests/js/report-written.test.cjs`; expected failures are sidecar export or missing prepared comment fields.
- [ ] **Step 3: Read prepared targets from comments and label provenance.** Use original text for same-language, missing, or stale translations. Keep answer counts and base IDs fixed; export `fact_comments`' column union to CSV, JSON, Parquet, and SQLite. Pivot the CLI's prepared CSV/Parquet input into comment target columns, remove sidecar entity/table handling, and update DBML.
- [ ] **Step 4: Verify green and commit.** Run targeted Python and JS tests and `git diff --check`; commit `feat(semantic): expose prepared comment targets at comment grain` and `feat(report): display prepared labels with raw fallback` as separate commits when their respective checks pass.

### Task 4: Runnable example and concise guide

**Files:**
- Create: `examples/survey_workflow.py`, `docs/guides/survey-workflow.md`
- Modify: `mkdocs.yml`, `docs/reference/python.md`, `docs/guides/api-access.md`, `docs/guides/combine-surveys.md`, `docs/guides/power-bi.md`, `docs/entity-model.md`
- Test: `tests/integration/test_export_parse_and_report.py`, `tests/integration/test_survey_workflow_example.py`

**Interfaces:**
- Consumes: public `QualtricsClient`, `parse_survey`, `prepare_translations`, `merge_entity_sets`, `write_entities`, `render_report`, `build_semantic_model`, `write_semantic_model`.
- Produces: a runnable script with named export, parse, translate, save, report, merge, and semantic stages plus a MkDocs guide with an offline input variant.

- [ ] **Step 1: Write a failing script test** with a controlled Qualtrics HTTP transport or monkeypatched public client methods. Assert duplicate IDs fail before export, translation runs before combine, absent callback makes no translation call, optional report paths appear only when requested, and semantic tables land under output.
- [ ] **Step 2: Verify red.** Run `uv run pytest tests/integration/test_survey_workflow_example.py -q`; missing script or result must fail.
- [ ] **Step 3: Implement the script with small named functions and a thin argument parser.** Use public imports only. Export QSF and ZIP, parse the ZIP directly, optionally load a user-owned callback from `module:function`, prepare each survey, write Parquet entities, merge distinct survey IDs once, optionally render HTML, and write Power BI Parquet. Give each stage a clear output path and failure message.
- [ ] **Step 4: Write the guide and update links.** Explain defaults, QSF-first labels, callback request/overrides, nullable combined columns, raw fallback, and the local ZIP/CSV + QSF path. Keep the guide short enough to scan without losing required behavior.
- [ ] **Step 5: Verify and commit.** Run targeted example tests, `uv run poe docs-build`, and `git diff --check`; commit `docs(translations): teach the export-to-power-bi workflow`.

### Task 5: Full verification

**Files:** All changed files.

- [ ] **Step 1: Run full checks.** Run `uv run poe check`, `uv run poe build`, and `uv run poe docs-build`; inspect all exit codes and failure counts.
- [ ] **Step 2: Smoke-test four supplied survey exports.** Parse each response ZIP/CSV with its QSF, prepare an explicit shared target using a deterministic local callback, combine, and verify no response/answer-count change or survey-ID duplication. Inspect null target columns for surveys without prepared targets.
- [ ] **Step 3: Review VCS diff and report.** Run `git status --short`, `git diff --check`, and `git log -5 --oneline`. Report branch, commits, checks, and any remaining limitation; do not push or open a PR.
