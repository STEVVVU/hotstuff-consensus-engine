package client

import (
	"crypto/sha256"
	"encoding/hex"
	"sync"
	"time"
)

// CommandSample records client observations; a canceled request may still commit.
type CommandSample struct {
	Sequence                     uint64
	Outcome                      string
	PayloadSHA256                string
	Error                        string
	Scheduled, Dispatched, Ended time.Time
}

type commandMeasurements struct {
	mu      sync.Mutex
	pending map[uint64]CommandSample
	observe func(CommandSample)
}

func (m *commandMeasurements) dispatch(sequence uint64, scheduled, dispatched time.Time, payload []byte) {
	if m == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	sample := CommandSample{Sequence: sequence, Outcome: "dispatched", Scheduled: scheduled, Dispatched: dispatched}
	hash := sha256.Sum256(payload)
	sample.PayloadSHA256 = hex.EncodeToString(hash[:])
	m.pending[sequence] = sample
	m.observe(sample)
}

func (m *commandMeasurements) complete(sequence uint64, outcome string, ended time.Time, err error) {
	if m == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	sample, ok := m.pending[sequence]
	if !ok {
		return
	}
	delete(m.pending, sequence)
	sample.Outcome, sample.Ended = outcome, ended
	if err != nil {
		sample.Error = err.Error()
		if len(sample.Error) > 512 {
			sample.Error = sample.Error[:512]
		}
	}
	m.observe(sample)
}

func (m *commandMeasurements) close(ended time.Time) {
	if m == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	for sequence, sample := range m.pending {
		sample.Outcome, sample.Ended = "canceled_pending", ended
		m.observe(sample)
		delete(m.pending, sequence)
	}
}
