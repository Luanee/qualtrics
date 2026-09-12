"""Embed the versioned DBML sources using dbdiagram's account-free viewer."""

import base64
from urllib.parse import quote

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

_MODELS = {"entity": "entity-model.dbml", "power_bi": "power-bi-model.dbml"}


def on_page_markdown(markdown: str, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    for name, source in _MODELS.items():
        placeholder = "{{ dbml_" + name + "_url }}"
        if placeholder not in markdown:
            continue
        schema = files.get_file_from_path(source)
        if schema is None:
            raise PluginError(f"Missing DBML schema for {page.file.src_uri}: {source}")
        encoded = base64.b64encode(schema.content_string.encode("utf-8")).decode("ascii")
        url = "https://dbdiagram.io/embed#c=" + quote(encoded, safe="")
        markdown = markdown.replace(placeholder, url)
    return markdown
