package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/relab/hotstuff"
	"github.com/relab/hotstuff/core/logging"
	"github.com/relab/hotstuff/protocol/rules"
	"github.com/relab/hotstuff/twins"
	"github.com/relab/hotstuff/workbench"
)

type journey struct {
	Name     string         `json:"name"`
	Twins    uint8          `json:"twins"`
	Faulty   hotstuff.ID    `json:"faulty_replica,omitempty"`
	Minimum  int            `json:"minimum_commits_per_honest_node"`
	Scenario twins.Scenario `json:"scenario"`
}
type result struct {
	Journey    journey                       `json:"journey"`
	Passed     bool                          `json:"passed"`
	Error      string                        `json:"error,omitempty"`
	Nodes      map[string][]workbench.Commit `json:"honest_commits"`
	PublicKeys map[string]string             `json:"public_key_sha256"`
}

func main() {
	output := flag.String("output", "scratch/campaign", "fresh evidence directory")
	input := flag.String("input", "", "replay saved scenarios.json")
	seed := flag.Int64("seed", 244, "scenario seed")
	count := flag.Int("scenarios", 12, "random scenarios, 1..64")
	flag.Parse()
	if *count < 1 || *count > 64 {
		panic("scenarios must be 1..64")
	}
	if _, err := os.Stat(*output); !os.IsNotExist(err) {
		panic("output must not exist")
	}
	must(os.MkdirAll(*output, 0700))
	write(filepath.Join(*output, "status.json"), map[string]bool{"passed": false})
	logging.SetLogLevel("info")
	var cases []journey
	if *input != "" {
		info, err := os.Stat(*input)
		must(err)
		if info.Size() > 2<<20 {
			panic("replay file exceeds 2 MiB")
		}
		data, err := os.ReadFile(*input)
		must(err)
		must(json.Unmarshal(data, &cases))
		if len(cases) < 1 || len(cases) > 69 {
			panic("replay requires 1..69 scenarios")
		}
	} else {
		cases = append(cases, controlled("healthy", 0, 1), controlled("leader-loss-heal", 0, 1), controlled("leader-loss-honest-quorum", 0, 1), controlled("no-quorum", 0, 0), controlled("twins-heal", 1, 1))
		g := twins.NewGenerator(logging.New("campaign"), twins.Settings{NumNodes: 4, NumTwins: 1, Partitions: 2, Views: 8})
		g.Shuffle(*seed)
		for i := 0; i < *count; i++ {
			s, err := g.NextScenario()
			must(err)
			cases = append(cases, journey{Name: fmt.Sprintf("seed-%d-%d", *seed, i), Twins: 1, Scenario: s})
		}
	}
	write(filepath.Join(*output, "scenarios.json"), cases)
	passed := true
	var results []result
	for i, c := range cases {
		must(validate(c))
		if len(c.Scenario) < 1 || len(c.Scenario) > 40 || c.Twins > 1 || c.Minimum < 0 || c.Minimum > 10 {
			panic("invalid replay bounds")
		}
		r := result{Journey: c, Nodes: map[string][]workbench.Commit{}, PublicKeys: map[string]string{}}
		res, err := twins.ExecuteScenario(c.Scenario, 4, c.Twins, 300, rules.NameChainedHotStuff)
		if err == nil {
			for id, key := range res.NodeKeyFingerprints {
				r.PublicKeys[id.String()] = key
			}
			for id, blocks := range res.NodeCommits {
				if id.TwinID != 0 || id.ReplicaID == c.Faulty {
					continue
				}
				list := []workbench.Commit{}
				for _, b := range blocks {
					h := b.Hash()
					signers := 0
					if sig := b.QuorumCert().Signature(); sig != nil {
						signers = sig.Participants().Len()
					}
					list = append(list, workbench.Commit{Hash: hex.EncodeToString(h[:]), View: uint64(b.View()), Signers: signers, QCView: uint64(b.QuorumCert().View())})
				}
				r.Nodes[id.String()] = list
			}
			err = workbench.Check(r.Nodes, c.Minimum)
			if err == nil && !res.Safe {
				err = fmt.Errorf("upstream safety oracle failed")
			}
			if c.Name == "no-quorum" {
				for _, blocks := range r.Nodes {
					if len(blocks) > 0 {
						err = fmt.Errorf("committed without quorum")
					}
				}
			}
		}
		r.Passed = err == nil
		if err != nil {
			r.Error = err.Error()
			passed = false
		}
		must(os.WriteFile(filepath.Join(*output, fmt.Sprintf("%02d-network.log", i)), []byte(res.NetworkLog), 0600))
		results = append(results, r)
	}
	write(filepath.Join(*output, "results.json"), struct {
		Passed  bool     `json:"passed"`
		Seed    int64    `json:"seed"`
		Results []result `json:"results"`
	}{passed, *seed, results})
	if !passed {
		os.Exit(1)
	}
	write(filepath.Join(*output, "status.json"), map[string]bool{"passed": true})
}
func controlled(name string, n uint8, minimum int) journey {
	all := twins.NewNodeSet(twins.Replica(2), twins.Replica(3), twins.Replica(4))
	if n == 1 {
		all.Add(twins.Replica(1).Twin(1))
		all.Add(twins.Replica(1).Twin(2))
	} else {
		all.Add(twins.Replica(1))
	}
	s := twins.Scenario{}
	for v := 0; v < 24; v++ {
		p := []twins.NodeSet{all}
		leader := hotstuff.ID(v%4 + 1)
		if name == "no-quorum" {
			p = []twins.NodeSet{twins.NewNodeSet(twins.Replica(1), twins.Replica(2)), twins.NewNodeSet(twins.Replica(3), twins.Replica(4))}
		}
		if (name == "leader-loss-heal" && v < 1) || name == "leader-loss-honest-quorum" {
			if name == "leader-loss-honest-quorum" {
				leader = 2
			}
			if v == 0 {
				leader = 1
			}
			p = []twins.NodeSet{twins.NewNodeSet(twins.Replica(1)), twins.NewNodeSet(twins.Replica(2), twins.Replica(3), twins.Replica(4))}
		}
		if name == "twins-heal" && v < 1 {
			leader = 1
			p = []twins.NodeSet{twins.NewNodeSet(twins.Replica(1).Twin(1), twins.Replica(2)), twins.NewNodeSet(twins.Replica(1).Twin(2), twins.Replica(3), twins.Replica(4))}
		}
		s = append(s, twins.View{Leader: leader, Partitions: p})
	}
	j := journey{Name: name, Twins: n, Minimum: minimum, Scenario: s}
	if name == "leader-loss-honest-quorum" {
		j.Faulty = 1
	}
	return j
}
func must(err error) {
	if err != nil {
		panic(err)
	}
}

func validate(c journey) error {
	if c.Twins > 1 || c.Faulty > 1 || (c.Faulty != 0 && c.Twins != 0) {
		return fmt.Errorf("at most one twin identity")
	}
	for _, v := range c.Scenario {
		if v.Leader < 1 || v.Leader > 4 {
			return fmt.Errorf("invalid leader")
		}
		seen := map[twins.NodeID]bool{}
		for _, partition := range v.Partitions {
			for id := range partition {
				if id.ReplicaID < 1 || id.ReplicaID > 4 || seen[id] {
					return fmt.Errorf("invalid or duplicated node")
				}
				if c.Twins == 1 && id.ReplicaID == 1 {
					if id.TwinID != 1 && id.TwinID != 2 {
						return fmt.Errorf("invalid twin")
					}
				} else if id.TwinID != 0 {
					return fmt.Errorf("unexpected twin")
				}
				seen[id] = true
			}
		}
		if len(seen) != 4+int(c.Twins) {
			return fmt.Errorf("missing node")
		}
	}
	return nil
}
func write(path string, v any) {
	data, err := json.MarshalIndent(v, "", "  ")
	must(err)
	must(os.WriteFile(path, data, 0600))
}
