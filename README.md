# Agora v2

An independent Python 3.12 experiment in bounded peer coordination and external context processing. The runnable first slice is an explicitly **scripted offline demo**, backed by real SQLite claims, independent reviews, helper admission/retirement, cost reservations and trace export. Real Docker tests separately verify generated Python using external context and a programmatic fake-model subcall.

```sh
uv sync
uv run agora-v2 replay --out runs/demo
uv run agora-v2 observe runs/demo --port 8765
```

Open http://127.0.0.1:8765 for read-only timeline playback, peer states, shared tasks and the cited final memo. Choose a fresh output directory for each run. `uv run agora-v2 inspect runs/demo` prints the trace. The replay uses synthetic model usage and pricing, requires no keys, and makes no provider requests.

```sh
uv run pytest -q
# Explicitly provision a container image; the executor never pulls automatically.
docker pull python:3.12-slim
uv run pytest tests/test_sandbox.py -m sandbox -q
uv build
```

Offline tests include an ephemeral localhost observer server. Sandbox tests additionally require Docker. The observer is bound to loopback and exposes GET-only snapshots/events, with no run controls. An optional Node-based regression checks browser replay artifact-version selection.

The default limits are USD 1.00, 480 seconds, 40 total model calls, three bootstrap peers across two model families, five execution contexts, eight lifetime identities, leaf recursion depth one and at most two task repair attempts. Twenty percent of the model budget is protected for review/finalization. Review and finalization phases restrict available actions to match those funds. Unknown usage retains unresolved billing liability. Peer and leaf calls share the same slot pool; waiting parents yield slots.

The four-day-week fixture is copied from frozen v1 with source revision and hashes. Gold is held separately under `eval/gold/` for export scoring and never included in peer context, sandbox capabilities or the wheel's demo fixture. V2 does not import or modify v1.

**Live mode is not ready.** The authors' RLM package has not passed the required adapter controls. `agora-v2 run` requires an explicit spend cap and refuses dispatch while this gate remains closed; it does not substitute a different live mechanism. No paid smoke or architecture comparison has run. See [adapter assessment](docs/rlm-adapter-assessment.md), [live status](docs/live-mode.md), and [evaluation/export contract](docs/evaluation.md).

The browser observer and export scoring are usable independently. Export scoring supports the five architecture labels but does not yet execute provider-backed comparison arms. Missing arms and unmeasured claim judgments remain explicit.

The [design](docs/superpowers/specs/2026-10-27-dynamic-swarm-design.md) and [implementation plan](docs/superpowers/plans/2026-10-27-dynamic-swarm.md) record the intended complete milestone; remaining live work is not claimed complete by this slice.
