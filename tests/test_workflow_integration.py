"""Opt-in real Docker workflow with deterministic Ollama HTTP responses.

The fixture tests orchestration and failure handling, not real model quality.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest
import requests
from suite.contracts import ROOT
from suite.llm import OllamaClient
from suite.workflow import build_project

pytestmark = [pytest.mark.docker, pytest.mark.skipif(os.environ.get('SUITE_DOCKER_TESTS') != '1',
              reason='Set SUITE_DOCKER_TESTS=1 to run isolated Docker integration')]


@pytest.mark.parametrize('kind,reference', [
    ('task_manager', 'project-20261113-131615-917f271f'),
    ('expense_tracker', 'project-20261113-154909-f2945762')])
def test_plan_generate_repair_verify_and_preview(tmp_path, monkeypatch, model_server, kind, reference):
    reference_app = ROOT.parent / 'workspaces' / reference / 'app'
    correct = (reference_app / 'app.py').read_text()
    if kind == 'task_manager':
        broken = correct.replace("title = data['title'].strip()", "title = data['title']")
    else:
        broken = correct.replace('type(amount) is not int', 'not isinstance(amount, int)')
    assert broken != correct
    spec = {'project_type': kind, 'name': 'Simulated build', 'summary': 'Local supported application',
            'requirements': ['Persistent local records'], 'acceptance_criteria': ['Records survive reload'],
            'tasks': [{'id': 'build', 'title': 'Build', 'description': 'Implement the agreed contract', 'depends_on': []}]}
    def respond(body):
        prompt = body['messages'][1]['content']
        if body['messages'][0]['content'].startswith('\nYou are a software project planner'):
            content = spec
        else:
            payload = json.loads(prompt)
            if 'requested_file' in payload:
                name = payload['requested_file']
                content = {'path': name, 'content': broken if name == 'app.py' else (reference_app / name).read_text()}
            else:
                assert 'current_backend' in payload
                assert 'observed_failures' in payload
                assert payload['contract'].get('project_type') == kind
                content = {'path': 'app.py', 'content': correct}
        return 200, {'message': {'content': json.dumps(content)}}
    acceptance_dir = ROOT / 'acceptance' / kind
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in acceptance_dir.glob('test_*.py')}
    with model_server(respond) as (url, calls):
        monkeypatch.setenv('OLLAMA_BASE_URL', url)
        workspace, report = build_project('Build a local supported application', kind, tmp_path,
                                          max_repairs=1, client=OllamaClient())
    assert report['passed'] and report['repairs_attempted'] == 1
    assert len(calls) == 6  # plan, four implementation files, one backend repair
    assert report['checks'][0]['result']['counts']['failed'] > 0
    assert report['checks'][-1]['result']['counts']['browser'] > 0
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in acceptance_dir.glob('test_*.py')}
    assert (next((workspace / 'runs').glob('*/check-0/app.py'))).read_text() == broken
    assert (workspace / 'app/app.py').read_text() == correct
    for name in before:
        assert (workspace / 'app/tests' / name).read_bytes() == (acceptance_dir / name).read_bytes()
    assert len(list((workspace / 'repairs').glob('*/changes.diff'))) == 1

    log_path = tmp_path / 'preview-output.log'
    with log_path.open('w') as log:
        process = subprocess.Popen([sys.executable, '-u', '-m', 'suite.preview', str(workspace)],
                                   cwd=ROOT.parent, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            url = None
            while time.monotonic() < deadline:
                text = log_path.read_text()
                if process.poll() is not None:
                    pytest.fail(f'Preview exited before readiness: {text}')
                matches = [line.split('=', 1)[1] for line in text.splitlines() if line.startswith('PREVIEW_URL=')]
                if matches:
                    url = matches[-1]; break
                time.sleep(.2)
            assert url, log_path.read_text()
            session = requests.Session(); session.trust_env = False
            assert session.get(url, timeout=5).status_code == 200
            endpoint = '/api/tasks' if kind == 'task_manager' else '/api/expenses'
            payload = {'title': 'Preview smoke'} if kind == 'task_manager' else {
                'date': '2024-02-29', 'category': 'Preview', 'amount_cents': 10}
            assert session.post(url + endpoint, json=payload, timeout=5).status_code == 201
            key = 'tasks' if kind == 'task_manager' else 'expenses'
            assert len(session.get(url + endpoint, timeout=5).json()[key]) == 1
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                process.wait(timeout=45)
    assert process.returncode == 0, log_path.read_text()
    assert 'Preview cleanup finished.' in log_path.read_text()


def test_python_311_collection_rejects_new_fstring_syntax(tmp_path):
    import shutil
    from suite.runner import verify
    reference = ROOT.parent / 'workspaces/project-20261113-131615-917f271f'
    shutil.copyfile(reference / 'contract.json', tmp_path / 'contract.json')
    shutil.copytree(reference / 'app', tmp_path / 'app')
    with (tmp_path / 'app/app.py').open('a') as output:
        output.write('\nvalue = f"{dict(key=1)["key"]}"\n')
    result = verify(tmp_path, 'backend')
    assert not result['passed'] and result['test_exit_code'] == 2
    assert result['counts']['errors'] > 0
    assert 'SyntaxError' in (tmp_path / 'backend-test.log').read_text()
