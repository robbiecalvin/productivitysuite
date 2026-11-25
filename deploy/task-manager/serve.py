import hmac
import os
import sys
from pathlib import Path

from flask import Response, request

from app import create_app


DATA_DIR = Path("/var/data/task-manager")
SERVICE_UID = SERVICE_GID = 10001


def create_demo():
    password = os.environ["DEMO_PASSWORD"].encode()
    if not password:
        raise RuntimeError("Set DEMO_PASSWORD to a nonempty value.")

    app = create_app({"DATABASE": str(DATA_DIR / "tasks.sqlite3")})

    @app.get("/healthz")
    def health():
        return "", 204

    @app.before_request
    def require_demo_login():
        if request.endpoint == "health":
            return None
        auth = request.authorization
        if (
            auth
            and auth.type == "basic"
            and auth.username == "demo"
            and hmac.compare_digest((auth.password or "").encode(), password)
        ):
            return None
        return Response(
            "Demo credentials required.\n",
            status=401,
            headers={"WWW-Authenticate": 'Basic realm="Task Manager Demo"'},
        )

    return app


if __name__ == "__main__":
    if not os.environ.get("DEMO_PASSWORD"):
        raise SystemExit("Set DEMO_PASSWORD to a nonempty value.")

    # A new hosting volume can arrive root-owned. Prepare its app directory
    # before dropping privileges for Gunicorn and the application.
    os.umask(0o077)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chown(DATA_DIR, SERVICE_UID, SERVICE_GID)
    os.setgroups([])
    os.setgid(SERVICE_GID)
    os.setuid(SERVICE_UID)

    port = os.environ.get("PORT", "8000")
    os.execv(sys.executable, [
        sys.executable, "-m", "gunicorn",
        "--bind", f"0.0.0.0:{port}", "--workers", "1", "--preload",
        "serve:create_demo()",
    ])
