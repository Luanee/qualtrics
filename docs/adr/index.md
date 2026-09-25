# Architecture decision records

Use an ADR to explain a decision that would be costly to reverse and surprising without its rationale. Record the trade-off when changing module boundaries, identity rules, table grains, or dependency contracts. Routine refactors need no ADR.

The root [architecture guide](https://github.com/Luanee/qualtrics/blob/main/ARCHITECTURE.md) describes the current design. ADRs explain how we chose it. Update that guide and the relevant tests in the same change as an architectural decision.

## Decisions

| Record | Status | Decision |
| --- | --- | --- |
| [0001](0001-protect-the-domain-model-from-adapters.md) | Accepted | Keep shared model operations independent of source parsers and interface adapters. |

## Add a record

Choose the next unused four-digit number and a descriptive filename, such as `0002-name-of-decision.md`. State the problem, the chosen approach, and why it fits. Include rejected alternatives or consequences when they help future maintainers understand the choice.

Use this starting format:

```markdown
# NNNN: Short decision title

Status: Proposed
Recorded: YYYY-MM-DD

Describe the context, decision, and reason in a short paragraph.

## Consequences

Describe the costs or constraints that readers cannot infer from the decision.
```

Mark a proposal **Accepted** after maintainer agreement, or use **Rejected** if it was considered and declined. An ADR that records an established implementation can start as accepted; say that it records an existing decision. To replace an accepted decision, add a new record, change the older record's status to **Superseded by ADR-NNNN**, and link both records. Preserve the earlier rationale.

Add each record to this index and to `nav` in `mkdocs.yml`. Run `uv run poe docs-build` to check the page and navigation links. Commit ADRs under `docs/adr/`; keep temporary plans and research under ignored `knowledge/`.
