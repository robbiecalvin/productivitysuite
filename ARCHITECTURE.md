# Productivity Suite architecture

The `suite/` package separates model access (`llm.py`), planning (`planner.py`), generation (`generator.py`), contracts (`contracts.py`), execution (`runner.py`), repair (`repair.py`), coordination (`controller.py`) and desktop preview (`desktop_preview.py`, `preview.py`).

## Evaluation boundary

Application contracts and acceptance tests define expected behavior. Generated code is evaluated in an isolated runner; repair attempts are bounded. Preserve acceptance tests rather than modifying them to obtain a passing result. Model-generated tests alone are not independent evidence.

## Known constraints

See [CODEX_HANDOFF.md](CODEX_HANDOFF.md) for task-specific assumptions, Python/Tk compatibility, local model connectivity and historical test evidence. This architecture summary does not certify isolation or runtime correctness.
