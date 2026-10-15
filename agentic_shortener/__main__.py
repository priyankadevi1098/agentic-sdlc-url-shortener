from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from .api import create_server
from .orchestrator import Orchestrator
from .scenarios import Scenario, built_in_scenario
from .shortener import ShortenerService
from .storage import UrlStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-shortener",
        description="Run the URL shortener or an offline SDLC orchestration scenario.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="Run the URL-shortener HTTP API.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--database", default="data/shortener.sqlite3")
    serve.add_argument("--base-url", default="http://localhost:8000")

    run = commands.add_parser("run", help="Run a deterministic engineering scenario.")
    scenario_source = run.add_mutually_exclusive_group(required=True)
    scenario_source.add_argument(
        "--scenario", choices=("greenfield", "brownfield", "ambiguous")
    )
    scenario_source.add_argument("--scenario-file", type=Path)
    run.add_argument(
        "--approve",
        action="append",
        default=[],
        choices=("publish_release", "irreversible_change"),
        help="Record a human approval for a named high-impact action.",
    )
    run.add_argument("--output", type=Path)
    return parser


def _load_scenario(args: argparse.Namespace) -> Scenario:
    if args.scenario:
        return built_in_scenario(args.scenario)
    return Scenario.from_json(args.scenario_file)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        database = Path(args.database)
        store = UrlStore(database)
        server = create_server(
            ShortenerService(store), args.host, args.port, args.base_url
        )
        print(f"Listening at http://{args.host}:{args.port} using {database}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server.")
        finally:
            server.server_close()
        return 0

    scenario = _load_scenario(args)
    report = Orchestrator().run(scenario, set(args.approve))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + os.linesep, encoding="utf-8")
    print(rendered)
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
