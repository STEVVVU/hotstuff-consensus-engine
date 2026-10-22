## Sub-features

Seeded partition campaign, twin equivocation, initial isolated leader/healing, permanent replica 1 isolation with a stable honest leader 2 and a three-node quorum, no-quorum partition, exact saved replay and honest commit-prefix comparison.

## How to get to it (user POV)

Build cmd/campaign and run with a fresh output directory.

## Driving it with Python

The driver runs campaign then replays the saved scenarios. Inspect each honest node's commit hashes, views and QC participant count. Oracle tests inject conflicting commit evidence to prove rejection.

## Gotchas

Generated scenarios are reproducible but upstream map iteration and fresh keys mean byte-identical execution is not guaranteed. A finite campaign cannot prove universal BFT correctness. Twin identities are excluded from the honest-prefix oracle. Scenario budget and ticks are capped.

Permanent replica 1 isolation with round-robin leaders produced no commits in 300 ticks, saved locally as scratch/quorum-proof/results.json with passed=false. The permanent-isolation progress case changes to stable honest leader 2. Healthy CLI networking and emulated fault journeys are distinct proofs. No general liveness claim applies to repeating faulty-leader schedules.
