# Agora v2

Agora v2 is a local, bounded swarm of peers that organize work through a shared SQLite ledger. Agents claim tasks, publish evidence, independently review artifacts, and can propose temporary helpers. The browser observer shows those recorded actions around a common message board.

The default live setup uses **GLM 5.3 Flash, DeepSeek V4.1 Flash 1017, and MiniMax M3.1 Flash on Fireworks**, with one `FIREWORKS_API_KEY`. Generated code runs through the pinned authors' RLM engine in isolated Docker containers. The sibling v1 implementation is preserved for comparisons.

## 1. Install and prepare the project

Run all commands from the v2 repository root. On the original development machine:

```sh
cd /Users/chamindawijayasundara/Documents/learning_102/self_organizing_agents_v2.0
```

Adjust that path if your checkout is elsewhere.

| Requirement | Needed for |
| --- | --- |
| `uv` on your PATH | Installing dependencies and running the CLI |
| Python 3.12 recommended; 3.13 also supported | The host application; Python 3.14 is not supported |
| A browser | Viewing the HTML dashboard |
| Docker Desktop or a working Docker Engine | Live runs, smoke tests, and container integration tests |
| A Fireworks account, API key, and available inference credits | Paid model calls |
| Node.js, optional | JavaScript replay regression tests; these tests skip when Node is unavailable |
| Existing sibling v1 checkout/interpreter, optional | The frozen-v1 integration test and comparison arm |

Check `uv`, provision the preferred Python version if needed, and install the application and development dependencies:

```sh
uv --version
uv python install 3.12
uv sync --python 3.12
uv run agora-v2 --help
```

Use `uv run` for the commands below so they use this project's environment. You do not need to activate `.venv` manually. Docker and provider keys are not needed for the offline demo.

## 2. Try the HTML dashboard without paid calls

Generate a fresh scripted run, then serve it:

```sh
AGORA_DEMO_OUT="runs/demo-$(date +%Y%m%d-%H%M%S)"
uv run agora-v2 replay --out "$AGORA_DEMO_OUT"
uv run agora-v2 observe "$AGORA_DEMO_OUT" --port 8767
```

Open **http://127.0.0.1:8767** manually in your browser. The terminal stays occupied while the observer serves the page. Use another terminal for later commands, or press **Ctrl-C** to stop this observer.

The replay starts automatically. It shows three bootstrap peers, an evidence finding, a proposed and independently admitted helper, task claims, published artifacts, independent reviews, helper retirement, and a final memo. Expected CLI result: `"status": "completed"` with `"mode": "scripted"` and `"synthetic_cost": true`.

This is a **scripted demonstration of real ledger transitions**, with synthetic models and costs. Its model identities are labeled as scripted; it does not call the configured Fireworks models or demonstrate live model quality.

If port 8767 is already occupied by an earlier preview, reuse that page or start this observer on another port, such as `--port 8768`, and open the matching URL.

## 3. Configure Fireworks credentials

Create the local environment file only if it does not exist:

```sh
if [ ! -f .env.local ]; then
  cp .env.example .env.local
fi
```

Open `.env.local` in your editor and fill this setting:

```dotenv
FIREWORKS_API_KEY=your_actual_fireworks_api_key
```

Keep any existing credentials you still need. The default configuration requires only the Fireworks key; direct Z.ai and DeepSeek keys are not required. `.env.local` is ignored by Git and excluded from the Docker build context. Keys remain on the host and are not passed into generated-code containers or the frozen-v1 subprocess.

Live commands below explicitly load `.env.local` with `uv run --env-file .env.local`.

### Default model configuration

[examples/models.example.json](examples/models.example.json) defines the model allowlist and startup roster:

| Config key | Fireworks model ID | Family | Default role |
| --- | --- | --- | --- |
| `glm` | `accounts/fireworks/models/glm-5p3-flash` | GLM | First bootstrap peer |
| `deepseek` | `accounts/fireworks/models/deepseek-v4p1-flash-1017` | DeepSeek | Second bootstrap peer; final checker and semantic leaf default |
| `minimax` | `accounts/fireworks/models/minimax-m3p1-flash` | MiniMax | Third bootstrap peer |

