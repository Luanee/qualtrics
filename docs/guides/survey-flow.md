# Understand a survey flow

Open **Flow** in the HTML report to see the order of blocks and the rules connecting them. Expand a card to inspect its questions, then follow a question link to its response analysis. The report includes definition-only questions even when the CSV has no answer column for them.

Try the [interactive flow example](../examples/survey-flow.md) with a fictional team survey and 24 fake responses.

## Add flow information to a report

A QSF normally contains its survey flow. Build the entity files again with that definition, then generate the report:

```bash
uv run qualtrics build data/customer.csv \
  --qsf data/customer.qsf \
  --output output/customer/entities

uv run qualtrics report \
  --folder output/customer/entities \
  --output output/customer/report.html
```

An API survey-definition JSON can also be passed to `--qsf`. Existing entity folders still work, but folders built before flow support need to be rebuilt from their source exports. Regenerating HTML alone cannot recover discarded flow information. The report explains when a definition has no available flow; it does not infer a flow from block order or responses.

## Download the flow through the API

With [API credentials configured](api-access.md), download the flow separately:

```bash
uv run qualtrics api flow \
  --survey-id SV_EXAMPLE \
  --output data/customer-flow.json

uv run qualtrics build data/customer.csv \
  --qsf data/customer.qsf \
  --flow data/customer-flow.json \
  --output output/customer/entities
```

`--flow` supplies the flow for one CSV or response ZIP. Keep `--qsf` when available: it supplies block names, question wording, and choices. Use files from the same survey and definition revision. The API flow is a snapshot of the configured definition at download time; it may differ from the version used to collect older responses.

Python users can retrieve the same data:

```python
import json
from pathlib import Path

from qualtrics import QualtricsClient, parse_survey, render_report

with QualtricsClient() as client:
    flow = client.survey_definitions.get_flow("SV_EXAMPLE")

Path("flow.json").write_text(json.dumps(flow), encoding="utf-8")
entities = parse_survey("responses.csv", "survey.qsf", flow_path="flow.json")
render_report(entities, "report.html")
```

The command uses Qualtrics' [Get Flow endpoint](https://www.postman.com/qualtrics-public-apis/qualtrics-public-workspace/request/u10zls2/get-flow) and the client's existing read retries. It does not change the live survey.

## Read the map

| Element | How to read it |
| --- | --- |
| Block | A set of questions encountered at this point in the survey. |
| Branch | Enter the nested steps when its condition holds, then continue with the next step after the branch unless the survey ended. |
| Group | Keep a set of steps together. |
| Randomizer | Choose the configured number of eligible children in a randomized order. |
| Embedded data | Set a field used by later rules, or read a value supplied from outside the survey. |
| End of survey | Stop this route, including any later steps outside the current branch. |
| Advanced or unknown element | Its position remains visible; the walkthrough explains what cannot be evaluated locally. |

Blocks can occur more than once. The map keeps each occurrence in place and shows source Flow IDs as secondary information. Search finds a block, question, condition, or embedded-data field and opens the matching card.

Qualtrics documents [branch continuation](https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/standard-elements/branch-logic/) and [randomizer behavior](https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/standard-elements/randomizer/). In particular, randomizers selecting branches consider their conditions before selecting them.

## Try a hypothetical walkthrough

Choose a survey and start the walkthrough. Enter hypothetical answers, continue through the blocks, and watch the map mark reached, skipped, and pending steps. Use Back to change an earlier answer or Reset to begin again. Changes replay the route and discard downstream answers that no longer belong to it.

At a randomizer, explicitly choose the elements and their order for this scenario. This illustrates one possible outcome; it does not reproduce Qualtrics' allocation history or evenly-present counters.

The first version evaluates common selected/not-selected choice conditions, explicit AND/OR combinations, and embedded-data equality and numeric comparisons. It applies literal embedded-data assignments. Unsupported operators and missing values stay unknown. Advanced elements, quotas, authentication, web services, question display/skip logic, and loop settings may require an explicit scenario assumption before continuing. The report lists these assumptions. It never calls a web service or executes survey JavaScript.

This is an explanation of the supplied definition with hypothetical inputs. It is not an observed respondent path, a complete simulation of all Qualtrics behavior, or proof that a respondent saw a question. Response counts and the dashboard remain based on the recorded responses; walkthrough answers do not change them.

## Saved formats and sharing

Flow metadata is stored as an optional JSON string in `surveys.flow_definition_json`. The existing nine entity tables remain unchanged. JSON, CSV, and Parquet retain the string, and the semantic model carries it into `dim_surveys`, including SQLite output. The report runs offline and does not require a hosted service.

The flow adds survey wording, condition descriptions, and embedded-data values to the report. Share the HTML with the same care as the rest of the exported survey content.
