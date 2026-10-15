# Implementation and change notes

## What was built

The deliverable is split into a small HTTP service and an orchestration demo so the code can be explained in two independent slices.

### URL shortener

- `agentic_shortener/api.py` maps HTTP paths to operations, bounds request size, parses JSON, and returns stable JSON errors.
- `agentic_shortener/shortener.py` owns URL validation, short-code generation, redirects, and analytics behavior.
- `agentic_shortener/storage.py` isolates SQLite schema and parameterized data operations. Each call uses and closes its own connection.
- `docs/api-contract.md` defines request/response examples, validation rules, and error shapes.
- URLs must be valid HTTP(S), are limited to 2,048 characters, and cannot contain embedded username/password credentials. Short codes are seven alphanumeric characters.
- Collision retries are capped. If allocation fails, the API reports a service-unavailable response rather than pretending creation succeeded.

### SDLC orchestration

- `agentic_shortener/orchestrator.py` defines an explicit graph with independent design and risk branches, a synchronization point, a clarification gate, validation, documentation, and release approval.
- `AgentProvider` is the boundary for future AI integration. `DeterministicProvider` produces stable, structured artifacts without network calls.
- Retry exhaustion falls back to a no-write human handoff. A failed validation discards the proposed implementation state and blocks later stages.
- Reports include a unique run ID, requirement digest, stage dependencies/results, decision context, event trace, and reliability counters.
- `agentic_shortener/scenarios/` holds the greenfield, brownfield, and ambiguous inputs. Brownfield intentionally injects one transient failure; ambiguous intentionally requires clarification.

### Tests

- `tests/test_shortener.py` covers destination validation, persistence, click analytics, unknown links, and an end-to-end HTTP create/redirect/analytics flow.
- `tests/test_orchestrator.py` covers parallel branch dependencies, approval, retry, ambiguity safe-stop, rollback, fallback, and denied actions.
- Tests use `unittest` and temporary SQLite files. They require no external service.

### Example execution reports

- `examples/reports/greenfield.json` shows the complete workflow with explicit release-readiness approval.
- `examples/reports/brownfield.json` shows the same gate plus one transient retry.
- `examples/reports/ambiguous.json` shows requirement questions, a safe stop, and skipped downstream stages.

## Decisions made for clarity

- Use an offline deterministic agent provider because the assessment does not require a specific model/provider, while a real provider would add keys, network/cost, nondeterminism, and setup friction.
- Generate reports as JSON and optionally save them under a caller-selected path. Keep generated databases and reports out of version control by default.
- Keep release approval as a gate only. An approval flag proves the workflow can record a human decision but does not authorize any real publication or deployment.
- Rerun changed requirements from the start and identify each run by its input hash. This is simpler and safer than caching outputs; it avoids stale downstream artifacts.
- Do not include the attached assessment PDF. It is labeled internal and is not required to run or explain the prototype.

## Deliberate non-goals

- No authentication, rate limiting, link expiration, abuse detection, or distributed analytics.
- No external LLM, tool execution, source-code patching, deployment, or GitHub upload.
- No claim that deterministic templates constitute production-grade autonomous engineering. The prototype demonstrates orchestration controls and transparent handoffs.

## Suggested walkthrough

1. Run the tests and show the URL-shortener integration test.
2. Run greenfield and show its dependency-linked report and `awaiting_approval` status.
3. Rerun greenfield with `--approve publish_release` and explain that this records readiness only.
4. Run brownfield and point to the transient failure, retry event, and `retry_count`.
5. Run ambiguous and show the clarification questions, safe-stop, and skipped implementation stage.
6. Open `orchestrator.py` and explain the DAG, provider boundary, policy decision, fallback, and rollback in that order.
