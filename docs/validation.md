# Validation and remaining platform checks

Validation was performed in the managed Linux cloud environment with Python
3.12.14/Tk 9.0.4 on the host and Python 3.11.18 inside Docker. Generated code ran
only inside Docker. No application was deployed or published.

## Completed checks

| Check | Result |
| --- | --- |
| `scripts/setup.sh` with hash-locked dependencies | Passed |
| Fast suite, with Linux Tk display | 51 passed |
| Full suite with Tk and opt-in Docker integration | 54 passed; no skips |
| Existing task manager, no repairs | 28 backend + 4 Chromium passed |
| Existing expense tracker, no repairs | 29 backend + 12 Chromium passed |
| Simulated task-manager and expense builds | Both passed after one deliberate backend defect and one repair each |
| Python 3.12-only f-string supplied to Python 3.11 runner | Correctly rejected as a collection error |
| Existing project tests/reference preservation | No Git changes; task fixtures copied byte-for-byte |
| `git diff --check` | Passed |

The 54-test host suite includes the three Docker integration cases. Acceptance
counts above are nested container results, not additional host pytest tests.

## Reference applications

The original task-manager backend passed its 28 existing tests before changes.
Its 28 backend and 4 Chromium acceptance tests subsequently passed through the
new runner/controller with no repairs. The entire reference workspace and the
repair-trial workspace remain unchanged in Git. The canonical task-manager
fixtures are exact copies of the original reference tests, without edits.

The expense tracker initially failed independent acceptance: 27 setup errors
and one failure from its removed Flask hook, missing initialization and related
contract violations. Its generated tests also reference nonexistent `app.db`,
use Flask response JSON as a function, and contain f-strings incompatible with
Python 3.11. Those generated files remain unchanged for provenance. They are
not reported as passing or used as independent acceptance evidence.

The expense application was corrected against its existing contract. Independent
acceptance covers date/type/length limits, boolean/fractional/over-limit cents,
rejected writes, exact totals, trimmed case-sensitive filters, persistent SQLite,
partial configuration overrides, responsive browser lifecycle, reload, literal
HTML, visible API/network failures with preserved form input, invalid decimal
dollar text, and exact 29-cent conversion. The final canonical suite contains
29 backend and 12 Chromium cases.

## Reproducible checks

```sh
./scripts/setup.sh
# Fast checks, including Tk when a display is available:
.venv-desktop/bin/python -m pytest -m 'not docker'
# Full orchestration plus actual HTTP-model/Docker/browser/preview integration:
SUITE_DOCKER_TESTS=1 .venv-desktop/bin/python -m pytest
# Verify the existing references without model repairs:
.venv-desktop/bin/python -m suite.controller workspaces/project-20261113-131615-917f271f --max-repairs 0
.venv-desktop/bin/python -m suite.controller workspaces/project-20261113-154909-f2945762 --max-repairs 0
```

Set `SUITE_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt` when needed in this cloud.
Linux Tk tests require a working display. Here they ran on an Xorg dummy display;
that is a headless rendering check, not a native macOS interaction test. Without a
display those tests are marked skipped. Docker integration is explicitly opt-in.

Simulated Ollama integration uses a local HTTP server with deterministic fixture
responses. For each supported type, it plans and generates a new temporary
project, supplies a deliberately incorrect backend, observes failing independent
tests, requests one repair through the real HTTP client/subprocess, verifies the
repaired backend and browser, and starts a loopback preview. It then creates and
reads a record over HTTP and stops the preview, checking cleanup. It asserts
that tests were not modified and the original source/checkpoints/diffs remain.
This proves the orchestration and supported fixture behavior, not real model
quality or connectivity to the user's Mac.

A separate Docker case supplies Python 3.12-only f-string syntax to the real
Python 3.11 runner and asserts collection fails. Infrastructure/collection
failures cannot trigger model repairs or earn verified status. Unit tests cover
build failures, timeouts, zero-test outcomes, stale reports, bounded repairs,
no-op/rejected repairs, protected-file changes, browser failures, interruption,
invalid model responses, and model transport failures.

## Native Mac verification still needed

- Install a modern Python with Tk 8.6+; launch both the module and the existing
  `.command` through Finder, where PATH and shell environment differ.
- Check text rendering, sizing, dialogs, keyboard focus, window closing, opening
  folders, and opening/stopping a preview in the default Mac browser.
- Run both acceptance profiles through Docker Desktop on the intended Intel or
  Apple Silicon Mac. Linux Chromium passed here; WebKit/Safari were not tested.
- Run a real local Ollama model through planning, generation and repair. Check
  model quality, latency, supported structured output, and resource use. Cloud
  simulations do not establish these properties.
- The launcher is not a self-contained `.app`. Packaging, signing, notarization,
  application icons and a native installer remain outside this change.

Preview storage is intentionally temporary. Persistent user-data management,
model-driven frontend repair, arbitrary application types and deployment remain
outside the supported workflow. Chromium OS packages come from signed Debian
repositories; fresh rebuilds can select a newer package version even though
Python packages and the Python base image are locked.
