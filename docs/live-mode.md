# Live GLM/DeepSeek execution

The live runtime, direct adapters, author-package integration and comparison runners are implemented. No paid verification has run yet: the user will supply GLM/DeepSeek keys and an explicit total spend cap. Offline fakes are always labeled `offline_fake`; they do not establish live autonomy, model quality or invoice accuracy.

Provision the pinned author image once, explicitly:

```sh
uv sync
docker build -f sandbox/Dockerfile -t agora-v2-rlms:d04208afbad2 .
cp .env.example .env.local
# Fill GLM_API_KEY and DEEPSEEK_API_KEY in .env.local locally.
```

The GLM key must be for the direct Z.ai general API; DeepSeek uses its direct API. Neither key is copied from v1, included in run configuration, passed into generated-code containers, or forwarded into the frozen-v1 subprocess. Environment files are ignored by Git and the Docker build context.

First run a capped usage/subcall smoke (the number is an example, not authorization):

```sh
uv run --env-file .env.local agora-v2 smoke \
  --models examples/models.example.json --budget-usd 0.10 --out runs/smoke
```

This requests reported usage from both providers, then requires an actual programmatic semantic call through the authors' RLM engine. A response that skips the leaf call fails the smoke. Missing usage retains an unresolved reservation. All requests use the same budget/call/slot controls; no automatic HTTP retries occur.

Run the business swarm with a live observer:

```sh
uv run --env-file .env.local agora-v2 run \
  --mission examples/evidence_review/mission.json \
  --models examples/models.example.json --budget-usd 1.00 \
  --out runs/live-demo --watch --port 8766
```

Open http://127.0.0.1:8766. The observer follows actual ledger events and stays available after the run until Ctrl-C. Without `--watch`, use `agora-v2 observe runs/live-demo` separately. Choose a fresh output directory every time. Helpers are created only when peers propose and independently admit them.

The author engine runs at recursion depth one inside a network-disabled, read-only, unprivileged container. Root and leaf requests cross a bounded stdio bridge into the host gateway. The image revision is checked before live construction and again inside the worker. Missing/mismatched images fail without host execution fallback. Live claims have a bounded run-length lease; failed owners release work promptly and exhausted required-task repairs terminate visibly.

Official pricing/protocol references, verified 2026-10-27: [Z.ai pricing](https://docs.z.ai/guides/overview/pricing), [Z.ai API](https://docs.z.ai/api-reference/llm/chat-completion), [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), [DeepSeek API](https://api-docs.deepseek.com/api/create-chat-completion/). The default catalog uses `glm-5.3-flash` and `deepseek-flash`, with reported cached-token usage. GLM uses low reasoning effort; output maxima include the provider's reported completion usage.

Costs are token-rated estimates, not reconciled invoices. DeepSeek uses the verified peak tariff as a conservative upper estimate; off-peak invoices may be lower. Unresolved reservations are separate from settled estimates, and cancellation does not promise a billing refund. Do not infer that real billing has been verified from fake-provider tests.
