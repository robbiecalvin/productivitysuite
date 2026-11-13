import json
from pathlib import Path
import pytest
from suite import repair
from suite.contracts import profile


@pytest.mark.parametrize('candidate', [
    {'path': '../app.py', 'content': 'def create_app(): pass'},
    {'path': 'app.py', 'content': ''},
    {'path': 'app.py', 'content': 'def broken('},
    {'path': 'app.py', 'content': 'print("missing factory")'}])
def test_rejected_candidate_preserves_application(tmp_path, monkeypatch, model_server, candidate):
    (tmp_path / 'app/tests').mkdir(parents=True)
    original = 'def create_app(test_config=None):\n    return None\n'
    (tmp_path / 'app/app.py').write_text(original)
    (tmp_path / 'app/tests/test_backend.py').write_text('original tests')
    (tmp_path / 'contract.json').write_text(json.dumps(profile('expense_tracker')))
    (tmp_path / 'backend-test.log').write_text('FAILED test_backend.py::test_create - assert 500 == 201')
    with model_server(lambda body: (200, {'message': {'content': json.dumps(candidate)}})) as (url, _):
        monkeypatch.setenv('OLLAMA_BASE_URL', url)
        monkeypatch.setattr('sys.argv', ['repair', str(tmp_path)])
        with pytest.raises(SystemExit, match='Repair stopped'):
            repair.main()
    assert (tmp_path / 'app/app.py').read_text() == original
    assert (tmp_path / 'app/tests/test_backend.py').read_text() == 'original tests'
    assert next((tmp_path / 'repairs').glob('*/app.before.py')).read_text() == original


@pytest.mark.parametrize('stage', ['flush', 'replace'])
def test_failed_repair_write_keeps_original_and_candidate(tmp_path, monkeypatch, stage):
    from suite import files
    (tmp_path / 'app/tests').mkdir(parents=True)
    original = 'def create_app(test_config=None):\n    return None\n'
    candidate = 'def create_app(test_config=None):\n    return "candidate"\n'
    app = tmp_path / 'app/app.py'
    app.write_text(original)
    (tmp_path / 'app/tests/test_backend.py').write_text('original tests')
    (tmp_path / 'contract.json').write_text(json.dumps(profile('expense_tracker')))
    (tmp_path / 'backend-test.log').write_text('FAILED test_backend.py::test_create')
    monkeypatch.setattr(repair.OllamaClient, 'chat', lambda *args, **kwargs:
                        json.dumps({'path': 'app.py', 'content': candidate}))
    def fail(*args):
        raise OSError('simulated storage failure')
    monkeypatch.setattr(files.os, 'fsync' if stage == 'flush' else 'replace', fail)
    monkeypatch.setattr('sys.argv', ['repair', str(tmp_path)])
    with pytest.raises(SystemExit, match='simulated storage failure'):
        repair.main()
    assert app.read_text() == original
    assert next((tmp_path / 'repairs').glob('*/app.before.py')).read_text() == original
    assert next((tmp_path / 'repairs').glob('*/app.after.py')).read_text() == candidate
    assert list((tmp_path / 'app').glob('.app.py-*')) == []


def test_replacement_preserves_permissions(tmp_path):
    from suite.files import replace_file
    app = tmp_path / 'app.py'
    app.write_text('original'); app.chmod(0o640)
    replace_file(app, 'candidate', expected='original')
    assert app.read_text() == 'candidate'
    assert app.stat().st_mode & 0o777 == 0o640


def test_replacement_detects_edit_while_candidate_is_staged(tmp_path, monkeypatch):
    from suite import files
    app = tmp_path / 'app.py'
    app.write_text('original')
    sync = files.os.fsync
    def concurrent_edit(descriptor):
        app.write_text('user edit')
        sync(descriptor)
    monkeypatch.setattr(files.os, 'fsync', concurrent_edit)
    with pytest.raises(RuntimeError, match='changed before replacement'):
        files.replace_file(app, 'candidate', expected='original')
    assert app.read_text() == 'user edit'
    assert list(tmp_path.iterdir()) == [app]
