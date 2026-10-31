import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import uuid


class FirmwareTests(unittest.TestCase):
    def test_host_build_finite_frames_and_protocol_errors(self):
        cmake = os.environ.get('CMAKE') or shutil.which('cmake')
        if not cmake:
            if os.environ.get('REQUIRE_FIRMWARE_TESTS'):
                self.fail('CMake required by CI but unavailable')
            self.skipTest('CMake unavailable; set CMAKE to run host compilation')
        root = Path(__file__).resolve().parents[1]
        (root / 'build').mkdir(exist_ok=True)
        tmp = root / 'build' / ('host-' + uuid.uuid4().hex[:8])
        tmp.mkdir()
        # Keep ignored build output available for troubleshooting.
        def run(args):
            result = subprocess.run(args, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout
        run([cmake, '-S', str(root / 'firmware'), '-B', str(tmp), '-DPC_BUILD=ON'])
        run([cmake, '--build', str(tmp), '--config', 'Release'])
        binaries = list(Path(tmp).rglob('node.elf')) + list(Path(tmp).rglob('node.exe'))
        checks = list(Path(tmp).rglob('protocol_check')) + list(Path(tmp).rglob('protocol_check.exe'))
        self.assertEqual(len(binaries), 1, 'one host binary required')
        self.assertEqual(len(checks), 1, 'protocol error harness required')
        frames = [json.loads(line) for line in run([str(binaries[0]), '--frames', '3']).splitlines()]
        self.assertEqual(len(frames), 3)
        for frame in frames:
            self.assertEqual(set(frame), {'id', 'name', 'ts', 'temp', 'hum', 'lux', 'anomaly'})
            self.assertIs(type(frame['anomaly']), bool)
            self.assertIs(type(frame['ts']), int)
            self.assertGreater(frame['ts'], 1700000000000)
        self.assertEqual(len({frame['ts'] for frame in frames}), 3)
        escaped = json.loads(run([str(checks[0])]))
        self.assertEqual(escaped['name'], 'a"b\\c\n')
        invalid = subprocess.run([str(binaries[0]), '--frames', '-1'], capture_output=True, timeout=3)
        self.assertNotEqual(invalid.returncode, 0)


if __name__ == '__main__':
    unittest.main()
