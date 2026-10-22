package cert_test

import (
	"github.com/relab/hotstuff"
	"github.com/relab/hotstuff/security/crypto"
	"testing"
)

func TestWorkbenchDistinctQuorum(t *testing.T) {
	signers, block := createSignersWithBlock(t, crypto.NameECDSA, 0)
	pcs := make([]hotstuff.PartialCert, 3)
	for i := range pcs {
		var err error
		pcs[i], err = signers[i].CreatePartialCert(block)
		if err != nil {
			t.Fatal(err)
		}
	}
	qc, err := signers[0].CreateQuorumCert(block, pcs)
	if err != nil {
		t.Fatal(err)
	}
	if err = signers[0].VerifyQuorumCert(qc); err != nil {
		t.Fatal(err)
	}
	short, err := signers[0].CreateQuorumCert(block, pcs[:2])
	if err != nil {
		t.Fatal(err)
	}
	if signers[0].VerifyQuorumCert(short) == nil {
		t.Fatal("two of four accepted")
	}
	sig := pcs[0].Signature().(crypto.Multi[*crypto.ECDSASignature])[0]
	duplicate := hotstuff.NewQuorumCert(crypto.NewMulti(sig, sig, sig), block.View(), block.Hash())
	if signers[0].VerifyQuorumCert(duplicate) == nil {
		t.Fatal("one signer repeated three times accepted")
	}
	bad := crypto.RestoreECDSASignature([]byte("invalid"), 3)
	invalid := hotstuff.NewQuorumCert(crypto.NewMulti(sig, pcs[1].Signature().(crypto.Multi[*crypto.ECDSASignature])[0], bad), block.View(), block.Hash())
	if signers[0].VerifyQuorumCert(invalid) == nil {
		t.Fatal("invalid signature accepted")
	}
	view := hotstuff.View(1)
	timeoutSig, err := signers[0].Sign(view.ToBytes())
	if err != nil {
		t.Fatal(err)
	}
	timeoutPart := timeoutSig.(crypto.Multi[*crypto.ECDSASignature])[0]
	if signers[0].VerifyTimeoutCert(hotstuff.NewTimeoutCert(crypto.NewMulti(timeoutPart, timeoutPart, timeoutPart), view)) == nil {
		t.Fatal("repeated timeout signer accepted")
	}
	genesis, err := signers[0].CreateQuorumCert(hotstuff.GetGenesis(), nil)
	if err != nil {
		t.Fatal(err)
	}
	msg := hotstuff.TimeoutMsg{ID: 1, View: view, SyncInfo: hotstuff.NewSyncInfoWith(genesis)}
	aggSig, err := signers[0].Sign(msg.ToBytes())
	if err != nil {
		t.Fatal(err)
	}
	aggPart := aggSig.(crypto.Multi[*crypto.ECDSASignature])[0]
	agg := hotstuff.NewAggregateQC(map[hotstuff.ID]hotstuff.QuorumCert{1: genesis}, crypto.NewMulti(aggPart, aggPart, aggPart), view)
	if _, err := signers[0].VerifyAggregateQC(agg); err == nil {
		t.Fatal("repeated aggregate signer accepted")
	}
}

func TestWorkbenchMalformedCertificates(t *testing.T) {
	signers, block := createSignersWithBlock(t, crypto.NameECDSA, 0)
	t.Run("nil timeout", func(t *testing.T) {
		if signers[0].VerifyTimeoutCert(hotstuff.NewTimeoutCert(nil, 1)) == nil {
			t.Fatal("nil timeout accepted")
		}
	})
	t.Run("nil aggregate", func(t *testing.T) {
		if _, err := signers[0].VerifyAggregateQC(hotstuff.NewAggregateQC(nil, nil, 1)); err == nil {
			t.Fatal("nil aggregate accepted")
		}
	})
	t.Run("genesis view", func(t *testing.T) {
		if signers[0].VerifyQuorumCert(hotstuff.NewQuorumCert(nil, 99, hotstuff.GetGenesis().Hash())) == nil {
			t.Fatal("forged genesis view accepted")
		}
	})
	t.Run("signed block view", func(t *testing.T) {
		pcs := make([]hotstuff.PartialCert, 3)
		for i := range pcs {
			var err error
			pcs[i], err = signers[i].CreatePartialCert(block)
			if err != nil {
				t.Fatal(err)
			}
		}
		qc, err := signers[0].CreateQuorumCert(block, pcs)
		if err != nil {
			t.Fatal(err)
		}
		if signers[0].VerifyQuorumCert(hotstuff.NewQuorumCert(qc.Signature(), block.View()+99, block.Hash())) == nil {
			t.Fatal("forged signed block view accepted")
		}
	})
}

func TestWorkbenchCacheSignerIdentity(t *testing.T) {
	signers, block := createSignersWithBlock(t, crypto.NameECDSA, 10)
	pcs := make([]hotstuff.PartialCert, 3)
	for i := range pcs {
		var err error
		pcs[i], err = signers[i].CreatePartialCert(block)
		if err != nil {
			t.Fatal(err)
		}
	}
	qc, err := signers[0].CreateQuorumCert(block, pcs)
	if err != nil {
		t.Fatal(err)
	}
	if err := signers[0].VerifyQuorumCert(qc); err != nil {
		t.Fatal(err)
	}
	parts := append(crypto.Multi[*crypto.ECDSASignature]{}, qc.Signature().(crypto.Multi[*crypto.ECDSASignature])...)
	parts[2] = crypto.RestoreECDSASignature(parts[2].ToBytes(), 99)
	if signers[0].VerifyQuorumCert(hotstuff.NewQuorumCert(parts, block.View(), block.Hash())) == nil {
		t.Fatal("cached signature relabeled as unknown signer accepted")
	}
}

func TestWorkbenchCacheBatchContents(t *testing.T) {
	signers, _ := createSignersWithBlock(t, crypto.NameECDSA, 10)
	batch := map[hotstuff.ID][]byte{1: []byte("first"), 2: []byte("second"), 3: []byte("third")}
	sigs := []hotstuff.QuorumSignature{}
	for i := range 3 {
		sig, err := signers[i].Sign(batch[hotstuff.ID(i+1)])
		if err != nil {
			t.Fatal(err)
		}
		sigs = append(sigs, sig)
	}
	combined, err := signers[0].Combine(sigs...)
	if err != nil {
		t.Fatal(err)
	}
	if err := signers[0].BatchVerify(combined, batch); err != nil {
		t.Fatal(err)
	}
	batch[2] = []byte("tampered")
	if signers[0].BatchVerify(combined, batch) == nil {
		t.Fatal("cached signature accepted modified batch")
	}
}
