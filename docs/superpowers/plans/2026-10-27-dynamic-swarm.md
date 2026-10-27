# Dynamic Swarm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver an independent Agora v2 with a truthful offline swarm demo, bounded RLM-equipped peers, opt-in live execution, a read-only observer, and comparable evaluation arms.

**Architecture:** SQLite is the transactional authority for work, membership, scope, spend, and events. Peers decide business work through validated actions; the runtime only schedules and enforces policy. Evidence remains external to conversations, and generated code executes exclusively in an isolated environment with a controlled semantic-call bridge.

**Tech Stack:** Python 3.12, uv, SQLite, asyncio, pytest, a project-owned model protocol, a Docker execution adapter, and a browser observer served locally. Choose and lock live provider dependencies only after adapter verification.

**Spec:** `docs/superpowers/specs/2026-10-27-dynamic-swarm-design.md`

## Execution status — 2026-10-27

All implementation tasks are delivered. The authors' RLM engine is pinned and verified in the isolated image; live GLM/DeepSeek adapters, capped smoke/live CLI, five executable comparison arms, independent claim judging and repeated-run reporting are implemented. Verification: 74 offline tests and 14 real container/v1 integration tests passed without keys. The conditional paid smoke and live comparison measurements await user-supplied credentials and an explicit spend cap; they have not been fabricated or marked verified. See `docs/implementation-status.md`.

## Global Constraints

- Preserve v1 without modifications or runtime imports. Do not copy credentials, virtual environments, generated run databases, or Git history.
- Python 3.12 with uv; install and run v2 independently.
- Defaults: USD 1.00 total model budget; 480-second wall clock; 40 model calls; three bootstrap peers; five active execution contexts; eight total peer identities; semantic recursion depth one; two repair attempts per failed task.
- Reserve 20 percent of the total model budget for review and finalization. All model calls, including planning and checking, use the same accounting and slot controls.
- Live execution requires an explicit spend cap, known pricing, reported usage, and isolated generated-code execution; no host fallback.
- Offline tests/replay require no credentials; real-sandbox tests are separate and mandatory before claiming isolated execution works.
- Gold answers are evaluator-only. Observer and business evidence access are read-only. No external business mutations, deployment, automatic tool installation, or model training.
- Bootstrap allowlist spans at least two model families. Helpers remain equal peers; semantic leaves have no ledger authority.
- Terminal outcomes: completed, insufficient_evidence, budget_exhausted, timed_out, stalled, cancelled, failed.

## Review Focus

- Stale lease holders cannot publish or release a replacement claim; test fencing tokens in Task 2.
- Late independent scope approval cannot race completion; test scope-version invalidation in Tasks 3 and 7.
- Concurrent calls and cancellation cannot erase liability or spend review reserves on exploration; test Task 5.
- Nested slot handoff cannot deadlock or exceed five contexts, including cancellation while reacquiring; test Tasks 5 and 8.
- Evidence traversal, symlinks, injected instructions, oversized output, and hidden gold cannot expand capabilities; test Tasks 1, 6, and 8.

## Repository and execution notes

The starting repository has only the spec, at commit `4dd9502`. No existing implementation plan or repository AGENTS.md was found. V1 is the sibling `../self_organizing_agents_v1.0`, clean at revision `b2bc646aa51b7444a22670283d462b59b7ddde22` when inspected. Record its status before and after implementation, comparing against that baseline rather than cleaning it.

Use package `agora_v2` and command `agora-v2` to avoid v1 collisions. All paths below are new files. Keep SQL transactions synchronous and short; never await a provider inside a transaction. Use injected clocks and scripted models for deterministic tests. Commit each completed task after its tests pass; do not publish externally.

Review this plan and select native or subagent execution before implementation, as required by the planning skill. At execution time apply the worktree skill, honoring the user's workspace preference. Tasks 1–7 produce the offline vertical slice. Tasks 8–11 finish the isolated/live/observer/evaluation milestone; do not describe the earlier slice as complete RLM functionality.

### Task 1: Installable project and scoped business fixture

