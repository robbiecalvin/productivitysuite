"""Desktop workflow with explicit operations and main-thread-only UI updates."""
import os
import queue
import signal
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from suite.contracts import SUPPORTED_TYPES
from suite.app_icon import apply_app_icon

ROOT = Path(__file__).resolve().parent.parent
# Preserve shell-selected tools; Finder still gets the usual Docker locations.
os.environ['PATH'] = os.pathsep.join([os.environ.get('PATH', '/usr/bin:/bin'),
    str(Path.home() / '.docker/bin'), '/Applications/Docker.app/Contents/Resources/bin',
    '/usr/local/bin', '/opt/homebrew/bin'])


def operation_command(operation, workspace=None, objective=None, project_type=None, repairs=0):
    if operation in ('plan', 'build'):
        if not objective or project_type not in SUPPORTED_TYPES:
            raise ValueError('Enter an objective and choose a supported project type.')
        return [sys.executable, '-u', '-m', 'suite.workflow', operation,
                '--objective', objective, '--project-type', project_type, '--max-repairs', str(repairs)]
    if workspace is None:
        raise ValueError('Choose a project first.')
    if operation == 'generate':
        return [sys.executable, '-u', '-m', 'suite.workflow', 'generate', '--workspace', str(workspace)]
    if operation == 'preview':
        return [sys.executable, '-u', '-m', 'suite.preview', str(workspace)]
    if operation in ('verify', 'repair') and type(repairs) is int and 0 <= repairs <= 3:
        return [sys.executable, '-u', '-m', 'suite.controller', str(workspace), '--max-repairs',
                str(repairs if operation == 'repair' else 0)]
    raise ValueError('Unsupported operation or repair limit.')


