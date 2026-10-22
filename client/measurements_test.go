package client

import (
	"testing"
	"time"
)

func TestCommandMeasurementsKeepPendingAndScheduledArrival(t *testing.T) {
	var samples []CommandSample
	m := &commandMeasurements{pending: map[uint64]CommandSample{}, observe: func(sample CommandSample) { samples = append(samples, sample) }}
	start := time.Unix(1, 0)
	m.dispatch(1, start, start.Add(time.Second), []byte("first"))
	m.dispatch(2, start, start.Add(2*time.Second), []byte("second"))
	m.complete(1, "finished", start.Add(3*time.Second), nil)
	m.close(start.Add(4 * time.Second))
	if len(samples) != 4 || len(m.pending) != 0 {
		t.Fatalf("samples=%v pending=%v", samples, m.pending)
	}
	if samples[2].Ended.Sub(samples[2].Scheduled) != 3*time.Second || samples[3].Outcome != "canceled_pending" {
		t.Fatalf("lost queue delay or pending outcome: %v", samples)
	}
}
