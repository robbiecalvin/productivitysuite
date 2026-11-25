# Intelligent Productivity Suite

A local desktop application project for planning, generating, testing, repairing and previewing supported applications from user descriptions.

## Architecture

The `suite/` package contains an Ollama client, planner, generator, contracts, Docker runner, bounded repair controller, desktop UI and preview engine. Generated application execution is intended to remain isolated.

## Evaluation approach

The project uses application contracts, backend tests, Chromium browser tests and bounded repair attempts. Acceptance tests should remain unchanged when repairing generated code. Generator tests are not independent acceptance evidence.

## Reference workspaces

The [Codex handoff](CODEX_HANDOFF.md) records prior task-manager and repair-trial results and an expense-tracker workspace whose behavior remains unverified. These historical results have not been independently rerun for this documentation update.

## Desktop entry point

`python -m suite.desktop_preview`

See the handoff for runtime limitations, local Ollama connectivity, Python/Tk compatibility and outstanding setup verification. The current launcher is not a self-contained distribution.

## Status

Development project; not a verified production release. Do not publish or deploy generated applications without explicit review.
