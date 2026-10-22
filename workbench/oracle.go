package workbench

import "fmt"

type Commit struct {
	Hash    string `json:"hash"`
	View    uint64 `json:"view"`
	Signers int    `json:"qc_signers"`
	QCView  uint64 `json:"qc_view"`
}

// Check compares every overlapping honest prefix, including replicas that lag.
func Check(nodes map[string][]Commit, minimum int) error {
	if len(nodes) < 2 {
		return fmt.Errorf("need at least two honest nodes")
	}
	byIndex := map[int]string{}
	for id, commits := range nodes {
		if len(commits) < minimum {
			return fmt.Errorf("%s committed %d, require %d", id, len(commits), minimum)
		}
		for i, block := range commits {
			if block.QCView > 0 && block.Signers < 3 {
				return fmt.Errorf("insufficient QC participants at %s index %d", id, i)
			}
			if block.Hash == "" || (i > 0 && block.View <= commits[i-1].View) {
				return fmt.Errorf("invalid order at %s index %d", id, i)
			}
			if hash, ok := byIndex[i]; ok && hash != block.Hash {
				return fmt.Errorf("conflicting commit at index %d", i)
			}
			byIndex[i] = block.Hash
		}
	}
	return nil
}
