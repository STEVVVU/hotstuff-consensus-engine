package workbench

import "testing"

func TestOracle(t *testing.T) {
	a := Commit{Hash: "a", View: 1, Signers: 3}
	b := Commit{Hash: "b", View: 2, Signers: 3}
	if err := Check(map[string][]Commit{"2": {a, b}, "3": {a}}, 1); err != nil {
		t.Fatal(err)
	}
	for name, nodes := range map[string]map[string][]Commit{
		"unsafe mutant": {"2": {a}, "3": {{Hash: "fork", View: 1, Signers: 3}}},
		"vacuous":       {"2": {}, "3": {}},
		"reordered":     {"2": {b, a}, "3": {b, a}},
		"short QC":      {"2": {{Hash: "a", View: 1, QCView: 1, Signers: 2}}, "3": {a}},
	} {
		t.Run(name, func(t *testing.T) {
			if Check(nodes, 1) == nil {
				t.Fatal("oracle accepted invalid evidence")
			}
		})
	}
}
