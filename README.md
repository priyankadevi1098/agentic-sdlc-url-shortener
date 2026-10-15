# Agentic Software Engineering System: URL Shortener

An intentionally small, local prototype for the AI Engineering Assessment. It contains a working URL-shortener API and an offline SDLC orchestrator that turns a requirement into a reviewable plan, design, risk analysis, implementation proposal, validation summary, and release-readiness decision.

The orchestration provider is deterministic. It demonstrates workflow control, not live LLM reasoning or automatic code generation. A narrow provider interface makes later model integration possible without making this submission depend on a key, network, or paid service.

## Requirements

- Python 3.11 or newer
- No runtime third-party packages

## Run the tests

From this project directory, in PowerShell:

```powershell
py -3 -m unittest discover -s tests -v
```

## Run the orchestration scenarios

Run each scenario and inspect the JSON report:

```powershell
py -3 -m agentic_shortener run --scenario greenfield
py -3 -m agentic_shortener run --scenario brownfield
py -3 -m agentic_shortener run --scenario ambiguous
```

Sample outputs for all three paths are included under `examples\reports\`.

The greenfield and brownfield scenarios reach the release gate and pause until approved. To record human approval of the release-readiness action:

```powershell
py -3 -m agentic_shortener run --scenario greenfield --approve publish_release --output artifacts\greenfield-approved.json
```

The approval is recorded in the workflow report; the prototype does not publish or deploy anything. The ambiguous scenario stops before implementation until its open questions are answered. It can be rerun with an edited scenario file:

```powershell
py -3 -m agentic_shortener run --scenario-file path\to\my-scenario.json
```

Every run fingerprints the requirement, creates a new run ID, and recomputes dependent stages rather than reusing stale stage output.

## Run the URL-shortener API

Start the local service:

```powershell
py -3 -m agentic_shortener serve
```

In another PowerShell window, create a short link:

```powershell
$created = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/shorten -ContentType 'application/json' -Body '{"url":"https://example.com/article"}'
$created
```

Visit `$created.short_url` in a browser to follow the redirect, then inspect analytics:

```powershell
Invoke-RestMethod "http://localhost:8000/api/analytics/$($created.code)"
```

The API binds to `127.0.0.1` by default and stores records in `data\shortener.sqlite3`. Configure `--host`, `--port`, `--database`, or `--base-url` for a local test setup.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/shorten` | Create a short code from `{"url":"https://..."}` |
| `GET` | `/{code}` | Record a click and redirect to the destination |
| `GET` | `/api/analytics/{code}` | Return destination, creation time, click count, and last access |
| `GET` | `/healthz` | Return service health |

Creation returns `201`; invalid input returns `400`; unknown short codes return `404`. Error bodies use `{"error":{"code":"...","message":"..."}}`.

## Project layout

- `agentic_shortener/shortener.py`, `storage.py`, `api.py`: URL-shortening rules, SQLite persistence, and HTTP surface.
- `agentic_shortener/orchestrator.py`: dependency graph, deterministic provider, policy gate, bounded retry/fallback, rollback, audit events, and metrics.
- `agentic_shortener/scenarios/`: the three assessment scenario inputs.
- `tests/`: standard-library unit and HTTP integration tests.
- `docs/`: architecture, detailed change notes, validation/limitations, and interview preparation.

## Documentation

- [API contract](docs/api-contract.md)
- [Architecture and workflow](docs/architecture.md)
- [Implementation and change notes](docs/implementation-notes.md)
- [Testing, assumptions, risks, and limitations](docs/testing-and-limitations.md)
- [Interview questions and suggested answers](docs/interview-qa.md)

## Assessment fit and boundaries

The project implements a real local URL shortener and demonstrates SDLC orchestration across requirements, decomposition, parallel design/risk analysis, implementation proposal, tests, documentation, and release readiness. It deliberately does not edit arbitrary source files or make external release actions. The assessment PDF was not copied into this project.
