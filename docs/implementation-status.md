# Implementation status — 2026-10-27

The first offline slice is implemented on `feat/dynamic-swarm`. The complete design is not yet delivered.

Implemented: independent package and copied evidence fixture/provenance; atomic SQLite tasks/claims; fencing; independently reviewed versioned scope and artifacts; bounded helper lifecycle; conservative model reservations and unresolved billing; shared execution slots; validated peer actions and external context; scripted replay; outcome checks; every terminal status and shutdown traces; real Docker context/semantic-call bridge; read-only browser observer; held-out export scoring.

The replay is scripted, its model usage/pricing synthetic, and its outcome-check response scripted. It exercises actual ledger transitions. The separate Docker tests exercise actual isolated generated Python and programmatic fake-model calls. Neither establishes autonomous live behavior or architectural superiority.

Remaining: author-package root/leaf integration with gateway reservations, shared scheduling, cancellation and isolation; provider adapters and current model/pricing selection; explicitly capped live usage/subcall smoke; actual baseline runners, independent claim judging and repeated architectural comparisons. The live preflight always refuses dispatch until integration is verified. Export scoring marks missing arms `not_run` and unmeasured claim judgments `null`.

Verification:

- Offline suite: 53 passed; three real-container tests excluded by the default marker.
- Real Docker suite: three passed, including active cancellation, submitted liability, no host credentials/gold, no unrestricted network, read-only root, output/timeout limits, shared-slot handoff and container removal.
- Fresh scripted CLI replay: completed with no issues, 20 metered synthetic model calls and independently recorded helper decisions/reviews.
- Export scorer: five business fields correct; four missing architectural arms explicitly not run.
- Wheel/sdist build passed. Built wheel installed without dependencies in a fresh `/tmp` environment; replay completed from `/tmp`. Wheel includes fixture, observer assets and worker; no gold files.
- Browser inspected at desktop and emulated 390×844 viewport; document width equals 390 pixels. Start/Latest controls moved between 0 and 128 actual events.
- V1 Git status remains clean at the original inspected revision.

Fresh review reproduced five Important defects: stale final reapproval, unusable review reserve, cancelled parent reacquisition, gold reachable under custom evidence roots, and malformed-summary scoring. All were fixed with failing-then-passing regression tests. Two observer findings were regraded Important for truthful replay: completed database status and showing a future memo at an earlier cursor. Both were fixed with regressions. Final inspection also added bounded artifact previews and no-progress stopping, with regression tests. No review minors remain deferred.

Decisions and costs if wrong:

1. Use the supplied checkout on a new feature branch instead of an unrequested worktree. Cost: less filesystem isolation.
2. Verify the CLI entry point in Task 7, where behavior was defined. Cost: later entry-point defect detection; installed-wheel replay now verifies it.
3. Store helper budgets as integer microdollars rather than floating USD. Cost: external callers must convert units.
4. Grant sandbox evidence through handles rather than a host directory mount. Cost: code expecting a `/data` filesystem API must adapt.
5. Keep live author-package integration gated after the upstream limit-method probe. Cost: live delivery is delayed; the separate Docker mechanism is explicitly identified.
6. Continue independent observer/export-scoring work while live integration remains pending. Cost: this slice cannot run live comparisons.
