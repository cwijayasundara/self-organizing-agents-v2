# Author-package integration assessment — 2026-10-27

The compatibility gap from the first slice is resolved by an explicit isolated adapter, not by relying on upstream budget enforcement.

Upstream is pinned to [revision d04208afbad29ca675ab13478c40ee8bebc84bfe](https://github.com/alexzhang13/rlm/tree/d04208afbad29ca675ab13478c40ee8bebc84bfe), package `rlms` 0.1.3. `sandbox/requirements.lock` pins the source archive SHA-256 and every tested dependency. The base image is pinned by digest. Build explicitly with `sandbox/Dockerfile`; runtime never installs tools or pulls images automatically.

The earlier `scripts/probe_rlms_limits.py` and `rlms-limit-probe.json` remain as historical evidence: the upstream iteration check accepts missing monetary cost and detects overspend after usage. V2 therefore replaces the backend client-factory seam inside the container with a proxy. Every actual root/leaf call is dispatched by the host gateway, with reservation before submission, reported token/cache settlement, global call limits and unresolved cancellation liability.

`AuthorRLMExecutor.reason()` supplies evidence as external REPL variables, passing only metadata and the bounded question to the root model. Generated Python may select slices, compute and invoke `llm_query` / `llm_query_batched`. Final text remains in the external context store with evidence provenance. Root requests use the peer slot; leaves yield the parent slot and acquire from the same pool. Native batch RPC is serialized, which limits concurrency and is disclosed as an execution characteristic. A named `root` alias used from a leaf query still routes as a leaf.

The authors' `environment='local'` runs inside the dedicated isolated container, never on the host. Generated code has no host filesystem, provider credentials, gold answers, Docker socket or unrestricted network. The container has an unprivileged user, read-only root, dropped capabilities, bounded memory/CPU/PIDs/output, scoped tmpfs and a hard wall-clock limit. The bridge grants no ledger or membership capabilities. Provider responses at leaf depth are text, not recursively executed programs.

Real-container tests now exercise the actual package: external context withheld from the initial root prompt, code-mediated semantic calls, batch accounting, one-slot parent handoff, named-model leaf routing, missing usage, global call-cap refusal, active cancellation and teardown. A complete round-robin peer run additionally exercises helper admission, independent review, retirement and a final memo through the real author engine using fake providers within 40 calls.

Actual provider compatibility and invoice reconciliation remain contingent on the user's supplied keys and spend cap. These are operational verification steps; the adapters and capped smoke command are implemented. The earlier hardcoded always-closed live gate has been removed and replaced by revision-verified image preflight and metered dispatch.
