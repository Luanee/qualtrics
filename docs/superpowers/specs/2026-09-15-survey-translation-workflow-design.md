# Survey translation workflow design

## Outcome

Users can export and parse distinct Qualtrics surveys, prepare optional translations with their own callbacks, read original and translated comments in the same table, render reports, combine surveys, and build Power BI tables. Translation changes display text and never changes response or answer counts, raw text, catalog identity, or option links.

## Languages and sources

- `UserLanguage` on the linked response is the source language of a written answer. Null or unknown values remain unknown and reach the user's callback as `None`.
- QSF `SurveyLanguage` is the source language of base question, field, and option labels. If absent, the callback receives `None`; the toolkit does not guess.
- Each survey's `SurveyLanguage` is its default target. A nonblank explicit `language` override applies one target to every survey in a combined collection, even when Qualtrics did not declare it in `AvailableLanguages`.
- `AvailableLanguages` describes Qualtrics-declared languages; it is not an authorization gate for a user-supplied translator. The manifest records prepared targets separately from QSF-declared languages.

## Translation interface

One public preparation function accepts an `EntitySet`, an optional target language, one default translator, and optional question, field, answer-option, and comment overrides. A translator receives a structured request with text, source and target languages, text kind, survey and question context, and the relevant field, option, or answer ID. It returns a nonblank string or raises. The toolkit bundles no provider and makes no network translation call itself.

For definition labels, use a QSF label when that exact target label exists; call the selected translator only for a missing target label. A target equal to the source language uses the base label without a call. Question, field, and option rows for callback-prepared targets have unique localized IDs, retain base question and field catalog IDs, and record provenance and the hash of the base source label. A stale callback label is unavailable until refreshed. Callback-generated option labels never become answer-resolution aliases; native IDs, recodes, and QSF translations remain the only match evidence.

For written answers, call the selected comment translator for every nonblank free-text answer whose `UserLanguage` differs from the target. When the languages match, keep only the original. If no comment translator is supplied, keep only original comments. Empty output or a callback exception fails preparation for that survey and does not mutate the input collection or publish partial translated results.

## Comment and semantic grain

`comments` has one row per original written `response_answer_id`. Its fixed columns retain original `answer_text`, `raw_value`, response, survey, question, field, and nullable `user_language`. Each prepared target adds three nullable columns: translated text, source-text hash, and source language. A reversible language-code encoding names those columns without collisions. Preparing another target retains existing current targets. Combined surveys publish the union of target columns, with null for a survey or response without that target.

The derived comment builder keeps translation columns while refreshing fixed columns from authoritative answer and response rows. Validation rejects invented or duplicated comment rows and malformed translation metadata. A changed original text or source language makes a prepared translation stale; report and semantic consumers use the original until the callback refreshes it. `fact_comments` mirrors this grain and includes the same target columns. The separate `comment_translations` entity and `fact_comment_translations` table disappear. The active Power BI fact and dimension grains remain unchanged.

## Consumer behavior

- Display-language selection changes definition labels and prepared written text, never raw `response_answers` or counts.
- A missing or stale target label or comment falls back to original text with a visible original-language cue in the HTML report. Power BI exports freshness metadata and a recipe for equivalent fallback.
- QSF-defined translations remain usable with no translator. With no comment translator, written answers remain raw and parsing/reporting stay offline.
- CSV, JSON, Parquet, and SQLite exports preserve prepared languages, nullable mixed-survey columns, lineage, and source hashes.

## User workflow

A runnable Python example uses only public package imports and small named stages: export QSF and response ZIP for each distinct survey ID, parse, optionally prepare translations, save each survey, optionally render each report, combine once, optionally render the combined report, and write Power BI data. It rejects repeated survey IDs before export and never combines response snapshots of one survey implicitly. A short MkDocs guide explains callback wiring, target rules, failure behavior, remote use, and an offline CSV/ZIP + QSF variant. The example does not add a new high-level package function.

## Verification

Tests cover QSF-first partial labels, callback-generated target rows and catalog links, known and unknown respondent languages, already-target and absent callbacks, multi-target retention, source changes, callback failure atomicity, no generated option alias linking, mixed-survey nullable columns, round-trips, report fallback, Power BI grains, and the runnable workflow. Run targeted tests, `uv run poe check`, and `uv run poe build`. No push or PR is part of this request.
