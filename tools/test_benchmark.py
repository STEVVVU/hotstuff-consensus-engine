import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import benchmark
from benchmark import safe_metrics,cells


class BenchmarkTests(unittest.TestCase):
    def test_secret_negative_control(self):
        marker='synthetic-private-key-never-upload'
        records=[{'@type':'type.googleapis.com/orchestrationpb.ReplicaOpts','PrivateKey':marker},{'@type':'type.googleapis.com/google.protobuf.Struct','value':{'schema':'hotstuff-client-command-v1','client':1,'sequence':'7','outcome':'finished','PrivateKey':marker,'latency_ms':2}}]
        result=safe_metrics(records)
        self.assertEqual(len(result),1)
        self.assertNotIn(marker,json.dumps(result))
        self.assertNotIn('PrivateKey',json.dumps(result))

    def test_axes(self):
        self.assertEqual({c['replicas'] for c in cells()},{4,7})
        self.assertEqual({c['payload'] for c in cells()},{32,1024,8192})

    def test_failed_sustained_slo_cannot_pass_campaign(self):
        def trial(path,cell,*args):
            return dict(passed=True,cell=cell,load_slo_passed=cell['seconds']<120,cleanup=dict(all_exited=True))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'scratch').mkdir()
            with mock.patch.object(benchmark,'ROOT',root), mock.patch.object(benchmark,'trial',side_effect=trial), \
                 mock.patch.object(benchmark,'environment',return_value={}), \
                 mock.patch.object(benchmark,'isolation',return_value=dict(passed=True,progress_passed=False,expected_progress_failure=True)), \
                 mock.patch.object(benchmark.sys,'argv',['benchmark.py','benchmark']), \
                 mock.patch.object(benchmark.sys,'platform','linux'), \
                 mock.patch.dict(benchmark.WORKLOAD,repeats=1,rates=[30]):
                self.assertEqual(benchmark.main(),1)
            summary=json.loads(next((root/'scratch').glob('benchmark-*/summary.json')).read_text())
            self.assertTrue(all(trial['passed'] for trial in summary['trials']))
            self.assertFalse(summary['stability_load_slo_passed'])
            self.assertFalse(summary['passed'])
            self.assertFalse(summary['isolation']['progress_passed'])
