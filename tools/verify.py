"""Bounded local CLI verification; evidence survives subprocess cleanup."""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
from processes import run_owned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hotstuff", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout",type=float,default=45)
    args = parser.parse_args()
    if not 0.1 <= args.timeout <= 45:
        parser.error("timeout must be between 0.1 and 45 seconds")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"passed": False, "commands": [], "process_model": "one local worker process, four networked replica goroutines"}
    env = dict(os.environ, GOMAXPROCS="2")

    def run(name, command):
        entry = {"command": [str(v) for v in command], "exit_code": None}
        report["commands"].append(entry)
        with (output / (name + ".log")).open("w", encoding="utf8") as log:
            code = run_owned(entry["command"], log, timeout=args.timeout, env=env)
        entry["exit_code"] = code
        if code:
            raise RuntimeError(name + " failed")

    try:
        hotstuff = Path(args.hotstuff).resolve()
        campaign = Path(args.campaign).resolve()
        run("doctor", [hotstuff, "help", "run"])
        run("campaign", [campaign, "-output", output / "campaign"])
        run("replay", [campaign, "-input", output / "campaign/scenarios.json", "-output", output / "replay"])
        empty = output / "empty-ssh-config"
        empty.write_text("", encoding="utf8")
        config = output / "local.yaml"
        config.write_text("{}", encoding="utf8")
        run("network", [hotstuff, "run", "--config", config, "--ssh-config", empty,
                        "--replicas", "4", "--clients", "1", "--duration", "3s",
                        "--crypto", "ecdsa", "--consensus", "chainedhotstuff",
                        "--fixed-timeout", "500ms", "--payload-size", "16", "--rate-limit", "30", "--measurement-interval", "500ms",
                        "--output", output / "network", "--log-level", "info"])
        measurements = output / "network/local/measurements.json"
        records = json.loads(measurements.read_text(encoding="utf8"))
        report["measurement_records"] = len(records)
        report["nonzero_throughput_records"] = sum(int(r.get("Commands", 0)) > 0 for r in records)
        if not report["nonzero_throughput_records"]:
            raise RuntimeError("no measured executed commands")
        executions = re.findall(r"Execution evidence replica=(\d+) commands=(\d+) hash=([0-9a-f]+)", (output / "network.log").read_text(encoding="utf8"))
        report["executions"] = executions
        if {r[0] for r in executions} != {"1", "2", "3", "4"} or any(int(r[1]) == 0 for r in executions):
            raise RuntimeError("missing nonvacuous replica execution evidence")
        if len({(r[1], r[2]) for r in executions}) != 1:
            raise RuntimeError("replicas did not finish with identical executed order")
        report["passed"] = True
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
    finally:
        (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
