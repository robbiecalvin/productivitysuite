import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(module, arguments):
    return subprocess.run(
        [sys.executable, "-m", module, *arguments],
        check=False,
    ).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--max-repairs", type=int, default=3)
    args = parser.parse_args()

    if not 0 <= args.max_repairs <= 3:
        raise SystemExit("--max-repairs must be between 0 and 3.")

    workspace = args.workspace.resolve()
    app_path = workspace / "app" / "app.py"

    protected = [
        workspace / "contract.json",
        workspace / "spec.json",
        workspace / "app" / "tests" / "test_backend.py",
        workspace / "app" / "tests" / "test_browser.py",
        workspace / "app" / "Dockerfile.backend-test",
        workspace / "app" / "Dockerfile.browser-test",
        workspace / "app" / "templates" / "index.html",
        workspace / "app" / "static" / "app.js",
        workspace / "app" / "static" / "style.css",
        workspace / "app" / "requirements.txt",
    ]

    for path in [app_path, *protected]:
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"Missing file or unsupported symlink: {path}")

    original_hashes = {path: fingerprint(path) for path in protected}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = workspace / "runs" / f"{stamp}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True)

    report = {
        "workspace": str(workspace),
        "scope": "existing Flask project; app.py repairs only",
        "passed": False,
        "repairs_attempted": 0,
        "checks": [],
        "status": "running",
    }

    def check_protected_files():
        for path, expected in original_hashes.items():
            if not path.is_file() or fingerprint(path) != expected:
                raise RuntimeError(f"Protected file changed: {path}")

    try:
        for attempt in range(args.max_repairs + 1):
            check_protected_files()

            checkpoint = run_dir / f"check-{attempt}"
            checkpoint.mkdir()
            shutil.copy2(app_path, checkpoint / "app.py")

            print(f"\n=== Verification {attempt + 1} ===", flush=True)
            code = invoke(
                "suite.runner",
                [str(workspace), "--mode", "browser"],
            )

            for name in (
                "browser-report.json",
                "browser-build.log",
                "browser-test.log",
            ):
                path = workspace / name
                if path.exists():
                    shutil.copy2(path, checkpoint / name)

            check_protected_files()

            runner_report_path = checkpoint / "browser-report.json"
            if not runner_report_path.exists():
                raise RuntimeError("Runner did not produce a report.")

            result = json.loads(
                runner_report_path.read_text(encoding="utf-8")
            )
            report["checks"].append({
                "attempt": attempt,
                "runner_exit_code": code,
                "result": result,
                "checkpoint": str(checkpoint),
            })

            if code == 0 and result.get("passed") is True:
                report["passed"] = True
                report["status"] = "passed"
                break

            if result.get("build_exit_code") != 0:
                report["status"] = "build_failed"
                break

            # pytest: 1 = failed tests; 2 = interrupted/collection error.
            # Other codes include usage errors, no tests, and timeouts.
            if result.get("test_exit_code") not in (1, 2):
                report["status"] = "test_infrastructure_failed"
                break

            test_log = workspace / "browser-test.log"
            text = test_log.read_text(encoding="utf-8")

            backend_failed = any(
                line.startswith(("FAILED ", "ERROR "))
                and "test_backend.py" in line
                for line in text.splitlines()
            )
            if not backend_failed:
                report["status"] = "frontend_or_unclassified_failure"
                break

            if attempt == args.max_repairs:
                report["status"] = "repair_limit_reached"
                break

            # Existing repair module reads this filename.
            shutil.copy2(test_log, workspace / "backend-test.log")

            print("\n=== Requesting backend repair ===", flush=True)
            report["repairs_attempted"] += 1

            before = fingerprint(app_path)
            repair_code = invoke("suite.repair", [str(workspace)])
            check_protected_files()

            if repair_code != 0:
                report["status"] = "repair_rejected"
                break
            if fingerprint(app_path) == before:
                report["status"] = "repair_made_no_change"
                break

    except KeyboardInterrupt:
        report["status"] = "interrupted"
    except (OSError, ValueError, RuntimeError) as error:
        report["status"] = "controller_error"
        report["error"] = str(error)
    finally:
        report_path = run_dir / "report.json"
        report_path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"\nResult: {report['status']}")
    print(f"Repairs attempted: {report['repairs_attempted']}")
    print(f"Report: {report_path}")
    if report.get("error"):
        print(report["error"])
    if not report["passed"]:
        print("Current application is unverified. Checkpoints were preserved.")

    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
