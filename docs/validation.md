# Validation record

Windows CPU verification used Go 1.27.3, Python 3.11, CGO_ENABLED=0, GOTOOLCHAIN=local, GOMAXPROCS=2 and package parallelism 2. Full-history upstream HEAD is 3179c6e62929294961acbfd9bf8445769716a121. The preserved README has exactly the upstream Git blob hash 6a94a251cfb44d0d797254a65eca3183d2530692.

## Reproduced failures and corrections

| Issue | Observed red evidence | Correction and regression |
| --- | --- | --- |
| Dependency compatibility | Baseline could not compile gRPC 1.78 because http2.TrailerPrefix was undefined with x/net 0.54. | Pin compatible gRPC 1.84 and module-selected transitive versions. |
| Repeated signer quorum | One real ECDSA signature repeated three times passed QC verification in a four-member configuration. | Certificate authority counts unique identities and rejects duplicates for QC, TC and aggregate QC. TestWorkbenchDistinctQuorum covers all three and invalid signatures/two-of-four. |
| Initial isolated leader | Emulation committed zero blocks after healing because timeout countdown started zero and decremented below zero. | Initialize countdown to five. TestWorkbenchInitialLeaderLossRecovery requires every replica to commit. |
| Missing signatures | Nonzero TC and aggregate QC with nil signatures panicked. | Return errors. TestWorkbenchMalformedCertificates covers both. The original upstream test expected the aggregate panic; it now requires rejection without panic. |
| Unsigned claimed view | Genesis QC accepted view 99; valid signed block accepted a different claimed QC view. | Require genesis view zero and QC view equal fetched block view. Focused malformed-certificate tests cover both. |
| Cached signer relabel | After warming a valid three-signer QC, changing signer 3 to unknown 99 with unchanged raw signature bytes passed. | Cache keys bind signer IDs; TestWorkbenchCacheSignerIdentity rejects the relabel. |
| Cached batch tamper | After warming BatchVerify, changing one message passed. The code discarded hasher.Sum's returned digest. | Store actual digest and bind sorted IDs, message lengths, signature identities and verification domain. TestWorkbenchCacheBatchContents rejects mutation. |

Raw local red proof is retained under ignored scratch/malformed-red.log, scratch/aggregate-red.log, scratch/identity-red.log and scratch/cache-batch-red.log. Original initial campaign failure is scratch/first/results.json with passed=false. These failures are intentional regression evidence, not final validation success.

## Checks

`go test -p 2 -timeout 3m ./...`, `go vet -p 2 ./...`, both binary builds and the product drive passed after final review corrections. Module checksum verification also passed. Consult the curated result and local scratch/review-tests.log and scratch/review-proof/summary.json. The long orchestration test takes roughly two minutes; this is not a performance benchmark.

`go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 ./...` initially found reachable vulnerabilities in pinned x/net, x/crypto and x/image. After targeted fixed-version updates, the scan reported zero called or imported-package vulnerabilities and one module-only advisory without a fix, GO-2026-5932 in x/crypto. No claim is made that dependencies are universally secure. The scan tool was run from a task-local module cache, not globally installed.

`python -m unittest discover -s tools -p test_verify.py -v` passes two real failure controls. One command exits 7; one parent spawns a child with a loopback listener then exceeds its two-second deadline. The maintained driver uses an owned PID tree on Windows and a private session group on POSIX. The control asserts both PIDs stopped and the listener closed, then preserves failed summaries under scratch/driver-controls/ after fixture cleanup. No unrelated processes are stopped.

## Product evidence and limits

The final campaign has 17 journeys at seed 244. Every overlapping honest committed prefix must agree in hash and order. Healthy and healed journeys require at least one commit per honest node. The no-quorum journey requires zero commits. The permanently isolated replica 1 journey excludes that replica as the single faulty identity and requires all remaining three replicas to commit with stable honest leader 2. Twins uses real ephemeral ECDSA signatures; public-key fingerprints, views and QC counts are saved without private keys. Exact scenarios are saved and replayed. The oracle has a controlled conflicting-hash mutant, empty-progress control, out-of-order control and insufficient-QC control.

The real CLI drive has four replica goroutines, one client and TLS loopback sockets inside one process. It requires identical nonzero final command counts and execution hashes from every replica. ClientIO's duplicate-execution regression verifies an identical client ID/sequence does not change command count or execution hash, then the next sequence does. Commands themselves are not application-signed. TLS and replica QC signatures are distinct boundaries.

The first permanent replica 1 isolation experiment with round-robin leaders had zero honest commits in 300 ticks, retained as scratch/quorum-proof/results.json with passed=false. The passing quorum experiment changes to stable honest leader 2. Because votes go to the next leader and commits require consecutive-view certified chains, the finite evidence does not establish liveness under arbitrary or repeating faulty-leader schedules. The simulator also indexes partitions by sender effective view, so long isolation can strand a stale replica in an old partition. These are inherited limitations, not fixed by the workbench.

No race detector was run because this Windows environment lacks configured CGO/C tooling. No crash/restart durability, four-process isolation, remote SSH, cloud, GPU, universal BFT proof, throughput benchmark or GitHub CI execution is claimed. In-memory storage does not provide durable anti-double-voting.
