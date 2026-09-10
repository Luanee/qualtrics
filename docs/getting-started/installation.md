# Installation

Install the command-line tool, then [make your first report](first-report.md) from a small example survey. You can follow these instructions without writing Python or connecting a Qualtrics account.

The main setup below gives you the tool, example files, and example scripts in one folder. You need an internet connection for installation.

## 1. Open a terminal

A terminal is an app where you paste a command and press **Enter** to run it.

- **Windows:** open **PowerShell** from the Start menu.
- **macOS:** open **Terminal** from Applications → Utilities.
- **Linux:** open your distribution's terminal app.

Run one command at a time. Copy the command itself, without the surrounding code box or any output shown beneath it.

## 2. Install uv and Git

Use **uv** to install and run this project. If you have it already, check it with:

```text
uv --version
```

If your terminal cannot find `uv`, use the installer for your operating system. These commands come from the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

=== "Windows PowerShell"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

Close and reopen the terminal after installation, then run `uv --version` again. Follow any path instructions printed by the installer if the command is still unavailable.

You also need **Git**, which downloads a copy of the project. Check for it:

```text
git --version
```

If needed, install Git using the instructions for your system on the [Git downloads page](https://git-scm.com/downloads/), reopen the terminal, and repeat the check.

The package requires Python 3.11 or later. The repository selects its Python version in `.python-version`; uv can download the required runtime during setup. You do not need to install Python first. See [uv's Python installation guide](https://docs.astral.sh/uv/guides/install-python/) if your organization manages Python installations.

## 3. Download and install the project

Move to a folder where you want to keep the project. For example:

=== "Windows PowerShell"

    ```powershell
    cd "$env:USERPROFILE/Documents"
    ```

=== "macOS / Linux"

    ```bash
    cd ~
    ```

Then run these commands on either operating system:

```text
git clone https://github.com/Luanee/qualtrics.git
cd qualtrics
uv sync --extra cli --extra ui --extra parquet
```

Git creates the `qualtrics` folder. uv installs the project and its dependencies into a `.venv` folder inside it. The `cli` extra installs the command-line tools, `ui` enables HTML reports, and `parquet` adds support for the table format used in the Power BI guide.

Keep this terminal in the `qualtrics` folder when following the guides. The `uv run --extra cli --extra ui` prefix selects the command-line and report dependencies when running a command; you do not need to activate `.venv` yourself.

## 4. Check the installation

```text
uv run --extra cli --extra ui qualtrics --help
```

You should see command help listing `build`, `report`, `api`, `entities`, and `semantic-model`. Continue to [your first report](first-report.md).

If the command fails, use [troubleshooting](../help/troubleshooting.md).

## Paths in the examples

A path such as `data/first-report/report.html` starts from the folder your terminal is in. In these guides, that is the `qualtrics` project folder.

- Use `pwd` to show your current folder in PowerShell, macOS, or Linux.
- Use `dir` in PowerShell or `ls` in macOS/Linux to list the files there.
- Put paths containing spaces in quotes: `"data/My survey/responses.csv"`.
- You can use forward slashes in the Python command paths on Windows, as the examples do.

On Windows, success messages may display those paths with backslashes instead.

Commands in the guides use single lines so you can paste them into PowerShell or a macOS/Linux terminal.

## Optional: install the published command-line tool

If you want the published command-line tool without a repository copy, install it in an isolated environment:

```text
uv tool install 'qualtrics[cli,ui,parquet]'
qualtrics --help
```

If uv reports that its tools directory is missing from your path, run `uv tool update-shell` and reopen your terminal. See [uv's tool guide](https://docs.astral.sh/uv/guides/tools/).

With this installation, use `qualtrics` wherever the guides show `uv run --extra cli --extra ui qualtrics`. Download the sample files from the [first-report page](first-report.md); the tool installation does not include the repository's example files or scripts. The published release may differ from the repository version documented here, so check your installed command's `--help` if an option is missing.


## Choose dependencies for Python projects

The SDK and data functions work with the base package:

```bash
python -m pip install qualtrics
```

Choose extras for the interfaces you use:

| Installation | Includes |
| --- | --- |
| `qualtrics` | API SDK, parsing, analytics, JSON/CSV data functions. |
| `qualtrics[cli]` | Typer/Rich command-line API and data commands. |
| `qualtrics[ui]` | Jinja HTML reports from Python, without CLI dependencies. |
| `qualtrics[cli,ui]` | Command-line tools including report generation. |
| `qualtrics[cli,ui,parquet]` | Complete command-line/report workflow with Parquet. |

For example, install Python report support with `python -m pip install 'qualtrics[ui]'` and import `render_report` from `qualtrics.ui`. The existing `from qualtrics import render_report` import remains supported. Parquet is independent of both interfaces; add it only when reading or writing Parquet tables.

The `_common` package layout keeps these dependency choices unchanged. The base installation still includes the remote API SDK dependencies. For shared data functions, use the public root imports in the [Python reference](../reference/python.md#public-imports); update earlier deep imports with the [migration table](../reference/python.md#migrate-earlier-deep-imports).
