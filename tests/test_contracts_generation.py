import json
from pathlib import Path
import pytest
from suite.contracts import build_contract, contract_type, profile, ROOT
from suite.generator import generate_project, validate_file
from suite.planner import validate_spec

REFERENCE = ROOT.parent / 'workspaces' / 'project-20261113-131615-917f271f'


@pytest.mark.parametrize('kind', ['task_manager', 'expense_tracker'])
def test_explicit_profiles(kind):
    contract = build_contract({'project_type': kind, 'name': 'Example', 'acceptance_criteria': ['Persistent records']})
    assert contract_type(contract) == kind
    assert ('expense' in contract) == (kind == 'expense_tracker')
    assert ('task' in contract) == (kind == 'task_manager')


def test_reject_unsupported_and_modified_contract():
    with pytest.raises(ValueError, match='Unsupported'):
        build_contract({'project_type': 'banking'})
    contract = profile('expense_tracker')
    contract['routes'] = []
    with pytest.raises(ValueError, match='routes'):
        contract_type(contract)
    with pytest.raises(ValueError, match='Unsupported'):
        build_contract({'name': 'Do not silently assume tasks'})


def test_original_contract_compatibility():
    assert contract_type(json.loads((REFERENCE / 'contract.json').read_text())) == 'task_manager'


def test_plan_dependency_validation():
    spec = {'project_type': 'expense_tracker', 'name': 'Ledger', 'summary': 'Local ledger',
            'requirements': ['Add'], 'acceptance_criteria': ['Store'],
            'tasks': [{'id': '1', 'title': 'Build', 'description': 'Implement', 'depends_on': ['future']}]}
    with pytest.raises(ValueError, match='earlier task'):
        validate_spec(spec)


@pytest.mark.parametrize('raw', ['{}', '{"path":"../../escape","content":"bad"}',
                                 '{"path":"app.py","content":"def broken("}'])
def test_generation_rejects_invalid_responses(raw):
    with pytest.raises((ValueError, SyntaxError)):
        validate_file(raw, 'app.py')


def test_generator_owns_acceptance_and_resumes_without_overwrite(tmp_path):
    contract = profile('task_manager')
    (tmp_path / 'spec.json').write_text('{}')
    (tmp_path / 'contract.json').write_text(json.dumps(contract))
    calls = []
    class Client:
        def chat(self, prompt, **kwargs):
            path = json.loads(prompt)['requested_file']; calls.append(path)
            return json.dumps({'path': path, 'content': (REFERENCE / 'app' / path).read_text()})
    generate_project(tmp_path, Client())
    assert calls == ['app.py', 'templates/index.html', 'static/style.css', 'static/app.js']
    assert (tmp_path / 'app/tests/test_backend.py').read_bytes() == (ROOT / 'acceptance/task_manager/test_backend.py').read_bytes()
    generate_project(tmp_path, Client())
    assert len(calls) == 4


def test_generator_refuses_symlink_parent(tmp_path):
    (tmp_path / 'spec.json').write_text('{}')
    (tmp_path / 'contract.json').write_text(json.dumps(profile('task_manager')))
    (tmp_path / 'app').symlink_to(REFERENCE / 'app', target_is_directory=True)
    with pytest.raises(SystemExit, match='symlink'):
        generate_project(tmp_path)


def test_scope_cannot_silently_change_supported_currency():
    contract = profile('expense_tracker')
    contract['scope']['currency'] = 'USD'
    with pytest.raises(ValueError, match='scope'):
        contract_type(contract)


def test_non_object_contract_rejected():
    with pytest.raises(ValueError, match='JSON object'):
        contract_type([])
