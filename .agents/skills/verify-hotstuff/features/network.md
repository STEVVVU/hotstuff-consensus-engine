## Sub-features

Four loopback replicas, one client, ECDSA certificates and round-robin leaders.

## How to get to it (user POV)

Build hotstuff and use its run command without remote host flags.

## Driving it with Python

Run tools/verify.py as documented in the skill. Confirm nonzero throughput, identical nonzero final execution counts and order hashes for all four replicas, and successful controller shutdown.

## Gotchas

One process hosts the upstream local worker and all four replicas. This path proves socket traffic, not process isolation, crash recovery or durable voting. Leader failure is covered separately by Twins partitions.
