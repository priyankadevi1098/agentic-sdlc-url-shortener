from __future__ import annotations

import hashlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Protocol

from .scenarios import Scenario


class TransientAgentError(Exception):
    pass


@dataclass(frozen=True)
class Task:
    name: str
    dependencies: tuple[str, ...]


TASKS = (
    Task("understanding", ()),
    Task("decomposition", ("understanding",)),
    Task("api_design", ("decomposition",)),
    Task("risk_analysis", ("decomposition",)),
    Task("human_review", ("api_design", "risk_analysis")),
    Task("implementation", ("human_review",)),
    Task("tests", ("implementation",)),
    Task("documentation", ("tests",)),
    Task("release_gate", ("documentation", "risk_analysis")),
)


class AgentProvider(Protocol):
    """Replacement boundary for a future hosted LLM; the demo provider is offline."""

    def run(
        self, task: str, scenario: Scenario, context: dict[str, Any], attempt: int
    ) -> dict[str, Any]: ...


class DeterministicProvider:
    def run(
        self, task: str, scenario: Scenario, context: dict[str, Any], attempt: int
    ) -> dict[str, Any]:
        if task in scenario.transient_failures and attempt == 1:
            raise TransientAgentError(f"Temporary simulated failure in {task}.")

        if task == "understanding":
            return {
                "normalized_requirement": scenario.requirement.strip(),
                "open_questions": list(scenario.open_questions),
                "assumptions": [],
            }
        if task == "decomposition":
            return {
                "work_items": [
                    {"id": "api-contract", "depends_on": []},
                    {"id": "persistence", "depends_on": ["api-contract"]},
                    {"id": "implementation", "depends_on": ["api-contract", "persistence"]},
                    {"id": "validation", "depends_on": ["implementation"]},
                    {"id": "documentation", "depends_on": ["validation"]},
                ],
                "parallel_groups": [["api_design", "risk_analysis"]],
                "synchronization_point": "human_review",
            }
        if task == "api_design":
            return {
                "endpoints": [
                    "POST /api/shorten",
                    "GET /{code} (redirect)",
                    "GET /api/analytics/{code}",
                    "GET /healthz",
                ],
                "decision": "Use SQLite for local durable storage and parameterized SQL.",
            }
        if task == "risk_analysis":
            return {
                "risks": [
                    {
                        "risk": "Invalid or credential-bearing destination URLs",
                        "control": "Allow only HTTP(S), reject embedded credentials, bound input size.",
                    },
                    {
                        "risk": "Unreviewed release action",
                        "control": "Pause at the release gate until a human supplies approval.",
                    },
                ],
                "policy": "No external calls, secrets, code execution, or publication in this prototype.",
            }
        if task == "implementation":
            return {
                "change_proposal": (
                    "Implement the URL-shortener API, SQLite storage, analytics, "
                    "and focused automated tests."
                ),
                "generated_or_modified_source": False,
                "decision": "The assessment demo emits a reviewable proposal; it does not edit arbitrary files.",
            }
        if task == "human_review":
            open_questions = context["understanding"]["open_questions"]
            return {
                "open_questions": open_questions,
                "decision": (
                    "Pause for clarification before implementation."
                    if open_questions
                    else "Scope is sufficiently clear for the implementation proposal."
                ),
                "approved": not open_questions,
            }
        if task == "tests":
            return {
                "checks": [
                    "URL validation and bounded short-code allocation",
                    "Create and redirect behavior",
                    "Click analytics",
                    "Approval and safe-stop gates",
                ],
                "passed": not scenario.fail_validation,
            }
        if task == "documentation":
            return {
                "artifacts": [
                    "README and setup guide",
                    "Architecture and workflow notes",
                    "Scenario trace and validation summary",
                ],
                "decision_lineage": [
                    "normalized requirement",
                    "decomposition and dependencies",
                    "design and risk controls",
                    "implementation proposal and validation",
                ],
            }
        if task == "release_gate":
            return {
                "action": "publish_release",
                "requires_human_approval": True,
                "approved": False,
            }
        raise ValueError(f"Unknown workflow task: {task}")


class PolicyEngine:
    HIGH_IMPACT_ACTIONS = {"publish_release", "irreversible_change"}
    DENIED_ACTIONS = {"credential_exfiltration", "delete_production_data"}

    def evaluate(self, action: str, approvals: set[str]) -> str:
        if action in self.DENIED_ACTIONS:
            return "denied"
        if action in self.HIGH_IMPACT_ACTIONS and action not in approvals:
            return "awaiting_approval"
        return "approved"


