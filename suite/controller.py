"""Bounded backend repair, with immutable inputs and per-attempt evidence."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from suite.contracts import ROOT, contract_type
from suite.runner import regular_file, verify


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(module, arguments):
    return subprocess.run([sys.executable, '-m', module, *arguments], check=False).returncode


def run_controller(workspace, max_repairs=3, verify_fn=None, repair_fn=None):
    if type(max_repairs) is not int or not 0 <= max_repairs <= 3:
        raise ValueError('--max-repairs must be between 0 and 3.')
    verify_fn = verify_fn or verify
    repair_fn = repair_fn or (lambda path: invoke('suite.repair', [str(path)]))
    workspace = Path(workspace).resolve()
    app_path = regular_file(workspace, 'app/app.py')
    kind = contract_type(json.loads(regular_file(workspace, 'contract.json').read_text()))
    regular_file(workspace, 'spec.json')
    # Every existing input except the single repair target is immutable.
    protected = [workspace / 'spec.json', workspace / 'contract.json']
    protected += [p for p in (workspace / 'app').rglob('*') if p.is_file() and p != app_path]
    protected += list((ROOT / 'acceptance' / kind).glob('test_*.py'))
    for path in protected:
        regular_file(path.parent, path.name)
    original_hashes = {path: fingerprint(path) for path in protected}
    original_files = {p.relative_to(workspace / 'app') for p in (workspace / 'app').rglob('*') if p.is_file()}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_dir = workspace / 'runs' / f'{stamp}-{uuid.uuid4().hex[:8]}'
    run_dir.mkdir(parents=True)
    report = {'workspace': str(workspace), 'scope': 'suite-owned acceptance; app.py repairs only',
              'passed': False, 'repairs_attempted': 0, 'checks': [], 'status': 'running'}
    (run_dir / 'protected-hashes.json').write_text(json.dumps({str(p): h for p, h in original_hashes.items()}, indent=2))

    def check_protected_files():
        regular_file(workspace, 'app/app.py')
        current = {p.relative_to(workspace / 'app') for p in (workspace / 'app').rglob('*') if p.is_file()}
        if current != original_files:
            raise RuntimeError('Application file membership changed during verification or repair.')
        for path, expected in original_hashes.items():
            regular_file(path.parent, path.name)
            if fingerprint(path) != expected:
                raise RuntimeError(f'Protected file changed: {path}')

    def check(mode, checkpoint):
        tested_source = fingerprint(app_path)
        result = verify_fn(workspace, mode)
        check_protected_files()
        if fingerprint(app_path) != tested_source:
            raise RuntimeError('app.py changed during verification; current source is unverified.')
        (checkpoint / f'{mode}-report.json').write_text(json.dumps(result, indent=2) + '\n')
        for name in (f'{mode}-build.log', f'{mode}-test.log', f'{mode}-results.xml'):
            source = workspace / name
            if source.is_file():
                shutil.copyfile(source, checkpoint / name)
        report['checks'].append({'mode': mode, 'result': result, 'checkpoint': str(checkpoint)})
        return result

    try:
        for attempt in range(max_repairs + 1):
            check_protected_files()
            checkpoint = run_dir / f'check-{attempt}'
            checkpoint.mkdir()
            shutil.copyfile(app_path, checkpoint / 'app.py')
            print(f'Verification {attempt + 1}: backend acceptance', flush=True)
            result = check('backend', checkpoint)
            if result.get('passed'):
                print('Backend passed; running backend and browser acceptance.', flush=True)
                result = check('browser', checkpoint)
                report['passed'] = result.get('passed') is True
                report['status'] = 'passed' if report['passed'] else 'browser_or_infrastructure_failure'
                break
            if result.get('build_exit_code') != 0:
                report['status'] = 'build_failed'
                break
            # Collection errors, timeouts, zero tests and runner errors are not repair evidence.
            if (result.get('test_exit_code') != 1 or result.get('error')
                    or not result.get('counts', {}).get('failed')):
                report['status'] = 'test_infrastructure_failed'
                break
            if attempt == max_repairs:
                report['status'] = 'repair_limit_reached'
                break
            before = fingerprint(app_path)
            report['repairs_attempted'] += 1
            code = repair_fn(workspace)
            check_protected_files()
            if code != 0:
                report['status'] = 'repair_rejected'
                break
            if fingerprint(app_path) == before:
                report['status'] = 'repair_made_no_change'
                break
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(status='controller_error', error=str(error))
    finally:
        (run_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f"Result: {report['status']}\nRepairs attempted: {report['repairs_attempted']}\nReport: {run_dir / 'report.json'}")
    if report.get('error'):
        print(report['error'])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--max-repairs', type=int, default=3)
    args = parser.parse_args()
    try:
        result = run_controller(args.workspace, args.max_repairs)
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
