# HotStuff consensus engine

## Contents

- [Architecture and execution guide](#architecture-and-execution-guide)
- [Run locally](#run-locally)
- [Evidence and limits](#evidence-and-limits)
- [Implementation techniques](#implementation-techniques)
- [Validation notes](docs/validation.md)

The [frozen native benchmark](.agents/skills/verify-hotstuff/features/benchmark.md) uses the real TLS/ECDSA CLI, opt-in bounded raw command observations, replica/payload/client/concurrency cells repeated five times, stability checks at offered rates and native CPU profiles. `python tools/benchmark.py smoke` checks exact raw outcomes and replica execution agreement; `benchmark` and `profile` require isolated Linux. `isolation` preserves the known round-robin zero-progress failure as a diagnostic with `progress_passed: false`. No consensus safety rule changed. Safe exported metrics exclude ephemeral private keys present in upstream network option records. The [hosted result audit](docs/benchmark-results.md) records that all 35 trials passed correctness checks, while the sustained 300/s SLO and permanent replica-isolation liveness check failed. The profile is diagnostic and does not establish capacity or an SLO fix. At 100 offered commands/s, the four-replica baseline finished 99.7/s with arrival-to-finish p99 33.184 ms, median of five runs [32.925, 33.266 ms]. At 300/s for 120 seconds, 35,448 of 36,000 planned commands finished, 547 were undispatched, and p99 reached 1,840.748 ms. These are one-process loopback replica goroutines, not multi-host capacity results.

A local adversarial workbench around the complete MIT-licensed [relab/hotstuff](https://github.com/relab/hotstuff) framework. It retains the upstream chained HotStuff, Fast HotStuff, Simple HotStuff, ECDSA/EdDSA/BLS crypto, Gorums networking, pacemaker, block fetch, clients and Twins executor. The added campaign saves exact partition scenarios, checks every overlapping honest commit prefix, rejects vacuous recovery, and replays failures.

This adaptation is inspired by Stanford CS244b's [HotStuff capstone report](https://www.scs.stanford.edu/24sp-cs244b/projects/HotStuff_Implementation_and_Advice.pdf), using a reusable framework rather than copying unlicensed student code. The algorithms and Twins framework are inherited. Read [provenance](docs/provenance.md), the unchanged [license](LICENSE), and the preserved [upstream README](docs/README.upstream.md).

## Architecture and execution guide

The inherited `relab/hotstuff` framework implements consensus protocols, cryptography, Gorums networking, leader rotation, clients, and the Twins simulator. This repository adds a bounded campaign, evidence oracle, exact scenario replay, and local product driver. Twins replicas are simulated participants; the network journey uses four replica goroutines and loopback sockets inside one process.

This boundary map separates the actual product paths used by the verification driver.

```mermaid
flowchart LR
    driver["Python verification driver"] --> campaign["Campaign CLI and commit oracle"]
    driver --> cli["HotStuff CLI"]
    campaign --> twins["Inherited Twins executor"]
    cli --> replicas["Replica goroutines and loopback RPC"]
    replicas --> client["Client command and reply quorum"]
```

The campaign CLI explores simulated partitions and checks committed histories. The local HotStuff CLI starts replicas and a client over loopback. Both paths reuse inherited consensus, certificate, and client code; neither represents multiple operating-system replica processes.

This sequence shows how campaign cases, replay, and the real loopback journey produce separate evidence.

```mermaid
flowchart TD
    subgraph Driver["Verification driver"]
        doctor["Check binaries and local prerequisites"] --> input["Write bounded seeded campaign cases"]
        input --> run["Run campaign and retain scenario records"]
        run --> replay["Replay saved cases"]
        replay --> network["Run four local replica goroutines and client"]
    end
    subgraph Campaign["Twins campaign"]
        twins["Emulate partitions, delays, and timeout events"] --> commits["Collect honest committed prefixes"]
        commits --> oracle["Check agreement and required progress"]
    end
    input --> twins
    run -->|"failed assertion or process timeout"| failure["Retain logs and passed=false result"]
    oracle --> evidence["Save bounded result and public fingerprints"]
    network --> evidence
```

The oracle requires agreement on overlapping honest commit prefixes and non-vacuous progress in journeys designated to make progress. No quorum requires zero commits. A finite campaign tests these named cases; it does not prove universal safety or liveness. A failed run keeps its logs and failure verdict.

| Subsystem | Responsibility | Owned state or invariant | Source |
| --- | --- | --- | --- |
| Protocol core | Coordinate proposal, votes, certificates, and commit rules | Protocol view and certified block chain | [`core/replica.go`](core/replica.go), [`hotstuff.go`](hotstuff.go) |
| Event loop | Serialize replica events and timeout processing | Per-replica event queue and lifecycle | [`core/eventloop/eventloop.go`](core/eventloop/eventloop.go) |
| Twins and protocol modules | Emulate partitions and compose consensus components | Scenario-defined network conditions and simulated participants | [`twins`](twins), [`protocol`](protocol) |
| CLI orchestration | Parse config and run local or configured workers | Local worker choice and bounded run settings | [`internal/cli/run.go`](internal/cli/run.go) |
| Client | Send commands and wait for `f+1` replies | Client sequence, pending commands, and bounded concurrency | [`client/client.go`](client/client.go) |
| Campaign oracle | Check commit agreement, progress, and replay | Honest identities, committed hashes/views, and pass criteria | [`cmd/campaign/main.go`](cmd/campaign/main.go) |

Terms used in these paths: [HotStuff](#concept-hotstuff), [replicas](#concept-replica), [views](#concept-view), [quorum certificates](#concept-quorum-certificate), [pacemaker](#concept-pacemaker), [Twins](#concept-twins), [honest committed prefixes](#concept-honest-prefix), and [liveness](#concept-liveness).

### Follow one verification run

1. Build the inherited HotStuff binary and the campaign binary, then run the Python driver with a fresh evidence directory.
2. The driver checks local prerequisites and writes a bounded set of seeded cases. Each case records a partition scenario and one twin identity.
3. The campaign runs each case in the inherited Twins executor. The oracle compares honest commit prefixes, checks quorum requirements, and rejects empty progress where progress is expected.
4. The driver replays saved scenarios, then starts the local network journey with four replica goroutines, TLS loopback connections, and one client.
5. The client waits for replies from `f+1` replicas. Repeating the same client sequence must not change the command count; a new sequence must execute.
6. The driver stores scenario records, logs, command results, and public-key fingerprints. Timeouts or failed assertions produce `passed:false` and preserve evidence.

### Design decisions and limits

These rationales are inferred from the current implementation. They do not record historic design intent.

| Choice | Practical rationale | Alternative and cost | Reconsider when |
| --- | --- | --- | --- |
| Reuse the inherited consensus framework | Keeps the campaign focused on behavior evidence and preserves upstream implementations | A fresh implementation would duplicate protocol and cryptographic code | The goal becomes implementing a protocol variant itself |
| Use Twins for adversarial schedules | Repeats named partitions and timeouts without remote hosts | Real multi-process or multi-host faults are more realistic but add deployment and environment dependencies | Process failure or network stack behavior is the question |
| Require agreement and non-vacuous progress | Prevents a safety-only or empty-progress run from passing | Weaker checks are easier to satisfy but could bless vacuous outcomes | The journey's contract changes and the oracle is updated with it |
| Keep the network journey loopback and in one process | Exercises actual RPC and client paths without SSH or deployment | Separate processes test crash boundaries but need owned process and storage lifecycle | Restart durability or process isolation becomes required |
| Preserve the failed round-robin isolation case | Reports a known no-progress condition instead of hiding it | Changing leadership behavior might improve that scenario but changes the tested schedule | A protocol change is independently justified and retested |

### Glossary

<a id="concept-hotstuff"></a>

<details><summary>What is HotStuff?</summary>

HotStuff is a Byzantine fault-tolerant consensus protocol. This repository preserves chained, Fast, and Simple HotStuff variants; the workbench does not replace their consensus rules.
</details>

<a id="concept-replica"></a>

<details><summary>What is a replica?</summary>

A replica is a participant that processes proposals and votes. In the local network journey, four replicas are goroutines in one process rather than four separate processes.
</details>

<a id="concept-view"></a>

<details><summary>What is a view?</summary>

A view is a protocol round associated with a leader and proposal progress. The isolation evidence tracks commit hashes and views to detect gaps in consecutive-view certified chains.
</details>

<a id="concept-quorum-certificate"></a>

<details><summary>What is a quorum certificate?</summary>

A quorum certificate (QC) aggregates sufficient replica votes for a block or event. The campaign records signer counts and checks certificate views; this evidence does not prove every certificate path correct.
</details>

<a id="concept-pacemaker"></a>

<details><summary>What is a pacemaker?</summary>

A pacemaker coordinates view changes and proposal timing. It is inherited from the framework; emulated timeout events drive it in Twins journeys.
</details>

<a id="concept-twins"></a>

<details><summary>What is Twins?</summary>

Twins is an executor for emulating Byzantine participants and network schedules. The campaign caps cases, views, and ticks so the run remains bounded.
</details>

<a id="concept-honest-prefix"></a>

<details><summary>What is an honest committed prefix?</summary>

It is the ordered sequence of commands committed by a replica that is not the designated twin. The oracle requires overlapping prefixes from honest replicas to agree.
</details>

<a id="concept-liveness"></a>

<details><summary>What is liveness?</summary>

Liveness is progress toward committing commands. The permanent replica-1 isolation journey passes only with a stable honest leader; the inherited round-robin schedule did not progress within 300 ticks.
</details>

## Implementation techniques

This section covers mechanisms used by the active campaign and documented local replica/client journey. The source audit excludes preserved protocol variants and inactive utilities. Rationale is inferred from current code, not attributed as historic author intent. The inherited HotStuff engine supplies consensus, crypto, networking, and client machinery; workbench additions supply bounded scenario replay and evidence checks.

| Active subsystem | Technique cards | Source |
| --- | --- | --- |
| Campaign generation, validation, and replay | [Seeded partition scenario generation](#technique-seeded-partition-scenario-generation), [Bounded exact scenario replay](#technique-bounded-exact-scenario-replay) | [`cmd/campaign/main.go`](cmd/campaign/main.go), [`twins/generator.go`](twins/generator.go), [`twins/scenario.go`](twins/scenario.go) |
| Twins network and adversarial identities | [View-indexed message partitioning](#technique-view-indexed-message-partitioning), [Shared-key twin equivocation simulation](#technique-shared-key-twin-equivocation), [Discrete-time event simulation](#technique-discrete-time-event-simulation) | [`twins/network.go`](twins/network.go), [`twins/sender.go`](twins/sender.go), [`twins/timeoutmgr.go`](twins/timeoutmgr.go) |
| Chained consensus and commit path | [Three-chain certified commit rule](#technique-three-chain-certified-commit), [Distinct-signer quorum certificate validation](#technique-quorum-certificate-validation) | [`protocol/rules/chainedhotstuff.go`](protocol/rules/chainedhotstuff.go), [`protocol/consensus/committer.go`](protocol/consensus/committer.go), [`security/cert/auth.go`](security/cert/auth.go) |
| Pacemaker and timeout certificates | [Timeout-certificate view advancement](#technique-timeout-certificate-view-advancement) | [`protocol/synchronizer/synchronizer.go`](protocol/synchronizer/synchronizer.go), [`security/cert/auth.go`](security/cert/auth.go) |
| Replica signatures and network dissemination | [ECDSA partial signatures and quorum aggregation](#technique-signed-quorum-certificate-aggregation), [Bounded certificate verification cache](#technique-bounded-certificate-verification-cache), [One-to-all proposals and votes to the next leader](#technique-one-to-all-vote-to-next-leader-dissemination), [Loopback RPC replica execution](#technique-loopback-rpc-replica-execution) | [`security/crypto/ecdsa.go`](security/crypto/ecdsa.go), [`security/cert/auth.go`](security/cert/auth.go), [`security/cert/cache.go`](security/cert/cache.go), [`protocol/comm/clique.go`](protocol/comm/clique.go), [`internal/cli/run.go`](internal/cli/run.go), [`replica/replica.go`](replica/replica.go) |
| Replica event processing | [Serialized event dispatch with a bounded drop-oldest queue](#technique-serialized-event-dispatch-with-bounded-drop-oldest-queue) | [`core/eventloop/eventloop.go`](core/eventloop/eventloop.go), [`core/eventloop/queue.go`](core/eventloop/queue.go) |
| Client reply and duplicate handling | [f+1 client reply quorum](#technique-f-plus-one-client-reply-quorum), [Per-client monotone sequence deduplication](#technique-per-client-monotone-sequence-deduplication) | [`client/client.go`](client/client.go), [`server/clientio.go`](server/clientio.go) |
| Agreement and progress oracle | [Honest-prefix agreement and nonvacuous progress checks](#technique-honest-prefix-agreement-and-nonvacuous-progress) | [`workbench/oracle.go`](workbench/oracle.go), [`cmd/campaign/main.go`](cmd/campaign/main.go) |

### Seeded partition scenarios and replay

<a id="technique-seeded-partition-scenario-generation"></a>

<details>
<summary>Seeded partition scenario generation</summary>

**Mechanism.** The inherited generator builds leader and partition combinations, then shuffles their order with a supplied seed. The campaign uses four replicas, one twin identity, two partitions, and eight generated views. The seed and resulting scenarios are written to `scenarios.json`.

**Example.** With `-seed 244 -scenarios 12`, the campaign names generated cases `seed-244-0` through `seed-244-11` and stores each view's leader and partition membership.

**Why here.** A saved scenario makes an adversarial schedule inspectable and repeatable as an input to the same executor.

**Tradeoffs.** The seed controls generated ordering, but fresh keys and upstream map iteration prevent byte-identical execution traces.

**Code and ownership.** [`Generator.Shuffle`](twins/generator.go#L89) and [`Generator.NextScenario`](twins/generator.go#L110). Inherited.

</details>

<a id="technique-bounded-exact-scenario-replay"></a>

<details>
<summary>Bounded exact scenario replay</summary>

**Mechanism.** The campaign accepts either generated cases or a saved JSON case list. Replay input is capped at 2 MiB and 69 scenarios; per-case validation checks node identities, leader IDs, views, twin count, partition membership, and commit minimum. Execution caps each case at 300 ticks and 40 views. The exact scenario structure is serialized before execution.

**Example.** `campaign -input scratch/proof/campaign/scenarios.json -output scratch/replay` feeds the recorded leaders and partitions back to `ExecuteScenario`.

**Why here.** A failed adversarial input can be rerun without regenerating the partition schedule.

**Tradeoffs.** Replaying the schedule does not reproduce random key bytes, map iteration order, or identical logs.

**Code and ownership.** [`main`](cmd/campaign/main.go#L33), [`validate`](cmd/campaign/main.go#L172), and [`ExecuteScenario`](twins/scenario.go#L54). Campaign bounds and validation are extensions; the Twins executor is inherited.

</details>

### Twins network and event simulation

<a id="technique-view-indexed-message-partitioning"></a>

<details>
<summary>View-indexed message partitioning</summary>

**Mechanism.** The simulator selects the partition list by the sender's effective protocol view. It delivers messages when sender and receiver share a partition. Configured message types are dropped across partitions. Proposals, votes, block fetch hashes, new-view messages, and timeouts are configured separately by the campaign.

**Example.** In the first leader-loss view, replica 1 occupies one partition while replicas 2, 3, and 4 share another; the schedule later merges them.

**Why here.** This lets a journey vary connectivity by view while preserving the protocol's actual message handlers.

**Tradeoffs.** The simulator's partition rule is an explicit schedule model. It does not model packet loss timing, kernel queues, or multi-host transport behavior.

**Code and ownership.** [`Network.shouldDrop`](twins/network.go#L208) and [`emulatedSender.sendMessage`](twins/sender.go#L41). Inherited.

</details>

<a id="technique-shared-key-twin-equivocation"></a>

<details>
<summary>Shared-key twin equivocation simulation</summary>

**Mechanism.** Twins have separate simulator node identities but share the private key and protocol replica ID. Their outgoing messages can reach different partitions, so one Byzantine identity can present inconsistent behavior while its signatures still verify as that replica.

**Example.** The `twins-heal` journey places twin 1 with replica 2 and twin 2 with replicas 3 and 4 for the first view, then uses the common partition.

**Why here.** The setup tests protocol behavior for an equivocating identity without a real adversarial process.

**Tradeoffs.** Two simulated twins do not model independent operating-system processes, crashes, or key compromise.

**Code and ownership.** [`NodeID.Twin`](twins/network.go#L34) and [`Network.createNodesAndTwins`](twins/network.go#L119). Inherited.

</details>

<a id="technique-discrete-time-event-simulation"></a>

<details>
<summary>Discrete-time event simulation</summary>

**Mechanism.** Each network tick delivers eligible pending messages, then enqueues a tick event for each node and drains its event loop. A timeout manager advances a per-node countdown and emits a timeout event at zero. The simulator stops at the supplied tick bound.

**Example.** `ExecuteScenario(..., 300, ...)` runs no more than 300 simulation ticks for one scheduled scenario.

**Why here.** A logical clock allows a campaign to exercise timeout and view-change paths under an explicit bounded schedule.

**Tradeoffs.** Simulated ticks are not wall-clock time or a timing guarantee for a real network.

**Code and ownership.** [`Network.tick`](twins/network.go#L181), [`timeoutManager.advance`](twins/timeoutmgr.go#L19), and [`ExecuteScenario`](twins/scenario.go#L54). Inherited.

</details>

### Consensus certificates and pacemaker

<a id="technique-three-chain-certified-commit"></a>

<details>
<summary>Three-chain certified commit rule</summary>

**Mechanism.** Chained HotStuff follows a proposal's QC to its parent, then follows that block's QC to a grandparent. It commits the grandparent only when all three blocks form consecutive-view parent links. The committer then records the block and recursively executes eligible uncommitted ancestors.

**Example.** A certified chain `b3 -> b2 -> b1` can commit `b1` when the parent links and views are consecutive.

**Why here.** The campaign runs the inherited chained protocol and observes committed block histories through its existing commit events.

**Tradeoffs.** Missing QCs, missing ancestors, or a gap in consecutive views prevents this commit rule from deciding a block. The liveness evidence documents a known gap under round-robin isolation.

**Code and ownership.** [`ChainedHotStuff.CommitRule`](protocol/rules/chainedhotstuff.go#L48) and [`Committer.TryCommit`](protocol/consensus/committer.go#L44). Inherited.

</details>

<a id="technique-quorum-certificate-validation"></a>

<details>
<summary>Distinct-signer quorum certificate validation</summary>

**Mechanism.** The certificate authority rejects nil signatures, counts distinct participant IDs against the configured quorum, loads the certified block, checks that the QC view matches that block's view, and verifies the signature over the block bytes. The same authority verifies timeout certificates against their view bytes.

**Example.** A QC whose participant set cannot meet the configured quorum is rejected before cryptographic verification succeeds as a protocol certificate.

**Why here.** Campaign results include signer counts, while the protocol still relies on the authority's validation at message boundaries.

**Tradeoffs.** A valid certificate establishes the configured signer threshold and signed message. It does not prove the whole run's safety or liveness.

**Code and ownership.** [`Authority.VerifyQuorumCert`](security/cert/auth.go#L116) and [`distinctQuorum`](security/cert/auth.go#L225). The authority is inherited; distinct-signer and view checks are workbench changes.

</details>

<a id="technique-timeout-certificate-view-advancement"></a>

<details>
<summary>Timeout-certificate view advancement</summary>

**Mechanism.** A local timeout signs the current view and sync information, stops voting in that view, broadcasts the timeout, and also processes it locally. The synchronizer verifies incoming signatures, collects timeout messages until quorum, applies timeout rules to form sync information, updates the high QC, and advances the view.

**Example.** The Twins timeout manager emits a timeout every five ticks, while the synchronizer consumes that event through the same timeout path used by the protocol.

**Why here.** Timeout events let the campaign exercise leader changes when a partition prevents normal proposal progress.

**Tradeoffs.** Collecting a timeout quorum alone does not guarantee progress under every leader schedule; the measured permanent-isolation round-robin journey remains failed.

**Code and ownership.** [`Synchronizer.OnRemoteTimeout`](protocol/synchronizer/synchronizer.go#L209), [`Synchronizer.advanceView`](protocol/synchronizer/synchronizer.go#L250), and [`Authority.VerifyTimeoutCert`](security/cert/auth.go#L147). Inherited.

</details>

### Signatures, dissemination, and replica execution

<a id="technique-signed-quorum-certificate-aggregation"></a>

<details>
<summary>ECDSA partial signatures and quorum aggregation</summary>

**Mechanism.** A replica signs serialized block bytes with ECDSA and returns a partial certificate containing that signature and the block hash. The authority combines partial signatures into a quorum signature and embeds it with the block view and hash in a QC. Verification checks participant identities against configured public keys.

**Example.** The four-replica configuration requires a three-participant QC; campaign output records the participant count from each committed block's QC.

**Why here.** The active local run and Twins campaign use the inherited ECDSA crypto implementation.

**Tradeoffs.** This is a collection of individual signatures, not a threshold signature that collapses them into one compact cryptographic signature. Private keys are generated for the simulated journey.

**Code and ownership.** [`ECDSA.Sign`](security/crypto/ecdsa.go#L62), [`ECDSA.Combine`](security/crypto/ecdsa.go#L75), and [`Authority.CreateQuorumCert`](security/cert/auth.go#L54). Inherited.

</details>

<a id="technique-bounded-certificate-verification-cache"></a>

<details>
<summary>Bounded certificate verification cache</summary>

**Mechanism.** The authority wraps the configured crypto implementation with an LRU cache when the runtime sets a positive capacity. For a signature check, the cache key includes a mode byte, the message hash, encoded signature bytes, and participant IDs. A cache miss verifies through the underlying crypto implementation before storing the key. Signature combination is not cached.

**Example.** The active Twins node configuration sets cache capacity to 100 entries.

**Why here.** Repeated checks of the same signed message and participant set can reuse a completed verification in the campaign.

**Tradeoffs.** Entries are bounded and evicted by recency. A cache hit is only valid for the full message and signature identity represented in the key.

**Code and ownership.** [`NewAuthority`](security/cert/auth.go#L23), [`Cache.Verify`](security/cert/cache.go#L73), and [`writeSignatureKey`](security/cert/cache.go#L136). Inherited.

</details>

<a id="technique-one-to-all-vote-to-next-leader-dissemination"></a>

<details>
<summary>One-to-all proposals and votes to the next leader</summary>

**Mechanism.** Clique broadcasts a proposal to replicas. Each voter creates a partial certificate and sends it to the leader of the next view. If the current replica is itself that next leader, it submits its own vote directly to the voting machine. The next leader collects votes and forms the QC.

**Example.** For a proposal in view `v`, `Aggregate` selects `GetLeader(v+1)` as the vote recipient.

**Why here.** This inherited communication mode is the configured path for the current campaign and documented local run.

**Tradeoffs.** This centralizes vote collection at the next leader. The preserved Kauri tree dissemination path is outside the active journeys documented here.

**Code and ownership.** [`Clique.Disseminate`](protocol/comm/clique.go#L36) and [`Clique.Aggregate`](protocol/comm/clique.go#L42). Inherited.

</details>

<a id="technique-loopback-rpc-replica-execution"></a>

<details>
<summary>Loopback RPC replica execution</summary>

**Mechanism.** The local CLI selects a worker that creates configured replica instances, starts their RPC listeners, connects replicas, and starts their run loops. The local experiment uses loopback addresses and the verification journey configures TLS for replica and client connections. The replicas are goroutines within one process.

**Example.** The documented journey starts four replica goroutines and one client, then checks their final command counts and order hashes.

**Why here.** It exercises the real RPC and client paths without remote hosts.

**Tradeoffs.** This does not test separate-process crashes, durable voting state, restart recovery, or multi-host network behavior.

**Code and ownership.** [`runSingleExperiment`](internal/cli/run.go#L42), [`localWorker`](internal/cli/run.go#L135), [`Worker.createReplica`](internal/orchestration/worker.go#L139), and [`Replica.StartServers`](replica/replica.go#L107). Mixed: inherited worker and replica runtime with local workbench configuration.

</details>

### Event handling and client sequence control

<a id="technique-serialized-event-dispatch-with-bounded-drop-oldest-queue"></a>

<details>
<summary>Serialized event dispatch with a bounded drop-oldest queue</summary>

**Mechanism.** The event loop dispatches registered handlers serially by event type. Producers add events to a mutex-protected circular buffer. When the buffer is full, `push` discards the oldest queued event to admit the newest and returns the dropped value.

**Example.** The loop's capacity is set when constructed; the campaign's simulated nodes use a capacity of 100.

**Why here.** Serial handlers let protocol modules coordinate through events without each module adding locks around its own state.

**Tradeoffs.** Queue overflow loses an event by design. The bounded queue does not provide backpressure or guarantee that every event is processed.

**Code and ownership.** [`EventLoop.processEvent`](core/eventloop/eventloop.go#L213) and [`queue.push`](core/eventloop/queue.go#L30). Inherited.

</details>

<a id="technique-f-plus-one-client-reply-quorum"></a>

<details>
<summary>f+1 client reply quorum</summary>

**Mechanism.** The client's quorum function accepts an execution response after it receives at least `f+1` replies for the command. The value of `f` comes from the configured replica count. The client handles pending requests in send order and advances its highest acknowledged sequence when a reply completes.

**Example.** With four replicas and `f=1`, the request completes after two replica replies.

**Why here.** The client can report completion without requiring every replica to answer.

**Tradeoffs.** A reply threshold is the client's completion rule; it does not by itself prove that the command was committed consistently by all replicas.

**Code and ownership.** [`qspec.ExecCommandQF`](client/client.go#L34), [`Client.Connect`](client/client.go#L126), and [`Client.handleCommands`](client/client.go#L276). Inherited.

</details>

<a id="technique-per-client-monotone-sequence-deduplication"></a>

<details>
<summary>Per-client monotone sequence deduplication</summary>

**Mechanism.** Each command carries a client ID and sequence number. On execution, the server checks the last executed sequence for that client under a mutex. It rejects a command whose sequence is at or below that watermark; otherwise it advances the watermark and updates the command hash and count.

**Example.** After sequence 7 executes for client 1, a retry of sequence 7 is aborted and does not increment the command count; sequence 8 can execute.

**Why here.** The network journey can retry commands without silently counting the same sequence twice.

**Tradeoffs.** The watermark is in memory. It does not survive replica restart, and the client command is not application-signed.

**Code and ownership.** [`ClientIO.Exec`](server/clientio.go#L93), [`ClientIO.isDuplicate`](server/clientio.go#L123), and [`Client.sendCommands`](client/client.go#L198). Mixed: inherited sequence handling with added workbench regression coverage.

</details>

### Agreement and progress evidence

<a id="technique-honest-prefix-agreement-and-nonvacuous-progress"></a>

<details>
<summary>Honest-prefix agreement and nonvacuous progress checks</summary>

**Mechanism.** The oracle requires at least two honest node histories, enforces a per-node minimum commit count, checks increasing commit views and QC signer counts, and compares every overlapping index so a lagging replica can agree on the prefix it has committed. The no-quorum case separately requires zero commits. The campaign excludes twin identities and the explicitly designated faulty replica from the honest set.

**Example.** A run with zero commits fails journeys whose minimum is one, while the no-quorum journey has a zero minimum and rejects any commit.

**Why here.** Prefix comparison catches conflicts without requiring replicas to finish at equal heights, and the minimum prevents empty histories from passing a progress case.

**Tradeoffs.** This is a finite oracle over recorded journeys. It is not a proof of universal safety or liveness; permanent isolation with round-robin leadership remains a known failed diagnostic.

**Code and ownership.** [`Check`](workbench/oracle.go#L12), [`controlled`](cmd/campaign/main.go#L130), and [`main`](cmd/campaign/main.go#L33). Extension.

</details>

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

The [message-trace audit](docs/benchmark-results.md#liveness-and-evidence-limits) identifies lost view-4 votes and the resulting certificate gaps. It matches a known limitation of chained HotStuff under four-replica round-robin leadership; no safety condition was removed to make the diagnostic pass.

The dependency fix moves gRPC 1.78 to 1.84 and updates affected x/net, x/crypto, x/image and x/text modules to fixed versions. Original workflow files remain inactive under docs/upstream-workflows. CI runs bounded read-only local checks.