class Orchestrator:
    def __init__(
        self, provider: AgentProvider | None = None, policy: PolicyEngine | None = None
    ) -> None:
        self.provider = provider or DeterministicProvider()
        self.policy = policy or PolicyEngine()

    def run(self, scenario: Scenario, approvals: set[str] | None = None) -> dict[str, Any]:
        approvals = approvals or set()
        run_id = str(uuid.uuid4())
        started = time.perf_counter()
        requirement_digest = hashlib.sha256(
            scenario.requirement.encode("utf-8")
        ).hexdigest()
        context: dict[str, Any] = {
            "scenario": scenario.name,
            "requirement_sha256": requirement_digest,
            "decisions": [],
        }
        task_results: dict[str, dict[str, Any]] = {}
        events: list[dict[str, Any]] = []
        retries = rollbacks = mttr_seconds = 0.0
        completed = failed = skipped = awaiting_approval = safe_stopped = 0

        pending = {task.name: task for task in TASKS}
        while pending:
            ready = sorted(
                name
                for name, task in pending.items()
                if all(dependency in task_results for dependency in task.dependencies)
            )
            if not ready:
                raise RuntimeError("Workflow graph contains a dependency cycle.")
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    name: executor.submit(
                        self._execute_task,
                        run_id,
                        name,
                        scenario,
                        context.copy(),
                    )
                    for name in ready
                    if all(
                        task_results[dependency]["status"] == "completed"
                        for dependency in pending[name].dependencies
                    )
                }
                results: dict[str, dict[str, Any]] = {}
                for name in sorted(futures):
                    results[name] = futures[name].result()

            for name in ready:
                task = pending.pop(name)
                if name not in results:
                    task_results[name] = {
                        "status": "skipped",
                        "dependencies": list(task.dependencies),
                    }
                    skipped += 1
                    events.append(self._event(run_id, name, "skipped", "upstream gate did not pass"))
                    continue

                result = results[name]
                retries += result["retries"]
                mttr_seconds += result["failed_attempt_seconds"]
                status = result["status"]
                output = result["output"]

                if name == "human_review" and not output.get("approved", False):
                    status = "safe_stopped"
                if name == "implementation" and status == "completed":
                    context["implementation_proposal_active"] = True
                if status == "safe_stopped":
                    safe_stopped += 1
                elif name == "tests" and not output["passed"]:
                    context["implementation_proposal_active"] = False
                    rollbacks += 1
                    failed += 1
                    status = "rolled_back"
                    events.append(
                        self._event(
                            run_id,
                            name,
                            "rollback",
                            "Validation failed; discard the proposed implementation state.",
                        )
                    )
                elif name == "release_gate":
                    approval = self.policy.evaluate(output["action"], approvals)
                    output["policy_decision"] = approval
                    output["approved"] = approval == "approved"
                    if approval == "awaiting_approval":
                        status = "awaiting_approval"
                        awaiting_approval += 1
                    elif approval == "denied":
                        status = "safe_stopped"
                        safe_stopped += 1
                    else:
                        status = "completed"
                        completed += 1
                elif status == "completed":
                    completed += 1
                else:
                    failed += 1

                task_results[name] = {
                    "status": status,
                    "dependencies": list(task.dependencies),
                    "attempts": result["attempts"],
                    "output": output,
                }
                context[name] = output
                if output.get("decision"):
                    context["decisions"].append(
                        {"stage": name, "decision": output["decision"]}
                    )
                if name == "human_review" and not output["approved"]:
                    events.append(
                        self._event(
                            run_id,
                            name,
                            "safe_stop",
                            "Open requirement questions must be resolved before implementation.",
                            task.dependencies,
                        )
                    )
                events.extend(result["events"])
                events.append(
                    self._event(
                        run_id,
                        name,
                        status,
                        f"Finished with {result['attempts']} attempt(s); status={status}.",
                        task.dependencies,
                    )
                )

        if safe_stopped:
            run_status = "safe_stopped"
        elif awaiting_approval:
            run_status = "awaiting_approval"
        elif failed:
            run_status = "failed"
        else:
            run_status = "completed"
        scheduled = len(TASKS)
        elapsed = time.perf_counter() - started
        events.append(
            self._event(
                run_id,
                "workflow",
                "replan_boundary",
                "Each run fingerprints its requirement and recomputes all dependent stages; no stale stage output is reused.",
            )
        )
        return {
            "run_id": run_id,
            "scenario": scenario.name,
            "scenario_kind": scenario.kind,
            "status": run_status,
            "requirement_sha256": requirement_digest,
            "context": context,
            "tasks": task_results,
            "events": events,
            "metrics": {
                "success_rate": round(completed / scheduled, 3),
                "retry_count": int(retries),
                "rollback_count": int(rollbacks),
                "mttr_seconds": round(mttr_seconds, 6),
                "end_to_end_latency_ms": round(elapsed * 1000, 3),
                "completed_tasks": completed,
                "failed_tasks": failed,
                "skipped_tasks": skipped,
                "awaiting_approval_tasks": awaiting_approval,
            },
        }

    def _execute_task(
        self, run_id: str, name: str, scenario: Scenario, context: dict[str, Any]
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        failed_attempt_seconds = 0.0
        attempts = 0
        for attempt in range(1, 3):
            attempts += 1
            started = time.perf_counter()
            try:
                output = self.provider.run(name, scenario, context, attempt)
            except TransientAgentError as error:
                duration = time.perf_counter() - started
                failed_attempt_seconds += duration
                events.append(
                    {
                        "run_id": run_id,
                        "task": name,
                        "event": "retry",
                        "attempt": attempt,
                        "reason": str(error),
                        "fallback": "retry once, then stop safely",
                    }
                )
                continue
            return {
                "status": "completed",
                "output": output,
                "attempts": attempts,
                "retries": attempts - 1,
                "failed_attempt_seconds": failed_attempt_seconds,
                "events": events,
            }
        return {
            "status": "safe_stopped",
            "output": {
                "fallback": "Conservative human handoff; no source changes applied.",
                "review_required": True,
            },
            "attempts": attempts,
            "retries": attempts - 1,
            "failed_attempt_seconds": failed_attempt_seconds,
            "events": events
            + [
                {
                    "run_id": run_id,
                    "task": name,
                    "event": "fallback",
                    "reason": "Use a conservative no-write human handoff.",
                },
                {
                    "run_id": run_id,
                    "task": name,
                    "event": "safe_stop",
                    "reason": "Bounded retry limit reached.",
                }
            ],
        }

    @staticmethod
    def _event(
        run_id: str,
        task: str,
        event: str,
        detail: str,
        dependencies: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return         {
            "run_id": run_id,
            "run_id": run_id,
            "task": task,
            "event": event,
            "detail": detail,
            "depends_on": list(dependencies),
        }
