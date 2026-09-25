# From survey to report and Power BI

Use one path for each survey: get its QSF and CSV/ZIP, parse, optionally prepare text, then combine **distinct** surveys once. The [runnable example](https://github.com/Luanee/qualtrics/blob/main/examples/survey_workflow.py) uses only public `qualtrics` imports for the data steps.

The example's `run_workflow` follows seven named stages, each callable on its own:

1. `acquire_survey_inputs` gets a QSF and CSV/ZIP from local files or the API.
2. `parse_survey_input` checks that the QSF names the requested survey.
3. `translate_survey` optionally prepares definition labels and comments through your callback.
4. `write_survey_outputs` saves each survey's entities and optional report.
5. `combine_survey_outputs` merges distinct surveys once; `write_combined_entities` saves the result.
6. `write_combined_report` creates the optional cross-survey HTML report.
7. `write_powerbi_model` exports the combined semantic tables.

See the [complete example](https://github.com/Luanee/qualtrics/blob/main/examples/survey_workflow.py) for their typed inputs and CLI orchestration.

## Start with exports you already have

Place each `definition.qsf` beside `export.zip` or `responses.csv` in a survey-ID folder. The ZIP can be parsed directly; there is no extraction step to maintain.

```text
data/
├── SV_123/definition.qsf + export.zip
└── SV_456/definition.qsf + responses.csv
```

From the repository root:

```bash
uv run --extra cli --extra ui python examples/survey_workflow.py SV_123 SV_456 \
  --from-files data --output output/run --report
```

Omit `--from-files` to download each QSF and response ZIP with your configured [Qualtrics API connection](api-access.md). `--report` is optional. Choose a fresh `--output` path for each snapshot; the example refuses a nonempty destination.

The example writes per-survey Parquet entities, one combined entity folder, nine Power BI Parquet tables, and optional HTML reports. It rejects repeated survey IDs before downloading and confirms each QSF describes the requested survey. Repeated exports of **one** survey are not separate surveys and must not be passed to `merge_entity_sets`.

The command prints one results table after the run. It lists each survey's response and comment counts, then prints the combined entities, Power BI, and optional report paths. Typer validates paths and options before work starts and reports invalid input without a Python traceback.

## Bring your own translator

Without a callback, parsing and report generation stay offline. The original free-text answers remain in `response_answers` and `comments`; no prepared text is invented. To connect your service, expose a function in a Python module:

```python
# my_adapter.py
from qualtrics import TranslationRequest


def translate(request: TranslationRequest) -> str:
    # Replace this call with your translation service or offline model.
    return my_translation_service.translate(
        text=request.text,
        source_language=request.source_language,
        target_language=request.target_language,
    )
```

Then run:

```bash
uv run --extra cli --extra ui python examples/survey_workflow.py SV_123 SV_456 \
  --from-files data --translator my_adapter:translate \
  --language EN --report --output output/english-run
```

`TranslationRequest.kind` is `question`, `field`, `answer_option`, or `comment`; it also includes survey and base-entity IDs for logging or routing. The example passes one shared callback. In your own script, override a kind when needed:

```python
from qualtrics import parse_survey, prepare_translations

entities = parse_survey("data/SV_123/export.zip", "data/SV_123/definition.qsf")
prepared = prepare_translations(
    entities,
    language="EN",
    translate=translate,  # default for every kind
    comment=translate_comments,  # optional comment-specific override
)
```

For definition labels, the QSF `SurveyLanguage` is the source. A QSF target label wins; the callback fills missing question, field, and choice labels. Generated locale rows keep base catalog IDs, but get distinct internal IDs and cannot multiply answer facts. Callback-generated choice labels are for display only; they never resolve response values.

For comments, `responses.UserLanguage` is the source when present. An unknown code stays `None`; the toolkit does not detect language from the text or substitute `SurveyLanguage`. A known source equal to the target skips the callback and uses the original. By default each survey targets its own `SurveyLanguage`; `--language` selects one target for all surveys, even outside QSF `AvailableLanguages`. Available language declarations do not limit a user-supplied translation target.

## Read the outputs

```text
output/run/
├── surveys/SV_123/entities/  # one survey, including comments and manifest.json
├── surveys/SV_456/entities/
├── combined/entities/        # both surveys; property and target columns union with nulls
├── combined/report.html      # only with --report
└── power-bi/                 # nine semantic tables + manifest.json
```

`comments` has one row per original written answer, regardless of prepared languages. Targets add nullable columns such as `translated_text__EN`, `translation_source_hash__EN`, and `translation_source_language__EN`; earlier targets survive a later preparation. `fact_comments` carries the same text plus `translation_is_current__EN`. If the original answer or respondent-language metadata changes, the stored translation is stale: reports and Power BI show the original with an unavailable/out-of-date cue until you refresh it. A survey without a target receives nulls when combined with one that has it.

In the HTML report, the respondent-language filter changes counts; the display-language selector changes labels and prepared written text only. In [Power BI](power-bi.md), keep the same two controls separate and use the currentness flag before showing a prepared comment. Raw answers are never replaced.
