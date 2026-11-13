import argparse
import subprocess
import time
import uuid
from pathlib import Path

import requests

from suite.runner import find_docker, run_logged


def docker_output(docker, arguments):
    result = subprocess.run(
        [docker, *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    app_dir = workspace / "app"
    dockerfile = app_dir / "Dockerfile.backend-test"

    if not dockerfile.is_file():
        raise SystemExit(f"Missing Dockerfile: {dockerfile}")

    docker = find_docker()
    identifier = uuid.uuid4().hex[:12]
    image = f"productivity-preview:{identifier}"
    container = f"productivity-preview-{identifier}"
    exit_code = 0

    try:
        print("Building preview image...", flush=True)
        build_log = workspace / "preview-build.log"
        code = run_logged(
            [docker, "build", "-f", str(dockerfile),
             "-t", image, str(app_dir)],
            build_log,
            timeout=600,
        )
        if code:
            raise RuntimeError(
                f"Preview build failed. See {build_log}"
            )

        print("Starting local preview...", flush=True)
        docker_output(docker, [
            "run", "-d", "--init", "--name", container,
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,size=128m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", "1g",
            "--cpus", "2",
            "--pids-limit", "128",
            "-p", "127.0.0.1::8000",
            image,
            "python", "-c",
            (
                "from app import create_app; "
                "app = create_app({'DATABASE': '/tmp/preview.sqlite3'}); "
                "app.run(host='0.0.0.0', port=8000, "
                "debug=False, use_reloader=False)"
            ),
        ])

        address = docker_output(
            docker, ["port", container, "8000/tcp"]
        ).splitlines()[0]
        url = f"http://{address}"

        deadline = time.monotonic() + 30
        with requests.Session() as session:
            session.trust_env = False
            while time.monotonic() < deadline:
                running = docker_output(
                    docker,
                    ["inspect", "-f", "{{.State.Running}}", container],
                )
                if running != "true":
                    raise RuntimeError("Preview container stopped during startup.")
                try:
                    response = session.get(url, timeout=2)
                    if response.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("Preview did not become ready within 30 seconds.")

        print(f"PREVIEW_URL={url}", flush=True)
        print("Preview ready. Click Open Preview.", flush=True)
        print("Tasks are temporary and disappear when stopped.", flush=True)

        while True:
            time.sleep(2)
            running = docker_output(
                docker,
                ["inspect", "-f", "{{.State.Running}}", container],
            )
            if running != "true":
                raise RuntimeError("Preview container stopped unexpectedly.")

    except KeyboardInterrupt:
        print("\nStopping preview...", flush=True)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"\nPreview error: {error}", flush=True)
        exit_code = 1
    finally:
        try:
            logs = docker_output(docker, ["logs", "--tail", "100", container])
            (workspace / "preview-container.log").write_text(
                logs, encoding="utf-8"
            )
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass

        for command in (
            [docker, "rm", "-f", container],
            [docker, "image", "rm", image],
        ):
            try:
                subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                pass

        print("Preview cleanup finished.", flush=True)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
