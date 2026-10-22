# HotStuff consensus engine

The [frozen native benchmark](.agents/skills/verify-hotstuff/features/benchmark.md) uses the real TLS/ECDSA CLI, opt-in bounded raw command observations, replica/payload/client/concurrency cells repeated five times, stability checks at offered rates and native CPU profiles. `python tools/benchmark.py smoke` checks exact raw outcomes and replica execution agreement; `benchmark` and `profile` require isolated Linux. `isolation` preserves the known round-robin zero-progress failure as a diagnostic with `progress_passed: false`. No consensus safety rule changed. Safe exported metrics exclude ephemeral private keys present in upstream network option records. The [hosted result audit](docs/benchmark-results.md) records that all 35 trials passed correctness checks, while the sustained 300/s SLO and permanent replica-isolation liveness check failed. The profile is diagnostic and does not establish capacity or an SLO fix. At 100 offered commands/s, the four-replica baseline finished 99.7/s with arrival-to-finish p99 33.184 ms, median of five runs [32.925, 33.266 ms]. At 300/s for 120 seconds, 35,448 of 36,000 planned commands finished, 547 were undispatched, and p99 reached 1,840.748 ms. These are one-process loopback replica goroutines, not multi-host capacity results.

A local adversarial workbench around the complete MIT-licensed [relab/hotstuff](https://github.com/relab/hotstuff) framework. It retains the upstream chained HotStuff, Fast HotStuff, Simple HotStuff, ECDSA/EdDSA/BLS crypto, Gorums networking, pacemaker, block fetch, clients and Twins executor. The added campaign saves exact partition scenarios, checks every overlapping honest commit prefix, rejects vacuous recovery, and replays failures.

This adaptation is inspired by Stanford CS244b's [HotStuff capstone report](https://www.scs.stanford.edu/24sp-cs244b/projects/HotStuff_Implementation_and_Advice.pdf), using a reusable framework rather than copying unlicensed student code. The algorithms and Twins framework are inherited. Read [provenance](docs/provenance.md), the unchanged [license](LICENSE), and the preserved [upstream README](docs/README.upstream.md).

## Run locally

Use Go 1.27.3 and Python 3. No cloud, SSH server, Docker, GPU or protobuf regeneration is needed.

```powershell
$env:GOTOOLCHAIN='local'
$env:CGO_ENABLED='0'
$env:GOMAXPROCS='2'
go build -p 2 -o scratch/hotstuff.exe ./cmd/hotstuff
go build -p 2 -o scratch/campaign.exe ./cmd/campaign
python tools/verify.py --hotstuff scratch/hotstuff.exe --campaign scratch/campaign.exe --output scratch/proof
go test -p 2 -timeout 3m ./...
go vet -p 2 ./...
```

Use a fresh evidence directory. The Python driver runs doctor, 17 bounded Twins journeys, replay, and a three-second four-replica/one-client network run. It records commands, exit codes, logs, measurements and passed=false on failure. It supplies empty local config files so user SSH/configuration is never used. The empty SSH file satisfies the inherited local runner's parser; no remote hosts are contacted. Each subprocess has a 45-second deadline.

```powershell
scratch/campaign.exe -input scratch/proof/campaign/scenarios.json -output scratch/replay
```

Campaign inputs are capped at 69 cases, 40 views per case and 300 emulation ticks. Seeded cases have one twin identity and two partitions. Controlled journeys cover healthy progress, initial leader isolation/healing, permanent isolation of replica 1 while the three honest replicas progress, twin partition/healing, and no progress without quorum. Results contain honest commit hashes/views, QC participant counts and ephemeral public-key fingerprints. Private keys stay in memory. Upstream map scheduling, timestamps and keys vary, so scenario replay does not promise byte-identical traces.

## Evidence and limits

The [verification skill](.agents/skills/verify-hotstuff/SKILL.md) and feature map are the maintained entry point. [Validation notes](docs/validation.md) record reproduced defects and evidence. The adapter validates distinct certificate signers and QC views, rejects malformed certificates, binds verification-cache entries to signer identities and message contents, initializes the emulated timeout countdown, and adds focused regressions, an intentionally conflicting commit-oracle control, and duplicate client execution checks.

The local runner uses four replica goroutines and real loopback sockets in one process. Twins emulates networking. Neither is a four-process crash experiment. Client commands carry IDs and sequence numbers but are not application-signed; network runs use TLS and replica QCs use ECDSA. ClientIO suppresses repeated execution by sequence number. There is no persistent anti-double-voting or restart recovery. Storage is an in-memory block cache. A bounded campaign is evidence for these journeys, not a universal BFT proof or performance benchmark. Partitions are indexed by each sender's effective view; recovery assertions cover the explicit one-view isolation/healing journey.

Permanent replica 1 isolation with round-robin leaders did not commit within 300 ticks in the controlled experiment. The inherited protocol collects votes at the next leader and requires consecutive-view certified chains. The passing permanent-isolation journey therefore switches to stable honest leader 2 after the initial failed leader. It does not establish liveness for arbitrary leader schedules. This limitation is retained in the validation notes.

The dependency fix moves gRPC 1.78 to 1.84 and updates affected x/net, x/crypto, x/image and x/text modules to fixed versions. Original workflow files remain inactive under docs/upstream-workflows. CI runs bounded read-only local checks.
