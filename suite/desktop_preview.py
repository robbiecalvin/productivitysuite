import os
import signal
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from suite.desktop import Desktop, ROOT


class PreviewDesktop(Desktop):
    def __init__(self, window):
        self.preview_process = None
        self.preview_url = None
        self.preview_active = False
        self.preview_stop_requested = False
        self.close_pending = False

        super().__init__(window)

        controls = ttk.Frame(self.progress.master)
        controls.pack(fill="x", pady=(8, 12), before=self.progress)

        ttk.Button(
            controls, text="Start Preview", command=self.start_preview
        ).pack(side="left")

        ttk.Button(
            controls, text="Open Preview", command=self.open_preview
        ).pack(side="left", padx=8)

        ttk.Button(
            controls, text="Stop Preview", command=self.stop_preview
        ).pack(side="left")

        ttk.Label(
            controls, text="Temporary data • local access only"
        ).pack(side="left", padx=12)

    def start_preview(self):
        if self.busy:
            messagebox.showinfo(
                "Operation running",
                "Finish the current operation before starting a preview.",
            )
            return

        try:
            self.selected_project()
        except ValueError as error:
            messagebox.showerror("Project required", str(error))
            return

        self.preview_active = True
        self.preview_stop_requested = False
        self.preview_url = None
        self.start(repairs=-1)
        self.status.set("Preview session active; see log for readiness.")

    def worker(self, workspace, repairs):
        if repairs != -1:
            return super().worker(workspace, repairs)

        code = 1
        try:
            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"

            with subprocess.Popen(
                [sys.executable, "-u", "-m", "suite.preview", str(workspace)],
                cwd=str(ROOT),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            ) as process:
                self.preview_process = process

                if self.preview_stop_requested:
                    process.send_signal(signal.SIGINT)

                for line in process.stdout:
                    if line.startswith("PREVIEW_URL="):
                        self.preview_url = line.strip().split("=", 1)[1]
                    self.events.put(("log", line))

                code = process.wait()

        except Exception as error:
            self.events.put(("log", f"\nPreview launch error: {error}\n"))
        finally:
            self.preview_process = None
            self.preview_url = None
            self.preview_active = False

            # Base desktop uses exit code 0 to mean tests passed.
            # A stopped preview is not a test verification.
            self.events.put(("done", 1))
            self.events.put((
                "log",
                f"\nPreview session ended (exit {code}). "
                "No test verification was performed by this preview.\n",
            ))

    def open_preview(self):
        if not self.preview_url:
            messagebox.showinfo(
                "Preview unavailable",
                "Start a preview and wait for 'Preview ready' in the log.",
            )
            return
        webbrowser.open(self.preview_url)

    def stop_preview(self):
        if not self.preview_active:
            return

        self.preview_stop_requested = True
        self.status.set("Stopping preview...")
        process = self.preview_process

        if process is not None:
            try:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
            except (OSError, ProcessLookupError):
                pass

    def close(self):
        if self.preview_active:
            self.close_pending = True
            self.stop_preview()
            self.window.after(100, self.finish_close)
            return
        super().close()

    def finish_close(self):
        if self.busy:
            self.window.after(100, self.finish_close)
        else:
            self.window.destroy()


def main():
    window = tk.Tk()
    from suite.desktop_build import BuildDesktop
    BuildDesktop(window)
    window.mainloop()


if __name__ == "__main__":
    main()
