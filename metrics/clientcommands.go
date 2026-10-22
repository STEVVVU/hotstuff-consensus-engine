package metrics

import (
	"strconv"
	"time"

	"github.com/relab/hotstuff/client"
	"google.golang.org/protobuf/types/known/structpb"
)

const NameClientCommands = "client-commands"

// CommandObserver writes bounded raw observations directly, including shutdown pending work.
func CommandObserver(logger Logger, id client.ID) func(client.CommandSample) {
	count := 0
	return func(sample client.CommandSample) {
		count++
		if count > 262145 {
			return
		}
		outcome := sample.Outcome
		if count == 262145 {
			outcome = "trace_overflow"
		}
		latency := 0.0
		ended := ""
		if !sample.Ended.IsZero() {
			latency = float64(sample.Ended.Sub(sample.Scheduled)) / float64(time.Millisecond)
			ended = strconv.FormatInt(sample.Ended.UnixNano(), 10)
		}
		value, err := structpb.NewStruct(map[string]any{
			"schema": "hotstuff-client-command-v1", "client": float64(id), "sequence": strconv.FormatUint(sample.Sequence, 10), "outcome": outcome,
			"payload_sha256": sample.PayloadSHA256, "error": sample.Error,
			"scheduled_unix_ns": strconv.FormatInt(sample.Scheduled.UnixNano(), 10), "dispatched_unix_ns": strconv.FormatInt(sample.Dispatched.UnixNano(), 10),
			"ended_unix_ns": ended, "dispatch_lag_ms": float64(sample.Dispatched.Sub(sample.Scheduled)) / float64(time.Millisecond),
			"latency_ms": latency,
		})
		if err != nil {
			panic(err)
		}
		logger.Log(value)
	}
}
