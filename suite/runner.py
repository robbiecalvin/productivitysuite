import argparse
import json
import shutil
import subprocess
import uuid
from pathlib import Path


def find_docker():
    candidates = [
        shutil.which("docker"),
        str(Path.home() / ".docker/bin/docker"),
        "/Applications/Docker.app/Contents/Resources/bin/docker",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Docker executable not found.")


def run_logged(command, log_path, timeout):
    with log_path.open("w", encoding="utf-8") as output:
        try:
            result = subprocess.run(
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            output.write(f"\nCommand exceeded {timeout} seconds.\n")
            return 124


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--mode", choices=("backend", "browser"), default="backend"
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    app_dir = workspace / "app"
    dockerfile = app_dir / f"Dockerfile.{args.mode}-test"

    if not dockerfile.is_file():
        raise SystemExit(f"Missing Dockerfile: {dockerfile}")

    try:
        docker = find_docker()
    except RuntimeError as error:
        raise SystemExit(str(error))

    identifier = uuid.uuid4().hex[:12]
    image = f"productivity-suite-test:{identifier}"
    container = f"productivity-suite-test-{identifier}"

    build_log = workspace / f"{args.mode}-build.log"
    test_log = workspace / f"{args.mode}-test.log"
    report_path = workspace / f"{args.mode}-report.json"
    report = {"mode": args.mode, "stage": "build", "passed": False}

    try:
        print("Building test environment...", flush=True)
        build_code = run_logged(
            [docker, "build", "-f", str(dockerfile),
             "-t", image, str(app_dir)],
            build_log,
            timeout=600,
        )
        report["build_exit_code"] = build_code

        if build_code == 0:
            report["stage"] = "test"
            print(f"Running {args.mode} tests...", flush=True)

            test_target = (
                "tests" if args.mode == "browser"
                else "tests/test_backend.py"
            )
            command = [
                docker, "run", "--rm", "--init",
                "--name", container,
                "--network", "none",
                "--read-only",
                "--tmpfs", "/tmp:rw,nosuid,size=512m",
                "--shm-size", "512m",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--memory", "2g",
                "--cpus", "2",
                "--pids-limit", "256",
                image,
                "python", "-m", "pytest", test_target,
                "-v", "--tb=short", "-p", "no:cacheprovider",
            ]
            if args.mode == "browser":
                command.append("--output=/tmp/test-results")

            test_code = run_logged(command, test_log, timeout=120)
            report["test_exit_code"] = test_code
            report["passed"] = test_code == 0

    except OSError as error:
        report["error"] = str(error)
    except KeyboardInterrupt:
        report["error"] = "Interrupted by user."

    finally:
        for command in (
            [docker, "rm", "-f", container],
            [docker, "image", "rm", image],
        ):
            try:
                subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass

        report_path.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

    log_path = test_log if report["stage"] == "test" else build_log
    if log_path.exists():
        print(log_path.read_text(encoding="utf-8"))

    print(f"Report: {report_path}")
    if "error" in report:
        print(f"Runner error: {report['error']}")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
