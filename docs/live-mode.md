# Live execution status

Live execution is gated, not implemented as a fallback to a different runtime. `agora-v2 run` validates an explicit positive `--budget-usd`, three allowlisted bootstrap entries spanning two families, and known prices, then reports the unverified author-package integration. It submits no provider request.

The assessment in `rlm-adapter-assessment.md` documents the controls still needed. Do not populate example configuration with guessed model identifiers/prices or claim that offline synthetic usage verifies provider accounting. No credentials were copied from v1. No paid requests or live smoke tests have run.

To finish live mode: integrate the authors' root/leaf backend dispatch with the gateway; verify reservations and cancellation under their execution model; select two model families with current official identifiers/prices; implement and lock provider adapters; run one explicitly capped usage/subcall smoke, then the full demo. Offline behavior and isolation can be reviewed independently.
