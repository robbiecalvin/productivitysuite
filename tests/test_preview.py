import subprocess
from types import SimpleNamespace

import pytest
from suite import preview


def test_cleanup_reports_failure_and_attempts_both_resources(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1, stderr='daemon unavailable', stdout='')
    monkeypatch.setattr(preview.subprocess, 'run', run)
    errors = preview.cleanup_resources('docker', 'container', 'image')
    assert errors == ['daemon unavailable', 'daemon unavailable']
    assert calls == [['docker', 'rm', '-f', 'container'], ['docker', 'image', 'rm', 'image']]


def test_cleanup_is_repeatable_for_absent_resources(monkeypatch):
    def run(command, **kwargs):
        missing = 'No such container' if command[1] == 'rm' else 'No such image'
        return SimpleNamespace(returncode=1, stderr=missing, stdout='')
    monkeypatch.setattr(preview.subprocess, 'run', run)
    assert preview.cleanup_resources('docker', 'container', 'image') == []


def test_cleanup_timeout_still_attempts_image_removal(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if command[1] == 'rm':
            raise subprocess.TimeoutExpired(command, 20)
        return SimpleNamespace(returncode=0, stderr='', stdout='')
    monkeypatch.setattr(preview.subprocess, 'run', run)
    assert len(preview.cleanup_resources('docker', 'container', 'image')) == 1
    assert len(calls) == 2


@pytest.mark.parametrize('address', ['', '0.0.0.0:8000', '127.0.0.1:0', '127.0.0.1:70000',
                                     '127.0.0.1:no', '127.0.0.1:8000\n127.0.0.1:9000'])
def test_invalid_published_address(address):
    with pytest.raises(RuntimeError, match='loopback'):
        preview.preview_address(address)


def test_valid_loopback_address():
    assert preview.preview_address('127.0.0.1:8000\n') == 'http://127.0.0.1:8000'


def test_cleanup_failure_prevents_success_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['preview', str(tmp_path)])
    monkeypatch.setattr(preview, 'find_docker', lambda: 'docker')
    def interrupted(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(preview, 'build_image', interrupted)
    monkeypatch.setattr(preview, 'docker_output', lambda *args: '')
    monkeypatch.setattr(preview, 'cleanup_resources', lambda *args: ['container removal failed'])
    with pytest.raises(SystemExit) as stopped:
        preview.main()
    assert stopped.value.code == 1
    output = capsys.readouterr().out
    assert 'cleanup incomplete' in output
    assert 'cleanup finished' not in output
