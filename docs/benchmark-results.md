# Hosted benchmark results and profile audit

The hosted runs passed correctness checks but did not meet the sustained arrival-rate SLO. The retained profile points to increasing delay before RPC dispatch, but it does not identify a safe product change that repairs that delay. No capacity, two-second finality, or optimization claim follows from these results.

## Five repeated trials

Run `39737854265` used clean source `582e218e892e95fb35e510118d69d0fa19e15bd8` on Linux 6.17.0-1022-azure, glibc 2.39, Python 3.11.17 and four visible cores. It set `GOMAXPROCS=2`, `GOMEMLIMIT=768MiB`, and seed 421. The CPU model and total RAM were not recorded. The campaign summary SHA-256 is `e0de9df0cd7a95e506f788c0d96252de44c7e1c6ccaa6fcf45f2c54ee7d16929`.

All 35 trials passed their command and replica-correctness checks. The overall campaign failed because the 120-second stability trial missed its load SLO. Of 30 matrix repeats, 29 passed the SLO; the concurrency-32 cell had one outlier with steady dispatch p99 of 156.399 ms. The four rate sweeps had three SLO passes. The other failed cells were the 1,000/s sweep and the 120-second 300/s trial.

The six matrix cells each ran five times for 10 seconds at an offered 100 commands/s. Throughput is capped by that offered rate. Each table entry reports the median across five runs and the full range of per-run p99 or throughput values. Latency starts at scheduled arrival. Dispatch lag measures the time from scheduled arrival to RPC dispatch.

| Replicas | Payload bytes | Clients | Concurrency | Finished/s median [range] | Scheduled arrival to finish p99 ms median [range] | Scheduled arrival to dispatch p99 ms median [range] | SLO passes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1,024 | 1 | 4 | 99.7 [99.7, 99.7] | 33.184 [32.925, 33.266] | 1.089 [1.084, 1.105] | 5/5 |
| 4 | 1,024 | 1 | 32 | 99.7 [98.2, 99.7] | 32.913 [32.582, 419.081] | 1.081 [1.079, 156.399] | 4/5 |
| 4 | 1,024 | 4 | 4 | 100 [100, 100] | 36.779 [36.685, 37.049] | 1.079 [1.071, 1.090] | 5/5 |
| 4 | 32 | 1 | 4 | 99.7 [98.2, 99.7] | 32.923 [32.530, 184.748] | 1.083 [1.076, 1.087] | 5/5 |
| 4 | 8,192 | 1 | 4 | 99.7 [99.6, 99.7] | 33.539 [33.435, 47.376] | 1.102 [1.097, 1.113] | 5/5 |
| 7 | 1,024 | 1 | 4 | 99.7 [99.7, 99.7] | 35.798 [35.613, 36.668] | 1.114 [1.087, 1.118] | 5/5 |

Each resource range covers the five repeats. RSS is the sampled peak for the tracked native process or Python launcher, in decimal MB.

| Replicas / payload / clients / concurrency | Native peak RSS median [range] MB | Launcher peak RSS median [range] MB |
| --- | ---: | ---: |
| 4 / 1,024 / 1 / 4 | 59.859 [58.520, 60.940] | 28.488 [18.330, 29.491] |
| 4 / 1,024 / 1 / 32 | 59.427 [58.507, 60.785] | 29.233 [27.709, 29.479] |
| 4 / 1,024 / 4 / 4 | 62.923 [62.693, 62.968] | 29.209 [27.337, 29.233] |
| 4 / 32 / 1 / 4 | 60.846 [58.814, 60.965] | 29.229 [27.693, 29.491] |
| 4 / 8,192 / 1 / 4 | 105.689 [105.394, 107.475] | 29.225 [27.312, 30.228] |
| 7 / 1,024 / 1 / 4 | 121.516 [119.140, 123.585] | 29.377 [26.100, 29.471] |

Across the 30 matrix runs, 30,000 commands were planned, 30,040 dispatched, and 29,894 finished. There were 68 extra dispatches, 28 undispatched offers, 69 canceled outcomes, and 77 canceled-pending outcomes. No request failed or timed out, and no dispatched request remained unresolved. The canceled count is a client outcome; it does not say whether replicas executed that command.

