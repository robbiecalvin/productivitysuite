"""Shared CLI and desktop orchestration; planning and generation are never verification."""
import argparse
import json
from pathlib import Path

from suite.contracts import SUPPORTED_TYPES, build_contract, contract_type
from suite.controller import run_controller
from suite.generator import generate_project
from suite.planner import plan_project

ROOT = Path(__file__).resolve().parent.parent


def generate(workspace, client=None):
    workspace = Path(workspace).resolve()
    contract_path = workspace / 'contract.json'
    if not contract_path.exists():
        spec = json.loads((workspace / 'spec.json').read_text())
        with contract_path.open('x') as output:
            json.dump(build_contract(spec), output, indent=2)
            output.write('\n')
    contract_type(json.loads(contract_path.read_text()))
    return generate_project(workspace, client=client)


def build_project(objective, project_type, root, max_repairs=3, client=None,
                  verify_fn=None, repair_fn=None):
    workspace = plan_project(objective, project_type, root, client)
    print(f'PROJECT_WORKSPACE={workspace}', flush=True)
    generate(workspace, client)
    return workspace, run_controller(workspace, max_repairs, verify_fn, repair_fn)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('plan', 'generate', 'build'))
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--objective')
    parser.add_argument('--project-type', choices=SUPPORTED_TYPES)
    parser.add_argument('--max-repairs', type=int, choices=range(4), default=3)
    args = parser.parse_args()
    if args.operation != 'generate' and (not args.objective or not args.project_type):
        parser.error('Planning/building requires --objective and --project-type.')
    try:
        if args.operation == 'build':
            _, report = build_project(args.objective, args.project_type, ROOT / 'workspaces', args.max_repairs)
            raise SystemExit(0 if report['passed'] else 1)
        if args.operation == 'plan':
            workspace = plan_project(args.objective, args.project_type, ROOT / 'workspaces')
            # Create a supported contract alongside the plan; generation can resume later.
            spec = json.loads((workspace / 'spec.json').read_text())
            (workspace / 'contract.json').write_text(json.dumps(build_contract(spec), indent=2) + '\n')
            print(f'PROJECT_WORKSPACE={workspace}', flush=True)
            print('Plan and contract saved. Application is not generated or verified.')
        else:
            if args.workspace is None:
                parser.error('Generation requires --workspace.')
            generate(args.workspace)
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f'Workflow stopped: {error}')


if __name__ == '__main__':
    main()
