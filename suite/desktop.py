import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


# Finder-launched applications do not load shell PATH settings.
docker_paths = [
    str(Path.home() / ".docker/bin"),
    "/Applications/Docker.app/Contents/Resources/bin",
    "/usr/local/bin",
    "/opt/homebrew/bin",
]
os.environ["PATH"] = os.pathsep.join(
    docker_paths + [os.environ.get("PATH", "/usr/bin:/bin")]
)

ROOT = Path(__file__).resolve().parent.parent


class Desktop:
    def __init__(self, window):
        self.window = window
        self.events = queue.Queue()
        self.busy = False

        window.title("Intelligent Productivity Suite")
        window.geometry("1000x700")
        window.minsize(760, 500)
        window.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Intelligent Productivity Suite",
            font=("Helvetica", 22, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text="Local project verification and bounded backend repair",
        ).pack(anchor="w", pady=(4, 18))

        project_row = ttk.Frame(frame)
        project_row.pack(fill="x")

        default = ROOT / "workspaces" / "project-20261113-131615-917f271f"
        self.workspace = tk.StringVar(
            value=str(default) if default.exists() else ""
        )

        self.project_entry = ttk.Entry(
            project_row, textvariable=self.workspace
        )
        self.project_entry.pack(side="left", fill="x", expand=True)

        self.choose_button = ttk.Button(
            project_row, text="Choose Project", command=self.choose
        )
        self.choose_button.pack(side="left", padx=(8, 0))

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=16)

        self.verify_button = ttk.Button(
            actions,
            text="Run All Tests",
            command=lambda: self.start(repairs=0),
        )
        self.verify_button.pack(side="left")

        self.repair_button = ttk.Button(
            actions,
            text="Test & Repair Backend",
            command=lambda: self.start(repairs=3),
        )
        self.repair_button.pack(side="left", padx=8)

        ttk.Button(
            actions, text="Open Project Folder", command=self.open_project
        ).pack(side="left")

        ttk.Button(
            actions, text="Open Run Reports", command=self.open_reports
        ).pack(side="left", padx=8)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 12))

        self.log = ScrolledText(
            frame,
            wrap="word",
            font=("Menlo", 11),
            background="#17191f",
            foreground="#e7e9ef",
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=(
                "Repairs can change app.py. Tests and frontend files are "
                "protected. Checkpoints are saved in the project's runs folder."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(10, 0))

        window.after(100, self.poll)

    def selected_project(self):
        value = self.workspace.get().strip()
        if not value:
            raise ValueError("Choose a project folder first.")

        path = Path(value).expanduser().resolve()
        if not (path / "contract.json").is_file():
            raise ValueError(
                "Select a workspace containing contract.json and an app folder."
            )
        return path

    def choose(self):
        folder = filedialog.askdirectory(
            initialdir=str(ROOT / "workspaces"),
            title="Choose project workspace",
        )
        if folder:
            self.workspace.set(folder)

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self, repairs):
        if self.busy:
            return

        try:
            workspace = self.selected_project()
        except ValueError as error:
            messagebox.showerror("Project required", str(error))
            return

        self.busy = True
        for widget in (
            self.verify_button,
            self.repair_button,
            self.choose_button,
            self.project_entry,
        ):
            widget.configure(state="disabled")

        self.status.set(
            "Testing and repairing..." if repairs else "Running tests..."
        )
        self.progress.start()
        self.append(f"\nProject: {workspace}\nRepair limit: {repairs}\n\n")

        threading.Thread(
            target=self.worker,
            args=(workspace, repairs),
            daemon=True,
        ).start()

    def worker(self, workspace, repairs):
        code = 1
        try:
            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"

            command = [
                sys.executable, "-u", "-m", "suite.controller",
                str(workspace), "--max-repairs", str(repairs),
            ]
            with subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            ) as process:
                for line in process.stdout:
                    self.events.put(("log", line))
                code = process.wait()

        except Exception as error:
            self.events.put(("log", f"\nLaunch error: {error}\n"))

        finally:
            self.events.put(("done", code))

    def poll(self):
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.append(value)
            elif kind == "done":
                self.busy = False
                self.progress.stop()
                self.status.set(
                    "Verified: all checks passed"
                    if value == 0
                    else "Stopped: review the log and saved report"
                )
                for widget in (
                    self.verify_button,
                    self.repair_button,
                    self.choose_button,
                    self.project_entry,
                ):
                    widget.configure(state="normal")

        self.window.after(100, self.poll)

    def open_path(self, path):
        try:
            subprocess.run(["open", str(path)], check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            messagebox.showerror("Could not open folder", str(error))

    def open_project(self):
        try:
            self.open_path(self.selected_project())
        except ValueError as error:
            messagebox.showerror("Project required", str(error))

    def open_reports(self):
        try:
            path = self.selected_project() / "runs"
            if not path.is_dir():
                raise ValueError("Run verification to create a report first.")
            self.open_path(path)
        except ValueError as error:
            messagebox.showerror("Reports unavailable", str(error))

    def close(self):
        if self.busy:
            messagebox.showinfo(
                "Operation running",
                "Let this operation finish before closing the application.",
            )
            return
        self.window.destroy()


def main():
    window = tk.Tk()
    Desktop(window)
    window.mainloop()


if __name__ == "__main__":
    main()
