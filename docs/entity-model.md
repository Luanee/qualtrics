# Qualtrics entity and semantic model

This reference defines the tables, IDs, and relationships used by the toolkit. For a plain-language introduction, start with [understand your data](understand/your-data.md). Follow the [Power BI guide](guides/power-bi.md) to export and connect the analysis tables.

Explore the ten exported entities and their relationships in the diagram below. The viewer needs an internet connection; no account or API key is required. The table descriptions on this page and the downloadable DBML remain available if the viewer cannot load.

<iframe class="dbml-model" title="Ten-entity Qualtrics data model" src="{{ dbml_entity_url }}" loading="lazy" referrerpolicy="no-referrer" allowfullscreen></iframe>

<p><a href="{{ dbml_entity_url }}" target="_blank" rel="noopener">Open the entity diagram at full size</a></p>

[Download the ten-entity DBML schema](entity-model.dbml) to inspect the full column and relationship contract in a compatible schema tool.

Parsing produces nine authoritative entities plus the derived `comments` table, for ten exported tables. A sibling `manifest.json` carries survey-specific flow and source-column descriptors; it is metadata, not an eleventh entity. Occurrence IDs are survey-safe hashes; `*_external_id` columns preserve Qualtrics lineage. Catalog IDs identify normalized semantics across surveys. Catalog merging compares the complete stored normalized content, including the parent question catalog ID for fields, while retaining the [first input’s representative display labels](guides/combine-surveys.md#representative-catalog-labels). Concrete question, field, and answer-option rows remain survey-specific.

When a QSF supplies `SurveyLanguage`, including under `SurveyOptions`, that code becomes `surveys.default_language` and identifies the language of the base question text used for catalog identity. The per-survey `manifest.json` entry also records `languages.base_language`, declared `languages.available_languages`, and `languages.all_languages` (the base, available, and every code found under a question's `Language` object). An absent QSF leaves these values empty or null; response `UserLanguage` is never inferred from them.

For every code in `all_languages`, `questions`, `question_fields`, and `answer_options` contain a language variant. Each variant has its own internal ID and `language_code`, but retains the base question and field catalog IDs and native external IDs. `label_source_language` records whether its visible label came from that translation or fell back to the base language. Localized rows have no separate CSV column or answer facts; the original base rows remain the fact targets. Combining surveys retains each survey's language registry and keeps same-named native IDs survey-scoped.

| Entity | Grain | Primary ID | Main parents |
|---|---|---|---|
| `surveys` | survey | `survey_id` | none |
| `sections` | survey block | `section_id` | `survey_id` |
| `question_catalog` | semantic question | `question_catalog_id` | none |
| `question_field_catalog` | semantic field | `question_field_catalog_id` | `question_catalog_id` |
| `questions` | survey question × definition language, exported or QSF-only | `question_id` | survey, section, question catalog |
| `answer_options` | definition option × language for one question field | `answer_option_id` | survey, question, question field |
| `question_fields` | exported or QSF-only question field × language | `question_field_id` | question, both catalogs |
| `responses` | submitted response | `response_id` | survey |
| `response_answers` | non-empty response field | `response_answer_id` | response, question, field, optional option |
| `comments` | derived nonblank text answer field | original `response_answer_id` | original answer, response, survey, question, field |

Each `sections` row represents one configured survey block, identified internally by the survey-scoped `section_id`. Its `section_external_id` retains the native block ID, including a dictionary key used when the block has no explicit `ID`. List position never becomes a block ID. `questions.section_id` links to that internal section ID; the flattened `dim_questions` carries the section name and block order. A block referenced more than once in survey flow still has one section row, while the flow keeps each occurrence as a separate node. Trash blocks have no section row, but their position remains in block ordering.

When a definition supplies both QSF `BL.Payload` and direct `Blocks`, direct entries take precedence. Matching dictionary keys retain their existing merge behavior and position. If one container is a dictionary and the other is a list, matching native block IDs also reconcile into one section at the first occurrence's position, even when dictionary keys differ. Two dictionaries with different keys remain separate under the established key-based behavior; reconcile conflicting definitions at the source.

Questions retain `question_type`, `selector`, and `sub_selector` exactly and add `canonical_question_type`. Fields and answers add `answer_value_type`. Unknown combinations remain available with `unsupported` classification.

Questions found only in the QSF also appear in `questions`. Answerable QSF-only definitions produce deterministic `question_fields` and, for discrete choices, `answer_options`; display-only questions do not get invented answer fields. All such rows carry `is_definition_only = true`. Their fields have null `source_column_index` and `import_external_id`, and their synthetic `field_external_id` begins with `QSF:` rather than naming an exported column. The codebook lists them as definition-only. They have no response facts and are excluded from response-rate, unanswered, and unused-field metrics; a missing CSV field is not a zero response.

`answer_options` is built exclusively from the QSF definition, never from observed response values. Its identity is the hash of `question_field_id` and the native Qualtrics `answer_id`. `answer_code` contains the configured recode or falls back to `answer_id`; `answer_order` is the 1-based definition order. Single-choice questions publish every choice, multiple-choice questions publish one choice per concrete selection field, and matrix questions publish every answer for each matrix-row field. Text, form, slider, and `*_TEXT` fields publish no options. The additive provenance fields below leave these identities and table grains unchanged.

`question_fields.choice_external_id` preserves the Choice or matrix-row lineage determined from export metadata and the full `ImportId`. Its optional `statement_text` preserves a matrix statement's label from the survey definition; `field_text` still describes the concrete exported field, which can include an individual option. `response_answers` preserves `answer_text` and provides nullable `answer_numeric`, `answer_boolean`, `is_selected`, and `answer_option_id` for analysis. Unknown or ambiguous response values remain raw with a null option ID. There is no cross-survey answer-option catalog.

For native Loop & Merge identifiers, the suffix after the matching question ID identifies the choice or matrix row: `2_QID1_1` is iteration 2, choice 1; `1_QID1_2` is iteration 1, choice 2. A native matrix cell such as `2_QID3_1_3` uses row 1 and scale answer 3. Valid explicit `choiceId`, `ChoiceId`, or `choiceID` metadata takes precedence over that suffix; valid `answerId`, `AnswerId`, or `answerID` metadata likewise overrides an inferred matrix answer. Invalid metadata falls back to the native suffix, not to an iteration number. The full exported field identity retains its loop prefix, so separate iterations remain separate fields and answers.

When there is no native choice suffix, the supported legacy prefix convention remains: `1_QID1_TEXT` and `2_QID1_TEXT` identify attached text for choices 1 and 2, including their choice-specific validation. Multiple-answer matrix cells also retain the legacy `row_QID_answer` convention when there is only one suffix position, for example `1_QID3_3` is row 1, answer 3. This ambiguous shape is interpreted as a legacy cell; native looped cells need both row and answer suffixes. Corrected choice links can change option IDs and, when normalized option content changes, catalog IDs. The identity algorithms and concrete survey, question, field, response, and answer IDs are unchanged.

Choice matching gives explicit `RecodeValues` priority within the answer's question field. If native choice `1` has recode `2`, an exported `2` links to that choice even when native choice `2` also exists. This also applies to categorical matrix answer domains. Without an explicit recode match, the parser uses an unambiguous match against the native ID, cleaned `Display` label, or export tag. Two choices sharing the same recode remain unresolved; a lower-priority alias does not break the tie. Raw answer text and option identities are preserved.

When `UserLanguage` identifies a QSF language, a translated choice or matrix-scale label can also resolve a categorical answer. An unambiguous translated label points to the **base** `answer_option_id`; it never creates another fact or rewrites `answer_text`/`raw_value`. Explicit recodes and native IDs retain priority over labels. A translated label can disambiguate a collision with a different base-language display label, but duplicate labels within the respondent's language remain unlinked. Null or unknown `UserLanguage` provides no translated alias; text and continuous numeric answers are never promoted to options.

For example, choice `1` with `Display: "Yes"` and recode `2` receives answers exported as either `2` or `Yes`, provided the selected matching level identifies one choice. A numeric display label can itself collide with another choice's recode; the explicit recode takes priority under this rule. Rebuild existing entities from the original CSV and matching QSF to apply the corrected links, then regenerate the report or semantic model.

## Comments

`comments` is a derived subset of `response_answers`, with one row for each nonblank text answer field. The original nine entity tables remain authoritative. Every comment remains in `response_answers` with its original ID, text, types, and option links. Do not add comment counts to all-answer counts.

| Column | Meaning |
| --- | --- |
| `response_answer_id` | Primary key reused from the original answer; no new ID is generated. |
| `response_id` | Linked response. |
| `survey_id` | Survey containing the answer. |
| `question_id` | Question containing the field. |
| `question_field_id` | Exact exported field containing the text. |
| `answer_text` | Original answer text, unchanged. |
| `raw_value` | Exact original CSV cell when available; null when an older answer lacks this provenance. |
| `user_language` | Language code copied only from the linked `responses` row; nullable. |

The language code describes the response metadata, not a detected language of the text. A missing response language stays null even when the survey has a default language. Whitespace, punctuation, and leading zeros in retained text remain unchanged. Two responses with the same comment produce two rows; two text fields from one response also produce two rows. Fields are never concatenated or deduplicated by text.

Membership follows the question's response role and the effective field type. Supported text-entry fields, form text, matrix text, and attached `*_TEXT` fields qualify. Categorical labels, numeric/date/file/structured/unsupported answers, technical fields, and response properties do not. A numeric-looking identifier in a text field still qualifies; a field with explicit numeric validation does not. Whitespace-only cells stay in `response_answers` but are excluded from `comments` and the report's **Written answers** view.

New `question_fields.is_comment_field` values carry nullable boolean classification evidence through entity files and into `dim_questions`. The parser prefers explicit source metadata, including unambiguous side-by-side column mappings. It does not guess an unknown side-by-side column's type from its label. Incomplete definitions and unsupported combinations can therefore omit fields from the comments projection while retaining their original answers.

Legacy nine-table folders remain valid: loading reconstructs comments from the available question and field types when `is_comment_field` is absent or null. Reparse with the matching QSF to recover stronger source evidence. Parse, merge, load, entity write, and semantic build regenerate the projection; a supplied comments file must agree with its source answers and responses. Edit or reparse the authoritative data instead of maintaining a separate comments copy. Current exports write `comments.json`, `comments.csv`, or `comments.parquet`, including an empty table when no fields qualify.

## Answer value provenance

Newly parsed options distinguish the definition's different representations:

| Column on `answer_options` | Meaning |
| --- | --- |
| `source_choice_id` | Native option ID as text. For a matrix, this is the scale answer ID, not the statement row ID. |
| `choice_value` | Cleaned respondent-visible `Display` text; an empty string when no text is provided. |
| `recode_value` | Explicit `RecodeValues` entry as text, or null when not provided in the source definition. Zero and codes such as `02` are preserved. |
| `variable_name` | Exact configured `VariableNaming` export label for a multiple-choice option, or null when not provided. Matrix variable-name mapping is not currently inferred. |
| `value` | `recode_value` when it is not null; otherwise `choice_value`. This is the toolkit's normalized value. |

Existing columns remain available: `answer_id` and `answer_external_id` retain the native ID, `answer_code` retains its recode-or-native-ID fallback, and `answer_text` retains the cleaned choice label. `answer_export_tag` remains separate from `variable_name`.

CSV entity files preserve empty required choice text and normalized values on rows carrying `source_choice_id`. Blank optional metadata cells, including `recode_value` and `variable_name`, follow the existing CSV convention and load as null.

Qualtrics assigns numeric recodes and export variable names by default. A null `recode_value` or `variable_name` here describes the explicit metadata available in the supplied definition; it does not mean Qualtrics has no default numeric code or label. Default export labels generally use the choice text. See [Qualtrics recode values and variable names](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/recode-values/).

`response_answers.raw_value` preserves the exact original nonempty CSV cell, including whitespace, punctuation, and leading zeros. The existing `response_answers.answer_text` is unchanged and contains that same raw text. Neither field is replaced by an option's normalized value. Without a definition, raw values still survive and unresolved option links remain null.

For native choice `1`, choice text `Yes`, explicit recode `2`, and configured export label `Affirmative`, the option's `value` is `2`. Raw `2`, `Yes`, or `Affirmative` can resolve to that option when their matching level is unambiguous. Explicit recodes take priority; the parser does not infer a universal numeric-versus-label export mode. Duplicate recodes remain unresolved. Use `answer_option_id` for the relationship, never a join from `raw_value` to `value`: representations can differ, and values can repeat within or across fields.

These columns also travel to `dim_answer_options` and `fact_response_answers`. Older entity folders remain readable and renderable, but missing provenance stays unavailable. In particular, a legacy `answer_code` does not prove an explicit recode. Reparse the original CSV/ZIP with its matching QSF to recover the source metadata, then rebuild the semantic model and report.

## Response properties and source columns

`responses` has one row per submission, including the existing normalized system columns and additional columns for embedded data, technical metadata, and unclassified source values. Custom columns contain the original text or null. No additional entity table is created.

Every entity and semantic export folder contains one `manifest.json`. Its `surveys` object is keyed by `survey_id`, so a combined export keeps metadata for every survey in the same file. Each entry has `flow_definition_json` (a JSON object or null) and `source_columns_json` (a JSON array). These are native JSON values, not JSON strings inside `surveys` or `dim_surveys` rows. The top-level `schema_version` is currently `1`.

Each `source_columns_json` descriptor contains:

| Key | Meaning |
| --- | --- |
| `source_column` | Original CSV column name, including duplicates |
| `source_column_index` | Zero-based CSV position |
| `source_import_id` | Export metadata identifier, when available |
| `label` | Exported column label |
| `kind` | `question`, `derived`, `system`, `embedded`, `quality`, `metadata`, `timing`, or `unclassified` |
| `reason` | Evidence used for classification |
| `storage_table` | `responses` for properties or `response_answers` for question fields |
| `storage_column` | Response property key, or external question-field key for answer rows |
| `question_external_id` | Question lineage when applicable |

Explicit question metadata and matching QSF definitions identify answer fields. Standard export identifiers identify system fields; embedded declarations are read recursively from the configured survey flow. Unique question export tags can supply a fallback. Missing or ambiguous evidence preserves the column as an unclassified response property. Business names alone do not identify question answers, and flow defaults never populate observed responses.

Standard columns retain existing normalized keys; `ResponseId` maps to `response_external_id` while `response_id` remains the internal stable identifier. Other property names normally retain their source spelling. The parser disambiguates duplicate headers and names that collide case-insensitively with normalized response columns. Combining surveys reconciles these mappings, preserves different source properties, and fills absent columns with null. Read the relevant survey's manifest entry for the actual column name rather than depending on a generated suffix.

Technical browser and timing values are stored on responses. Existing question-field definitions can still describe those exported fields. Derived question outputs retain their question relationship and existing answer identities; their dictionary classification distinguishes them from direct answers. The established entity and catalog hash algorithms are unchanged.

`questions.question_role` is optional in legacy entity folders. Report analytics and the comments projection honor a saved role; otherwise they classify the normalized question type and selector, then related question fields' `import_external_id` (falling back to legacy `source_import_id`). ImportId evidence is confined to the same survey and question. Timing and metadata questions are omitted from respondent-facing report counts, question spotlights, coverage, and unused-field diagnostics, while their saved question fields, responses, answer rows, raw values, language, and IDs remain intact. A question without surviving technical evidence defaults to the response role; rebuilding a report does not restore evidence absent from the saved entities.

When an older `comments` file contains text that the corrected question-wide role excludes, strict loading rejects that stale projection. Remove the stale `comments` file, load the nine authoritative entity tables, and write a new entity folder to regenerate comments. Rebuild the semantic model from that folder to refresh `fact_comments`; the original `response_answers` and response language remain authoritative.

Reparse the original export to recover fields omitted by older versions. An older entity folder without `manifest.json` remains readable, but it cannot provide source evidence or values it never retained. New exports write the manifest for every survey, including combined folders.

## Semantic projection

`qualtrics semantic-model build ENTITY_FOLDER --output MODEL_FOLDER` writes Parquet by default. Use `--format json` or `--format csv` when needed. It creates:

- `fact_responses`
- `fact_response_answers`
- `dim_surveys`
- `dim_questions`
- `dim_answer_options`
- `fact_comments`
- `dim_display_languages`
- `dim_question_labels`
- `dim_answer_option_labels`

The semantic model has nine exported tables plus the sibling `manifest.json`: six base-grain fact-path tables and three display-label tables. Its diagram shows six fact-path and two label-only relationships; DBML symbols describe cardinality, while Power BI's cross-filter direction is a separate setting.

<iframe class="dbml-model" title="Nine-table Power BI semantic model" src="{{ dbml_power_bi_url }}" loading="lazy" referrerpolicy="no-referrer" allowfullscreen></iframe>

<p><a href="{{ dbml_power_bi_url }}" target="_blank" rel="noopener">Open the Power BI diagram at full size</a></p>

[Download the nine-table Power BI DBML schema](power-bi-model.dbml). The interactive viewer requires an internet connection; the relationship instructions below also describe the model.

`dim_questions` has one row per analyzable exported question field and flattens section, question, field, and catalog attributes. Create these active single-direction relationships in Power BI:

The active `dim_questions` and `dim_answer_options` keep only base-language, exported rows. Definition-only and localized entity rows are reserved for the codebook and dedicated localization tables, so adding languages never duplicates measures or creates zero-looking answer categories.

`dim_display_languages` lists each display code across the combined collection; `is_available` marks codes declared available or used as a base by at least one survey. `dim_question_labels` maps each exported base `question_field_id` and display code to its question and field text; `dim_answer_option_labels` maps each base `answer_option_id` and display code to its choice text. Missing translations fall back to that survey's base labels, recorded in the source-language columns. These tables do not duplicate facts or replace the base IDs. Use a single-select display-language slicer separately from `fact_responses.user_language`; only the latter filters respondents. See the [Power BI display-label recipe](guides/power-bi.md#display-language-recipe).

```text
dim_surveys[survey_id] 1 -> * fact_responses[survey_id]
fact_responses[response_id] 1 -> * fact_response_answers[response_id]
dim_questions[question_field_id] 1 -> * fact_response_answers[question_field_id]
dim_answer_options[answer_option_id] 1 -> * fact_response_answers[answer_option_id]
fact_responses[response_id] 1 -> * fact_comments[response_id]
dim_questions[question_field_id] 1 -> * fact_comments[question_field_id]
```

Set cross-filter direction to **Single**, from each one side to its many side. Survey filters reach responses and then both answer tables. Question filters reach both answer tables; option filters reach only `fact_response_answers`.

`fact_comments` carries the same eight columns and membership as `comments`. It is a convenient text subset, while `fact_response_answers` remains the complete answer fact. Do not join the two answer facts or add a direct active path from `dim_surveys` to `fact_comments`. Use `fact_responses.user_language` as a shared language slicer; the copied language on `fact_comments` can label individual comments.

`dim_answer_options` has one row per field-specific option. Use `question_field_id` to associate it with `dim_questions`; keep the fact relationship on `answer_option_id`.

Create a model-local Date table and relate it to `fact_responses[recorded_at]`. This optional table is created in Power BI and is not one of the nine exported tables. Do not add parallel active paths from surveys, questions, labels, or catalogs to the answer fact.

## Baseline DAX

```DAX
Responses := DISTINCTCOUNT(fact_responses[response_id])

Respondents With Answer := DISTINCTCOUNT(fact_response_answers[response_id])

Answer Rows := COUNTROWS(fact_response_answers)

Comment Rows := COUNTROWS(fact_comments)

Responses With Comment := DISTINCTCOUNT(fact_comments[response_id])

Question-scoped Responses :=
CALCULATE(
    [Responses],
    TREATAS(VALUES(dim_questions[survey_id]), fact_responses[survey_id])
)

Question Response Rate := DIVIDE([Respondents With Answer], [Question-scoped Responses])

Numeric Answer Average := AVERAGE(fact_response_answers[answer_numeric])
```

Use `Responses` for survey denominators because the answer fact intentionally excludes empty fields.

`Comment Rows` counts text fields, while `Responses With Comment` counts submissions with at least one such field. Both are already included in the corresponding all-answer measures. See the [Power BI guide](guides/power-bi.md#5-add-measures-with-the-right-denominator) for a comment response rate and a worked example.
