from pathlib import Path

from qualtrics import parse_survey
from qualtrics.serialization.io import load_entities, write_entities


def test_csv_round_trip_preserves_analytical_answer_types(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)
    answer = entities.response_answers[0]
    answer["answer_numeric"] = 12.5
    answer["answer_boolean"] = True
    answer["is_selected"] = False
    write_entities(entities, tmp_path, "csv")
    loaded = load_entities(tmp_path)
    restored = loaded.response_answers[0]
    assert restored["answer_numeric"] == 12.5
    assert restored["answer_boolean"] is True
    assert restored["is_selected"] is False
