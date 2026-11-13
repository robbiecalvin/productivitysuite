# Intelligent Productivity Suite

## Goal and current state

A local desktop application where the user describes a supported application and
plans, generates, independently tests, repairs, and previews it. The connected
workflow is implemented on `feat/supported-project-workflow`.

Desktop entry point: `.venv-desktop/bin/python -m suite.desktop_preview`.
Run `./scripts/setup.sh` first. See README.md for dependencies, CLI commands,
Ollama configuration and the supported scope.

## Implemented workflow

- Explicit `task_manager` and `expense_tracker` profiles define the API, fields,
  validation, selectors and acceptance checks. Other types fail explicitly.
- The desktop connects plan, generate, build-and-verify, test, bounded backend
  repair and temporary preview operations. Planning needs no existing project.
- Suite-owned Docker recipes execute only allowlisted application sources and
  canonical acceptance fixtures. Generated dependency lists, Dockerfiles and
  tests cannot control verification. Generated apps never run on the host.
- Repairs affect only app.py, with a 0–3 limit. Preserve source checkpoints,
  acceptance fixtures, protected-input hashes, responses, candidates and diffs.
- New files and repaired backends are published atomically. Malformed inputs,
  source changes observed during verification, and failed cleanup cannot earn a
  successful verified/cleaned-up status.

## Reference projects and evidence

- `workspaces/project-20261113-131615-917f271f`: original task manager, preserved
  unchanged; 28 backend and 4 Chromium acceptance cases passed.
- `workspaces/repair-trial-001`: original repair experiment, preserved unchanged.
- `workspaces/project-20261113-154909-f2945762`: expense implementation corrected
  against its existing contract; 29 independent backend and 12 Chromium cases
  passed. Its original generated tests remain unchanged for provenance and are
  broken; they are not used or reported as passing acceptance evidence.

Final combined cloud validation: 86 tests passed, no failures or skips, with
Linux Tk and all three Docker integration cases enabled. Simulated Ollama HTTP
workflows for both types exercised generation, one deliberate backend defect,
one repair, independent acceptance and preview CRUD/cleanup. The simulation does
not establish real model quality. Full commands and evidence: docs/validation.md.

## Remaining verification and limits

- Verify Finder launch, dialogs/focus, closing, folder opening and default-browser
  preview on a native Mac with modern Python/Tk.
- Verify Docker Desktop on the intended Intel/Apple Silicon Mac and a real local
  Ollama model. Cloud localhost cannot reach the user's Mac localhost; configure
  a reachable OLLAMA_BASE_URL and OLLAMA_MODEL for live generation.
- Preview storage is temporary. Frontend repair, arbitrary application types and
  deployment are outside the supported scope.
- The existing .command is a launcher, not a self-contained, signed or notarized
  Mac application. Packaging remains outside this implementation.

Keep generated application execution isolated. Preserve independent acceptance
tests; never weaken checks to make generated code pass. Do not publish or deploy.