**Files:** `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `README.md`, `src/agora_v2/{__init__,mission,evidence}.py`, `examples/evidence_review/{brief.md,manifest.json,provenance.json,sources/**}`, `eval/gold/evidence_review.json`, `tests/test_mission_evidence.py`.

**Interfaces:** Frozen `Limits` and `Mission` dataclasses; `load_mission(path: Path) -> Mission`; `EvidenceStore(manifest: Path).read(ref: str, start: int, length: int) -> str`; `.metadata() -> list[EvidenceMetadata]`. Evidence references identify manifest files and bounded ranges.

- [x] Write tests for exact defaults, invalid limits, immutable brief/rubric, hash mismatch, bounded reads, unknown files, absolute/traversal paths and symlink escape; assert gold is absent from the manifest and peer-visible payloads.
- [x] Run `uv run pytest tests/test_mission_evidence.py -q`; confirm behavior fails before implementation.
- [x] Create installable package with pytest dev tooling. Copy only v1's brief and nine source files; copy gold into evaluator-only location. Record source revision, original paths and SHA-256 values. Preserve the five summary keys and under-450-word memo rubric. Reject evidence links outside the declared root and enforce reads against verified files.
- [x] Run the test command successfully, then `uv build` and verify installed import/entry-point packaging. Commit the task.

### Task 2: Transactional ledger, claims, artifacts, events

**Files:** `src/agora_v2/ledger/{__init__,schema,tasks,artifacts,events}.py`, `tests/test_ledger.py`.

**Interfaces:** `Ledger(path: Path)`; `propose_task(spec: TaskSpec) -> Task`; `claim(task_id: str, peer_id: str, lease_seconds: float) -> ClaimResult`; `publish(claim: Claim, content: str, evidence: list[EvidenceRef]) -> Artifact`; `expire_claims(now: float) -> int`; `events(after: int) -> list[Event]`. Claim includes a unique fencing token. TaskSpec includes objective, deliverable key, schema, evidence requirements, acceptance criteria and dependency IDs.

- [x] Write competing-connection tests: normalized duplicate proposals return one ID; one claimant wins; conflict identifies current holder/expiry; dependencies block claim; expired token cannot publish; artifact and event writes commit atomically. Reject dependency cycles and missing IDs.
- [x] Run `uv run pytest tests/test_ledger.py -q`; confirm failure.
- [x] Implement schema/version metadata and atomic transactions, using SQLite constraints and conditional updates. Store append-only events with monotonic sequence, actor, type and structured payload; artifacts are immutable versions. A review records reviewer identity and the exact artifact version.
- [x] Rerun ledger tests successfully and commit.

### Task 3: Independently reviewed versioned scope

**Files:** `src/agora_v2/ledger/scope.py`, `tests/test_scope.py`.

**Interfaces:** `propose_scope(author: str, required_task_ids: list[str], base_version: int) -> ScopeProposal`; `review_scope(proposal_id: str, reviewer: str, approve: bool, reason: str) -> ScopeDecision`; `completion_snapshot() -> CompletionSnapshot` containing accepted scope version and required artifact versions.

- [x] Test unreviewed initial scope blocks final claim, self-review fails, stale amendments fail, accepted amendment updates final dependencies atomically, and critical rejected changes remain unresolved. Optional tasks do not block; promoting them requires reviewed scope amendment. A late amendment invalidates a prior completion snapshot.
- [x] Run `uv run pytest tests/test_scope.py -q`; confirm failure.
- [x] Implement scope proposals and approvals against active identities, version checks and transactional dependency changes. Bind review and completion to exact versions.
- [x] Rerun scope/ledger tests successfully and commit.

### Task 4: Peer membership and retirement

**Files:** `src/agora_v2/{profiles,membership}.py`, `src/agora_v2/ledger/membership.py`, `tests/test_membership.py`.

**Interfaces:** `HelperProposal(requester, capability, task_ids, model_key, budget_usd, evidence)`; `Membership.propose(proposal) -> str`; `.review(proposal_id: str, reviewer: str, approve: bool) -> MembershipDecision`; `.retire(peer_id: str, reason: str) -> None`. Profiles expose allowlisted model key, family and capabilities.

- [x] Test three bootstrap peers spanning two families; self-approval, unknown capabilities/models, duplicate helpers and unfunded proposals fail; five active/eight lifetime bounds hold under concurrent admission. Retirement cannot strand required reviews or bootstrap held work; helper retirement releases leases without reusing identities or resetting spend.
- [x] Run `uv run pytest tests/test_membership.py -q`; confirm failure.
- [x] Implement deterministic admission after independent usefulness review; store reasons, task links, evidence, requested budget and profile. Requested budget is a constraint within shared funds, not newly created money. Reject unavailable review capacity and emit actual lifecycle events.
- [x] Rerun membership tests successfully and commit.

### Task 5: Model gateway, accounting, execution slots

**Files:** `src/agora_v2/models/{__init__,protocol,scripted,gateway}.py`, `src/agora_v2/{budget,slots}.py`, `tests/{test_budget,test_slots,test_models}.py`.

**Interfaces:** `Model.complete(request: ModelRequest) -> ModelResponse` async; response has content, input/output usage and request ID. `Gateway.call(request, purpose, execution) -> ModelResponse`; `ExecutionSlots.enter(kind, identity)` async context manager; `execution.yield_to_child()` async context manager. Money uses integer microdollars and conservative rounding. Scripted pricing is explicitly synthetic.

- [x] Test concurrent reservations never exceed USD 1.00; exploration stops at USD 0.80 while review can use the remaining USD 0.20; calls beyond 40 fail. Unknown pricing, missing/invalid usage and oversized prompts fail visibly. Cancellation after submission retains unresolved reservation; reconciliation is idempotent.
- [x] Test five-slot peak across peers/leaves, waiting parents yield, nested leaves cannot recurse, and cancellation during slot handoff leaks no permits or identities.
- [x] Run `uv run pytest tests/test_budget.py tests/test_slots.py tests/test_models.py -q`; confirm failures.
- [x] Implement one gateway for every model dispatch, reserving bounded prompt plus maximum output before submission, then settling reported usage. Usage exceeding reservation is recorded as accounting failure, never clipped. Persist call lifecycle and settled/unresolved amounts. Membership admission consults current funds and context availability from this task.
- [x] Rerun tests successfully and commit.

### Task 6: External context and validated peer actions

**Files:** `src/agora_v2/context/{__init__,store,protocol}.py`, `src/agora_v2/{actions,peer}.py`, `tests/{test_context,test_peer}.py`.

**Interfaces:** `ContextStore.put(value, evidence) -> ContextHandle`; `.preview(handle, max_chars: int) -> Preview`; `.slice(handle, start, length) -> ContextHandle`. `Peer.step(snapshot: PeerSnapshot) -> StepResult` async. Typed actions cover proposing/claiming tasks, publishing findings/artifacts, independent reviews, scope/membership proposals/reviews, context operations and retirement. Runtime validates actor authority on every action.

- [x] Test external handles retain full values while previews truncate with explicit references; citations survive slicing and assembly. Malformed actions, invented handles, self-approval, injected evidence instructions and oversized outputs cannot mutate authority. Model errors produce bounded repair feedback, at most two repairs per task.
- [x] Run `uv run pytest tests/test_context.py tests/test_peer.py -q`; confirm failure.
- [x] Implement the peer loop reading brief, rubric, metadata and ledger state. Models propose work and select claims; scheduling never chooses business strategy. Publish shared findings promptly. Use gateway for planning and review. Define `ContextExecutor.execute(code: str, handles: list[ContextHandle], execution) -> ExecutionResult` as an injected async protocol; scripted tests use a named fake until Task 8 supplies isolation.
- [x] Rerun tests successfully and commit.

### Task 7: Offline runtime, independent outcome checks, trace export

**Files:** `src/agora_v2/{runtime,outcome,cli,trace}.py`, `src/agora_v2/business/evidence_review.py`, `examples/evidence_review/replay.json`, `tests/{test_runtime,test_outcome,test_offline_demo}.py`.

**Interfaces:** `Runtime.run(mission: Mission) -> RunResult` async; `.cancel() -> None`; `OutcomeChecker.check(snapshot: CompletionSnapshot) -> OutcomeDecision`; `export_run(ledger: Ledger, destination: Path) -> Path`. Commands: `agora-v2 replay --out PATH`, `agora-v2 inspect PATH`.

- [x] Write end-to-end scripted test with three peers, evidence discovery, peer-proposed helper, independent admission/review, actual claims/artifacts, helper retirement and a cited memo. Assert events come from ledger mutations, not UI animation. Assert summary fields use v1 semantics without giving gold to peers.
- [x] Parameterize all seven terminal outcomes, in-flight cancellation, lease expiry, no-progress stall, scope amendment during outcome checking and unavailable evidence. Require no held leases/slots or local resources at termination; unresolved billing remains disclosed.
- [x] Run `uv run pytest tests/test_runtime.py tests/test_outcome.py tests/test_offline_demo.py -q`; confirm failure.
- [x] Implement fair mechanical episode scheduling, deadline enforcement, drain/cancel/cleanup and immutable trace exports with configuration, hashes, scope versions and artifacts. Completion requires accepted scope, reviewed required versions, deterministic citation/summary checks and independent rubric coverage check against original brief. Gold correctness belongs only to evaluation. Stop admission/claims before draining; record teardown failures truthfully.
- [x] Run tests and `uv run agora-v2 replay --out /tmp/agora-v2-demo`; verify labeled scripted output and inspect export. Commit. This is the first runnable offline slice.

### Task 8: Real isolated RLM execution and author-package assessment

**Files:** `src/agora_v2/context/{docker,bridge}.py`, `sandbox/{Dockerfile,worker.py}`, `tests/{test_bridge,test_sandbox}.py`, `docs/rlm-adapter-assessment.md`.

**Interfaces:** Docker implementation of `ContextExecutor`; sandbox bridge exposes bounded `read_context`, `store`, and async `semantic_call(model_key, context_handles, instruction, max_output_tokens) -> ContextHandle`. Leaves receive no ledger or membership operations and cannot call the bridge recursively.

- [x] Write real-container tests executing generated Python that selects evidence, computes a value and invokes a scripted model programmatically. Assert full results stay external, citations persist, leaf depth is one, global slots/accounting apply, and missing sandbox causes refusal.
- [x] Test no credentials, host files, gold, Docker socket or unrestricted network are exposed; evidence is read-only; scratch is scoped; runaway CPU/output/time and cancelled children are terminated. The controlled host bridge validates every request and never accepts arbitrary host paths or methods.
- [x] Run `uv run pytest tests/test_sandbox.py -m sandbox -q`; confirm failures. Keep sandbox marker excluded from default offline suite and report unavailable Docker explicitly.
- [x] Implement per-run constrained containers with unprivileged user, read-only root, dropped capabilities, no network, bounded resources/output, evidence-only mount and scratch. Bridge through validated framed stdin/stdout; credentials/providers stay in host gateway. Tear down container and scratch in all exits.
- [x] Inspect current official authors' `rlms` API/source through an adapter experiment. Document tested revision, usage reporting, cancellation, recursion, isolation, compatibility and dependency decision. Pin only if controls pass; otherwise explicitly report the integration gap and keep live RLM unavailable pending review rather than substituting silently.
- [x] Run bridge and real-sandbox tests successfully, including programmatic semantic subcall; commit assessment and implementation.

### Task 9: Live adapters and opt-in smoke

**Files:** `src/agora_v2/models/live.py`, `examples/models.example.json`, `tests/{test_live_adapter,test_live_smoke}.py`, `docs/live-mode.md`; update gateway/CLI/package dependencies.

**Interfaces:** `LiveModel` implements the Task 5 protocol. Command `agora-v2 run --mission PATH --models PATH --budget-usd AMOUNT --out PATH`; explicit `--live` marker for smoke tests.

- [x] Test omitted cap, missing price/usage, unknown model, one-family bootstrap config, unavailable isolation and failed author-adapter gate all refuse dispatch. Use recorded mock responses for provider parsing, retry liability and streaming/cancellation behavior.
- [x] Run `uv run pytest tests/test_live_adapter.py -q`; confirm failure.
- [x] Verify identifiers, current official pricing and usage semantics for two selected model families; record verification date/source and lock adapter versions. Secrets come from environment only, never copied from v1 or passed into sandboxes. Route all live operations through gateway; do not invent activity when no helper is proposed.
- [x] Rerun offline adapter tests. When live credentials and an explicit cap are supplied, run an opt-in smoke proving reported usage and one bounded semantic subcall. Until then record live verification as pending. Commit.

### Task 10: Read-only browser observer and truthful replay

**Files:** `src/agora_v2/observer/{__init__,server}.py`, `src/agora_v2/web/{index.html,app.js,style.css}`, `tests/test_observer.py`; update CLI/README.

**Interfaces:** `agora-v2 observe RUN_PATH --port 8765`; GET-only `/api/snapshot` and `/api/events?after=SEQ`; same schema for active ledger and exported replay.

- [x] Test mutation requests fail, cursors preserve event order, peer states and membership reasons match ledger, semantic nodes have no voting/claim controls, and scripted labeling persists throughout playback. Treat artifact/evidence text as untrusted; render as text and reject path traversal.
- [x] Run `uv run pytest tests/test_observer.py -q`; confirm failure.
- [x] Implement local read-only observer showing joining/ready/working/waiting/reviewing/draining/retired/failed states, task claims, findings, proposal decisions, scope, calls, settled/unresolved cost and final artifacts. Replay consumes captured real events with playback controls; live view adds no synthetic transitions.
- [x] Rerun tests and inspect browser at desktop/mobile sizes using scripted run, including retired helper and final memo. Commit.

### Task 11: Comparable evaluation arms and final acceptance

**Files:** `src/agora_v2/eval/{__init__,contracts,arms,score,runner}.py`, `tests/test_evaluation.py`, `docs/evaluation.md`; update CLI/README.

**Interfaces:** `Arm.run(input: EvaluationInput) -> ArmResult` async, with brief, evidence manifest, rubric, model keys, limits and seed; gold is excluded. `score(result: ArmResult, gold: Path) -> EvaluationScore`. Command `agora-v2 evaluate --config PATH --out PATH`.

- [x] Test adapters for frozen v1 export/subprocess, plain single agent with tools, external context without semantic calls, dynamic swarm RLM, and single-root RLM ablation. Spy arms must never receive gold. Require equal configured evidence/rubric/budget/deadline and explicit enforcement-difference metadata.
- [x] Run `uv run pytest tests/test_evaluation.py -q`; confirm failure.
- [x] Implement evaluator-only five-field correctness, citation resolution/coverage, unsupported-claim review, status, settled/reserved cost, latency, peer/membership/call counts and execution errors. Separate deterministic scores from model-judged metrics and their costs. Record seeds, repetitions, pricing/model revisions and missing metrics; imported v1 results disclose missing controls.
- [x] Rerun evaluation tests, `uv run pytest -q`, real-sandbox suite and `uv build`. Re-run scripted CLI plus observer checks; verify no v1 status changes and no runtime imports. Document any unperformed live checks and avoid superiority claims from a single demo. Commit final docs and results.

## Plan self-review

Coverage: Tasks 1–3 implement immutable mission, evidence, ledger and reviewed scope; 4–5 implement bounded membership, shared slots and accounting; 6–8 implement peer behavior, outcomes, cleanup and external-context semantic execution; 9–11 implement live mode, observer and comparisons. The five review-focus failures each have explicit owning tests. Live integration remains conditional on real compatibility evidence and an explicitly supplied cap; an offline demo is not evidence of live accounting or isolation. Market-entry/scale studies remain follow-up work as specified.