All three use `FIREWORKS_API_KEY` and Fireworks Standard serverless. GLM and MiniMax use low reasoning effort; DeepSeek reasoning is disabled. MiniMax's reasoning remains enabled because this model requires it. Peer responsibilities emerge from the mission and shared work; the bootstrap roster does not assign permanent departments.

Model IDs, family identities, and input/cache/output tariffs are validated against the adapter's catalog. Changing a model ID or price in JSON alone does not add support for an unverified model. For pricing references and accounting details, see [live setup](docs/live-mode.md).

## 4. Build the isolated RLM environment

Start Docker Desktop, or ensure your Docker Engine is running, then check it and build the pinned image:

```sh
docker info
docker build -f sandbox/Dockerfile -t agora-v2-rlms:d04208afbad2 .
docker image inspect agora-v2-rlms:d04208afbad2 --format '{{.Id}}'
```

The first build downloads the base image and pinned dependencies. Reuse the image for subsequent runs. Live execution checks the author-engine revision and refuses a missing or mismatched image; there is no fallback that runs generated code on your host.

## 5. Run a capped paid smoke test

This command makes real Fireworks requests with a **USD 0.10 total cap for this command**:

```sh
AGORA_SMOKE_OUT="runs/fireworks-smoke-$(date +%Y%m%d-%H%M%S)"
uv run --env-file .env.local agora-v2 smoke \
  --models examples/models.example.json \
  --budget-usd 0.10 \
  --out "$AGORA_SMOKE_OUT"
```

The smoke checks reported usage from each configured model, then requires an actual programmatic semantic subcall through the isolated authors' RLM engine. It is an infrastructure check rather than a full business swarm.

Check the terminal JSON or open `$AGORA_SMOKE_OUT/smoke.json`. Success requires:

- `status` is `completed` and `mode` is `live`.
- `semantic_calls` is at least `1`.
- `issues` is empty.
- `cost` reports model calls, settled usage estimates, and any unresolved reservations.

If it fails, read `issues` before starting another paid run. Missing usage or cancellation can leave unresolved liability. Provider errors are not automatically retried.

## 6. Run the real swarm with the live HTML dashboard

After the smoke succeeds, start the evidence-review mission. This is a **separate command with its own USD 1.00 cap**:

```sh
AGORA_LIVE_OUT="runs/fireworks-live-$(date +%Y%m%d-%H%M%S)"
uv run --env-file .env.local agora-v2 run \
  --mission examples/evidence_review/mission.json \
  --models examples/models.example.json \
  --budget-usd 1.00 \
  --out "$AGORA_LIVE_OUT" \
  --watch --port 8766
```

Open **http://127.0.0.1:8766** when the terminal prints the observer URL. The page is served locally; it does not launch a run or collect API keys. The initial peers use GLM, DeepSeek 1017, and MiniMax respectively, and the page follows new ledger events automatically.

The runtime creates helpers only when peers propose and independently admit them. A live run without a helper is valid. The scripted demo's sequence is not imposed on live agents.

With `--watch`, the terminal prints the run result and keeps the observer available after completion. Press **Ctrl-C** to stop the observer once you have finished inspecting it. Interrupting before the run finishes cancels execution rather than merely closing the page; inspect the saved trace and unresolved costs afterward. Closing or refreshing the browser alone does not cancel the run.

Use a fresh output directory for every smoke, replay, live, or comparison command. The timestamped examples avoid reusing previous runs. Do not delete an earlier run just to rerun the command.

### What to click in the dashboard

