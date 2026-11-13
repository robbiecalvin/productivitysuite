# Intelligent Productivity Suite

A local Python/Tk desktop app that plans a supported Flask/SQLite application,
creates an explicit contract, generates implementation files through Ollama,
runs independent acceptance checks in Docker, attempts up to three backend
repairs, and starts a temporary local preview.

Supported types are deliberately limited:

| Type | Contract |
| --- | --- |
| `task_manager` | Create/list tasks, toggle completion, delete; persistent SQLite |
| `expense_tracker` | Add dated CAD expenses, category filter, integer-cent totals; no edit/delete |

Unsupported types or changes to the supported API/UI contracts fail explicitly.
Free-text objectives describe a project within the chosen type; they do not add
arbitrary features to the verified scope.

## Setup

Requirements: Python 3.11+ with Tk 8.6+ (tested here with Python 3.12/Tk 9), Docker
Desktop on macOS or a running Docker Engine on Linux, and network access for
PyPI, Docker Hub and signed Debian package repositories. Start Docker first.

```sh
./scripts/setup.sh
.venv-desktop/bin/python -m suite.desktop_preview
```

The setup script installs hash-locked development dependencies in the ignored
`.venv-desktop/`. The existing `Productivity Suite.command` uses that environment
on macOS. It is a launcher, not a packaged or signed application.

For generation, start Ollama and install a suitable coding model separately:

```sh
ollama pull qwen2.5-coder:7b
export OLLAMA_MODEL=qwen2.5-coder:7b
export OLLAMA_BASE_URL=http://localhost:11434
.venv-desktop/bin/python -m suite.llm
```

In cloud tasks, localhost refers to the cloud machine, not your Mac. Configure a
reachable Ollama HTTP(S) service through your environment's supported networking.
Do not put credentials in its URL. The simulated-service integration tests below
need no real model or Mac connection and do not demonstrate model quality.

If Docker builds require a corporate/cloud CA, set `SUITE_CA_BUNDLE` to a combined
PEM trust bundle (in this cloud: `/etc/ssl/certs/ca-certificates.crt`). The runner
also recognizes `SSL_CERT_FILE` and the managed `CODEX_PROXY_CERT` binding. The
bundle is mounted only during pip installation; TLS and package hashes remain
verified. Do not disable verification. No external Docker wrapper is required.

## Workflow

Choose the project type in the desktop. **Plan New Project** saves a specification
and contract without needing an existing workspace. **Generate Selected** fills
missing implementation files; rerunning preserves existing files. New specifications,
contracts and application files are published atomically, so failed writes do not
leave partial files that block a corrected retry. **Build &
Verify New Project** plans, generates, tests, and attempts bounded backend repairs.
**Run All Tests** performs no repairs. **Test & Repair Backend** uses the displayed
0–3 limit. Backend acceptance must pass before the browser suite runs. A frontend
failure stops the workflow; frontend files and tests are never model-repaired.

Only a completed backend-and-browser acceptance run earns a **Verified** status.
Planning, generation, and preview have separate completion messages. Each run
saves source checkpoints, protected-input hashes, JUnit results and logs under
`workspaces/<project>/runs/`. Repair attempts retain original/candidate source,
model responses and diffs under `repairs/`. Failed repairs may leave an unverified
backend candidate; the prior source remains in checkpoints for manual recovery.

CLI equivalents, from this checkout:

```sh
.venv-desktop/bin/python -m suite.workflow build \
  --project-type expense_tracker --objective 'A personal CAD expense ledger' --max-repairs 3
.venv-desktop/bin/python -m suite.controller workspaces/<project> --max-repairs 0
.venv-desktop/bin/python -m suite.runner workspaces/<project> --mode backend
.venv-desktop/bin/python -m suite.preview workspaces/<project>
```

Use **Start/Open/Stop Preview** in the desktop. The service binds only to a random
loopback port. Data lives in a container tmpfs and disappears on stop. Closing the
desktop while previewing requests cleanup first. Preview is local development,
not publication or deployment, and does not verify behavior.

## Verification and isolation

The suite-owned fixtures in `suite/acceptance/` are independent of the generator.
Task-manager fixtures are byte-for-byte copies of the preserved reference tests.
Expense fixtures were written from the agreed contract; original broken generated
expense tests remain untouched for provenance and are not used as acceptance.
New projects receive copies of suite-owned tests. Existing project tests remain
unchanged, and the runner always selects the canonical suite-owned fixtures.

Only allowlisted source files and trusted acceptance fixtures enter the build
context. Generated `requirements.txt`, Dockerfiles and tests cannot control the
suite's build/test commands. Runtime Python is pinned to a Python 3.11 image
digest; Python dependencies are hash-locked. Chromium comes from the base
image's signed Debian repositories, so its exact OS package version may change
on a fresh uncached build. This is a repeatable setup recipe, not a bit-for-bit
OS image lock.

Acceptance runs as UID 10001 with no network, a read-only filesystem, bounded
CPU/memory/processes, dropped capabilities and temporary storage. Only an empty
results directory is writable on the host. Preview uses the same container
restrictions but a bridge network for the loopback-published service; it is not
a network-free container. Treat generated code as untrusted and review it before
using it with sensitive data. Suite modules and test fixtures run on the host;
generated app modules are never imported by host tests.

Run fast orchestration and failure checks:

```sh
.venv-desktop/bin/python -m pytest -m 'not docker'
```

Desktop checks require `DISPLAY` on Linux and are explicitly skipped without it.
The opt-in test below serves deterministic Ollama responses over actual HTTP,
generates both project types in temporary workspaces, injects a backend defect,
repairs it once, runs real backend/Chromium acceptance, then exercises and stops
the isolated preview:

```sh
SUITE_DOCKER_TESTS=1 .venv-desktop/bin/python -m pytest
```

The host syntax check uses the running Python's parser. Actual Python 3.11
compatibility is established by Docker execution, including collection errors
from unsupported f-strings; host `ast.feature_version` alone is not sufficient.
See [validation evidence and Mac checks](docs/validation.md).
