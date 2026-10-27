# Evaluation status and export contract

`agora-v2 evaluate --config CONFIG --out DIRECTORY` scores existing exports for five named arms: `frozen_v1`, `plain_single`, `external_context`, `dynamic_swarm`, `single_root_rlm`. It does not yet execute those architectures. Missing exports are `not_run`, and a scripted export is labeled mechanics-only regardless of its arm slot.

Configuration is JSON with `mission`, `gold`, `seeds: [0]`, and `exports: {"dynamic_swarm": "/path/to/trace.json"}`. Relative paths resolve against the config file. An export describes one recorded run; it cannot be reused to fabricate repeated seeds. Evaluate separate exports for real repeated runs. The evaluator alone receives the gold path; arm inputs contain only brief, rubric, manifest, limits and seed. Gold must remain outside the actual evidence root and must not alias a manifest file.

Exports use `format_version: 1`, `status`, `mode`, `final_memo`, `cost: {settled_micro, unresolved_micro, calls}`, `latency_seconds`, `peers`, `events`, `brief`, `rubric`, `limits`, and `evidence_hashes`. V1 can be represented by an exported wrapper of this schema outside its repository. Missing fields and unavoidable enforcement differences must be disclosed; model revisions are optional metadata and absence is retained. No v1 subprocess or model request is invoked by export scoring.

The scorer reports five-field correctness, valid cited-file coverage, output-format/citation errors, reported cost/latency, identity count, membership transitions and recorded execution errors. Coverage counts distinct cited evidence files, not semantic support. Unsupported claims remain `null` because this deterministic scorer does not independently judge every claim. Missing imported accounting stays unknown, never zero. A scripted outcome checker is not a live evidence judge.

The first replay fixture scores 5/5 expected business fields, exercising the pipeline. This is not an architectural comparison or evidence of superiority. Provider-backed baseline runners, author-package RLM integration, matched model policies, current price verification, independent claim judging, and repeated live comparisons remain pending.
