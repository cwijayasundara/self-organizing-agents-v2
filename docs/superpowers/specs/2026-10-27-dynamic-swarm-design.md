# Agora v2: small dynamic swarm with RLM context processing

Date: 2026-10-27
Status: proposed design for written review; implementation has not started.
Target repository: `/Users/chamindawijayasundara/Documents/learning_102/self_organizing_agents_v2.0`

## Intent and agreed direction

Demonstrate a few agents organizing themselves around a business problem, creating useful temporary capacity, publishing reviewed evidence, and shutting down. Preserve v1's fixed-roster implementation without modifications. The user's latest clarification selects a visible swarm rather than one central agent with hidden model calls.

Three bootstrap peers and a maximum of five active execution contexts are proposed demo defaults. These numbers are implementation assumptions, not user-specified requirements. Initial peers are generalists with different starting lenses, not permanent departments. Their roles and work emerge from the brief and findings. No business supervisor assigns work or writes the strategy for the others.

RLM is the context-processing mechanism inside peers. The combination of decentralized peer coordination and RLM execution is an experimental hybrid, not a reproduction of the original single-root RLM architecture or a proven performance improvement.

## Approaches considered

1. Small dynamic peer swarm with RLM-equipped peers (selected): preserves the user's demonstration goal and allows bounded temporary helpers; requires shared task, membership, and cost controls.
2. One root RLM with temporary calls: simpler accountability and less coordination, but does not demonstrate equal peers self-organizing; retained as an evaluation arm.
3. A generated roster fixed at startup: simpler lifecycle implementation, but cannot demonstrate adaptation after discovering new evidence; retained as a baseline.

## First milestone and exclusions

Deliver a local, read-only business-evidence demonstration, offline scripted replay, live provider mode, a browser observer, and architecture comparisons. Use the four-day-week evidence review as the first business example. Market-entry and scaled evidence collections follow after the vertical slice works.

No external business mutations, cloud deployment, automatic tool installation, model training, distributed worker cluster, or arbitrary permission generation. Live use is opt-in and bounded by an explicit spend limit. Offline tests and replay require no credentials. Do not copy v1 credentials, virtual environment, generated run databases, or Git history.

## Architecture and ownership

The new repository owns its runtime and does not import v1 at execution time. Python 3.12 with uv is the proposed baseline. A project-owned model interface supports scripted fakes and live adapters. Evaluate the authors' `rlms` package through an adapter before pinning a dependency; verify actual provider accounting, cancellation, recursion limits, and execution isolation. Do not silently substitute a different mechanism if the integration lacks these controls.

Components:

- Mission: immutable original brief, acceptance rubric, read-only evidence manifest, and limits.
- Ledger: SQLite tasks, dependencies, claims, artifacts, findings, membership proposals, profiles, spend reservations, and append-only events.
- Peer loop: reads shared state, proposes work, claims an available task, processes evidence, publishes, and reviews another peer's work.
- Context engine: external evidence objects and intermediate variables; bounded previews; code-mediated semantic subcalls; evidence references preserved in results.
- Runtime: admits membership proposals, schedules episodes, enforces limits, repairs expired claims, and drains/cancels execution. It does not select business strategy or assign tasks to agents.
- Outcome checker: verifies acceptance coverage and final artifact state independently of the peer that produced it.
- Observer: reads events and artifacts; never changes the run.

## Bootstrap and self-organization

Launch three peers from a configured allowlist covering at least two model families. Reuse v1 provider configuration formats where useful, but verify provider identifiers and prices before live runs. Suggested initial lenses: evidence/quantities, source credibility, and operations/contradictions. Lenses guide attention without fixing ownership.

Start with the brief, evidence manifest, and a required final-deliverable task. Peers propose supporting tasks with objectives, output schemas, evidence requirements, dependencies, and acceptance criteria. Task creation is atomic and deduplicated by normalized deliverable identity. Peers claim work themselves using leases; failed claims return actionable contention information.

The final task cannot be claimed until an initial scope proposal has been independently reviewed. A peer cannot approve its own scope proposal. Critical additions amend a versioned scope and update dependencies transactionally. Required scope changes need independent review and cannot silently disappear on rejection. Optional exploration never blocks completion unless promoted through this process.

The immutable brief and original rubric remain available to the outcome checker. Completing generated tasks alone does not establish business success.

## Dynamic membership

A peer proposes a helper with a concrete missing capability or independent evidence partition, associated task IDs, allowed model key, requested budget, and evidence references explaining the need. A different peer reviews usefulness; deterministic admission checks enforce capabilities, duplication, available review capacity, slots, total identities, and shared budget.

Admitted helpers join the same ledger as peers and claim tasks; the requester does not gain authority over them. The initial prototype caps membership at five active contexts and eight identities over the whole run, preventing unlimited replacement churn. Bootstrap peers may retire only when no held work remains and the remaining team can review pending artifacts. Helper retirement releases leases and records a reason; no identity is reused to reset spending.

Distinguish a peer from a semantic subcall: peers claim and review shared work; semantic calls analyze supplied evidence and return results without ledger authority. Both consume the same global execution-slot pool, so recursive calls cannot invisibly exceed the five-context cap. A peer waiting on a child yields its execution slot while retaining its membership identity, preventing nested-call deadlocks.

## RLM behavior

Each peer can access evidence through external variables/handles without initially copying the corpus into its conversation. It can inspect metadata, select slices, execute calculations, and invoke a model from interpreter code over selected evidence. Large results stay in external storage; only bounded previews and references return to the peer conversation. Final artifacts can be assembled from stored variables.

