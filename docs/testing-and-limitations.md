# Testing, assumptions, risks, and limitations

## Validation approach

Run all tests from the project root:

```powershell
py -3 -m unittest discover -s tests -v
```

The tests cover:

- Accepting valid HTTP(S) URLs and rejecting malformed schemes, malformed hosts, embedded credentials, and unknown codes.
- Creating a link, redirecting, and updating click count/last-accessed analytics over HTTP.
- Explicit stage dependencies, parallel design/risk branches, and synchronization.
- Release approval, clarification safe-stop, bounded retry, fallback, rollback after failed validation, and policy denial.

The HTTP integration test starts a server on an ephemeral loopback port and uses a temporary database. It does not need an internet connection.

## Assumptions

- Python 3.11+ is available.
- The prototype is run by one developer on one machine.
- URL destinations are HTTP(S); destination ownership and reachability are not verified.
- A click means a redirect request received by this service; bot filtering is not implemented.
- Scenario reports are evidence of orchestration behavior, not proof that a live model built or reviewed the source.
- Human approval flags simulate an explicit decision in the CLI. They do not authorize an external side effect.

## Risks and mitigations

| Risk | Mitigation in this prototype | Remaining gap |
|---|---|---|
| Malformed or dangerous URL schemes | Parse and allow only HTTP(S); reject embedded credentials and oversized values | Does not inspect destinations for malware or SSRF if the service later fetches them |
| Short-code collision | Random codes, database uniqueness, and a fixed retry cap | No capacity planning or custom alias support |
| SQL injection | Parameterized SQL and isolated storage methods | Database file permissions remain an operator responsibility |
| Unreviewed changes/releases | Clarification and release gates; no arbitrary file writes or external action | Approval identity/authentication is not implemented |
| Agent/provider failure | One retry, conservative fallback, safe-stop, and event trace | No durable job queue or distributed recovery |
| Failed output being treated as release-ready | Validation failure rolls back proposal state and skips downstream stages | Rollback is modeled state, not an external source-control revert |
| Lost run history | Optional JSON output path and per-run ID/input digest | There is no built-in report database, retention, or access control |

## Important product limitations

- The shortener is an educational local prototype: no authentication, authorization, throttling, expiry, abuse prevention, custom domains, or multi-tenant isolation.
- SQLite suits local demonstration, not high-throughput multi-instance deployment.
- Analytics stores a total click count and last timestamp only; no user/IP identifiers are collected.
- The HTTP server is from Python's standard library and is not intended as a production internet-facing server.
- Orchestration stages emit deterministic structured proposals. There is no actual AI reasoning or automatic source-code generation.
- Reliability metrics are demo estimates. In particular, `mttr_seconds` sums failed-attempt durations; real MTTR needs durable timestamps and incident lifecycle definitions.
- Replanning is conservative full recomputation for each new run, not incremental DAG caching.
