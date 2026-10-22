import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


class DriverFailureTests(unittest.TestCase):
    def drive(self, root, timeout):
        driver = Path(__file__).with_name("verify.py").resolve()
        return subprocess.run([sys.executable, str(driver), "--hotstuff", sys.executable,
                               "--campaign", sys.executable, "--output", str(root / "proof"),
                               "--timeout", str(timeout)], cwd=root, capture_output=True, timeout=15)

    def test_command_failure_keeps_false_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "help").write_text("raise SystemExit(7)", encoding="utf8")
            result = self.drive(root, 2)
            self.assertEqual(result.returncode, 1)
            summary = json.loads((root / "proof/summary.json").read_text())
            self.assertFalse(summary["passed"])
            self.assertEqual(summary["commands"][0]["exit_code"], 7)
            preserve("command-failure",summary)

    def test_timeout_cleans_owned_descendant_listener(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = "import os,socket,json,time; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); open('child.json','w').write(json.dumps({'parent':os.getppid(),'child':os.getpid(),'port':s.getsockname()[1]})); time.sleep(60)"
            (root / "help").write_text("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(child) + "])\ntime.sleep(60)\n", encoding="utf8")
            result = self.drive(root, 2)
            self.assertEqual(result.returncode, 1, result.stderr)
            state = json.loads((root / "child.json").read_text())
            summary = json.loads((root / "proof/summary.json").read_text())
            self.assertFalse(summary["passed"])
            self.assertIn("timed out", summary["error"])
            for pid in (state["parent"], state["child"]):
                self.assertFalse(alive(pid), f"owned PID {pid} survived cleanup")
            with socket.socket() as connection:
                connection.settimeout(1)
                self.assertNotEqual(connection.connect_ex(("127.0.0.1", state["port"])), 0)
            preserve("timeout",dict(summary,owned_pids=state,owned_processes_stopped=True,listener_closed=True))


def alive(pid):
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ctypes.WinError(ctypes.get_last_error())
            return code.value == 259
        finally:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def preserve(name, evidence):
    output=Path(__file__).resolve().parents[1]/"scratch/driver-controls"
    output.mkdir(parents=True,exist_ok=True)
    (output/(name+".json")).write_text(json.dumps(evidence,indent=2),encoding="utf8")


if __name__ == "__main__":
    unittest.main()
