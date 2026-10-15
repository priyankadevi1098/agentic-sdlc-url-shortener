from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Scenario:
    name: str
    kind: str
    requirement: str
    open_questions: tuple[str, ...] = ()
    transient_failures: tuple[str, ...] = ()
    fail_validation: bool = False

    @classmethod
    def from_json(cls, path: str | Path) -> "Scenario":
        with Path(path).open(encoding="utf-8") as scenario_file:
            value: dict[str, Any] = json.load(scenario_file)
        return cls(
            name=value["name"],
            kind=value["kind"],
            requirement=value["requirement"],
            open_questions=tuple(value.get("open_questions", [])),
            transient_failures=tuple(value.get("transient_failures", [])),
            fail_validation=bool(value.get("fail_validation", False)),
        )


def built_in_scenario(name: str) -> Scenario:
    try:
        return Scenario.from_json(Path(__file__).parent / "scenarios" / f"{name}.json")
    except FileNotFoundError as error:
        raise ValueError(f"Unknown scenario: {name}") from error
