from qualtrics.reporting.question_presentation import render_question_analysis


def numeric_chart(values: list[object]) -> str:
    body, _, _ = render_question_analysis(
        {"question_type": "Slider"},
        [{"field_id": "score", "answer_value_type": "numeric"}],
        [
            {"response_id": str(index), "field_id": "score", "answer_text": str(value)}
            for index, value in enumerate(values)
        ],
        [],
        {},
        len(values),
    )
    return body


def test_numeric_chart_shows_ordered_values_with_observed_frequencies() -> None:
    chart = numeric_chart([4, -2, 4, 1])
    assert "Value distribution" in chart
    assert chart.index("title='-2'") < chart.index("title='1'") < chart.index("title='4'")
    assert "<b>2</b><small>50%</small>" in chart
    assert "Percentages use 4 numeric values." in chart


def test_numeric_chart_groups_many_values_and_includes_maximum() -> None:
    from qualtrics.reporting.question_presentation import numeric_distribution

    rows = numeric_distribution([float(value) for value in range(101)])
    assert len(rows) == 8
    assert sum(count for _, count in rows) == 101
    assert rows[-1][1] == 13
    assert rows[0][0].startswith("0 ≤ value < ")
    assert rows[-1][0].endswith("≤ 100")


def test_numeric_chart_excludes_invalid_values_and_handles_one_value() -> None:
    chart = numeric_chart(["bad", "nan", "inf", 2])
    assert "3 non-numeric or non-finite values excluded." in chart
    assert "<b>1</b><small>100%</small>" in chart
    assert "Percentages use 1 numeric value." in chart


def test_numeric_bins_do_not_overflow_for_large_ranges() -> None:
    from qualtrics.reporting.question_presentation import numeric_distribution

    rows = numeric_distribution([-1e308, 1e308, *map(float, range(20))])
    assert sum(count for _, count in rows) == 22
    assert all("inf" not in label for label, _ in rows)
