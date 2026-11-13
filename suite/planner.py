import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from suite.llm import OllamaClient
from suite.files import create_file
from suite.contracts import SUPPORTED_TYPES


SYSTEM = """
You are a software project planner.

Return only one valid JSON object with these fields:
{
  "project_type": "task_manager or expense_tracker",
  "name": "Short project name",
  "summary": "What the application does",
  "requirements": ["Specific functional requirement"],
  "acceptance_criteria": ["Observable behavior that can be tested"],
  "tasks": [
    {
      "id": "task_1",
      "title": "Task title",
      "description": "Concrete implementation work",
      "depends_on": []
    }
  ]
}

Rules:
- Target a small local Flask application with HTML, CSS, and JavaScript.
- Use Python's sqlite3 module if persistent storage is needed.
- Do not require paid services, external APIs, or credentials.
- Include backend tests and browser tests in the task plan.
- Order tasks so dependencies appear before the tasks that need them.
- Use unique task IDs.
- Do not include source code or shell commands.
- Support only task_manager (create, list, toggle, delete tasks) or expense_tracker
  (add dated CAD expenses, filter category, exact cent totals; no edit/delete).
- Reject unrelated scope. Do not include deployment, authentication, or paid services.
- Keep scope realistic for a first working prototype.
"""


def validate_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("The specification must be a JSON object.")

    if spec.get("project_type") not in SUPPORTED_TYPES:
        raise ValueError("Choose a supported project_type: task_manager or expense_tracker.")

    for field in ("name", "summary"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"Missing or invalid field: {field}")

    for field in ("requirements", "acceptance_criteria"):
        values = spec.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(item, str) or not item.strip() for item in values)
        ):
            raise ValueError(f"{field} must be a nonempty list of text.")

    tasks = spec.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("The plan must contain tasks.")

    seen = set()

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task must be an object.")

        for field in ("id", "title", "description"):
            if not isinstance(task.get(field), str) or not task[field].strip():
                raise ValueError(f"Task has missing or invalid {field}.")

        task_id = task["id"]
        if task_id in seen:
            raise ValueError(f"Duplicate task ID: {task_id}")

        dependencies = task.get("depends_on")
        if not isinstance(dependencies, list):
            raise ValueError(f"{task_id}: depends_on must be a list.")

        for dependency in dependencies:
            if not isinstance(dependency, str) or dependency not in seen:
                raise ValueError(
                    f"{task_id}: dependency must reference an earlier task."
                )

        seen.add(task_id)

    return spec


def plan_project(objective, project_type, root, client=None):
    if not objective.strip() or project_type not in SUPPORTED_TYPES:
        raise ValueError("Enter an objective and a supported project type.")
    client = client or OllamaClient()
    response = client.chat(
        prompt=f"Create a specification for project_type={project_type}:\n{objective}",
        system=SYSTEM, json_mode=True,
    )
    spec = validate_spec(json.loads(response))
    if spec['project_type'] != project_type:
        raise ValueError("Planner returned a different project type.")
    spec['objective'] = objective.strip()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    workspace = Path(root) / f"project-{timestamp}-{uuid.uuid4().hex[:8]}"
    workspace.mkdir(parents=True, exist_ok=False)
    create_file(workspace / 'spec.json', json.dumps(spec, indent=2) + '\n')
    return workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--objective')
    parser.add_argument('--project-type', choices=SUPPORTED_TYPES, required=True)
    args = parser.parse_args()
    objective = args.objective or input("What do you want to build?\n> ")
    try:
        workspace = plan_project(objective, args.project_type,
                                 Path(__file__).resolve().parent.parent / 'workspaces')
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Planning failed: {error}")
    print(f"Saved specification: {workspace / 'spec.json'}")


if __name__ == "__main__":
    main()
