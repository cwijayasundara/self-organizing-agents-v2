# RLM adapter assessment — 2026-10-27

Upstream: https://github.com/alexzhang13/rlm/tree/d04208afbad29ca675ab13478c40ee8bebc84bfe
Package metadata at this revision says `rlms` 0.1.3. No rlms dependency is pinned in v2.

The source was fetched into `/tmp/agora-v2-rlm-assessment` for inspection. `scripts/probe_rlms_limits.py` executes the extracted upstream `_check_iteration_limits` method with fake usage objects. `rlms-limit-probe.json` records the result. This is a narrow behavior probe, not a successful whole-package integration or provider billing test.

The upstream public loop checks budget after each iteration using `usage.total_cost or 0.0`. The probe confirms missing cost passes that check, while already incurred overspend is detected afterwards. V2 needs conservative reservation before every dispatch and must retain missing usage as unresolved liability. Wrapping only `RLM.completion` cannot enforce those requirements for its internal calls.

`max_depth=1` is available. The loop's `max_timeout` checks occur between iterations; an adapter still needs cancellation of active provider calls and isolated execution. Upstream LM handling uses threaded servers and a separate batch semaphore. Those do not automatically participate in v2's shared peer/leaf slot handoff. A whole adapter must route every root/leaf request through the gateway and verify cancellation and container teardown.

Decision: the author-package adapter compatibility gate remains closed. No live run can bypass it by choosing a local environment or by labeling v2's separate context executor an author-package integration. The project-owned Docker executor is an explicit experimental mechanism, exercised with fake models: a real isolated Python program reads external context, computes a result, invokes a semantic leaf through the gateway, and stores cited output. This is useful infrastructure, not evidence that the authors' package has passed integration.

Real Docker tests passed for read-only root, lack of host paths/gold/provider credentials, programmatic leaf call, one-slot parent handoff, output limits, runaway termination, and removal of execution containers. Image used: `python:3.12-slim`, digest `sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f`. Image provisioning is explicit; executor uses `--pull=never`. Sandbox access to evidence is through granted handles, without a host evidence directory mount.

Remaining gate work: integrate the upstream root/leaf backend seam with the gateway; verify actual provider usage and conservative request bounds; verify active cancellation; prove shared slots across author-package batches; run the adapter inside the configured isolation boundary. Live mode and live comparison arms remain unavailable until those checks pass.