| Control or panel | What it shows or does |
| --- | --- |
| Swarm graph | Actual joined identities, model families, working/reviewing states, and helper lifecycle. Activity pulses follow recorded events. |
| Agent node or roster card | Opens details: model/provider/family, capability, held task, recorded token usage, spend, latest action, and public board posts. |
| Central **Shared board** node or **Open board** button | Opens full public findings, artifacts, helper requests, and review reasons, like the v1 shared-ledger dialog. |
| Board dialog filters | Filter by author/type, search message and evidence text, and select newest- or oldest-first order. **Close** or **Escape** dismisses the dialog. |
| Inline common message board | A running feed with independent author/type filters. Long posts have **Read full artifact/message** controls. |
| Task board | Open, claimed, in-review, and completed work. Select a card to inspect its objective, dependencies, artifact, and review. |
| Semantic calls | Evidence-analysis subcalls, separate from peer identities; leaves cannot claim tasks or vote. |
| Metrics | Run status, active/total peers, model calls, settled usage estimate, and reserved/unresolved liability. |
| Final memo | The published deliverable and its review status; expand **Original mission** to read the stored brief. |
| Event log | Recorded lifecycle, task, model-accounting, and runtime events. |
| **Pause**, **Step**, **Restart**, speed, and timeline | Inspect recorded events at your own pace. **Restart** rewinds the view; it does not run the agents again. |
| **Latest** | Jumps to the newest event and resumes following updates during a live run. |

Clicking the shared board works with the mouse or Enter/Space when focused. The dialog respects the selected replay moment: later messages and artifacts stay hidden until you advance. During live following, new posts appear as they are recorded. Filters and playback affect only the observer, not the agents.

The mode badge distinguishes **SCRIPTED REPLAY**, **FAKE PROVIDERS · REAL RUNTIME**, and **LIVE MODEL RUN**. Public posts are ledger records, not a transcript of private reasoning. Agent content is displayed as text.

## 7. Inspect results or reopen a previous run

Print a completed trace:

```sh
uv run agora-v2 inspect "$AGORA_LIVE_OUT"
```

Or reopen the observer in a later terminal session, replacing the path with your saved run directory:

```sh
uv run agora-v2 observe runs/fireworks-live-YOUR_TIMESTAMP --port 8766
```

Open **http://127.0.0.1:8766**. Observing an existing run does not make model calls. You can also observe a run in progress from another terminal. A running database snapshot may lack the original brief until the completed trace is exported; the page labels missing information.

| Output | Contents |
| --- | --- |
| `run.db` | Tasks, peers, scope, artifacts, calls, reservations, and append-only events |
| `trace.json` | Exported run status, issues, mission, events, artifacts, cost totals, and final memo |
| `configuration.json` | Live swarm's model configuration and verified execution metadata; no key values |
| `context/` | External context objects and stored intermediate results |
| `smoke.json` | Smoke-test status, semantic-call count, issues, and costs; smoke runs only |

A `completed` result requires the implemented independent checks. Other terminal statuses include `insufficient_evidence`, `budget_exhausted`, `timed_out`, `stalled`, `cancelled`, and `failed`. Check `issues`, reviews, and the final memo rather than inferring success from animation or completed model calls.

## 8. Run automated verification without provider charges

```sh
# Offline application tests; no Docker or keys required.
uv run pytest -q

# Real container and optional frozen-v1 tests; no paid model calls.
uv run pytest -m 'sandbox or v1' -q

# Build the wheel and source distribution into dist/.
uv build
```

Start Docker and build the image from step 4 before the integration suite. To run only container tests without the optional v1 test:

```sh
uv run pytest -m sandbox -q
```

The frozen-v1 test needs the existing `../self_organizing_agents_v1.0` checkout and its `.venv/bin/python`. The pinned v1 revision is `b2bc646aa51b7444a22670283d462b59b7ddde22`; tracked source changes cause verification to refuse that comparison. Do not copy v1's environment or credentials into v2.

Last verified on 2026-10-28: **92 offline tests and 14 container/v1 integration tests passed**, the package built, and desktop/mobile browser checks passed for the dashboard and shared-board dialog. These checks use scripted/fake providers. Paid Fireworks smoke and business-quality verification remain separate operational steps.

## 9. Optional paid architecture comparison

The example executes five architectures across two seed labels: frozen v1, a plain single agent, external context without semantic calls, the dynamic swarm, and a single-root RLM. It requires the Fireworks setup, Docker image, and pinned sibling v1 checkout described above.

