"""Explicit supported application contracts and independent acceptance fixtures."""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPPORTED_TYPES = ("task_manager", "expense_tracker")
FILES = ["app.py", "requirements.txt", "templates/index.html", "static/style.css",
         "static/app.js", "tests/test_backend.py", "tests/test_browser.py"]


def profile(project_type):
    if project_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported project_type {project_type!r}; choose {', '.join(SUPPORTED_TYPES)}.")
    return json.loads((ROOT / "profiles" / f"{project_type}.json").read_text())


def contract_type(contract):
    if not isinstance(contract, dict):
        raise ValueError("Contract must be a JSON object.")
    kind = contract.get("project_type")
    # Compatibility only for the original, agreed task-manager contract.
    if kind is None and "task" in contract and any(
        route.get("path") == "/api/tasks" for route in contract.get("routes", [])
    ):
        kind = "task_manager"
    expected = profile(kind)
    for field in expected:
        if field in ("project_name", "project_type", "acceptance_criteria"):
            continue
        if contract.get(field) != expected.get(field):
            raise ValueError(f"Contract {field} differs from supported {kind} profile; explicit support is required.")
    entity = "task" if kind == "task_manager" else "expense"
    if contract.get(entity) != expected.get(entity):
        raise ValueError(f"Contract {entity} differs from supported profile.")
    return kind


def build_contract(spec):
    if not isinstance(spec, dict):
        raise ValueError("Specification must be a JSON object.")
    kind = spec.get("project_type")
    contract = copy.deepcopy(profile(kind))
    contract.update(project_type=kind, project_name=spec["name"],
                    acceptance_criteria=spec["acceptance_criteria"])
    return contract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--project-type", choices=SUPPORTED_TYPES)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    try:
        spec = json.loads((workspace / "spec.json").read_text())
        if args.project_type:
            spec["project_type"] = args.project_type
        contract = build_contract(spec)
        with (workspace / "contract.json").open("x") as output:
            json.dump(contract, output, indent=2)
            output.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Cannot build contract: {error}")
    print(f"Saved contract: {workspace / 'contract.json'}")


if __name__ == "__main__":
    main()
