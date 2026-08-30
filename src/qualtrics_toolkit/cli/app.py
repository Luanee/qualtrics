import typer

from .api import app as api_app
from .build import build
from .report import report

app = typer.Typer(help="Parse, model, analyze, report, and export Qualtrics surveys.")
app.command()(build)
app.command()(report)
app.add_typer(api_app, name="api")
