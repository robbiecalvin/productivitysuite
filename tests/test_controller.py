import json
import pytest
from suite.contracts import profile
from suite.controller import run_controller


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / 'app/tests').mkdir(parents=True)
    (tmp_path / 'app/app.py').write_text('original')
    (tmp_path / 'app/tests/test_backend.py').write_text('independent original')
    (tmp_path / 'contract.json').write_text(json.dumps(profile('task_manager')))
    (tmp_path / 'spec.json').write_text('{}')
    return tmp_path


def result(passed=False, code=1, build=0):
    return {'passed': passed, 'build_exit_code': build, 'test_exit_code': code,
            'counts': {'failed': 0 if passed else 1}}


@pytest.mark.parametrize('failure,status', [
    ({'build_exit_code': 1}, 'build_failed'),
    ({'build_exit_code': 0, 'test_exit_code': 2}, 'test_infrastructure_failed'),
    ({'build_exit_code': 0, 'test_exit_code': 124}, 'test_infrastructure_failed'),
    ({'build_exit_code': 0, 'test_exit_code': 5}, 'test_infrastructure_failed')])
def test_infrastructure_never_triggers_repair(workspace, failure, status):
    def forbidden(path):
        pytest.fail('Must not repair infrastructure failure')
    report = run_controller(workspace, verify_fn=lambda *args: failure, repair_fn=forbidden)
    assert report['status'] == status and report['repairs_attempted'] == 0


def test_bound_and_checkpoints(workspace):
    def repair(path):
        with (path / 'app/app.py').open('a') as out:
            out.write('repaired')
        return 0
    report = run_controller(workspace, 2, verify_fn=lambda *args: result(), repair_fn=repair)
    assert report['status'] == 'repair_limit_reached' and report['repairs_attempted'] == 2
    assert len(list((workspace / 'runs').glob('*/check-*/app.py'))) == 3
    assert (next((workspace / 'runs').glob('*/check-0/app.py'))).read_text() == 'original'


@pytest.mark.parametrize('code,status', [(0, 'repair_made_no_change'), (1, 'repair_rejected')])
def test_rejected_or_noop_repair(workspace, code, status):
    report = run_controller(workspace, verify_fn=lambda *args: result(), repair_fn=lambda path: code)
    assert report['status'] == status


def test_detects_protected_test_mutation(workspace):
    def repair(path):
        (path / 'app/tests/test_backend.py').write_text('weakened')
        return 0
    report = run_controller(workspace, verify_fn=lambda *args: result(), repair_fn=repair)
    assert report['status'] == 'controller_error'
    assert 'Protected file changed' in report['error']


def test_browser_failure_never_requests_backend_repair(workspace):
    calls = []
    def verify(path, mode):
        calls.append(mode)
        return result(passed=(mode == 'backend'))
    report = run_controller(workspace, verify_fn=verify, repair_fn=lambda path: pytest.fail('Frontend is protected'))
    assert calls == ['backend', 'browser']
    assert not report['passed'] and report['status'] == 'browser_or_infrastructure_failure'


def test_success_after_one_repair(workspace):
    def verify(path, mode):
        return result(passed=(path / 'app/app.py').read_text() == 'fixed')
    def repair(path):
        (path / 'app/app.py').write_text('fixed'); return 0
    report = run_controller(workspace, verify_fn=verify, repair_fn=repair)
    assert report['passed'] and report['repairs_attempted'] == 1
    assert len(report['checks']) == 3


def test_interrupt_saves_report(workspace):
    def interrupted(*args):
        raise KeyboardInterrupt
    report = run_controller(workspace, verify_fn=interrupted)
    assert report['status'] == 'interrupted'
    assert json.loads(next((workspace / 'runs').glob('*/report.json')).read_text())['status'] == 'interrupted'
