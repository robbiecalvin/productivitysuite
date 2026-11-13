import queue
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from suite.desktop import ROOT
from suite.desktop_preview import PreviewDesktop


class BuildDesktop(PreviewDesktop):
    def __init__(self, window):
        self.plan_updates = queue.Queue()
        self.objective = ""
        super().__init__(window)

        controls = ttk.Frame(self.progress.master)
        controls.pack(fill="x", pady=(4, 8), before=self.progress)

        ttk.Button(
            controls,
            text="Plan New Project",
            command=self.plan_project,
        ).pack(side="left")

        ttk.Label(
            controls,
            text="Describe an idea → create its specification",
        ).pack(side="left", padx=12)

    def plan_project(self):
        if self.busy:
            messagebox.showinfo(
                "Operation running",
                "Finish the current operation or stop the preview first.",
            )
            return

        objective = simpledialog.askstring(
            "New Project",
            "What would you like to build?\n\n"
            "Current planning target: a small local Flask web application.",
            parent=self.window,
        )
        if not objective or not objective.strip():
            return

        # Existing start() validates a selected workspace even though
        # planning creates a new one.
        try:
            self.selected_project()
        except ValueError as error:
            messagebox.showerror("Select an existing workspace first", str(error))
            return

        self.objective = objective.strip()
        self.start(repairs=-2)
        self.status.set("Planning a new project...")

    def worker(self, workspace, repairs):
        if repairs != -2:
            return super().worker(workspace, repairs)

        success = False
        new_workspace = None

        try:
            self.events.put(("log", f"Objective: {self.objective}\n"))
            result = subprocess.run(
                [sys.executable, "-u", "-m", "suite.planner"],
                cwd=str(ROOT),
                input=self.objective + "\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=720,
                check=False,
            )
            self.events.put(("log", result.stdout))

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Saved specification: "):
                        spec = Path(line.split(": ", 1)[1]).resolve()
                        if (
                            spec.name == "spec.json"
                            and spec.is_file()
                            and spec.parent.parent == ROOT / "workspaces"
                        ):
                            new_workspace = spec.parent
                            success = True
                            break

        except subprocess.TimeoutExpired:
            self.events.put(("log", "\nPlanning exceeded 12 minutes.\n"))
        except Exception as error:
            self.events.put(("log", f"\nPlanning error: {error}\n"))
        finally:
            # Planning is not test verification.
            self.events.put(("done", 1))
            self.plan_updates.put((success, new_workspace))

    def poll(self):
        super().poll()

        # Process the planning result only after the base UI has handled
        # its completion event and re-enabled the controls.
        if not self.busy:
            try:
                success, workspace = self.plan_updates.get_nowait()
            except queue.Empty:
                return

            if success:
                self.workspace.set(str(workspace))
                self.status.set("Plan saved. Application not generated yet.")
                self.append(
                    "\nNew project selected. Review spec.json before generation.\n"
                )
            else:
                self.status.set("Planning stopped. Review the log.")