class Desktop:
    def __init__(self, window):
        self.window = window
        self.events = queue.Queue()
        self.busy = False
        self.operation = None
        self.process = None
        self.preview_url = None
        self.stop_requested = threading.Event()
        self.close_pending = False
        window.title('Intelligent Productivity Suite')
        apply_app_icon(window)
        window.geometry('1100x760')
        window.minsize(820, 600)
        window.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(window, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Intelligent Productivity Suite', font=('Helvetica', 22, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Plan → generate → independent acceptance → bounded backend repairs → temporary preview').pack(anchor='w', pady=(6, 12))
        self.controls = []
        row = ttk.Frame(frame); row.pack(fill='x')
        self.project_type = tk.StringVar(value='task_manager')
        types = ttk.Combobox(row, textvariable=self.project_type, values=SUPPORTED_TYPES, state='readonly', width=20)
        types.pack(side='left'); self.controls.append((types, 'readonly'))
        self.button(row, 'Plan New Project', lambda: self.new_project('plan'))
        self.button(row, 'Build & Verify New Project', lambda: self.new_project('build'))
        row = ttk.Frame(frame); row.pack(fill='x', pady=10)
        default = ROOT / 'workspaces' / 'project-20261113-131615-917f271f'
        self.workspace = tk.StringVar(value=str(default) if default.exists() else '')
        entry = ttk.Entry(row, textvariable=self.workspace)
        entry.pack(side='left', fill='x', expand=True); self.controls.append((entry, 'normal'))
        self.button(row, 'Choose Project', self.choose)
        row = ttk.Frame(frame); row.pack(fill='x')
        self.button(row, 'Generate Selected', lambda: self.start('generate'))
        self.button(row, 'Run All Tests', lambda: self.start('verify'))
        self.button(row, 'Test & Repair Backend', lambda: self.start('repair'))
        ttk.Label(row, text='Repair limit:').pack(side='left', padx=(12, 0))
        self.repairs = tk.IntVar(value=3)
        limit = ttk.Spinbox(row, from_=0, to=3, textvariable=self.repairs, width=3)
        limit.pack(side='left'); self.controls.append((limit, 'normal'))
        row = ttk.Frame(frame); row.pack(fill='x', pady=10)
        self.button(row, 'Start Preview', lambda: self.start('preview'))
        ttk.Button(row, text='Open Preview', command=self.open_preview).pack(side='left', padx=4)
        ttk.Button(row, text='Stop Preview', command=self.stop_preview).pack(side='left', padx=4)
        self.button(row, 'Open Project', self.open_project)
        self.button(row, 'Open Reports', self.open_reports)
        self.status = tk.StringVar(value='Ready — choose a supported type or an existing project.')
        ttk.Label(frame, textvariable=self.status).pack(anchor='w')
        self.progress = ttk.Progressbar(frame, mode='indeterminate'); self.progress.pack(fill='x', pady=10)
        self.log = ScrolledText(frame, wrap='word', font=('Menlo', 11), state='disabled')
        self.log.pack(fill='both', expand=True)
        ttk.Label(frame, text='Only app.py is eligible for model repair. Tests, contracts and frontend are protected; checkpoints are saved in runs/. Preview data is temporary.', wraplength=1000).pack(anchor='w', pady=8)
        window.after(100, self.poll)

    def button(self, parent, label, command):
        button = ttk.Button(parent, text=label, command=command)
        button.pack(side='left', padx=4)
        self.controls.append((button, 'normal'))
        return button

    def selected_project(self):
        value = self.workspace.get().strip()
        if not value:
            raise ValueError('Choose a project folder first.')
        path = Path(value).expanduser().resolve()
        if not (path / 'spec.json').is_file():
            raise ValueError('Choose a workspace containing spec.json.')
        return path

    def choose(self):
        folder = filedialog.askdirectory(initialdir=str(ROOT / 'workspaces'), title='Choose project workspace')
        if folder:
            self.workspace.set(folder)

    def new_project(self, operation):
        if self.busy:
            return
        objective = simpledialog.askstring('New Project',
            'Describe the project within the selected type.\nTask manager: add/list/toggle/delete. Expense tracker: add CAD expenses/filter/total.', parent=self.window)
        if objective and objective.strip():
            self.start(operation, objective.strip())

    def append(self, text):
        self.log.configure(state='normal'); self.log.insert('end', text); self.log.see('end'); self.log.configure(state='disabled')

    def start(self, operation, objective=None):
        if self.busy:
            return
        try:
            workspace = None if operation in ('plan', 'build') else self.selected_project()
            repairs = self.repairs.get()
            if not 0 <= repairs <= 3:
                raise ValueError('Repair limit must be between 0 and 3.')
            command = operation_command(operation, workspace, objective, self.project_type.get(), repairs)
        except (ValueError, tk.TclError) as error:
            messagebox.showerror('Cannot start operation', str(error)); return
        self.busy = True
        self.operation = operation
        self.preview_url = None
        self.stop_requested.clear()
        for widget, _ in self.controls:
            widget.configure(state='disabled')
        self.status.set(f'{operation.capitalize()} in progress...')
        self.progress.start()
        self.append(f'\nOperation: {operation}\n')
        threading.Thread(target=self.worker, args=(operation, command), daemon=True).start()

    def worker(self, operation, command):
        code = 1
        try:
            with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace') as process:
                self.process = process
                if operation == 'preview' and self.stop_requested.is_set():
                    process.send_signal(signal.SIGINT)
                for line in process.stdout:
                    self.events.put(('log', line))
                    if line.startswith('PROJECT_WORKSPACE='):
                        self.events.put(('workspace', line.strip().split('=', 1)[1]))
                    if line.startswith('PREVIEW_URL='):
                        self.events.put(('preview', line.strip().split('=', 1)[1]))
                code = process.wait()
        except Exception as error:
            self.events.put(('log', f'Launch error: {error}\n'))
        finally:
            self.process = None
            self.events.put(('done', (operation, code)))

    def poll(self):
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.append(value)
            elif kind == 'workspace':
                path = Path(value).resolve()
                if path.parent == ROOT / 'workspaces' and (path / 'spec.json').is_file():
                    self.workspace.set(str(path))
            elif kind == 'preview':
                self.preview_url = value
                self.status.set('Preview ready — temporary data; no verification performed.')
            elif kind == 'done':
                operation, code = value
                self.busy = False; self.operation = None; self.preview_url = None
                self.progress.stop()
                statuses = {'plan': 'Plan and contract saved; application not generated or verified.',
                            'generate': 'Application generated; acceptance tests have not run.',
                            'build': 'Verified: backend and browser acceptance passed.',
                            'verify': 'Verified: backend and browser acceptance passed.',
                            'repair': 'Verified: backend and browser acceptance passed.',
                            'preview': 'Preview stopped; temporary data removed. No verification performed.'}
                self.status.set(statuses[operation] if code == 0 else 'Stopped: review the log and saved reports.')
                for widget, state in self.controls:
                    widget.configure(state=state)
                if self.close_pending:
                    self.window.destroy(); return
        self.window.after(100, self.poll)

    def open_preview(self):
        if self.preview_url:
            webbrowser.open(self.preview_url)
        else:
            messagebox.showinfo('Preview unavailable', 'Start a preview and wait for readiness.')

    def stop_preview(self):
        if self.operation != 'preview':
            return
        self.stop_requested.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
        self.status.set('Stopping preview and removing temporary data...')

    def open_path(self, path):
        command = ['open'] if sys.platform == 'darwin' else ['xdg-open']
        try:
            subprocess.Popen([*command, str(path)])
        except OSError as error:
            messagebox.showerror('Could not open folder', str(error))

    def open_project(self):
        try:
            self.open_path(self.selected_project())
        except ValueError as error:
            messagebox.showerror('Project required', str(error))

    def open_reports(self):
        try:
            path = self.selected_project() / 'runs'
            if not path.is_dir():
                raise ValueError('Run verification to create reports first.')
            self.open_path(path)
        except ValueError as error:
            messagebox.showerror('Reports unavailable', str(error))

    def close(self):
        if self.operation == 'preview':
            self.close_pending = True
            self.stop_preview()
        elif self.busy:
            messagebox.showinfo('Operation running', 'Let this operation finish before closing.')
        else:
            self.window.destroy()


def main():
    window = tk.Tk()
    Desktop(window)
    window.mainloop()


if __name__ == '__main__':
    main()
