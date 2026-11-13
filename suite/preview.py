import argparse
import subprocess
import time
import uuid
from pathlib import Path

import requests

from suite.runner import find_docker, build_image, container_options


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


def cleanup_resources(docker, container, image):
    errors = []
    for arguments, missing in ((['rm', '-f', container], 'No such container'),
                               (['image', 'rm', image], 'No such image')):
        try:
            result = subprocess.run([docker, *arguments], capture_output=True,
                                    text=True, timeout=20, check=False)
            if result.returncode and missing not in result.stderr:
                errors.append(result.stderr.strip() or result.stdout.strip() or
                              f"Docker {' '.join(arguments)} failed ({result.returncode}).")
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(str(error))
    return errors


def preview_address(output):
    addresses = output.splitlines()
    if len(addresses) != 1:
        raise RuntimeError('Preview did not publish exactly one loopback port.')
    host, separator, port = addresses[0].rpartition(':')
    if host != '127.0.0.1' or not separator or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise RuntimeError('Preview port is not a valid loopback address.')
    return f'http://{addresses[0]}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    docker = find_docker()
    identifier = uuid.uuid4().hex[:12]
    image = f"productivity-preview:{identifier}"
    container = f"productivity-preview-{identifier}"
    exit_code = 0

    try:
        print("Building preview image...", flush=True)
        build_log = workspace / "preview-build.log"
        code = build_image(docker, workspace, image, 'backend', build_log)
        if code:
            raise RuntimeError(
                f"Preview build failed. See {build_log}"
            )

        print("Starting local preview...", flush=True)
        docker_output(docker, [
            "run", "-d", "--name", container,
            *container_options(),
            "--network", "bridge",
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

        url = preview_address(docker_output(docker, ["port", container, "8000/tcp"]))

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
        print("Preview records are temporary and disappear when stopped.", flush=True)

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
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
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

        cleanup_errors = cleanup_resources(docker, container, image)
        if cleanup_errors:
            exit_code = 1
            print("Preview cleanup incomplete; resources may remain:", flush=True)
            for error in cleanup_errors:
                print(error, flush=True)
        else:
            print("Preview cleanup finished.", flush=True)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
