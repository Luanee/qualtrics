from pathlib import Path

from qualtrics import parse_survey
from qualtrics.models.semantic import build_semantic_model


def test_semantic_model_flattens_question_fields_and_preserves_fact_grains(
    survey_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*survey_files)
    model = build_semantic_model(entities)
    assert len(model.fact_responses) == len(entities.responses)
    assert len(model.fact_response_answers) == len(entities.response_answers)
    assert len(model.dim_question_fields) == len(entities.question_fields)
    dimension = model.dim_question_fields[0]
    assert dimension["question_text"]
    assert dimension["question_catalog_id"]
    assert "section_name" in dimension
