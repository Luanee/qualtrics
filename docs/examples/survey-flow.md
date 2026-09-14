# Explore a survey flow

Choose a route through a fictional team survey. Change an answer, and watch the next steps change. The explorer opens in its own tab so the map and walkthrough have room to work.

<div class="report-example-actions">
  <a class="md-button md-button--primary" href="{{ flow_report_url }}#survey-flow" target="_blank" rel="noopener">Open flow explorer ↗</a>
  <a class="md-button" href="{{ flow_report_url }}" download>Download report</a>
</div>

<div class="flow-example-preview" role="group" aria-label="Three possible routes through the fictional team survey">
  <p class="flow-example-preview__eyebrow">A route, not a result</p>
  <ol>
    <li><strong>Sales</strong><span>Sales follow-up → concept A → decline conversation</span></li>
    <li><strong>Engineering</strong><span>Engineering follow-up → concept B → request conversation <em>→ web-service assumption</em></span></li>
    <li><strong>Prefer not to say</strong><span>Early ending → skips both department blocks</span></li>
  </ol>
</div>

The **Engineering** route pauses at a web-service step and explains the assumption needed to continue. Go back and change an earlier choice to see the route change. Your hypothetical answers never alter the charts, which use the example's **24 fake responses**.

The example includes branches, embedded-data assignments, a randomizer, and an early ending. It is regenerated from source whenever the docs build.

## Use the example files

<ul>
  <li><a href="{{ flow_survey_url }}" download>Survey definition (QSF)</a></li>
  <li><a href="{{ flow_flow_url }}" download>Flow definition (JSON)</a></li>
  <li><a href="{{ flow_responses_url }}" download>Fake responses (CSV)</a></li>
</ul>

```bash
uv run --extra ui python -m scripts.survey_flow_showcase --output data/survey-flow-showcase
```

This reproducible fixture is not a live Qualtrics export and has not been import-tested in Qualtrics. Its fake responses follow the illustrated branches; no live web service is configured.

See [understand a survey flow](../guides/survey-flow.md) for your own exports, supported conditions, and the limits of hypothetical walkthroughs.
