"""Label indexes keep missing lineage from turning into cross-occurrence joins."""

from copy import deepcopy

from qualtrics._common.models.definition_labels import DefinitionLabelIndex, current_definition_label
from qualtrics._common.models.entities import EntitySet
from qualtrics._common.models.translation_columns import source_text_hash


def test_label_index_preserves_unique_legacy_catalogs_and_current_rows() -> None:
    fields = []
    options = []
    for number in (1, 2):
        for language in ("EN", "DE"):
            field_id = f"field-{number}-{language}"
            fields.append({
                "survey_id": "SV_1",
                "question_field_id": field_id,
                "question_external_id": "QID1",
                "field_external_id": None,
                "question_field_catalog_id": f"catalog-{number}",
                "language_code": language,
                "is_localized": language != "EN",
                "field_text": f"Field {number} {language}",
            })
            options.append({
                "survey_id": "SV_1",
                "question_field_id": field_id,
                "answer_external_id": "1",
                "language_code": language,
                "is_localized": language != "EN",
                "answer_text": f"Option {number} {language}",
            })
    entities = EntitySet(question_fields=fields, answer_options=options)
    before = deepcopy(entities)
    index = DefinitionLabelIndex(entities)
    for rows, kind in ((fields, "field"), (options, "answer_option")):
        for offset in (0, 2):
            assert index.get(kind, rows[offset], "de") is rows[offset + 1]
            assert index.get(kind, rows[offset + 1]) is rows[offset]
            assert index.get(kind, rows[offset], "FR") is None
    assert index.get("answer_option", {"question_field_id": "missing"}, "DE") is None
    assert entities == before


def test_definition_freshness_uses_live_source_without_caching() -> None:
    base = {"question_text": "Original"}
    variant = {
        "question_text": "Translated",
        "label_origin": "callback",
        "label_source_text_hash": source_text_hash("Original"),
    }
    assert current_definition_label(base, None, "question_text") is base
    assert current_definition_label(base, variant, "question_text") is variant
    base["question_text"] = "Revised"
    assert current_definition_label(base, variant, "question_text") is base
    variant["label_origin"] = "qsf"
    assert current_definition_label(base, variant, "question_text") is variant