| Offered rate | Duration | Planned / dispatched | Finished | Canceled / canceled-pending | Undispatched | Scheduled arrival to finish p50 / p95 / p99 ms | Steady dispatch p99 ms | Load SLO |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30/s | 10 s | 300 / 301 | 297 | 1 / 3 | 0 | 101.805 / 102.456 / 103.579 | 1.187 | Pass |
| 100/s | 10 s | 1,000 / 1,001 | 997 | 1 / 3 | 0 | 31.647 / 32.245 / 33.582 | 1.093 | Pass |
| 300/s | 10 s | 3,000 / 3,001 | 2,997 | 1 / 3 | 0 | 11.558 / 12.392 / 14.014 | 1.086 | Pass |
| 1,000/s | 10 s | 10,000 / 5,853 | 5,819 | 2 / 32 | 4,147 | 2,128.137 / 3,983.050 / 4,146.356 | 4,125.494 | Fail |
| 300/s | 120 s | 36,000 / 35,453 | 35,448 | 2 / 3 | 547 | 634.889 / 1,744.016 / 1,840.748 | 1,786.247 | Fail |

These five trials reported no failed, timed-out, or unresolved dispatched commands. Short runs can dispatch one command beyond the planned count; the table keeps that extra dispatch visible. In the 120-second run, every replica executed 35,449 commands with the same order hash, `f321c964d90df283902dc3079fd740c461b530e42a2207abb43eef0463504902`, while the client recorded 35,448 finished requests. Client terminal outcomes and replica execution counts are separate evidence. The steady window dispatched and finished all 34,800 scheduled offers, yet its arrival-to-finish p99 was 1,799.488 ms and dispatch p99 was 1,786.247 ms, above the 100 ms dispatch limit.

Across the rate sweeps, native process peak RSS was 47.75 MB at 30/s, 60.78 MB at 100/s, 80.50 MB at 300/s, and 128.33 MB at 1,000/s. The matching Python launcher peaks were 29.23, 29.24, 36.12, and 58.90 MB. The 120-second native process reached 558.281 MB peak RSS and averaged 110.304% of one core over its sampled lifecycle. Its Python launcher reached 308.208 MB and includes post-exit JSON processing. Samples cover setup and shutdown; the replicas and client are goroutines in the same native process.

## Native profile

Run `39740846299` profiled the same four-replica, one-client, 1,024-byte, concurrency-32, 300/s, 120-second cell from clean source `d2cecc54163b5f83eff20f760c2941e15cc2c3e5`. Its profile summary SHA-256 is `2bef0b4d633be6fc80f5cb80f46c88644ee710175f86059efb304814329a191c`. Artifact `12409058920` has ZIP SHA-256 `6e0ff828330e08f497577ed91bd1485af2f466c0880060f3e2f389a7edd77801` and expands to 31,947,386 bytes. The CPU and heap profile hashes are `31254e7deb651363a72f020eba482e1ec78f7bef2b135be07a40daaa4959c1ab` and `3e231bb2f244e8d754037386469695ac2addfe3cd9f39e633ce12779b7078d84`. Both carry native build ID `dcc7af53058d62d691ba2258d18fcf64ec4bf2e5`.

The profile run planned 36,000 commands, dispatched 35,251, and finished 35,247. It recorded 749 undispatched, one canceled, three canceled-pending, and zero failed, timed-out, or unresolved dispatched requests. All four replicas reported 35,247 executions with order hash `d12e0ae573ebc331e9af2541958948a28216d041259d50d7c65be108093cf9a9`. Its `passed` field records successful profile capture and trial correctness; the trial's load SLO still failed. Sampled peak RSS was 565.256 MB for the native process and 301.195 MB for the Python launcher.

For finished commands, scheduled arrival to finish p99 was 2,169.625 ms. Dispatch to finish p99, calculated from the same raw timestamps, was 36.275 ms, with a 458.901 ms maximum. The p99 for scheduled arrival to dispatch rose from 1.100 ms in the first 20-second window to 2,451.225 ms in the last. These observations locate most accumulated delay before dispatch, but do not isolate the scheduler, garbage collector, or network cause for each late command. The CPU profile spans 122.53 seconds and sampled 135.97 CPU seconds, or 110.96% of one core. Profile timings are diagnostic and are excluded from baseline comparisons.

The profile attributes 41.65% cumulative CPU to required ECDSA verification, 18.69% flat to Linux syscalls, 15.89% cumulative to the gRPC loopy writer, 14.25% cumulative to TLS writes, 3.81% cumulative to GC background workers, and 2.04% cumulative CPU to `Block.ToBytes`. Cumulative shares overlap. Allocation history estimates 9.50 GB allocated; `Block.ToBytes` accounts for 2.51 GB flat and 4.20 GB cumulative, or 44.26%. The CPU listing attributes 2.77 seconds, or 2.04%, to that function. Allocation volume alone does not show an overall speedup opportunity.

