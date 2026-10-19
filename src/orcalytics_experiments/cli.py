"""Command line entry point shared by all experiments."""

import argparse
import json
from pathlib import Path

from jsonschema import ValidationError

from .config import create_client, load_environment, store_id_for
from .experiments import TASKS, run_experiment
from .retrieval import prepare_store
from .taxonomy import load_json


def write_json(value, destination=None):
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if destination:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Saved {path}")
    else:
        print(text, end="")


def parser():
    root = argparse.ArgumentParser(description="Run Orcalytics classification experiments.")
    root.add_argument("--env-file", type=Path, help="Default: .env in the current directory")
    commands = root.add_subparsers(dest="command", required=True)
    setup = commands.add_parser(
        "prepare-store", help="Create and index one taxonomy store explicitly"
    )
    setup.add_argument("--task", choices=("industry", "event"), required=True)
    setup.add_argument("--taxonomy", type=Path, required=True)
    setup.add_argument("--name")
    setup.add_argument("--output", type=Path, required=True, help="Save store ID and file manifest")

    run = commands.add_parser(
        "classify", help="Classify an article using a reusable store or industry input"
    )
    run.add_argument("--task", choices=TASKS, required=True)
    run.add_argument("--article", type=Path, required=True)
    run.add_argument("--taxonomy", type=Path, required=True)
    run.add_argument("--industries", type=Path, help="Upstream industry JSON; required for event")
    run.add_argument("--strategy", choices=("vector", "file-search"), default="vector")
    run.add_argument("--vector-store-id", help="Defaults to the appropriate .env store ID")
    run.add_argument("--model", help="Override OPENAI_MODEL and the experiment's original default")
    run.add_argument("--max-results", type=int, default=20)
    run.add_argument("--output", type=Path, help="Default: print the JSON result to stdout")
    return root


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    load_environment(args.env_file)
    try:
        taxonomy = load_json(args.taxonomy)
        if args.command == "prepare-store":
            result = prepare_store(create_client(), args.task, taxonomy, args.name)
        else:
            article = args.article.read_text(encoding="utf-8-sig")
            industries = load_json(args.industries) if args.industries else None
            result = run_experiment(
                create_client(),
                args.task,
                article,
                taxonomy,
                industries=industries,
                strategy=args.strategy,
                model=args.model,
                max_results=args.max_results,
                vector_store_id=args.vector_store_id or store_id_for(args.task),
            )
        write_json(result, args.output)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, ValidationError) as exc:
        arguments.exit(1, f"Error: {exc}\n")
