import json
from pathlib import Path
import pytest
from suite import runner
from suite.contracts import ROOT

REFERENCE = ROOT.parent / 'workspaces/project-20261113-131615-917f271f'


def test_build_excludes_generated_recipes_dependencies_and_tests(monkeypatch, tmp_path):
    def capture(command, log, timeout):
        context = Path(command[-1])
        recipe = (context / 'Dockerfile').read_text()
        assert 'requirements.txt' not in recipe
        assert (context / 'checks/test_backend.py').read_bytes() == (ROOT / 'acceptance/task_manager/test_backend.py').read_bytes()
        assert not (context / 'source/tests').exists()
        assert not (context / 'source/requirements.txt').exists()
        assert 'COPY --chmod=0755' in recipe
        return 0
    monkeypatch.setattr(runner, 'run_logged', capture)
    assert runner.build_image('docker', REFERENCE, 'example', 'backend', tmp_path / 'build.log') == 0


def test_outcomes_distinguish_skips_errors_and_zero(tmp_path):
    xml = tmp_path / 'results.xml'
    xml.write_text('<testsuites><testsuite><testcase classname="test_backend"/><testcase classname="test_browser"><skipped/></testcase><testcase><error/></testcase><testcase><failure/></testcase></testsuite></testsuites>')
    assert runner.outcomes(xml) == {'total': 4, 'passed': 1, 'skipped': 1, 'errors': 1, 'failed': 1, 'backend': 1, 'browser': 1}
    xml.write_text('<testsuites/>')
    assert runner.outcomes(xml)['passed'] == 0


def test_stale_report_cannot_pass_build_failure(monkeypatch, tmp_path):
    (tmp_path / 'contract.json').write_bytes((REFERENCE / 'contract.json').read_bytes())
    (tmp_path / 'backend-report.json').write_text('{"passed":true}')
    (tmp_path / 'backend-results.xml').write_text('<stale/>')
    monkeypatch.setattr(runner, 'find_docker', lambda: 'docker')
    monkeypatch.setattr(runner, 'build_image', lambda *args: 1)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *args, **kwargs: None)
    report = runner.verify(tmp_path, 'backend')
    assert not report['passed'] and report['build_exit_code'] == 1
    assert not (tmp_path / 'backend-results.xml').exists()


def test_unknown_runtime_mode_never_enters_build(tmp_path):
    with pytest.raises(ValueError, match='runtime mode'):
        runner.build_image('docker', REFERENCE, 'example', 'untrusted', tmp_path / 'log')
