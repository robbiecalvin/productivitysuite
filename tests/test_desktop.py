import os
import queue
from pathlib import Path
import pytest
from suite.desktop import Desktop, operation_command


def test_plan_requires_no_existing_project():
    command = operation_command('plan', objective='A ledger', project_type='expense_tracker')
    assert '--workspace' not in command and '--project-type' in command
    assert '-2' not in command


@pytest.mark.parametrize('operation', ['generate', 'verify', 'repair', 'preview'])
def test_existing_project_commands(operation, tmp_path):
    command = operation_command(operation, tmp_path, repairs=2)
    assert str(tmp_path) in command
    assert '-1' not in command


@pytest.mark.desktop
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Tk display required')
def test_render_and_completion_states():
    import tkinter as tk
    root = tk.Tk(); desktop = Desktop(root); root.update()
    assert root.winfo_width() >= 820
    for operation, expected in [('plan', 'not generated'), ('generate', 'have not run'),
                                ('verify', 'Verified:'), ('preview', 'No verification')]:
        desktop.busy = True
        desktop.events.put(('done', (operation, 0)))
        desktop.poll()
        assert expected in desktop.status.get()
        assert not desktop.busy
    root.destroy()


@pytest.mark.desktop
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Tk display required')
def test_start_plan_with_empty_selection_and_preview_stop(monkeypatch):
    import tkinter as tk
    from threading import Event
    root = tk.Tk(); desktop = Desktop(root)
    desktop.workspace.set('')
    commands = []
    finished = Event()
    def worker(operation, command):
        commands.append((operation, command)); finished.set()
    monkeypatch.setattr(desktop, 'worker', worker)
    desktop.start('plan', 'A local task manager')
    assert finished.wait(2)
    assert commands[0][0] == 'plan' and desktop.busy
    assert '--workspace' not in commands[0][1]
    desktop.events.put(('done', ('plan', 0))); desktop.poll()
    desktop.operation = 'preview'; desktop.busy = True
    signals = []
    class Process:
        def poll(self): return None
        def send_signal(self, value): signals.append(value)
    desktop.process = Process()
    desktop.close()
    assert desktop.close_pending and desktop.stop_requested.is_set() and signals
    desktop.events.put(('done', ('preview', 0))); desktop.poll()
