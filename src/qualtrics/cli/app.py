import typer

from .api import app as api_app
from .build import build
from .entities import app as entities_app
from .report import report
from .semantic_model import app as semantic_model_app

app = typer.Typer(help="Parse, model, analyze, report, and export Qualtrics surveys.")
app.command()(build)
app.command()(report)
app.add_typer(api_app, name="api")
app.add_typer(entities_app, name="entities")
app.add_typer(semantic_model_app, name="semantic-model")
