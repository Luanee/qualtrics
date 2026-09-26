"""Identity assignment must not search all fields for every observed answer."""

from qualtrics import EntitySet
from qualtrics._common.parsers.survey import _apply_identity_contract


def test_answer_identity_assignment_uses_linear_field_lookups() -> None:
    field_id_reads = 0

    class ObservedField(dict[str, object]):
        def __getitem__(self, key: str) -> object:
            nonlocal field_id_reads
            if key == "question_field_id":
                field_id_reads += 1
            return super().__getitem__(key)

    field_count, response_count = 40, 10
    entities = EntitySet(
        surveys=[{"survey_id": "SV_SCALING"}],
        questions=[
            {
                "question_id": "QID1",
                "question_text": "Scores",
                "question_type": "Slider",
                "selector": "HSLIDER",
                "question_role": "response",
            }
        ],
        question_fields=[
            ObservedField(question_id="QID1", field_id=f"QID1_{index}", field_text=f"Item {index}")
            for index in range(field_count)
        ],
        responses=[{"response_id": f"R_{index}"} for index in range(response_count)],
        response_answers=[
            {"response_id": f"R_{response}", "question_id": "QID1", "field_id": f"QID1_{field}", "answer_text": "02"}
            for response in range(response_count)
            for field in range(field_count)
        ],
    )

    _apply_identity_contract(entities)

    # Count real row accesses, not wall-clock time: the budget permits a few
    # linear passes but catches a field scan for each of the 400 answer rows.
    assert field_id_reads <= 3 * (field_count + len(entities.response_answers))
    fields = {row["question_field_id"]: row for row in entities.question_fields}
    assert len(entities.response_answers) == 400
    assert len({row["response_answer_id"] for row in entities.response_answers}) == 400
    for answer in entities.response_answers:
        field = fields[answer["question_field_id"]]
        assert answer["field_external_id"] == field["field_external_id"]
        assert answer["question_field_catalog_id"] == field["question_field_catalog_id"]
        assert answer["answer_text"] == "02"
        assert answer["answer_numeric"] == 2.0
