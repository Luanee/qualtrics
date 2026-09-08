# Qualtrics entity and semantic model

This reference defines the tables, IDs, and relationships used by the toolkit. For a plain-language introduction, start with [understand your data](understand/your-data.md). Follow the [Power BI guide](guides/power-bi.md) to export and connect the analysis tables.

[Download the DBML schema](entity-model.dbml) to inspect the full column and relationship contract in a compatible schema tool.

Parsing always produces nine normalized entities. Occurrence IDs are survey-safe hashes; `*_external_id` columns preserve Qualtrics lineage. Catalog IDs identify normalized semantics across surveys.

| Entity | Grain | Primary ID | Main parents |
|---|---|---|---|
| `surveys` | survey | `survey_id` | none |
| `sections` | survey block | `section_id` | `survey_id` |
| `question_catalog` | semantic question | `question_catalog_id` | none |
| `question_field_catalog` | semantic field | `question_field_catalog_id` | `question_catalog_id` |
| `questions` | survey question | `question_id` | survey, section, question catalog |
| `answer_options` | definition option for one exported question field | `answer_option_id` | survey, question, question field |
| `question_fields` | exported question field | `question_field_id` | question, both catalogs |
| `responses` | submitted response | `response_id` | survey |
| `response_answers` | non-empty response field | `response_answer_id` | response, question, field, optional option |

Questions retain `question_type`, `selector`, and `sub_selector` exactly and add `canonical_question_type`. Fields and answers add `answer_value_type`. Unknown combinations remain available with `unsupported` classification.

`answer_options` is built exclusively from the QSF definition, never from observed response values. Its identity is the hash of `question_field_id` and the native Qualtrics `answer_id`. `answer_code` contains the configured recode or falls back to `answer_id`; `answer_order` is the 1-based definition order. Single-choice questions publish every choice, multiple-choice questions publish one choice per concrete selection field, and matrix questions publish every answer for each matrix-row field. Text, form, slider, and `*_TEXT` fields publish no options. This field-scoped identity is a breaking entity-contract change, so existing entity folders must be rebuilt from CSV/ZIP and QSF.

`question_fields.choice_external_id` preserves the Choice or matrix-row lineage determined from export metadata and the full `ImportId`. Its optional `statement_text` preserves a matrix statement's label from the survey definition; `field_text` still describes the concrete exported field, which can include an individual option. `response_answers` preserves `answer_text` and provides nullable `answer_numeric`, `answer_boolean`, `is_selected`, and `answer_option_id` for analysis. Unknown or ambiguous response values remain raw with a null option ID. There is no cross-survey answer-option catalog.

## Semantic projection

`qualtrics semantic-model build ENTITY_FOLDER --output MODEL_FOLDER` writes Parquet by default. Use `--format json` or `--format csv` when needed. It creates:

- `fact_responses`
- `fact_response_answers`
- `dim_surveys`
- `dim_questions`
- `dim_answer_options`

`dim_questions` has one row per analyzable exported question field and flattens section, question, field, and catalog attributes. Create these active single-direction relationships in Power BI:

```text
dim_surveys[survey_id] 1 -> * fact_responses[survey_id]
fact_responses[response_id] 1 -> * fact_response_answers[response_id]
dim_questions[question_field_id] 1 -> * fact_response_answers[question_field_id]
dim_answer_options[answer_option_id] 1 -> * fact_response_answers[answer_option_id]
```

`dim_answer_options` has one row per field-specific option. Use `question_field_id` to associate it with `dim_questions`; keep the fact relationship on `answer_option_id`.

Create a model-local Date table and relate it to `fact_responses[recorded_at]`. Do not add parallel active paths from surveys, questions, or catalogs to the answer fact.

## Baseline DAX

```DAX
Responses := DISTINCTCOUNT(fact_responses[response_id])

Respondents With Answer := DISTINCTCOUNT(fact_response_answers[response_id])

Answer Rows := COUNTROWS(fact_response_answers)

Question-scoped Responses :=
CALCULATE(
    [Responses],
    TREATAS(VALUES(dim_questions[survey_id]), fact_responses[survey_id])
)

Question Response Rate := DIVIDE([Respondents With Answer], [Question-scoped Responses])

Numeric Answer Average := AVERAGE(fact_response_answers[answer_numeric])
```

Use `Responses` for survey denominators because the answer fact intentionally excludes empty fields.
