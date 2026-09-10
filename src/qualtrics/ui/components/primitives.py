"""Typed entry points for shared, autoescaped template macros."""

from ..templating import render_template


def page_heading(
    title: str,
    introduction: str = "",
    *,
    heading_id: str = "",
    disclosure: bool = False,
    count: str = "",
    count_id: str = "",
) -> str:
    return render_template(
        "components/primitive.html.jinja",
        component="page_heading",
        arguments={
            "title": title,
            "introduction": introduction,
            "heading_id": heading_id,
            "disclosure": disclosure,
            "count": count,
            "count_id": count_id,
        },
    )


def search_control(control_id: str, label: str, *, placeholder: str = "") -> str:
    return render_template(
        "components/primitive.html.jinja",
        component="search_control",
        arguments={"control_id": control_id, "label": label, "placeholder": placeholder},
    )


def empty_state(element_id: str, message: str, *, hidden: bool = False) -> str:
    return render_template(
        "components/primitive.html.jinja",
        component="empty_state",
        arguments={"element_id": element_id, "message": message, "hidden": hidden},
    )


def pagination(element_id: str) -> str:
    return render_template(
        "components/primitive.html.jinja", component="pagination", arguments={"element_id": element_id}
    )


def metric(element_id: str, value: int, label: str, *, kind: str = "stat") -> str:
    return render_template(
        "components/primitive.html.jinja",
        component="metric",
        arguments={"element_id": element_id, "value": value, "label": label, "kind": kind},
    )
