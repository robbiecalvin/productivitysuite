# Intelligent Productivity Suite

## Goal
Build a local desktop application where the user describes a supported
application and the system plans, generates, tests, repairs, and previews it.

## Existing implementation
Inspect suite/ for the Ollama client, planner, generator, contracts,
Docker runner, bounded repair controller, desktop UI, and preview engine.
Desktop entry point: python -m suite.desktop_preview

## Reference projects
- workspaces/project-20261113-131615-917f271f:
  Task manager; previously passed 28 backend and 4 Chromium browser tests.
- workspaces/repair-trial-001:
  Disposable automatic repair experiment; eventually passed all 32 tests
  after repair-prompt adjustments.
- workspaces/project-20261113-154909-f2945762:
  Expense tracker; specification, contract, and generated files exist.
  Application behavior is unverified.

## Known limitations
- Contract creation and repair prompts contain task-manager assumptions.
- Generator tests are not independent acceptance evidence.
- Python 3.11 compatibility needs checking, including generated f-strings.
- Preview uses temporary storage.
- Desktop uses negative repair limits as internal operation markers.
- Desktop runtime needs modern Python/Tk; Apple Python 3.9/Tk 8.5 rendered blank.
- Cloud localhost cannot reach Ollama running on the user's Mac.
- The current .app is only a launcher, not a self-contained distribution.

## Requested work
1. Inspect the repository and document reproducible setup.
2. Preserve the task-manager reference and independently verify its tests.
3. Inspect and verify the expense tracker against its contract.
4. Replace project-specific assumptions with explicit supported contracts.
5. Connect generation, testing, bounded repairs, and preview to the desktop UI.
6. Preserve acceptance tests and checkpoints; never weaken tests to pass.
7. Add meaningful checks for controller failure paths and model-service errors.
8. Use a simulated model service for cloud checks when local Ollama is unavailable.
9. Report exactly what was tested and what still requires native Mac verification.

Keep generated application execution isolated. Do not publish or deploy.
