# Maintain the documentation

The site uses [MkDocs](https://www.mkdocs.org/) with the requested [Material for MkDocs theme](https://github.com/squidfunk/mkdocs-material). Write pages in Markdown under `docs/`; use `mkdocs.yml` to arrange the navigation and configure the site.

## Preview your changes

From the repository root, run:

```bash
uv sync --locked --group docs --extra cli --extra ui
uv run --locked --group docs --extra ui mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. MkDocs rebuilds the preview when you save a page. Press **Ctrl+C** in the terminal to stop the server.

To check the site without starting a server:

```bash
uv run --locked --group docs --extra ui mkdocs build --strict
```

The command writes the site to `site/`, which Git ignores. CI runs this strict build for pull requests and changes to `main`. Missing pages, broken internal links, missing anchors, and pages omitted from navigation cause a build failure. The equivalent task shortcuts are `uv run poe docs-serve` and `uv run poe docs-build`.

## Keep guides useful

Start with the reader's task, the files they need, and the command they should run. Explain what they should see afterwards. Define a new term the first time you use it, or link to the [glossary](../understand/glossary.md).

- Verify commands against the current CLI before publishing them. `uv run --extra cli --extra ui qualtrics COMMAND --help` shows the actual flags and defaults.
- Use the synthetic survey in `docs/assets/examples/` for tutorials. Keep real survey responses and credentials out of documentation assets.
- Add new pages to `nav` in `mkdocs.yml` and use relative Markdown links.
- Give images descriptive alternative text and explain a diagram's meaning in prose.
- Keep the [entity contract](../entity-model.md) and [DBML file](../entity-model.dbml) aligned with the parser. Existing tests depend on those paths.

`docs/superpowers/` contains internal implementation history. The `exclude_docs` setting keeps it out of the generated site and search index while preserving the files in Git.

## Maintain the report showcase

The [interactive report example](../examples/question-types.md) uses `scripts/question_type_showcase.py` to generate a synthetic QSF, 100 fictional responses, a coverage manifest, and a report through the production parser and renderer. Edit the generator when adding question cases; keep its coverage labels aligned with the actual exported fields and report presentation. The fixture is not import-tested in Qualtrics, and generic displays or definition-only cases must remain identified as such.

The MkDocs hook in `scripts/docs_showcase.py` generates the four assets in a temporary directory, then adds their contents to the site under `assets/examples/question-types/`. It also fills the example page's coverage table from the generated manifest. Generated HTML and data are not written into `docs/` or committed to Git. The small `feedback.csv` and `feedback.qsf` tutorial files remain separate beginner examples.

Build or preview with the usual `--group docs` commands above. The hook needs both toolkit runtime dependencies and MkDocs; `--only-group docs` skips the toolkit and cannot build this example. `mkdocs serve` watches the generator and toolkit source so code changes rebuild the embedded report. Restart the preview server after changing the hook itself, because MkDocs imports hook modules at startup.

For an independent copy, run:

```bash
uv run --extra ui python -m scripts.question_type_showcase --output data/question-type-showcase
```

Check the generated report and downloads at desktop and phone widths. Verify that its summary charts, question search, written answers, and codebook work, and keep all data fictional. The documentation tests build the site from outside the repository and check the embedded report and download paths with both directory URLs and `.html` URLs.

The [flow example](../examples/survey-flow.md) has a separate generator, `scripts/survey_flow_showcase.py`, and hook, `scripts/docs_flow_showcase.py`. It produces a QSF, standalone flow JSON, 24 fictional responses, and an embedded report under `assets/examples/survey-flow/`. Rebuild locally with `uv run --extra ui python -m scripts.survey_flow_showcase --output data/survey-flow-showcase`. Keep fake responses consistent with the defined branches, and verify the early ending, randomizer, Back/Reset controls, unknown-rule assumptions, and cross-view question links after changing flow behavior.

## Package architecture

Keep implementation code in four packages under `src/qualtrics/`:

| Package | Responsibility |
| --- | --- |
| `api/` | Remote SDK: HTTP clients, endpoints, API models, settings, and errors. |
| `cli/` | Typer commands and terminal progress. |
| `ui/` | Report preparation, Jinja templates, and bundled browser assets. |
| `_common/` | Shared `models`, `parsers`, `analytics`, and `serialization` implementations. |

Keep public exports, command entry points, version information, and `py.typed` at the package root. Use root imports for shared operations in examples and application code; `_common` is private. See [Python import migration](../reference/python.md#migrate-earlier-deep-imports) for the removed deep paths and their replacements.

Keep `_common/__init__.py` minimal. Shared code must not import `api`, `cli`, `ui`, Typer, Rich, or Jinja. Parsers, analytics, and serialization can use shared models; analytics must not depend on parsers. Put question-role classification in the shared question models. Preserve the separate identity algorithms in the parser and model modules when changing them, since their identifiers serve different contracts.

The package layout does not change installation requirements. The base package still installs the remote SDK dependencies and supports parsing, analytics, and JSON/CSV serialization. Keep Typer/Rich in `cli`, Jinja/MarkupSafe in `ui`, and PyArrow in `parquet`. Import Parquet dependencies only when a Parquet operation needs them, and keep the root `render_report` import usable before installing UI dependencies.

## Maintain the report components

The generated report has six views inside one offline HTML document. Maintain the canonical renderer in `src/qualtrics/ui/` and expose it through `qualtrics.ui.render_report` and the root `qualtrics.render_report` import.

Install contributor dependencies with `uv sync --all-groups --all-extras`. Documentation hooks generate both showcase reports, so even a docs-only environment needs the `ui` extra.

The UI modules have these boundaries:

| Module | Responsibility |
| --- | --- |
| `report.py` | Public entry point: build the context, render pages, and write the document. |
| `context.py` | Analyze the entity set once and prepare shared lookups for page renderers. |
| `layouts/document.py` | Prepare document context for the shared Jinja layout. |
| `components/` | Prepare reusable controls, navigation, and field labels for template macros. |
| `pages/` | Render Summary, Flow, Questions, Written answers, Responses, and Codebook from the shared context. |
| `templating.py` | Cached Jinja environment with packaged templates, strict undefined values, and explicit autoescaping. |
| `templates/` | HTML layouts, page templates, includes, and reusable macros. |
| `assets.py` | Ordered stylesheet and script manifest. Dependencies must precede consumers. |
| `static/components/` | Shared browser controls, pagination, and common styles. |
| `static/pages/` | Page filtering, search, presentation, and page-specific styles. |
| `static/layouts/` | View navigation, shell styling, responsive layout, and print rules. |

`static/report.js` composes the browser controllers and connects shared survey selection. Responses, written answers, search results, and the codebook use the same pagination controls. Keep filtering separate from screen visibility so printing and codebook downloads retain the full filtered collection.

Survey Flow separates configured structure (`flow-graph.js`), canvas interaction (`flow-canvas.js`), scenario evaluation (`flow-engine.js`), and the walkthrough controller (`flow.js`). Keep graph edges faithful to branch continuation and terminal endings. A randomizer's alternatives must not imply that every child runs in a fixed sequence. Use occurrence IDs, since a block or question can appear more than once.

Add new assets to the manifest; the renderer embeds their contents rather than linking to a server or CDN. Keep HTML in `.html.jinja` templates and prepare explicit view models in Python. The shared environment uses `PackageLoader`, `StrictUndefined`, and `autoescape=True`, including the `.jinja` suffix. Only already-rendered internal markup and bundled assets cross the narrow trusted-HTML boundary; survey text must remain escaped. Use DOM `textContent` for survey data and script-safe serialization for inline JSON. Preserve stable anchors when moving components: search, chart links, walkthroughs, and browser history depend on them.

Run `node --test tests/js/*.test.cjs` for browser logic and `uv run --all-extras pytest` for Python behavior. The generated showcase integration tests also check the embedded reports with both MkDocs URL modes. After building one wheel into `dist/`, run `bash scripts/smoke_wheel.sh` to check the installed four-package layout, public imports, and operations with base, CLI-only, UI-only, and combined installations; optional dependencies must be absent in the corresponding environments. Before shipping a UI change, inspect desktop and phone widths, both themes, all six pages, empty survey selections, deep links, the canvas controls, and print output.

## Theme and plugin decisions

**Maintenance check: 8 September 2026.** The [catalog's charts, images, tables, and graphs section](https://github.com/mkdocs/catalog#-charts-images-tables--graphs) is a useful starting point. Its inactivity badges can lag behind upstream releases. The decisions below use upstream repositories, release metadata, and Material's integration documentation.

### Included in this site

| Component | Version observed at the check | Why we use it |
| --- | --- | --- |
| [Material for MkDocs](https://pypi.org/project/mkdocs-material/) | 9.7.7, released 17 July 2026 | The requested theme supplies responsive navigation, search presentation, light/dark modes, and code-copy buttons. |
| [GLightbox](https://pypi.org/project/mkdocs-glightbox/) | 0.5.2, released 23 October 2025 | Readers can enlarge the workflow figure. Material [recommends this integration](https://squidfunk.github.io/mkdocs-material/reference/images/#lightbox); the repository is unarchived and had a push on 8 March 2026. |
| MkDocs search | Bundled with MkDocs | Readers can find commands, error messages, and concepts. Keep `search` in the explicit plugin list. |

GLightbox uses locally packaged JavaScript and CSS. We enable automatic captions from image alternative text and automatic light/dark theming. Enlarge the [workflow figure on the home page](../index.md#from-export-to-report) to try it.

For diagrams, we use [Material's native Mermaid integration](https://squidfunk.github.io/mkdocs-material/reference/diagrams/) through PyMdown SuperFences. For tables, we use Markdown. These features do not need separate chart or table plugins. The small example-count table also has a downloadable CSV.

Material loads the Mermaid rendering library from a CDN when a page needs it. Those interactive diagrams need a connection on first load; their accompanying prose and the static home-page illustration remain readable without that library. We disable external web fonts with `font: false`.

!!! note "Material's maintenance status"

    Material is in maintenance mode, with critical and security fixes continuing. The maintainer describes Zensical as its successor in the [transition announcement](https://squidfunk.github.io/mkdocs-material/blog/2025/11/05/zensical/#looking-ahead). We retain Material as requested and constrain MkDocs to version 1.x. A move to a different generator needs a separate compatibility review, especially for plugins.

### Useful candidates if the docs grow

These plugins are recommendations for specific future needs, rather than dependencies installed by this project.

| Plugin | Latest release observed | Add it when… |
| --- | --- | --- |
| [mkdocs-panzoom-plugin](https://pypi.org/project/mkdocs-panzoom-plugin/) | 0.5.2, 22 December 2025 | Readers need to move around a large diagram. Avoid overlapping its image behavior with GLightbox. |
| [mkdocs-d2-plugin](https://pypi.org/project/mkdocs-d2-plugin/) | 1.7.0, 9 April 2026 | You need D2-specific diagrams and can install the D2 rendering tool in CI. |
| [mkdocs-kroki-plugin](https://pypi.org/project/mkdocs-kroki-plugin/) | 1.6.0, 13 April 2026 | You need several diagram languages. Review its extra dependencies and rendering service: the default server is `kroki.io`. |
| [plantuml-markdown](https://pypi.org/project/plantuml-markdown/) | 3.11.2, 18 April 2026 | You already maintain PlantUML diagrams and have a rendering setup. |

The table-reader plugin remains [documented by Material](https://squidfunk.github.io/mkdocs-material/reference/data-tables/#import-table-from-file), but its [latest release](https://pypi.org/project/mkdocs-table-reader-plugin/) was 3.1.0 on 29 August 2024. It is a mature, quiet project; we do not label it recently maintained. Our small tables do not justify adding pandas and another plugin.

The [charts plugin](https://pypi.org/project/mkdocs-charts-plugin/) can embed Vega-Lite charts, but its latest observed release was 0.0.13 on 2 September 2025. Consider it only when a documentation page needs an interactive chart and after testing its JavaScript dependencies. The toolkit's generated survey reports do not depend on this plugin.

We also omit the extra [mermaid2 plugin](https://pypi.org/project/mkdocs-mermaid2-plugin/): its 1.2.3 release and 2026 repository activity show that it is usable, but Material already handles our Mermaid diagrams. Avoid choosing the much older [mkdocs-mermaid-plugin](https://pypi.org/project/mkdocs-mermaid-plugin/) by mistake; its latest release dates to 2018.

### Update dependencies

Documentation dependencies live in the `docs` group of `pyproject.toml`; `uv.lock` records the resolved versions. They are separate from the toolkit's runtime dependencies. Dependabot already checks this repository's uv dependencies each month.

For a deliberate update, run:

```bash
uv lock --upgrade-package mkdocs --upgrade-package mkdocs-material --upgrade-package mkdocs-glightbox --upgrade-package pymdown-extensions
uv sync --locked --group docs --extra cli --extra ui
uv run --locked --group docs --extra ui mkdocs build --strict
```

Then inspect search, navigation, code copying, the enlarged figure, and the Mermaid diagram at desktop and phone widths. Check the [first-report tutorial](../getting-started/first-report.md) against the current parser and CLI. Update the maintenance notes above when you review the upstream projects again.

## Publish the site

The **Deploy documentation** workflow in `.github/workflows/deploy-docs.yml` builds the static site and publishes it to GitHub Pages. It runs when documentation, toolkit source, repository scripts, site configuration, build dependencies, the Python version, or the workflow itself changes on `main`. Source changes rebuild the embedded report with the current renderer. Pull requests are checked by CI; deployment happens after merge.

### Enable GitHub Pages once

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Merge the workflow and documentation into `main`.
4. Open **Actions → Deploy documentation** and wait for both the build and deployment jobs to finish. The deployment links to the published site.

The default address for this repository is [https://luanee.github.io/qualtrics/](https://luanee.github.io/qualtrics/). Follow [GitHub's custom workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) for the Pages settings. The workflow uses GitHub's built-in token and the `github-pages` environment; you do not need to add a personal access token or maintain a `gh-pages` branch.

### Publish again manually

Open **Actions → Deploy documentation → Run workflow**, select **main**, then click **Run workflow**. This rebuilds and publishes the current documentation on `main`. Runs selected from other branches are skipped. The workflow must be on the default branch before GitHub displays the manual run button.

The workflow installs the toolkit and locked documentation dependencies, runs `mkdocs build --strict`, and uploads `site/` as a Pages artifact. Deployment starts only after that build succeeds. A failed build leaves the published site in place. The separate CI workflow continues to check documentation on pull requests.

`mkdocs.yml` sets the public `site_url`, which MkDocs uses for canonical links and `sitemap.xml`. During deployment, `DOCS_SITE_URL` takes the URL from GitHub Pages, including a custom domain configured in Pages settings. Local builds use the repository's default Pages address. If you move the site permanently, update that fallback address too.

A local preview or build does not publish anything. You can also host the contents of `site/` with another static web host; set `DOCS_SITE_URL` to that site's public URL when building it.
