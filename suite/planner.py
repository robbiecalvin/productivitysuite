import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from suite.llm import OllamaClient


SYSTEM = """
You are a software project planner.

Return only one valid JSON object with these fields:
{
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
- Keep scope realistic for a first working prototype.
"""


def validate_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("The specification must be a JSON object.")

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


def main():
    objective = input("What do you want to build?\n> ").strip()
    if not objective:
        raise SystemExit("Enter an objective before generating a plan.")

    client = OllamaClient()
    print("\nCreating project specification...")

    try:
        response = client.chat(
            prompt=f"Create a project specification for:\n{objective}",
            system=SYSTEM,
            json_mode=True,
        )
        debug_dir = Path(__file__).resolve().parent.parent / "workspaces"
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / "last_planner_response.txt"
        debug_path.write_text(response, encoding="utf-8")
        spec = validate_spec(json.loads(response))
    except (RuntimeError, ValueError) as error:
        raise SystemExit(f"Planning failed: {error}")

    root = Path(__file__).resolve().parent.parent
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    project_id = f"project-{timestamp}-{uuid.uuid4().hex[:8]}"
    workspace = root / "workspaces" / project_id
    workspace.mkdir(parents=True, exist_ok=False)

    spec["objective"] = objective

    spec_path = workspace / "spec.json"
    spec_path.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nProject: {spec['name']}")
    print(spec["summary"])

    print("\nAcceptance criteria:")
    for criterion in spec["acceptance_criteria"]:
        print(f"- {criterion}")

    print("\nTasks:")
    for task in spec["tasks"]:
        print(f"- {task['id']}: {task['title']}")

    print(f"\nSaved specification: {spec_path}")


if __name__ == "__main__":
    main()
