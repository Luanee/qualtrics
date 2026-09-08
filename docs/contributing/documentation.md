# Maintain the documentation

The site uses [MkDocs](https://www.mkdocs.org/) with the requested [Material for MkDocs theme](https://github.com/squidfunk/mkdocs-material). Write pages in Markdown under `docs/`; use `mkdocs.yml` to arrange the navigation and configure the site.

## Preview your changes

From the repository root, run:

```bash
uv sync --locked --group docs
uv run --locked --group docs mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. MkDocs rebuilds the preview when you save a page. Press **Ctrl+C** in the terminal to stop the server.

To check the site without starting a server:

```bash
uv run --locked --group docs mkdocs build --strict
```

The command writes the site to `site/`, which Git ignores. CI runs this strict build for pull requests and changes to `main`. Missing pages, broken internal links, missing anchors, and pages omitted from navigation cause a build failure. The equivalent task shortcuts are `uv run poe docs-serve` and `uv run poe docs-build`.

## Keep guides useful

Start with the reader's task, the files they need, and the command they should run. Explain what they should see afterwards. Define a new term the first time you use it, or link to the [glossary](../understand/glossary.md).

- Verify commands against the current CLI before publishing them. `uv run qualtrics COMMAND --help` shows the actual flags and defaults.
- Use the synthetic survey in `docs/assets/examples/` for tutorials. Keep real survey responses and credentials out of documentation assets.
- Add new pages to `nav` in `mkdocs.yml` and use relative Markdown links.
- Give images descriptive alternative text and explain a diagram's meaning in prose.
- Keep the [entity contract](../entity-model.md) and [DBML file](../entity-model.dbml) aligned with the parser. Existing tests depend on those paths.

`docs/superpowers/` contains internal implementation history. The `exclude_docs` setting keeps it out of the generated site and search index while preserving the files in Git.

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
uv sync --locked --group docs
uv run --locked --group docs mkdocs build --strict
```

Then inspect search, navigation, code copying, the enlarged figure, and the Mermaid diagram at desktop and phone widths. Check the [first-report tutorial](../getting-started/first-report.md) against the current parser and CLI. Update the maintenance notes above when you review the upstream projects again.

## Publish the site

The **Deploy documentation** workflow in `.github/workflows/deploy-docs.yml` builds the static site and publishes it to GitHub Pages. It runs when documentation, site configuration, build dependencies, the Python version, or the workflow itself changes on `main`. Pull requests are checked by CI; deployment happens after merge.

### Enable GitHub Pages once

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Merge the workflow and documentation into `main`.
4. Open **Actions → Deploy documentation** and wait for both the build and deployment jobs to finish. The deployment links to the published site.

The default address for this repository is [https://luanee.github.io/qualtrics/](https://luanee.github.io/qualtrics/). Follow [GitHub's custom workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) for the Pages settings. The workflow uses GitHub's built-in token and the `github-pages` environment; you do not need to add a personal access token or maintain a `gh-pages` branch.

### Publish again manually

Open **Actions → Deploy documentation → Run workflow**, select **main**, then click **Run workflow**. This rebuilds and publishes the current documentation on `main`. Runs selected from other branches are skipped. The workflow must be on the default branch before GitHub displays the manual run button.

The workflow installs the locked documentation dependencies, runs `mkdocs build --strict`, and uploads `site/` as a Pages artifact. Deployment starts only after that build succeeds. A failed build leaves the published site in place. The separate CI workflow continues to check documentation on pull requests.

`mkdocs.yml` sets the public `site_url`, which MkDocs uses for canonical links and `sitemap.xml`. During deployment, `DOCS_SITE_URL` takes the URL from GitHub Pages, including a custom domain configured in Pages settings. Local builds use the repository's default Pages address. If you move the site permanently, update that fallback address too.

A local preview or build does not publish anything. You can also host the contents of `site/` with another static web host; set `DOCS_SITE_URL` to that site's public URL when building it.
