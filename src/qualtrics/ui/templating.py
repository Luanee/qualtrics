"""One strict, autoescaped environment for installed report resources."""

from __future__ import annotations

import html
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jinja2 import Environment
    from markupsafe import Markup


def trusted_html(text: str) -> Markup:
    """Mark only internally rendered components or bundled assets as HTML."""
    from markupsafe import Markup

    return Markup(text)


def _finalize(value: object) -> object:
    from markupsafe import Markup

    # Keep the report's established &quot;/&#x27; serialization. Escaping happens
    # before marking text safe; Undefined must pass through to StrictUndefined.
    if isinstance(value, str) and not isinstance(value, Markup):
        return Markup(html.escape(value, quote=True))
    return value


@cache
def get_environment() -> Environment:
    from jinja2 import Environment, PackageLoader, StrictUndefined

    return Environment(
        loader=PackageLoader("qualtrics.ui", "templates"),
        undefined=StrictUndefined,
        autoescape=True,
        finalize=_finalize,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(name: str, **context: object) -> str:
    return get_environment().get_template(name).render(**context)