Initial maximum semantic recursion depth is one: peers may call leaf models; leaves cannot spawn more calls. Direct solving and code-only computation remain valid paths. A loop of ordinary file reads followed by a manually written summary must not be labeled RLM unless external context and programmatic model subcalls are genuinely exercised.

Execute generated code in a configured isolated environment. No host execution fallback in live mode. Supply only the evidence mount, scoped scratch space, and controlled capability bridges. Provider credentials stay outside generated-code execution. Evidence and peer messages are untrusted data, not permission-bearing instructions.

## Budget, limits, and termination

Proposed demo defaults: USD 1.00 total model budget, 480-second wall clock, 40 model calls across the entire run, three bootstrap peers, five active contexts, eight total peer identities, semantic recursion depth one, and at most two repair attempts per failed task. All defaults are visible and configurable within policy.

Reserve a conservative request cost before dispatch using bounded prompt size and maximum output, then settle against reported usage. Refuse dispatch if reservations plus settled spending exceed the cap. Include planning, reviews, leaf calls, retries, and outcome checking. Unknown pricing or missing usage is an accounting error; do not report it as zero cost. Reserve 20 percent of the model budget for review and finalization; this is part of the total, not extra capacity.

Provider billing for a submitted request may complete after local cancellation. Report settled spend and unresolved reservations separately; never promise that cancellation reverses billing.

Terminal outcomes: completed, insufficient_evidence, budget_exhausted, timed_out, stalled, cancelled, or failed. Completed requires independently approved final scope, reviewed required artifacts, passing deterministic checks, and a checked final deliverable. Completion is checked at a ledger scope version; new accepted critical work invalidates a previous completion candidate.

Shutdown first closes admission and new work claims, drains bounded in-flight work, releases unfinished leases, cancels remaining calls, settles or exposes outstanding reservations, tears down execution environments, and records final state. Persist artifacts, configuration, evidence hashes, accepted scope versions, and events for replay; scratch state is disposable.

## Demonstration and observer

Show peers around the shared ledger, with actual states: joining, ready, working, waiting, reviewing, draining, retired, and failed. Show task claims, evidence findings, membership proposals/decisions, model subcalls, scope changes, spend, and final results. Separate semantic-call nodes visually from voting/claiming peers. Explain creation and retirement reasons in plain language.

Provide deterministic scripted replay that reliably demonstrates three initial peers, an evidence discovery, an admitted helper, independent review, and retirement. Label replay clearly as scripted; do not present it as autonomous live behavior. Live mode creates helpers only when justified; a run without helper creation is valid and must not animate fabricated activity.

The first business fixture copies the v1 evidence room, brief, and gold answer into v2 with provenance and source revision recorded. Gold answers are accessible to the evaluator only, never mounted in any peer or interpreter environment. Include evidence citations in the final memo and validate the summary fields using the same business semantics as v1. Three bootstrap peers is a deliberate change from v1's four-peer example.

## Evaluation

Four arms: frozen v1 fixed peers; plain single agent with tools/skills; external-context execution without semantic subcalls; small dynamic swarm with RLM-equipped peers. Additionally run a single-root RLM ablation when comparing whether peer coordination adds value beyond recursion.

Keep evidence, business rubric, model selections where applicable, total budget, deadline, citation checks, and output requirements comparable. V1 runs externally through a subprocess/export contract or reads existing exported results; no changes to v1. Record any unavoidable enforcement differences. The gold answer is held out in every arm.

Report business-field correctness, evidence coverage, unsupported claims, completion status, total settled/reserved cost, latency, number of peers, membership changes, model calls, and execution errors. Repeat live tasks across seeds/runs; one visually successful demo establishes behavior, not superiority. Small fixtures demonstrate mechanics; scale studies are required to assess RLM context benefits.

## Verification and acceptance

Offline tests cover concurrent claims and deduplication, scope review and amendments, five-context enforcement across peers/leaves, review-family availability during retirement, cost reservations under concurrency, hidden gold data, evidence path isolation, malformed model output, failed subcalls, cancellation, and shutdown cleanup.

An integration test uses fake models to complete the business fixture with actual ledger transitions and externally held context. A separate execution-environment test exercises a real sandbox and programmatic model-call bridge using fake model responses. Replay verifies events reflect those real transitions. Optional live smoke runs verify provider usage and one bounded semantic subcall before a complete demonstration.

Acceptance: v1 Git status remains unchanged; v2 is independently installable; offline tests pass without keys; scripted replay truthfully displays membership changes; live mode requires an explicit spend cap; recursive calls cannot evade slots/accounting; final outputs cite evidence and disclose unresolved issues; every termination path releases local execution resources and preserves its trace.

## Delivery sequence

1. Written spec review and implementation plan.
2. Independent repository, ledger, scoped evidence, fake-model peer loop, and offline demo fixture.
3. Bounded membership and scope changes, accounting, and real isolated context execution.
4. Observer and truthful replay; live adapter smoke verification.
5. Business-demo run and architecture comparisons, with measured limitations documented.

## Research basis

- RLM definition and mechanisms: https://arxiv.org/html/2512.24601v3#S2
- Author explanation distinguishing context decomposition: https://alexzhang13.github.io/blog/2025/rlm/
- Official implementation and environment choices: https://github.com/alexzhang13/rlm
- Conditional case for consolidating agent loops: https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop
- Interpreter-based orchestration across configured agents: https://docs.langchain.com/oss/python/deepagents/dynamic-subagents

These sources motivate the experiment. The decentralized RLM-equipped swarm and proposed defaults are project design decisions, not results established by those sources.
