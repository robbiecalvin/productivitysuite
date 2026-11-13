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
