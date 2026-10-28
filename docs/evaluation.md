# Executable architecture comparisons

`agora-v2 evaluate` supports exports and actual execution of five architectures:

- `frozen_v1`: unchanged v1 source in an external process, four fixed peers and its original template; models injected through public `arun_swarm(models=...)`.
- `plain_single`: one agent with scoped evidence reads and a bounded arithmetic calculator.
- `external_context`: one agent with external handles and isolated Python; semantic calls are refused by the host bridge.
- `dynamic_swarm`: self-claiming peers, reviewed scope, bounded helpers and the isolated authors' RLM engine.
- `single_root_rlm`: one authors' RLM root with external evidence and bounded leaf calls, without peer coordination.

```sh
uv run --env-file .env.local agora-v2 evaluate \
  --config examples/comparison.example.json --budget-usd 5.00 --out runs/comparison
```

The CLI budget is the TOTAL cap for this comparison command. It is divided equally, rounding down to microdollars, across all requested arms and repetitions. For five arms and seeds `[0,1]`, USD 5 allocates USD 0.50 per run including independent judging. Prior overruns or unresolved liability can prevent later dispatches; exceptions recover accounting from persisted calls. A smoke or standalone demo is a separate command/cap, so allocate any overall verification allowance explicitly between commands.

Every arm receives the same original brief, rubric, manifest, configured model choices where applicable, per-run cap and deadline. Gold is evaluator-only and never passed to a runner, model or interpreter. Seeds are included as prompt metadata; they do not guarantee provider RNG determinism. Repeated seed labels create separate run directories rather than reusing an export.

Frozen v1 must be the pinned source revision `b2bc646aa51b7444a22670283d462b59b7ddde22`, with no staged or unstaged tracked changes. Its existing interpreter is used without copying its environment or credentials. Only verified manifest files are materialized into a fresh read-only evidence snapshot, excluding nonmanifest files and hidden gold aliases. Its native model requests retain tool schemas, message roles, reported token/cache usage and return through the same host budget. No v1 source is modified. Native scheduling/leases, four initial peers alternating the first two bootstrap model keys, fixed scope and serialized provider dispatch are recorded enforcement differences. The dynamic swarm starts all three configured bootstrap families; the frozen-v1 roster retains its original two-family pattern.

Each completed candidate passes deterministic memo/citation checks and an independent model judgment against the original rubric and complete evidence within the configured prompt bound. Overlarge judge context fails explicitly rather than silently truncating evidence. Judging is charged inside each arm's budget. The report includes unsupported claims and rubric coverage when the judge returns a valid result; missing/invalid judgments stay unknown.

Outputs: per-run databases/traces/artifacts; `report.json` with raw rows and aggregates; `report.md` with correctness, citation coverage, unsupported claims, settled token-rated estimates, unresolved reservations, calls and latency. Aggregates include run/completion counts, mean correctness, sample deviation and mean latency. Model configuration, evidence hashes, seeds and enforcement differences travel with results.

For existing exports, omit `execute` and supply `exports: {"dynamic_swarm":"/path/to/trace.json"}` with one seed. Exports are not fabricated into repeated runs. Missing arms are `not_run`, unknown imported metrics remain unknown, and fake/scripted results are labeled mechanics-only. No live superiority or invoice accuracy is established by the offline suite.

The default GLM, DeepSeek and MiniMax models run on Fireworks Standard serverless using one `FIREWORKS_API_KEY`; their input/cache/output tariffs were verified from official Fireworks sources on 2026-10-28. Model-family identity remains independent of hosting provider. Reported costs are estimates rather than reconciled invoices. See `live-mode.md` for source links and credential setup.