After worker shutdown and forced GC, the heap profile reported 166.91 MB in use. Its largest allocation sites were protobuf byte decoding at 115.60 MB, `NewBlock` at 12.50 MB, restored ECDSA signatures at 7 MB, and `Blockchain.Store` at 5.76 MB. These are allocation sites, not a reference graph of live objects or proof that request data remains retained. In `BlockFromProto`, the code calls `NewBlock` and then `SetTimestamp`; the constructor hashes `Block.ToBytes`, and `SetTimestamp` hashes it again. `Block.ToBytes` marshals the batch and certificate. The profile does not prove those paths cause the dispatch SLO failure. It also does not justify deleting blocks needed for chain traversal, bypassing signature verification, changing limiter burst, or tuning GC as an SLO fix.

The client uses `rate.NewLimiter(rate.Limit(conf.RateLimit), 1)` and `Wait`; its observer records scheduled arrival independently. The pinned [`golang.org/x/time v0.14.0` limiter source](https://github.com/golang/time/blob/v0.14.0/rate/rate.go) caps replenished tokens at burst. This bounds catch-up after a delay. It does not explain which runtime delay caused dispatch drift or establish that changing burst improves consensus behavior.

## Liveness and evidence limits

The separate permanent replica-1 isolation diagnostic remains a negative result. It exited 1, honest replicas r2/r3/r4 each committed zero, and `progress_passed` is false. A passing expected-failure diagnostic means the stall reproduced; it does not mean fault liveness passed. The profile smoke, healthy campaign, and this isolation case answer different questions.

Source and message-trace review located the first lost certificate: the honest view-4 proposal carries QC3, but all three honest votes go to isolated replica 1, the next leader. The view-6 honest proposal consequently extends the block certified by QC3. Available certified chains advance in pairs separated by view gaps, which the unchanged consecutive-view commit rule rejects. `protocol/comm/clique.go` sends votes exclusively to the next leader; `protocol/rules/chainedhotstuff.go` requires consecutive certified ancestors. The retained local trace is `scratch/benchmark-isolation-1792648235520195900/isolation/campaign/00-network.log`; its result records cleanup and zero honest commits.

This observed schedule matches the four-replica round-robin limitation analyzed in [Giridharan et al., BeeGees, PODC 2023, sections 3.3–3.4](https://nacrooks.github.io/bibliography/publications/2023-podc-beegees.pdf). That paper also explains why simply accepting nonconsecutive certificates can break safety. The current evidence does not establish an implementation defect in that commit condition or justify removing it. The stable-honest-leader control remains a separate positive journey. Supporting arbitrary faulty leader schedules requires a separately specified protocol or leadership-policy change and adversarial review; neither crypto optimization nor the passing control repairs the failed round-robin case.

The two campaigns ran from different source commits, so their measurements do not establish a causal change. No CPU model or total RAM was recorded. The profile heap was captured after worker shutdown and forced GC, and resource measurements include setup or cleanup. These limits keep the evidence useful for diagnosis but insufficient to claim maximum capacity, a sustained SLO, finality within 2 seconds, safe block pruning, or a security change.

The full campaign summary and original P08 report are retained at `C:\Users\steve\.codex\orchestrate\metrics30-20261022\evidence\P08-39737854265` and `C:\Users\steve\.codex\orchestrate\metrics30-20261022\reports\distributed-p08.md`. The profile archive and inspected pprof text outputs are retained at `C:\Users\steve\.codex\orchestrate\metrics30-20261022\evidence\P08-profile-39740846299`. The profile pprof reports are `cpu-flat.txt`, `cpu-cumulative.txt`, `cpu-all-cumulative.txt`, `heap-inuse.txt`, `heap-alloc.txt`, `heap-retained-paths.txt`, and `block-serialization.txt`.

## Reproduction and hosted receipts

Run the pinned Go checks and build from [AGENTS.md](../AGENTS.md), then `python tools/benchmark.py benchmark` for the frozen matrix and `python tools/benchmark.py profile` for separate diagnostics. The read-only manual workflow retains its allowlisted artifacts for 14 days. The original [full campaign](https://github.com/STEVVVU/hotstuff-consensus-engine/actions/runs/39737854265) and [native profile](https://github.com/STEVVVU/hotstuff-consensus-engine/actions/runs/39740846299) remain distinct runs. The local archive paths above identify retained copies after hosted artifact expiration.
