"""Run suite-owned acceptance tests against generated code inside Docker."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from suite.contracts import ROOT, contract_type

SOURCES = ('app.py', 'templates/index.html', 'static/app.js', 'static/style.css')


def find_docker():
    for candidate in (shutil.which('docker'), str(Path.home() / '.docker/bin/docker'),
                      '/Applications/Docker.app/Contents/Resources/bin/docker'):
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError('Docker executable not found. Start Docker Desktop or the managed Docker daemon.')


def run_logged(command, log_path, timeout):
    with log_path.open('w', encoding='utf-8') as output:
        try:
            return subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                  timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            output.write(f'\nCommand exceeded {timeout} seconds.\n')
            return 124


def regular_file(root, relative):
    path = root / relative
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
        raise ValueError(f'Missing regular file or unsupported symlink: {path}')
    return path


def build_image(docker, workspace, image, mode, log):
    """Stage only allowed source and trusted tests; never execute generated recipes."""
    if mode not in ('backend', 'browser'):
        raise ValueError('Unsupported runtime mode.')
    contract = json.loads(regular_file(workspace, 'contract.json').read_text())
    kind = contract_type(contract)
    with tempfile.TemporaryDirectory(prefix='suite-build-') as directory:
        context = Path(directory)
        for relative in SOURCES:
            source = regular_file(workspace / 'app', relative)
            target = context / 'source' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        checks = ROOT / 'acceptance' / kind
        for relative in ('test_backend.py', 'test_browser.py'):
            target = context / 'checks' / relative
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(checks / relative, target)
        shutil.copyfile(ROOT / 'runtime' / 'conftest.py', context / 'checks' / 'conftest.py')
        for lock in ('backend.lock', 'browser.lock'):
            shutil.copyfile(ROOT / 'runtime' / lock, context / lock)
        recipe = (ROOT / 'runtime' / 'Dockerfile').read_text()
        recipe += f'\nFROM {mode} AS application\nCOPY --chmod=0755 source/ /app/\nCOPY --chmod=0755 checks/ /checks/\n'
        (context / 'Dockerfile').write_text(recipe)
        command = [docker, 'build', '-t', image]
        # Use the combined trust bundle when supplied by a managed cloud runtime.
        bundle = os.environ.get('SUITE_CA_BUNDLE') or os.environ.get('SSL_CERT_FILE')
        if not bundle and os.environ.get('CODEX_PROXY_CERT'):
            bundle = '/etc/ssl/certs/ca-certificates.crt'
        if bundle:
            if not Path(bundle).is_file():
                raise ValueError(f'CA bundle is not a file: {bundle}')
            command += ['--secret', f'id=proxy_ca,src={bundle}']
        command.append(str(context))
        return run_logged(command, log, timeout=900)


def container_options():
    return ['--init', '--read-only', '--tmpfs', '/tmp:rw,nosuid,size=512m',
            '--shm-size', '512m', '--cap-drop', 'ALL', '--security-opt',
            'no-new-privileges', '--memory', '2g', '--cpus', '2', '--pids-limit', '256']


def outcomes(path):
    cases = ET.parse(path).getroot().findall('.//testcase')
    counts = dict(total=len(cases), passed=0, failed=0, errors=0, skipped=0, backend=0, browser=0)
    for case in cases:
        status = next((key for key, tag in [('failed', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]
                       if case.find(tag) is not None), 'passed')
        counts[status] += 1
        for target in ('backend', 'browser'):
            if 'test_' + target in case.get('classname', ''):
                counts[target] += 1
    return counts


def verify(workspace, mode='browser'):
    workspace = Path(workspace).resolve()
    docker = find_docker()
    identifier = uuid.uuid4().hex[:12]
    image = f'productivity-suite-test:{identifier}'
    container = f'productivity-suite-test-{identifier}'
    report_path = workspace / f'{mode}-report.json'
    result_path = workspace / f'{mode}-results.xml'
    log = workspace / f'{mode}-test.log'
    report = {'run_id': identifier, 'mode': mode, 'stage': 'build', 'passed': False,
              'acceptance_source': 'suite-owned', 'project_type': None}
    # Clear stale artifacts before invoking any build or process.
    for path in (report_path, result_path, log, workspace / f'{mode}-build.log'):
        if path.is_symlink():
            raise ValueError(f'Refusing symlink output: {path}')
        path.unlink(missing_ok=True)
    output_dir = tempfile.TemporaryDirectory(prefix='suite-results-')
    Path(output_dir.name).chmod(0o777)
    try:
        report['project_type'] = contract_type(json.loads(regular_file(workspace, 'contract.json').read_text()))
        report['acceptance_hashes'] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / 'acceptance' / report['project_type']).glob('test_*.py')}
        print('Building trusted test environment...', flush=True)
        report['build_exit_code'] = build_image(docker, workspace, image, mode, workspace / f'{mode}-build.log')
        if report['build_exit_code'] == 0:
            report['stage'] = 'test'
            target = '/checks' if mode == 'browser' else '/checks/test_backend.py'
            command = [docker, 'run', '--name', container, '--network', 'none', *container_options(),
                       '--mount', f'type=bind,src={output_dir.name},dst=/results', image,
                       'python', '-m', 'pytest', target, '-v', '--tb=short', '-p', 'no:cacheprovider',
                       '--junitxml=/results/results.xml']
            if mode == 'browser':
                command.append('--output=/tmp/test-results')
            report['test_exit_code'] = run_logged(command, log, timeout=180)
            current_result = Path(output_dir.name) / 'results.xml'
            if current_result.is_file() and not current_result.is_symlink():
                shutil.copyfile(current_result, result_path)
                report['counts'] = outcomes(result_path)
                counts = report['counts']
                report['passed'] = (report['test_exit_code'] == 0 and counts['passed'] > 0
                                    and counts['passed'] == counts['total'] and counts['backend'] > 0
                                    and (mode != 'browser' or counts['browser'] > 0))
            else:
                report['error'] = 'Current test run did not produce JUnit results.'
    except KeyboardInterrupt:
        report['error'] = 'Interrupted by user.'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, ET.ParseError) as error:
        report['error'] = str(error)
    finally:
        for command in ([docker, 'rm', '-f', container], [docker, 'image', 'rm', image]):
            try:
                subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
        output_dir.cleanup()
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    selected_log = log if report['stage'] == 'test' else workspace / f'{mode}-build.log'
    if selected_log.exists():
        print(selected_log.read_text())
    print(f'Report: {report_path}')
    if report.get('error'):
        print(report['error'])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--mode', choices=('backend', 'browser'), default='backend')
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.mode)
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(str(error))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
