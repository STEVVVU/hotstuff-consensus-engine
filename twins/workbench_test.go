package twins

import (
	"github.com/relab/hotstuff"
	"github.com/relab/hotstuff/protocol/rules"
	"testing"
)

func TestWorkbenchInitialLeaderLossRecovery(t *testing.T) {
	all := NewNodeSet(Replica(1), Replica(2), Replica(3), Replica(4))
	s := Scenario{}
	for i := 0; i < 24; i++ {
		p := []NodeSet{all}
		leader := hotstuff.ID(i%4 + 1)
		if i < 1 {
			leader = 1
			p = []NodeSet{NewNodeSet(Replica(1)), NewNodeSet(Replica(2), Replica(3), Replica(4))}
		}
		s = append(s, View{Leader: leader, Partitions: p})
	}
	r, err := ExecuteScenario(s, 4, 0, 300, rules.NameChainedHotStuff)
	if err != nil {
		t.Fatal(err)
	}
	if !r.Safe {
		t.Fatal("unsafe")
	}
	for id, blocks := range r.NodeCommits {
		if len(blocks) == 0 {
			t.Fatalf("%s failed to progress after healing", id)
		}
	}
}
