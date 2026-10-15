# Architecture and orchestration model

## Overview

The prototype contains two small, independent capabilities:

1. A runnable URL-shortener API backed by SQLite.
2. An offline SDLC workflow that converts one scenario requirement into a structured, traceable engineering report.

Python's standard library is used throughout. This keeps setup reproducible, avoids credentials and network dependencies, and keeps the demonstration focused on orchestration rather than framework configuration.

```text
HTTP client
    |
    v
API handler -> ShortenerService -> UrlStore -> SQLite

Scenario JSON -> Orchestrator -> AgentProvider -> stage outputs
                      |               |
                      |               +-- deterministic provider now
                      |                   (future LLM adapter seam)
                      +-- policy decisions, dependency graph,
                          audit events, metrics, JSON report
```

## URL-shortener data flow

`POST /api/shorten` validates an HTTP(S) destination, rejects embedded credentials and oversized input, generates a cryptographically random seven-character code, and stores the mapping. A unique constraint is the final defense against code collisions; generation retries are capped at five attempts.

`GET /{code}` looks up the code, atomically increments its click count, records the UTC access time, and returns an HTTP redirect. `GET /api/analytics/{code}` returns the mapping and counters. Each store operation uses parameterized SQL and a short-lived SQLite connection.

## Workflow graph

The orchestrator runs explicit task dependencies rather than a single hard-coded chain:

```text
understanding
     |
decomposition
   /       \
api_design  risk_analysis
   \       /
  human_review
       |
implementation
       |
     tests
       |
documentation
       |
  release_gate  [human approval required]
```

`api_design` and `risk_analysis` are submitted together to a two-worker executor and synchronize at `human_review`. The report records every task's dependencies and status. Task outputs are passed as context to downstream tasks; key design decisions are also collected into a decision lineage.

The three checked-in inputs exercise different paths:

- **Greenfield:** clear new-service requirement; reaches a release-readiness approval gate.
- **Brownfield:** enhancement to an existing service; simulates one temporary design-agent failure to show a bounded retry.
- **Ambiguous:** unresolved safety and analytics requirements; stops at human review before implementation.

## Governance and failure behavior

- **Policy:** `PolicyEngine` denies explicitly prohibited actions and requires approval for high-impact actions such as `publish_release` and `irreversible_change`.
- **Human checkpoint:** the release gate returns `awaiting_approval` unless the CLI records the named approval. This prototype records approval only; it never deploys, publishes, or changes external state.
- **Clarification stop:** open requirement questions stop the workflow before an implementation proposal is accepted.
- **Retry and fallback:** transient provider failures are retried once. Exhaustion returns a conservative no-write human handoff and safe-stops dependent stages.
- **Rollback:** a failed validation discards the proposed implementation state, records a rollback event, and prevents documentation/release stages from presenting the result as successful.
- **Replanning:** each invocation creates a new run ID and hashes the requirement. A changed scenario is rerun from the start so all downstream stages are recomputed; prior JSON reports preserve historical lineage rather than serving stale outputs.
- **Auditability:** each stage result includes dependency IDs, status, attempts, and output. Events carry the run ID, task, event type, detail, and upstream tasks.

## Metrics

Each report records success rate, retry count, rollback count, elapsed time of failed attempts (`mttr_seconds`), total end-to-end latency, completed/failed/skipped task counts, and approval-wait counts. Success rate is completed stages divided by the fixed number of graph stages, so a safe stop or approval wait does not appear as a full success.

For a real production workflow, MTTR would be calculated from incident start to recovery over persisted, timestamped operational events; this prototype's failed-attempt duration is only an illustrative proxy.

## Key choices and trade-offs

- **Python:** fast to prototype and easy to connect to AI libraries later. The candidate's Java experience is still valuable; the implementation keeps familiar service boundaries, persistence isolation, explicit contracts, and tests.
- **SQLite:** durable and zero-configuration for a single-user demo. It is not a multi-instance production database.
- **Standard-library HTTP server:** avoids framework setup and makes the execution path easy to explain. A production service would normally use a maintained application framework and server.
- **Provider seam, no live LLM:** makes governance behavior deterministic and testable, but does not claim generated code or model reasoning. A future adapter would need strict output validation, tool permissions, secrets handling, and human review.
- **No arbitrary code execution:** implementation is a proposal artifact; the workflow never writes or executes generated source.
