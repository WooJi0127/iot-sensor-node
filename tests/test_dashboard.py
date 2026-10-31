from pathlib import Path
import shutil
import subprocess
import unittest


class DashboardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node unavailable for native dashboard regression')
    def test_ingest_deduplicates_reconnects_and_preserves_node_colors(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'tests/test_dashboard.cjs'], cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
