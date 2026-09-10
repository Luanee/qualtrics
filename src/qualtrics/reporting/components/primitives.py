"""Small shared markup components. Text and attribute inputs are always escaped."""

import html


def page_heading(
    title: str,
    introduction: str = "",
    *,
    heading_id: str = "",
    disclosure: bool = False,
    count: str = "",
    count_id: str = "",
) -> str:
    if disclosure:
        identity = f" id='{html.escape(count_id, quote=True)}'" if count_id else ""
        count_markup = f"<span{identity} class='section-count'>{html.escape(count)}</span>" if count else ""
        return (
            "<summary class='section-summary'><span><strong role='heading' aria-level='2'>"
            f"{html.escape(title)}</strong><small>{html.escape(introduction)}</small></span>"
            f"{count_markup}</summary>"
        )
    identity = f" id='{html.escape(heading_id, quote=True)}'" if heading_id else ""
    intro = f"<p class='section-intro'>{html.escape(introduction)}</p>" if introduction else ""
    return f"<div class='view-heading'><h2{identity}>{html.escape(title)}</h2>{intro}</div>"


def search_control(control_id: str, label: str, *, placeholder: str = "") -> str:
    identity = html.escape(control_id, quote=True)
    hint = f" placeholder='{html.escape(placeholder, quote=True)}'" if placeholder else ""
    return f"<label for='{identity}'>{html.escape(label)}</label><input id='{identity}' type='search'{hint}>"


def empty_state(element_id: str, message: str, *, hidden: bool = False) -> str:
    return f"<p id='{html.escape(element_id, quote=True)}'{' hidden' if hidden else ''}>{html.escape(message)}</p>"


def pagination(element_id: str) -> str:
    return f"<div id='{html.escape(element_id, quote=True)}' class='pagination'></div>"


def metric(element_id: str, value: int, label: str, *, kind: str = "stat") -> str:
    return (
        f"<div class='{html.escape(kind, quote=True)}'><strong id='{html.escape(element_id, quote=True)}'>"
        f"{value:,}</strong><span>{html.escape(label)}</span></div>"
    )
