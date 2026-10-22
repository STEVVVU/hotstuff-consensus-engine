"""Run an owned process with a bounded deadline and process-tree cleanup."""
import os
import signal
import subprocess


def run_owned(command, log, timeout, env):
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                               start_new_session=os.name != "nt")
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    capture_output=True, timeout=10)
            if killed.returncode and process.poll() is None:
                raise RuntimeError("owned process tree cleanup failed")
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        raise
