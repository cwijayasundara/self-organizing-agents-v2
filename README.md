# Agora v2

A bounded dynamic peer swarm with independently reviewed work, temporary helpers and the authors' RLM engine in isolated containers. Supports direct GLM/DeepSeek APIs, a live browser observer, deterministic scripted replay and executable architecture comparisons. V1's source is preserved.

Offline demo, no keys:

```sh
uv sync
uv run agora-v2 replay --out runs/demo
uv run agora-v2 observe runs/demo --port 8765
```

Open http://127.0.0.1:8765 and use Play events to watch actual ledger transitions. Scripted replay is explicitly labeled; fake-provider verification runs are labeled separately from live runs. The observer shows peers, helper reasons, claims/reviews, semantic calls, costs and the final memo, with no mutation controls.

Provision the pinned author engine and configure local keys:

```sh
docker build -f sandbox/Dockerfile -t agora-v2-rlms:d04208afbad2 .
cp .env.example .env.local
# Fill GLM_API_KEY and DEEPSEEK_API_KEY in .env.local locally.
uv run --env-file .env.local agora-v2 smoke --models examples/models.example.json \
  --budget-usd 0.10 --out runs/smoke
uv run --env-file .env.local agora-v2 run --mission examples/evidence_review/mission.json \
  --models examples/models.example.json --budget-usd 1.00 --out runs/live-demo --watch --port 8766
```

Keys remain in the host environment and are never mounted into generated-code execution or forwarded to v1. Environment files are ignored by Git. Live commands require an explicit spend cap and fresh output directory. `--watch` keeps the read-only observer available after the run until Ctrl-C. The examples do not authorize paid execution by themselves.

Compare frozen v1, a plain single agent, external context without semantic calls, the dynamic RLM swarm and a single-root RLM:

```sh
uv run --env-file .env.local agora-v2 evaluate --config examples/comparison.example.json \
  --budget-usd 5.00 --out runs/comparison
```

This cap covers all arms and seeds in that command, including independent final judging. Reports disclose enforcement differences and do not invent missing results. See [comparison details](docs/evaluation.md).

Verification:

```sh
uv run pytest -q
uv run pytest -m 'sandbox or v1' -q
uv build
```

The second suite requires the built Docker image and, for the optional frozen-v1 test, the existing sibling v1 checkout/interpreter. No credentials are needed for either suite. Current verification: 74 offline tests and 14 container/v1 integration tests passed. Paid verification awaits the user's keys and cap.

Default policy: USD 1.00; 480 seconds; 40 global model calls; three bootstrap peers spanning two families; five execution contexts; eight lifetime identities; semantic leaf depth one; two task repairs. Twenty percent of the total budget is protected for review/finalization. Submitted cancellations retain unresolved liability. Costs use reported token/cache usage and verified tariffs; DeepSeek peak rates are conservative upper estimates, not reconciled invoices.

The business fixture includes provenance and evidence hashes. Gold is evaluator-only, outside peer/interpreter capabilities and absent from the wheel fixture. See [live setup](docs/live-mode.md), [author integration assessment](docs/rlm-adapter-assessment.md), [implementation status](docs/implementation-status.md), and the [approved design](docs/superpowers/specs/2026-10-27-dynamic-swarm-design.md).
