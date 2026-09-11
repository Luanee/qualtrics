import base64
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

pytest.importorskip("mkdocs")
from mkdocs.config import load_config  # noqa: E402
from mkdocs.exceptions import PluginError  # noqa: E402
from mkdocs.structure.files import File, Files  # noqa: E402
from mkdocs.structure.pages import Page  # noqa: E402


def test_embed_uses_current_utf8_dbml_content_from_mkdocs_files(tmp_path: Path) -> None:
    from scripts.docs_dbml import on_page_markdown

    docs = tmp_path / "docs"
    docs.mkdir()
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text("site_name: Test\ndocs_dir: docs\nplugins: []\n")
    config = load_config(config_file=str(config_path))
    schema_path = docs / "entity-model.dbml"
    content = "Table réponses {\n  id varchar [pk, note: 'Café & 中文 / +']\n}\n"
    schema_path.write_text(content, encoding="utf-8")
    schema_file = File("entity-model.dbml", str(docs), config.site_dir, True)
    page = Page("Model", File("entity-model.md", str(docs), config.site_dir, True), config)

    url = on_page_markdown("{{ dbml_entity_url }}", page=page, config=config, files=Files([schema_file]))
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path, parts.query) == ("https", "dbdiagram.io", "/embed", "")
    assert parts.fragment.startswith("c=")
    assert base64.b64decode(unquote(parts.fragment[2:])).decode("utf-8") == content

    schema_path.write_text(content + "// updated schema\n", encoding="utf-8")
    updated = on_page_markdown("{{ dbml_entity_url }}", page=page, config=config, files=Files([schema_file]))
    assert base64.b64decode(unquote(urlsplit(updated).fragment[2:])).decode("utf-8") == content + "// updated schema\n"


def test_missing_referenced_dbml_fails_with_the_source_filename(tmp_path: Path) -> None:
    from scripts.docs_dbml import on_page_markdown

    docs = tmp_path / "docs"
    docs.mkdir()
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text("site_name: Test\ndocs_dir: docs\nplugins: []\n")
    config = load_config(config_file=str(config_path))
    page = Page("Model", File("guides/power-bi.md", str(docs), config.site_dir, True), config)

    with pytest.raises(PluginError, match="power-bi-model.dbml"):
        on_page_markdown("{{ dbml_power_bi_url }}", page=page, config=config, files=Files([]))
    assert on_page_markdown("No model here.", page=page, config=config, files=Files([])) == "No model here."
