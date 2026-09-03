# Qualtrics entity and semantic model

Parsing always produces nine normalized entities. Occurrence IDs are survey-safe hashes; `*_external_id` columns preserve Qualtrics lineage. Catalog IDs identify normalized semantics across surveys.

| Entity | Grain | Primary ID | Main parents |
|---|---|---|---|
| `surveys` | survey | `survey_id` | none |
| `sections` | survey block | `section_id` | `survey_id` |
| `question_catalog` | semantic question | `question_catalog_id` | none |
| `question_field_catalog` | semantic field | `question_field_catalog_id` | `question_catalog_id` |
| `questions` | survey question | `question_id` | survey, section, question catalog |
| `answer_options` | survey question option | `answer_option_id` | question |
| `question_fields` | exported question field | `question_field_id` | question, both catalogs |
| `responses` | submitted response | `response_id` | survey |
| `response_answers` | non-empty response field | `response_answer_id` | response, question, field, optional option |

Questions retain `question_type`, `selector`, and `sub_selector` exactly and add `canonical_question_type`. Fields and answers add `answer_value_type`. Unknown combinations remain available with `unsupported` classification.

`response_answers` preserves `answer_text` and provides nullable `answer_numeric`, `answer_boolean`, `is_selected`, `answer_option_id`, and `answer_option_catalog_id` for analysis.

## Semantic projection

`qualtrics semantic-model build ENTITY_FOLDER --output MODEL_FOLDER` writes Parquet by default. Use `--format json` or `--format csv` when needed. It creates:

- `fact_responses`
- `fact_response_answers`
- `dim_surveys`
- `dim_question_fields`
- `dim_answer_options`

`dim_question_fields` flattens section, question, field, and catalog attributes. Create these active single-direction relationships in Power BI:

```text
dim_surveys[survey_id] 1 -> * fact_responses[survey_id]
fact_responses[response_id] 1 -> * fact_response_answers[response_id]
dim_question_fields[question_field_id] 1 -> * fact_response_answers[question_field_id]
dim_answer_options[answer_option_id] 1 -> * fact_response_answers[answer_option_id]
```

Create a model-local Date table and relate it to `fact_responses[recorded_at]`. Do not add parallel active paths from surveys, questions, or catalogs to the answer fact.

## Baseline DAX

```DAX
Responses := DISTINCTCOUNT(fact_responses[response_id])

Respondents With Answer := DISTINCTCOUNT(fact_response_answers[response_id])

Answer Rows := COUNTROWS(fact_response_answers)

Question-scoped Responses :=
CALCULATE(
    [Responses],
    TREATAS(VALUES(dim_question_fields[survey_id]), fact_responses[survey_id])
)

Question Response Rate := DIVIDE([Respondents With Answer], [Question-scoped Responses])

Numeric Answer Average := AVERAGE(fact_response_answers[answer_numeric])
```

Use `Responses` for survey denominators because the answer fact intentionally excludes empty fields.
