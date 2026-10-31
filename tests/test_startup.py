import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from urllib.request import urlopen


class StartupTests(unittest.TestCase):
    def test_documented_entrypoint_starts_under_legacy_pipe_encoding(self):
        root = Path(__file__).resolve().parents[1]
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        env = dict(os.environ, SENSOR_PORT=str(port), SENSOR_INTERVAL='0.05',
                   SENSOR_SEED='startup-17', PYTHONIOENCODING='cp1252')
        child = subprocess.Popen([sys.executable, 'run.py'], cwd=root, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and child.poll() is None:
                try:
                    with urlopen(f'http://127.0.0.1:{port}/latest', timeout=0.5) as response:
                        frames = json.load(response)
                    self.assertEqual(len(frames), 3)
                    self.assertTrue(all(isinstance(frame['anomaly'], bool) for frame in frames))
                    break
                except OSError:
                    time.sleep(0.05)
            else:
                self.fail('documented entrypoint failed to become ready')
            self.assertIsNone(child.poll(), 'startup logging terminated the service')
        finally:
            child.terminate()
            output, errors = child.communicate(timeout=5)
            self.assertNotIn(b'UnicodeEncodeError', errors, output + errors)
