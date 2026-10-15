from __future__ import annotations

import unittest
from threading import Barrier

from agentic_shortener.orchestrator import (
    DeterministicProvider,
    Orchestrator,
    PolicyEngine,
    TASKS,
    TransientAgentError,
)
from agentic_shortener.scenarios import Scenario, built_in_scenario


class AlwaysFailProvider(DeterministicProvider):
    def run(self, task, scenario, context, attempt):
        if task == "understanding":
            raise TransientAgentError("Simulated repeated failure.")
        return super().run(task, scenario, context, attempt)


class ParallelBranchProvider(DeterministicProvider):
    def __init__(self) -> None:
        self.design_barrier = Barrier(2)

    def run(self, task, scenario, context, attempt):
        if task in {"api_design", "risk_analysis"}:
            self.design_barrier.wait(timeout=2)
        return super().run(task, scenario, context, attempt)


class OrchestratorTests(unittest.TestCase):
    def test_parallel_design_branches_join_before_human_review(self) -> None:
        dependencies = {task.name: task.dependencies for task in TASKS}

        self.assertEqual(dependencies["api_design"], ("decomposition",))
        self.assertEqual(dependencies["risk_analysis"], ("decomposition",))
        self.assertEqual(
            set(dependencies["human_review"]), {"api_design", "risk_analysis"}
        )

    def test_independent_design_branches_execute_in_parallel(self) -> None:
        report = Orchestrator(ParallelBranchProvider()).run(
            built_in_scenario("greenfield"), {"publish_release"}
        )

        self.assertEqual(report["status"], "completed")

    def test_release_waits_for_explicit_approval(self) -> None:
        scenario = built_in_scenario("greenfield")

        waiting = Orchestrator().run(scenario)
        released = Orchestrator().run(scenario, {"publish_release"})

        self.assertEqual(waiting["status"], "awaiting_approval")
        self.assertEqual(
            waiting["tasks"]["release_gate"]["output"]["policy_decision"],
            "awaiting_approval",
        )
        self.assertEqual(released["status"], "completed")
        self.assertTrue(released["tasks"]["release_gate"]["output"]["approved"])

    def test_brownfield_retries_transient_failure_once(self) -> None:
        report = Orchestrator().run(built_in_scenario("brownfield"), {"publish_release"})

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["metrics"]["retry_count"], 1)
        self.assertEqual(report["tasks"]["api_design"]["attempts"], 2)
        self.assertTrue(
            all(event["run_id"] == report["run_id"] for event in report["events"])
        )

    def test_ambiguous_requirement_safe_stops_before_implementation(self) -> None:
        report = Orchestrator().run(built_in_scenario("ambiguous"))

        self.assertEqual(report["status"], "safe_stopped")
        self.assertEqual(report["tasks"]["human_review"]["status"], "safe_stopped")
        self.assertEqual(report["tasks"]["implementation"]["status"], "skipped")

    def test_failed_validation_rolls_back_proposed_state(self) -> None:
        scenario = Scenario(
            name="forced-failure",
            kind="test",
            requirement="Validate rollback.",
            fail_validation=True,
        )
        report = Orchestrator().run(scenario)

        self.assertEqual(report["metrics"]["rollback_count"], 1)
        self.assertEqual(report["tasks"]["tests"]["status"], "rolled_back")
        self.assertFalse(report["context"]["implementation_proposal_active"])
        self.assertEqual(report["tasks"]["documentation"]["status"], "skipped")

    def test_retry_exhaustion_uses_safe_fallback_and_stops(self) -> None:
        scenario = built_in_scenario("greenfield")
        report = Orchestrator(AlwaysFailProvider()).run(scenario)

        self.assertEqual(report["status"], "safe_stopped")
        self.assertEqual(
            report["tasks"]["understanding"]["output"]["review_required"], True
        )
        self.assertEqual(report["tasks"]["decomposition"]["status"], "skipped")
        self.assertTrue(any(event["event"] == "fallback" for event in report["events"]))

    def test_policy_denies_explicitly_forbidden_actions(self) -> None:
        self.assertEqual(PolicyEngine().evaluate("delete_production_data", set()), "denied")


if __name__ == "__main__":
    unittest.main()
