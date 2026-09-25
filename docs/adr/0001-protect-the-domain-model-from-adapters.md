# 0001: Protect the domain model from adapters

Status: Accepted (records the existing implementation)
Recorded: 2026-09-25

The toolkit supports loading saved entities, parsing raw Qualtrics exports, preparing translations, rendering reports, and building semantic tables. These workflows need the same entity rules after parsing. Keeping localization materialization in the parser previously forced translation models to import parser internals, reversing the dependency direction and tying post-parse operations to source interpretation.

We keep source interpretation in `_common/parsers` and reusable operations on `EntitySet` in `_common/models`. Parsers, analytics, and serialization may depend on models. Models and analytics do not import parsers, and shared code does not import API, CLI, or UI adapters. Adapters coordinate operations through those shared implementations. The root package provides the public facade; shared implementations use internal imports to avoid depending on that facade.

## Alternatives considered

- **Keep post-parse localization in the parser.** This keeps related language code together, but makes model transformations depend on QSF parsing internals even when callers start from saved entity tables.
- **Duplicate the transformation in each consumer.** This removes the reverse import, but allows IDs, missing-label handling, and freshness rules to diverge between reports and semantic exports.

## Consequences

Put a reusable transformation in the model layer if it needs only an `EntitySet`; keep QSF/CSV interpretation in parsers. Translation preparation and consumers can then share model rules without importing each other's adapters. This boundary also keeps CLI and UI dependencies optional for SDK and data users.

The model package currently includes survey-manifest JSON helpers and accepts caller-supplied translation callbacks. This decision constrains package dependencies; it does not assert that every model operation is free of side effects.

Enforce the boundary in `tests/unit/test_architecture.py` and optional-installation behavior in `tests/test_optional_dependencies.py`. The [architecture guide](https://github.com/Luanee/qualtrics/blob/main/ARCHITECTURE.md) lists current owners and public entry points. Future changes to this dependency direction require a superseding ADR and corresponding test changes.
