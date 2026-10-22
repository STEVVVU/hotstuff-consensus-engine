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

    def test_profile_reuses_failed_sustained_workload(self):
        def trial(path,cell,profile,binary):
            self.assertTrue(profile)
            self.assertEqual(cell,dict(replicas=4,payload=1024,clients=1,concurrency=32,rate=300,seconds=120))
            return dict(passed=True,cell=cell,cleanup=dict(all_exited=True))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'scratch').mkdir()
            with mock.patch.object(benchmark,'ROOT',root), mock.patch.object(benchmark,'trial',side_effect=trial) as run, \
                 mock.patch.object(benchmark,'environment',return_value={}), \
                 mock.patch.object(benchmark.sys,'argv',['benchmark.py','profile']), \
                 mock.patch.object(benchmark.sys,'platform','linux'):
                self.assertEqual(benchmark.main(),0)
                self.assertEqual(run.call_count,1)

    def test_profile_requires_cpu_and_heap_receipts(self):
        for include_heap in [False,True]:
            with self.subTest(include_heap=include_heap), tempfile.TemporaryDirectory() as directory:
                path=Path(directory);output=path/'network'/'local';output.mkdir(parents=True)
                record=dict(schema='hotstuff-client-command-v1',client=1,sequence='1',scheduled_unix_ns='0',latency_ms=1,dispatch_lag_ms=0)
                records=[dict({'@type':'type.googleapis.com/google.protobuf.Struct'},value=dict(record,outcome=outcome)) for outcome in ['dispatched','finished']]
                (output/'measurements.json').write_text(json.dumps(records))
                (output/'cpuprofile').write_bytes(b'cpu receipt fixture')
                if include_heap:(output/'memprofile').write_bytes(b'heap receipt fixture')
                (path/'network.log').write_text('\n'.join(f'Execution evidence replica={replica} commands=1 hash=abcd' for replica in range(1,5)))
                run=mock.Mock(path=path)
                run.launch.return_value.wait.return_value=0
                run.cleanup.return_value=dict(all_exited=True,errors=[])
                with mock.patch.object(benchmark,'Run',return_value=run):
                    result=benchmark.trial(path,dict(replicas=4,payload=1024,clients=1,concurrency=32,rate=300,seconds=120),profile=True)
                self.assertEqual(result['passed'],include_heap)
                self.assertIn('--cpu-profile',run.launch.call_args.args[1])
                self.assertIn('--mem-profile',run.launch.call_args.args[1])
                if include_heap:self.assertEqual([Path(value) for value in result['profile_files']],[Path('network/local/cpuprofile'),Path('network/local/memprofile')])
                else:self.assertIn('missing native CPU or heap profile',result['error'])

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
