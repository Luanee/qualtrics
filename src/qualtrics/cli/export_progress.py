"""Terminal presentation and bounded scheduling for survey export commands."""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from threading import Event, Lock
from typing import TypeVar

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ..api import ExportCallback, ExportEvent

ResultT = TypeVar("ResultT")


def validate_survey_ids(survey_ids: list[str]) -> None:
    """Reject duplicates and characters unsafe in URLs or portable output paths."""
    if not survey_ids or any(not re.fullmatch(r"SV_[A-Za-z0-9_-]+", value) for value in survey_ids):
        raise typer.BadParameter("survey IDs must start with SV_ and contain only letters, numbers, _ or -")
    if len({value.casefold() for value in survey_ids}) != len(survey_ids):
        raise typer.BadParameter("survey IDs must be unique (including filename case)")


def run_surveys(
    survey_ids: list[str],
    worker: Callable[[str, ExportCallback], ResultT],
    *,
    batch_size: int = 1,
    show_progress: bool = True,
    description: str = "Exported surveys",
    console: Console | None = None,
) -> tuple[dict[str, ResultT], dict[str, Exception]]:
    """Run at most ``batch_size`` jobs; count only successfully completed workers.

    Progress is sent to stderr. Redirected commands get stage lines instead of
    animated terminal control sequences. Each worker's error is retained while
    other surveys finish, so callers can return a failing exit code afterwards.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    console = console or Console(stderr=True)
    animated = show_progress and console.is_terminal
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}", markup=False),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TextColumn("elapsed"),
        TimeElapsedColumn(),
        TextColumn("remaining"),
        TimeRemainingColumn(),
        console=console,
        disable=not animated,
        redirect_stdout=False,
        redirect_stderr=False,
    )
    overall = progress.add_task(description, total=len(survey_ids))
    tasks = {survey_id: progress.add_task(f"{survey_id}: queued", total=100, start=False) for survey_id in survey_ids}
    task_rows = {task.id: task for task in progress.tasks}
    previous: dict[str, str] = {}
    lock = Lock()
    cancelled = Event()
    results: dict[str, ResultT] = {}
    failures: dict[str, Exception] = {}

    def update(event: ExportEvent) -> None:
        if cancelled.is_set():
            raise CancelledError("Survey export interrupted")
        with lock:
            stage = "downloaded" if event.stage == "complete" else event.stage
            task_id = tasks[event.survey_id]
            total = 100 if event.percent_complete is not None else None
            if previous.get(event.survey_id) != stage:
                row = task_rows[task_id]
                started_at = row.start_time
                progress.reset(task_id, total=total)
                # Rich's update/reset treat total=None as "unchanged". Set the
                # public Task field to make downloads indeterminate, preserving
                # elapsed time across the survey's different stages.
                row.total = total
                if started_at is not None:
                    row.start_time = started_at
            progress.update(
                task_id,
                description=f"{event.survey_id}: {stage}",
                total=total,
                completed=max(0, min(event.percent_complete or 0, 100)),
            )
            if show_progress and not animated and previous.get(event.survey_id) != stage:
                console.print(f"{event.survey_id}: {stage}", markup=False, highlight=False)
            previous[event.survey_id] = stage

    concurrency = min(batch_size, max(1, len(survey_ids)))
    remaining = iter(survey_ids)
    with progress:
        executor = ThreadPoolExecutor(max_workers=concurrency)
        pending: dict[Future[ResultT], str] = {}
        try:
            while True:
                # Submit only enough jobs to fill active slots. In particular,
                # interruption must not leave the rest of the survey list in
                # an executor queue that runs while the client is shutting down.
                while len(pending) < concurrency:
                    survey_id = next(remaining, None)
                    if survey_id is None:
                        break
                    pending[executor.submit(worker, survey_id, update)] = survey_id
                if not pending:
                    break
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    survey_id = pending.pop(future)
                    try:
                        results[survey_id] = future.result()
                    except Exception as error:
                        failures[survey_id] = error
                        progress.update(tasks[survey_id], description=f"{survey_id}: failed")
                        progress.stop_task(tasks[survey_id])
                    else:
                        progress.update(
                            tasks[survey_id], description=f"{survey_id}: complete", total=100, completed=100
                        )
                        progress.advance(overall)
                    progress.update(overall, description=f"{description} ({len(failures)} failed)")
        except BaseException:
            cancelled.set()
            for future in pending:
                future.cancel()
            raise
        finally:
            # Running requests may still need to finish. Their next progress
            # callback raises CancelledError, which stops SDK polling/download
            # transitions without turning Ctrl+C into an ordinary batch failure.
            executor.shutdown(wait=True, cancel_futures=True)
            progress.stop_task(overall)
    if show_progress and not animated:
        console.print(
            f"{description}: {len(results)}/{len(survey_ids)} complete; {len(failures)} failed",
            markup=False,
            highlight=False,
        )
    return (
        {survey_id: results[survey_id] for survey_id in survey_ids if survey_id in results},
        {survey_id: failures[survey_id] for survey_id in survey_ids if survey_id in failures},
    )