```sh
AGORA_COMPARISON_OUT="runs/comparison-$(date +%Y%m%d-%H%M%S)"
uv run --env-file .env.local agora-v2 evaluate \
  --config examples/comparison.example.json \
  --budget-usd 5.00 \
  --out "$AGORA_COMPARISON_OUT"
```

The **USD 5.00 cap covers the entire comparison command**, including all arms, repetitions, and independent judging. With the example's five arms and two seeds, each run receives USD 0.50. The smoke and standalone swarm commands have separate caps; running all three paid examples allows up to USD 6.10 in total requested caps.

Read `report.json` and `report.md` in the comparison directory. Per-run subdirectories retain their traces. Frozen v1 preserves four fixed peers alternating the first two model keys; the dynamic swarm starts all three configured families. These and other enforcement differences are disclosed. Seed labels do not guarantee provider sampling determinism, and small samples establish no architectural superiority. See [comparison details](docs/evaluation.md).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `uv` not found | Install `uv` and ensure its executable is on your shell's PATH. |
| Unsupported Python / import or CLI not found | Use Python 3.12 and rerun `uv sync --python 3.12`; invoke the app through `uv run agora-v2`, not system Python. |
| Missing `FIREWORKS_API_KEY` | Fill `.env.local` and include `uv run --env-file .env.local` on live commands. A key in v1's environment is not loaded automatically. |
| Docker daemon/socket unavailable | Start Docker Desktop/Engine and confirm `docker info` succeeds in the same terminal. |
| Missing or mismatched author image | Build the exact image/tag from step 4. The adapter verifies the pinned engine rather than accepting an arbitrary Python image. |
| Output directory already exists / is not fresh | Choose a new timestamped output path; retain earlier traces for inspection. |
| Address/port already in use | Stop your earlier observer with Ctrl-C or choose another `--port`, then open the corresponding URL. |
| Browser cannot connect | Keep the observer terminal running and use the URL/port it prints. Run `observe` again if you stopped it. |
| Updated UI is missing | Refresh the browser to load the current HTML/JavaScript. |
| HTTP 401/403 or account-access error | Check that the key belongs to Fireworks and the account can access the selected serverless models. |
| HTTP 429/503 | Check account rate limits/credits and provider availability. Requests are not automatically retried; inspect saved costs before starting a new capped run. |
| Unknown model, family mismatch, or tariff mismatch | Check the exact IDs in the model table. Config and the verified adapter catalog must agree; arbitrary endpoints and unverified IDs are rejected. |
| Smoke has no semantic subcall | Inspect `smoke.json` issues. A model response that skips the required leaf call fails the check; it is not reported as success. |
| Run stops before a memo is approved | Inspect status, `issues`, required-task reviews, remaining budget, and call/deadline limits. Choose any new cap deliberately for a fresh run. |
| No helper appears | Helpers are proposed by peers, not guaranteed by the runtime. Use scripted replay to inspect the known helper sequence. |
| Reserved/unresolved cost remains | A submitted request lacked reconciled usage, failed, or was cancelled. It is not treated as free; cancellation does not promise a billing refund. |

## Limits, accounting, and further reading

Default mission policy: USD 1.00 total budget unless overridden by an explicit CLI cap; 480-second wall clock; 40 global model calls; three bootstrap peers; five execution contexts shared by peers and semantic leaves; eight lifetime identities; semantic leaf depth one; two repair attempts per task. Twenty percent of the total model budget is protected for review/finalization. All model calls share the gateway's reservations and spending controls.

Reported costs use provider token/cache usage and verified tariffs. They are estimates, not reconciled invoices. Unknown usage retains unresolved reservations. The business fixture includes provenance and evidence hashes; evaluator-only gold is outside peer/interpreter capabilities and absent from the wheel fixture.

Read [live setup and pricing sources](docs/live-mode.md), [architecture comparisons](docs/evaluation.md), [author integration assessment](docs/rlm-adapter-assessment.md), [implementation status](docs/implementation-status.md), and the [design](docs/superpowers/specs/2026-10-27-dynamic-swarm-design.md).
