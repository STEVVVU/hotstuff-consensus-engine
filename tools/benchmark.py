"""Real ECDSA network benchmark and explicit bounded isolation diagnosis."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time

from benchmark_support import Run, environment, quantiles, save

ROOT=Path(__file__).resolve().parents[1]
WORKLOAD=dict(version=1,seed=421,replicas=[4,7],payload=[32,1024,8192],clients=[1,4],concurrency=[4,32],rate=100,repeats=5,seconds=10,rates=[30,100,300,1000],stability_seconds=120)
RAW_FIELDS={'schema','client','sequence','outcome','scheduled_unix_ns','dispatched_unix_ns','ended_unix_ns','dispatch_lag_ms','latency_ms','payload_sha256','error'}


def safe_metrics(records):
    """Allow only measurement fields; orchestration options contain ephemeral private keys."""
    clean=[]
    for record in records:
        if record.get('@type')=='type.googleapis.com/google.protobuf.Struct':
            value=record.get('value',{})
            if value.get('schema')=='hotstuff-client-command-v1':
                clean.append({key:value[key] for key in RAW_FIELDS if key in value})
        elif record.get('@type')=='type.googleapis.com/types.ThroughputMeasurement':
            event=record.get('Event',{})
            clean.append(dict(schema='hotstuff-throughput-v1',event={key:event[key] for key in ['ID','Client','Timestamp'] if key in event},commands=record.get('Commands',0),commits=record.get('Commits',0),duration=record.get('Duration')))
    return clean


def cells():
    base=dict(replicas=4,payload=1024,clients=1,concurrency=4,rate=WORKLOAD['rate'],seconds=WORKLOAD['seconds'])
    result=[]
    for axis in ['replicas','payload','clients','concurrency']:
        for value in WORKLOAD[axis]:
            cell=dict(base,**{axis:value})
            if cell not in result:result.append(cell)
    return result


def trial(path,cell,profile=False,binary=None):
    run=Run(path)
    result=dict(passed=False,cell=cell)
    try:
        config=run.path/'local.yaml';config.write_text('{}')
        ssh=run.path/'empty-ssh-config';ssh.write_text('')
        output=run.path/'network'
        command=[str(binary or ROOT/'scratch/hotstuff.exe'),'run','--config',str(config),'--ssh-config',str(ssh),'--replicas',str(cell['replicas']),'--clients',str(cell['clients']),'--max-concurrent',str(cell['concurrency']),'--duration',str(cell['seconds'])+'s','--crypto','ecdsa','--consensus','chainedhotstuff','--fixed-timeout','500ms','--payload-size',str(cell['payload']),'--rate-limit',str(cell['rate']/cell['clients']),'--measurement-interval','500ms','--metrics','throughput,client-commands','--shared-seed','421','--output',str(output),'--log-level','info']
        if profile:command.extend(['--cpu-profile','--mem-profile'])
        result['command']=command
        process=run.launch('network',command,dict(os.environ,GOMAXPROCS='2'))
        result['exit_code']=process.wait(timeout=cell['seconds']+30)
        assert result['exit_code']==0,result['exit_code']
        records=json.loads((output/'local/measurements.json').read_text())
        safe=safe_metrics(records);save(run.path/'metrics-safe.json',safe)
        (output/'local/measurements.json').write_text(json.dumps(safe))
        commands=[r for r in safe if r['schema']=='hotstuff-client-command-v1']
        starts={(r['client'],r['sequence']):r for r in commands if r['outcome']=='dispatched'}
        finishes={(r['client'],r['sequence']):r for r in commands if r['outcome']!='dispatched'}
        assert starts,'raw command observer did not run'
        assert not any(r['outcome']=='trace_overflow' for r in commands),'bounded command trace overflowed'
        assert set(finishes)<=set(starts),'completion without dispatch'
        outcomes={kind:sum(r['outcome']==kind for r in finishes.values()) for kind in ['finished','failed','timed_out','canceled','canceled_pending']}
        unresolved=len(set(starts)-set(finishes))
        result.update(planned_offers=math.ceil(cell['rate']*cell['seconds']),dispatched=len(starts),not_dispatched=max(0,math.ceil(cell['rate']*cell['seconds'])-len(starts)),outcomes=outcomes,unresolved=unresolved)
        result['extra_dispatched']=max(0,len(starts)-result['planned_offers'])
        result['latency_ms']=quantiles([r['latency_ms'] for r in finishes.values() if r['outcome']=='finished'])
        result['dispatch_lag_ms']=quantiles([r['dispatch_lag_ms'] for r in starts.values()])
        result['client_finished_per_second']=outcomes['finished']/cell['seconds']
        log=(run.path/'network.log').read_text(errors='replace')
        executions=re.findall(r'Execution evidence replica=(\d+) commands=(\d+) hash=([0-9a-f]+)',log)
        result['executions']=executions
        assert {int(v[0]) for v in executions}==set(range(1,cell['replicas']+1)),'missing replica execution proof'
        assert len({(v[1],v[2]) for v in executions})==1 and int(executions[0][1])>0,'replica executed order mismatch or no commits'
        result['replica_committed_commands']=int(executions[0][1]);result['replica_committed_per_second']=int(executions[0][1])/cell['seconds']
        result['passed']=not unresolved and outcomes['finished']>0
        steady_keys=set()
        if cell['seconds']>4:
            for client in {key[0] for key in starts}:
                first=min(int(value['scheduled_unix_ns']) for key,value in starts.items() if key[0]==client)
                steady_keys.update(key for key,value in starts.items() if key[0]==client and 2e9<=int(value['scheduled_unix_ns'])-first<(cell['seconds']-2)*1e9)
        per_client_rate=cell['rate']/cell['clients']
        expected_steady=cell['clients']*(math.ceil((cell['seconds']-2)*per_client_rate)-math.ceil(2*per_client_rate)) if cell['seconds']>4 else 0
        steady_finished=[finishes[key] for key in steady_keys if key in finishes and finishes[key]['outcome']=='finished']
        result['steady_window']=dict(scope='Exclude first2s warmup and final2s shutdown boundary; all whole-run outcomes remain above.',expected_offers=expected_steady,dispatched=len(steady_keys),finished=len(steady_finished),latency_ms=quantiles([r['latency_ms'] for r in steady_finished]),dispatch_lag_ms=quantiles([starts[key]['dispatch_lag_ms'] for key in steady_keys]))
        result['load_slo_passed']=result['passed'] and expected_steady>0 and len(steady_finished)==len(steady_keys)==expected_steady and result['steady_window']['dispatch_lag_ms']['p99']<100 and result['steady_window']['latency_ms']['p99']<5000
        if profile:
            profiles=list(output.rglob('cpuprofile'));assert profiles and all(file.stat().st_size for file in profiles),'missing native CPU profile'
            result['profile_files']=[str(file.relative_to(run.path)) for file in profiles]
    except Exception as error:result['error']=repr(error)
    finally:
        result['cleanup']=run.cleanup()
        result['passed']=result['passed'] and result['cleanup']['all_exited'] and not result['cleanup']['errors']
        save(run.path/'result.json',result)
    return result


def isolation(path):
    run=Run(path);result=dict(passed=False,expected_progress_failure=True)
    try:
        process=run.launch('campaign',[str(ROOT/'scratch/campaign.exe'),'-input',str(ROOT/'tools/fixtures/permanent-isolation.json'),'-output',str(run.path/'campaign')])
        result['exit_code']=process.wait(timeout=30)
        evidence=json.loads((run.path/'campaign/results.json').read_text());case=evidence['results'][0]
        result['honest_commits']={node:len(commits) for node,commits in case['honest_commits'].items()}
        result['progress_passed']=all(count>0 for count in result['honest_commits'].values())
        result['error']=case.get('error')
        result['passed']=result['exit_code']==1 and set(result['honest_commits'])=={'r2n0','r3n0','r4n0'} and all(count==0 for count in result['honest_commits'].values())
    except Exception as error:result['driver_error']=repr(error)
    finally:
        result['cleanup']=run.cleanup();result['passed']=result['passed'] and result['cleanup']['all_exited'];save(run.path/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['smoke','benchmark','profile','isolation'],nargs='?',default='smoke');parser.add_argument('--hotstuff',type=Path,default=ROOT/'scratch/hotstuff.exe');args=parser.parse_args()
    assert args.mode in ['smoke','isolation'] or sys.platform=='linux','isolated Linux required'
    directory=ROOT/'scratch'/('benchmark-'+args.mode+'-'+str(time.time_ns()));directory.mkdir(parents=True)
    summary=dict(passed=False,mode=args.mode,environment=environment(ROOT),workload=WORKLOAD,trials=[])
    def run(cell):
        value=trial(directory/('trial-'+str(len(summary['trials']))),cell,args.mode=='profile',args.hotstuff.resolve());summary['trials'].append(value);save(directory/'summary.json',summary)
        print(json.dumps(dict(passed=value['passed'],evidence=str(directory))),flush=True)
        if value.get('error') or not value['cleanup']['all_exited']:raise RuntimeError(value.get('error','cleanup failure'))
        return value
    try:
        base=dict(replicas=4,payload=32,clients=1,concurrency=4,rate=30,seconds=3)
        if args.mode=='smoke':run(base)
        elif args.mode=='isolation':summary['isolation']=isolation(directory/'isolation');summary['trials'].append(summary['isolation'])
        elif args.mode=='profile':run(dict(base,payload=1024,rate=1000,concurrency=32,seconds=30))
        else:
            matrix=cells()
            for repeat in range(WORKLOAD['repeats']):
                for cell in matrix if repeat%2==0 else reversed(matrix):run(dict(cell,repeat=repeat))
            sweeps=[run(dict(base,payload=1024,rate=rate,concurrency=32,seconds=10)) for rate in WORKLOAD['rates']]
            eligible=[value for value in sweeps if value['load_slo_passed']]
            if eligible:
                stability=run(dict(eligible[-1]['cell'],seconds=WORKLOAD['stability_seconds']))
                summary['stability_load_slo_passed']=stability['load_slo_passed']
            else:summary['stability_blocked']='No interior zero-loss rate with all steady-window offers dispatched and dispatch-p99<100ms. Whole-run shutdown cancellation remains explicit. Expand lower rates before SLO claim.'
            summary['isolation']=isolation(directory/'isolation')
        summary['passed']=all(value['passed'] for value in summary['trials']) and not summary.get('stability_blocked') and (args.mode!='benchmark' or summary.get('stability_load_slo_passed',False))
    except Exception as error:summary['error']=repr(error)
    finally:save(directory/'summary.json',summary)
    print(directory/'summary.json');return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
