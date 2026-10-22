# Provenance

Full-history clone of https://github.com/relab/hotstuff at 3179c6e62929294961acbfd9bf8445769716a121. No squash or shallow clone. MIT copyright 2020 John Ingve Olsen and Hans Erik Frøyland is retained. Source, authorship and APIs remain except focused correctness fixes and an additive public-key-fingerprint scenario result field. Module path remains github.com/relab/hotstuff for compatibility.

The Stanford [capstone](https://www.scs.stanford.edu/24sp-cs244b/projects/HotStuff_Implementation_and_Advice.pdf) motivates chained consensus, leader changes and adversarial verification. Its student source had no established reusable license and was not copied. The [Twins paper](https://arxiv.org/abs/2004.10617) motivates replayable partition and equivocation testing. The generator and engine are inherited; this adaptation adds bounded campaigns and explicit oracle/liveness requirements.

Dependencies are pinned in go.mod/go.sum. The baseline failed because gRPC 1.78.0 used http2.TrailerPrefix, removed by x/net 0.54.0. gRPC 1.84.0 resolves this, and minimum-version selection updates its required transitive modules. No new direct dependency was added. Module checksum verification, tests and vet do not establish absence of vulnerabilities.
