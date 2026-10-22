package main

import "testing"

func TestReplayValidation(t *testing.T) {
	c := controlled("healthy", 0, 1)
	if err := validate(c); err != nil {
		t.Fatal(err)
	}
	c.Scenario[0].Leader = 0
	if validate(c) == nil {
		t.Fatal("invalid leader accepted")
	}
	c = controlled("twins-heal", 1, 1)
	if err := validate(c); err != nil {
		t.Fatal(err)
	}
	c.Scenario[0].Partitions = append(c.Scenario[0].Partitions, c.Scenario[0].Partitions[0])
	if validate(c) == nil {
		t.Fatal("duplicate node accepted")
	}
}
