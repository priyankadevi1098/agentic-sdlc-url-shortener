# Interview preparation: likely questions and suggested answers

Adapt these answers to your own experience. Be candid that this is a deterministic orchestration prototype rather than a live LLM coding agent.

## 1. Why did you choose Python instead of Java?

The assessment is focused on demonstrating an agent/workflow prototype quickly, and Python has a compact standard library and a strong future AI ecosystem. I kept the service, persistence, and workflow boundaries explicit, so the design is still easy to transfer to Java. For a production service in my team's Java stack, I would choose Java/Spring Boot for consistency and operational support.

## 2. Is this really agentic if the provider is deterministic?

It is a prototype of the agentic control plane, not a claim of model reasoning. The provider interface separates task orchestration from task execution. Deterministic behavior makes dependency ordering, approvals, retries, failure handling, and audit results reproducible. A future LLM provider can implement the same interface after defining structured outputs and permissions.

## 3. What does the orchestrator contribute beyond a linear pipeline?

Tasks have declared dependencies. API design and risk analysis can run independently, then synchronize at human review. The workflow tracks each task and its upstream dependencies, can skip descendants after a gate or failure, and records decisions and run events. That graph makes the control flow explicit and testable.

## 4. How do you prevent an agent from making a risky change?

The prototype does not execute arbitrary code or write generated source. It checks high-impact actions through a policy gate, pauses for human approval, and stops when requirements remain ambiguous. The approval flag only records the decision; there is no publish/deploy implementation behind it.

## 5. How are retries and fallback bounded?

The orchestrator retries a transient task failure once. If it still fails, it emits a conservative human handoff, marks the task safe-stopped, and skips dependent stages. This prevents an unbounded loop and avoids a success-shaped fallback.

## 6. What does rollback mean here?

The implementation stage produces a proposal, not a file mutation. If validation fails, the proposal's applied-state marker is cleared, a rollback event is recorded, and documentation/release stages are skipped. A production implementation would need transactional writes or a source-control workspace and a tested revert mechanism.

## 7. How do you handle ambiguous requirements?

The requirement-understanding stage carries explicit open questions. The human-review gate stops before implementation if any remain. For the demo, the ambiguous scenario asks what “safer” means and what analytics/retention are expected. I would clarify these rather than invent product behavior.

## 8. How does re-planning work when a requirement changes?

Each run has a unique ID and a SHA-256 digest of its requirement. I rerun changed input from the start and recompute every dependent stage; I intentionally avoid reusing cached outputs so stale decisions cannot leak into a new plan. Prior reports preserve lineage for comparison.

## 9. What metrics are available?

The report includes success rate, retries, rollbacks, failed-attempt duration as an MTTR proxy, end-to-end latency, and task outcomes. In production I would persist timestamped events and define incident start/recovery boundaries before reporting MTTR.

## 10. Why SQLite?

It gives the runnable demo durable state without infrastructure or credentials. The data access code is isolated behind `UrlStore`, so moving to PostgreSQL or another service is localized. SQLite is not the right choice for a distributed high-write production service.

## 11. How do you avoid SQL injection?

Every query uses placeholders and bound parameters. The API does not concatenate user-provided codes or URLs into SQL.

## 12. What URL validation do you perform?

I allow only HTTP and HTTPS, reject malformed hosts, embedded username/password credentials, empty values, and inputs longer than 2,048 characters. I do not fetch destinations, so this service does not currently have a server-side request forgery path; if link previews or scanning were added, outbound egress controls would be necessary.

## 13. What would you change before production?

I would add authentication/authorization, rate limiting and abuse controls, link expiry/ownership policy, stronger URL reputation checks, operational metrics, structured logs, a production server, deployment configuration, and a scalable database. I would also run a real model behind a constrained tool interface and evaluate its outputs against adversarial and regression tests.

## 14. How would you integrate a real LLM safely?

Implement a provider adapter that accepts typed task input and returns schema-validated output. Give it no direct shell or filesystem access. Restrict tools to allowlisted, isolated operations; redact secrets; set time/token budgets; record model and prompt versions; apply policy checks to outputs; and require human approval for high-impact changes. Keep deterministic tests around the orchestration layer.

## 15. How would you test this system?

I test service behavior and HTTP flows with a temporary SQLite database, then test orchestration gates, graph dependencies, retries, fallback, rollback, and policy decisions with deterministic providers. A real model adapter would additionally need contract tests, evaluation datasets, failure injection, prompt-injection tests, and controlled integration tests.

## 16. What is the main trade-off you made?

I optimized for a reliable, explainable end-to-end demo over broad AI autonomy. The control plane and URL-shortener behavior are real and testable, but the “agents” use fixed outputs. That makes the governance story credible without overstating what the prototype can do.
