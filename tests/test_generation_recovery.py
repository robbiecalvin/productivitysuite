import json

import pytest
from suite import workflow
from suite.contracts import ROOT, profile
from suite.generator import generate_project

REFERENCE = ROOT.parent / 'workspaces/project-20261113-131615-917f271f/app'


def test_invalid_spec_does_not_leave_empty_contract(tmp_path):
    (tmp_path / 'spec.json').write_text(json.dumps({'project_type': 'unsupported'}))
    with pytest.raises(ValueError, match='Unsupported'):
        workflow.generate(tmp_path)
    assert not (tmp_path / 'contract.json').exists()
    (tmp_path / 'spec.json').write_text(json.dumps({
        'project_type': 'task_manager', 'name': 'Recovered project', 'acceptance_criteria': ['Create tasks']}))
    class Client:
        def chat(self, prompt, **kwargs):
            name = json.loads(prompt)['requested_file']
            return json.dumps({'path': name, 'content': (REFERENCE / name).read_text()})
    workflow.generate(tmp_path, Client())
    assert json.loads((tmp_path / 'contract.json').read_text())['project_type'] == 'task_manager'
    assert (tmp_path / 'app/app.py').is_file()


def test_atomic_write_failure_leaves_no_partial_target(tmp_path, monkeypatch):
    from suite import files
    def fail(descriptor):
        raise OSError('disk write failed')
    monkeypatch.setattr(files.os, 'fsync', fail)
    with pytest.raises(OSError, match='disk write failed'):
        files.create_file(tmp_path / 'app.py', 'complete source')
    assert list(tmp_path.iterdir()) == []


def test_atomic_create_preserves_existing_file(tmp_path):
    from suite.files import create_file
    path = tmp_path / 'app.py'
    path.write_text('user work')
    with pytest.raises(FileExistsError):
        create_file(path, 'generated replacement')
    assert path.read_text() == 'user work'
    assert list(tmp_path.iterdir()) == [path]


def test_generation_can_resume_after_failed_source_write(tmp_path, monkeypatch):
    from suite import files
    (tmp_path / 'spec.json').write_text('{}')
    (tmp_path / 'contract.json').write_text(json.dumps(profile('task_manager')))
    class Client:
        def chat(self, prompt, **kwargs):
            name = json.loads(prompt)['requested_file']
            return json.dumps({'path': name, 'content': (REFERENCE / name).read_text()})
    sync = files.os.fsync
    def fail(descriptor):
        raise OSError('interrupted write')
    monkeypatch.setattr(files.os, 'fsync', fail)
    with pytest.raises(SystemExit, match='interrupted write'):
        generate_project(tmp_path, Client())
    assert not (tmp_path / 'app/app.py').exists()
    assert list((tmp_path / 'app').iterdir()) == []
    monkeypatch.setattr(files.os, 'fsync', sync)
    generate_project(tmp_path, Client())
    assert (tmp_path / 'app/app.py').read_bytes() == (REFERENCE / 'app.py').read_bytes()
    assert (tmp_path / 'app/tests/test_backend.py').is_file()
