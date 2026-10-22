---
name: verify-hotstuff
description: Build and drive the local HotStuff CLI and bounded Twins campaign, preserving commit evidence.
---

## Launch

Use Go 1.27.3 or newer with GOTOOLCHAIN=local and CGO_ENABLED=0. Set GOMAXPROCS=2. Build with `go build -p 2 -o scratch/hotstuff.exe ./cmd/hotstuff` and `go build -p 2 -o scratch/campaign.exe ./cmd/campaign`. No protobuf regeneration is needed. Builds terminate; no service remains.

## Doctor

Run `scratch/hotstuff.exe help run` and `scratch/campaign.exe -h`. Never provide remote hosts or a user SSH configuration. The driver supplies its own empty SSH parser input for local-only execution. Use a fresh output directory for each run.

## Drive

Run `python tools/verify.py --hotstuff scratch/hotstuff.exe --campaign scratch/campaign.exe --output scratch/proof`. The driver invokes real loopback replica/client orchestration and the Twins executor. See features/README.md.

## Evidence

The output directory holds commands, exit codes, logs, exact scenarios, commit hashes, public-key fingerprints, network measurements and a passed boolean. Failed commands leave passed=false. The real CLI journey requires identical nonzero command counts and execution hashes from all four replicas. Inspect assertions and resulting state. Safety with no commits does not prove liveness. The local upstream CLI uses one process containing networked replica goroutines. Twins emulates networking and generates ephemeral ECDSA keys; private keys are never written.

## Cleanup

The driver uses bounded subprocess deadlines. On Windows it invokes taskkill /T /F against the still-owned live PID; on POSIX it kills the owned session group. Commands normally terminate naturally. Preserve the output directory after cleanup. Do not kill processes by name. Verify summary.json survives. Run `python -m unittest discover -s tools -p test_verify.py -v` to inject command failure and a timed-out parent/child listener. The checks assert both owned PIDs stopped and the listener closed, then preserve passed=false summaries under scratch/driver-controls/ after fixture cleanup.

## Helpers

`tools/verify.py` drives the binaries. `cmd/campaign` performs bounded scenario execution and an independent honest-prefix oracle. Run `go test ./workbench` for oracle regression and sensitivity checks.
