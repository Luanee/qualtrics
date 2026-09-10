# Try the survey flow explorer

This fictional team survey demonstrates branches, an early ending, embedded-data assignments, a randomizer, and a web-service step that cannot run offline. It contains **24 fake responses** and is regenerated from source whenever the documentation builds.

<div class="report-example-actions">
  <a class="md-button md-button--primary" href="{{ flow_report_url }}#survey-flow" target="_blank" rel="noopener">Open flow report</a>
  <a class="md-button" href="{{ flow_report_url }}" download>Download report</a>
</div>

<iframe class="report-example-frame" src="{{ flow_report_url }}#survey-flow" title="Fictional team survey flow and hypothetical walkthrough" loading="lazy"></iframe>

## Three paths to explore

1. Select **Sales**, answer the sales follow-up, choose **concept A**, and decline a follow-up conversation.
2. Select **Engineering**, answer its follow-up, choose **concept B**, and request a conversation. The walkthrough pauses at the web-service step and explains why it needs an assumption.
3. Select **Prefer not to say**. The early ending stops the survey before either department block.

Go back and change an earlier choice to see the route change. The report keeps these hypothetical answers separate from the fictional responses used in its charts.

## Download or rebuild the example

<ul>
  <li><a href="{{ flow_survey_url }}" download>Survey definition (QSF)</a></li>
  <li><a href="{{ flow_flow_url }}" download>Flow definition (JSON)</a></li>
  <li><a href="{{ flow_responses_url }}" download>Fake responses (CSV)</a></li>
</ul>

```bash
uv run --extra ui python -m scripts.survey_flow_showcase --output data/survey-flow-showcase
```

The fixture is a reproducible toolkit example, not a live Qualtrics export, and has not been import-tested in Qualtrics. The fake responses are consistent with the illustrated branches; no live web service is configured.

See [understand a survey flow](../guides/survey-flow.md) for your own exports, supported conditions, and the limits of hypothetical walkthroughs.
