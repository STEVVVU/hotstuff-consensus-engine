package server_test

import (
	"bytes"
	"github.com/relab/hotstuff/core/eventloop"
	"github.com/relab/hotstuff/core/logging"
	"github.com/relab/hotstuff/internal/proto/clientpb"
	"github.com/relab/hotstuff/server"
	"testing"
)

func TestWorkbenchDuplicateExecution(t *testing.T) {
	logger := logging.New("dedup")
	srv := server.NewClientIO(eventloop.New(logger, 10), logger, clientpb.NewCommandCache(1))
	t.Cleanup(srv.Stop)
	batch := &clientpb.Batch{Commands: []*clientpb.Command{{ClientID: 1, SequenceNumber: 1, Data: []byte("once")}}}
	srv.Exec(batch)
	first := srv.Hash().Sum(nil)
	srv.Exec(batch)
	if srv.CmdCount() != 1 || !bytes.Equal(first, srv.Hash().Sum(nil)) {
		t.Fatal("duplicate changed execution state")
	}
	srv.Exec(&clientpb.Batch{Commands: []*clientpb.Command{{ClientID: 1, SequenceNumber: 2, Data: []byte("next")}}})
	if srv.CmdCount() != 2 || bytes.Equal(first, srv.Hash().Sum(nil)) {
		t.Fatal("next command did not execute")
	}
}
