# Live GLM/DeepSeek/MiniMax execution through Fireworks

The live runtime, Fireworks and direct adapters, author-package integration and comparison runners are implemented. No paid verification has run yet: the user will supply a Fireworks API key and an explicit total spend cap. Offline fakes are always labeled `offline_fake`; they do not establish live autonomy, model quality or invoice accuracy.

Provision the pinned author image once, explicitly:

```sh
uv sync
docker build -f sandbox/Dockerfile -t agora-v2-rlms:d04208afbad2 .
cp -n .env.example .env.local
# Fill FIREWORKS_API_KEY in .env.local locally (serves all three models).
```

The default configuration uses Fireworks Standard serverless for all three model families with one `FIREWORKS_API_KEY`. GLM, DeepSeek and MiniMax remain distinct families for bootstrap and review rules, even though Fireworks hosts all three. The key is never copied from v1, included in run configuration, passed into generated-code containers, or forwarded into the frozen-v1 subprocess. Existing `.env.local` credentials are preserved; add the Fireworks key locally. The direct Z.ai and DeepSeek adapters remain available for explicit alternate configurations. Environment files are ignored by Git and the Docker build context.

First run a capped usage/subcall smoke (the number is an example, not authorization):

```sh
uv run --env-file .env.local agora-v2 smoke \
  --models examples/models.example.json --budget-usd 0.10 --out runs/smoke
```

This requests reported usage from all three configured models on Fireworks, then requires an actual programmatic semantic call through the authors' RLM engine. A response that skips the leaf call fails the smoke. Missing usage retains an unresolved reservation. All requests use the same budget/call/slot controls; no automatic HTTP retries occur.

Run the business swarm with a live observer:

```sh
uv run --env-file .env.local agora-v2 run \
  --mission examples/evidence_review/mission.json \
  --models examples/models.example.json --budget-usd 1.00 \
  --out runs/live-demo --watch --port 8766
```

Open http://127.0.0.1:8766. The observer follows actual ledger events and stays available after the run until Ctrl-C. Without `--watch`, use `agora-v2 observe runs/live-demo` separately. Choose a fresh output directory every time. Helpers are created only when peers propose and independently admit them.

The author engine runs at recursion depth one inside a network-disabled, read-only, unprivileged container. Root and leaf requests cross a bounded stdio bridge into the host gateway. The image revision is checked before live construction and again inside the worker. Missing/mismatched images fail without host execution fallback. Live claims have a bounded run-length lease; failed owners release work promptly and exhausted required-task repairs terminate visibly.

Official pricing/protocol references, verified 2026-10-28: [Fireworks Standard pricing](https://docs.fireworks.ai/serverless/pricing), [chat completions API](https://docs.fireworks.ai/api-reference/post-chatcompletions), [GLM model](https://app.fireworks.ai/models/fireworks/glm-5p3-flash), [DeepSeek model](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash-1017), and [MiniMax model](https://fireworks.ai/models/fireworks/minimax-m3p1-flash).

The next live swarm starts one peer from each family: GLM, DeepSeek and MiniMax. The checker and semantic leaf defaults remain DeepSeek. The default allowlist is:

| Family | Fireworks model ID | Input / cached input / output USD per million tokens |
| --- | --- | --- |
| GLM | `accounts/fireworks/models/glm-5p3-flash` | 0.15 / 0.03 / 0.50 |
| DeepSeek | `accounts/fireworks/models/deepseek-v4p1-flash-1017` | 0.30 / 0.006 / 1.20 |
| MiniMax | `accounts/fireworks/models/minimax-m3p1-flash` | 0.15 / 0.015 / 0.60 |

Requests select the default Standard tier, GLM and MiniMax low reasoning effort, and DeepSeek reasoning disabled. MiniMax keeps reasoning enabled because this model requires it. All three use Fireworks `usage.prompt_tokens_details.cached_tokens`; the full reported completion count (including reasoning) is charged once. Output maxima bound completion tokens. Missing cache metadata is conservatively charged at the uncached input rate; missing or invalid total usage fails accounting. Arbitrary endpoints, unverified model IDs, incorrect family labels and changed tariffs are rejected.

Costs are token-rated estimates, not reconciled invoices. Unresolved reservations are separate from settled estimates, and cancellation does not promise a billing refund. Do not infer that real billing has been verified from fake-provider tests. Direct-provider catalog rates retain their 2026-10-27 verification; direct DeepSeek rates are conservative peak estimates.
