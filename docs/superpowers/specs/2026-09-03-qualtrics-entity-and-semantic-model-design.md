# Qualtrics Entity and Semantic Model Design

## Goal

Produce nine normalized entities from every Qualtrics CSV/QSF parse, give those entities stable analytical identities, and provide a separate star-schema projection centered on response answers for Power BI and similar tools.

The repository is in beta. The new schema replaces the current schema directly. Loaders reject stale entity folders instead of migrating them.

## Delivery and branch stack

Implementation is split into four stacked branches:

1. `feat/entity-identity-contract`, based on `main`
2. `feat/response-answer-fact`, based on `feat/entity-identity-contract`
3. `feat/entity-contract-validation`, based on `feat/response-answer-fact`
4. `feat/powerbi-semantic-model`, based on `feat/entity-contract-validation`

Each branch must pass the complete repository check before the next branch is created.

## Normalized parser contract

Parsing a Qualtrics response CSV or ZIP, with an optional QSF definition, always returns the existing nine entities:

- `surveys`
- `sections`
- `question_catalog`
- `question_field_catalog`
- `questions`
- `answer_options`
- `question_fields`
- `responses`
- `response_answers`

Survey-definition versioning and legacy entity migration are outside scope.

### Identity rules

`survey_id` remains the Qualtrics SurveyID. Every other occurrence receives a deterministic SHA-256 identifier built from length-delimited UTF-8 components and an entity domain. Examples:

```python
entity_id("question", survey_id, question_external_id)
entity_id("response", survey_id, response_external_id)
semantic_id("question", canonical_question_content)
```

Source identifiers remain available as `*_external_id`. Identifiers never depend on display order, block membership, or whether unrelated surveys are parsed together.

### Semantic catalog rules

Catalog identities represent equivalent analytical concepts across surveys. Canonical semantic content uses deterministic JSON with:

- Unicode normalization
- HTML removal and entity decoding
- collapsed whitespace
- case-normalized comparison text
- explicit null representation
- named roles for choices, statements, scale points, and fields
- order-independent multisets that preserve duplicate labels

Question semantics include normalized wording, canonical question type, field roles, and normalized answer content. They exclude survey IDs, QIDs, block IDs, source choice IDs, and display order.

Catalog deduplication compares both ID and canonical content. Equal IDs with unequal canonical content are an error.

## Complete question-type handling

The parser preserves raw QSF/API values verbatim:

- `question_type`
- `selector`
- `sub_selector`

It derives `canonical_question_type` and `answer_value_type` from the complete tuple. Compound questions also place `answer_value_type` and `field_role` on each `question_field` because one question can export fields with different analytical behavior.

The supported registry covers all question types and documented variants in the Qualtrics Create Question API and Qualtrics Question Types overview, including multiple choice, text entry, descriptive text/graphic, matrix, form field, calendar, slider, rank order, side by side, NPS, timing, graphic slider, constant sum, file upload, number scale, pick/group/rank, drill down, signature, heat map, hot spot, meta info, captcha, highlight, screen capture, video response, unmoderated user testing, location selector, ArcGIS map, solicit reviews, tree testing, and org hierarchy.

Unknown future combinations retain their raw metadata, definition content, fields, and answers and receive `canonical_question_type="unsupported"` and `answer_value_type="unsupported"`. Unsupported classification never drops data.

Tests use API-shaped and QSF-shaped fixtures, cover every documented type and selector combination available in the reference material, and verify missing and unknown tuples.

## Response-answer fact

`response_answers` keeps one row per non-empty exported response field. It carries:

- `response_answer_id`
- `survey_id`
- `response_id`
- `question_id`
- `question_catalog_id`
- `question_field_id`
- `question_field_catalog_id`
- nullable `answer_option_id`
- `answer_text`
- nullable `answer_numeric`
- nullable `answer_boolean`
- nullable `is_selected`
- `answer_value_type`

`answer_text` preserves the exported value. Typed columns add analytical interpretations without replacing it. Option IDs are populated only when the parser can map a value unambiguously.

`responses` remains a separate one-row-per-response fact header so reports can count empty and partially answered responses correctly.

## Validation and serialization

`validate_entity_set` checks primary-ID uniqueness for every present entity. It checks a relationship when both participating entity collections are present. Strict validation additionally requires all nine collections and every required column.

JSON, CSV, and Parquet round trips preserve the full contract. Identifiers and hashes remain strings. Stale beta folders fail with an error naming the entity and missing columns.

Mixed-format combination continues to work. Surveys must be unique by `survey_id`; catalogs deduplicate by semantic ID only after their canonical payloads match.

## Semantic projection

The semantic projection is built from an existing nine-entity `EntitySet`; it does not change parser output. It contains:

- `fact_responses`
- `fact_response_answers`
- `dim_surveys`
- `dim_question_fields`
- `dim_answer_options`

`dim_question_fields` flattens `sections`, `questions`, `question_catalog`, `question_fields`, and `question_field_catalog`. It supports occurrence analysis through question and field IDs and cross-survey analysis through catalog IDs.

The projection uses these active, single-direction relationships:

```text
dim_surveys[survey_id] 1 -> * fact_responses[survey_id]
fact_responses[response_id] 1 -> * fact_response_answers[response_id]
dim_question_fields[question_field_id] 1 -> * fact_response_answers[question_field_id]
dim_answer_options[answer_option_id] 1 -> * fact_response_answers[answer_option_id]
```

A model-local Date dimension relates to `fact_responses.recorded_at`. It is not a parser entity or exported semantic table.

The normalized source tables may retain other foreign keys for validation, but the semantic model does not create active relationships that produce alternate paths from surveys, questions, fields, or catalogs to the answer fact.

## CLI behavior

A separate semantic-model command reads a complete entity folder and writes the five projection tables. Parquet is the default; JSON and CSV remain available. It validates the source strictly before projection and refuses to overwrite a non-empty output entity collection.

## Reporting and analytics

All analytics, standard reporting, and any executive reporting present on the branch use internal IDs. Measures distinguish response headers from answer rows:

- total responses count distinct `fact_responses.response_id`
- respondents with an answer count distinct `fact_response_answers.response_id`
- answer volume counts fact answer rows
- question response rate divides respondents with an answer by eligible responses
- numeric measures use `answer_numeric`

## Documentation

`docs/entity-model.md` documents all nine normalized entities, their grains, fields, types, nullability, and keys. `docs/entity-model.dbml` mirrors that contract. Power BI documentation explains the five-table projection, active relationships, Date table, and baseline DAX measures.

## Verification

Each branch uses test-driven changes and focused commits. Before advancing the stack, run formatting, Ruff, type checking, pytest with configured coverage, and package build checks. Final verification parses real fixtures, round-trips all three formats, validates the nine entities, builds the semantic projection, and renders the HTML report.

## References

- [Qualtrics Create Question API](https://api.qualtrics.com/5d41105e8d3b7-create-question)
- [Qualtrics Question Types overview](https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/question-types-guide/question-types-overview/)
