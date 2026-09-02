from __future__ import annotations
import sys
import unittest
from pathlib import Path
SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path: sys.path.insert(0, str(SERVICE_ROOT))
from app.config import Settings
from app.due_diligence.orchestrator import DueDiligenceOrchestrator
from app.due_diligence.snapshot import RawProjectData
from .test_snapshot import raw_project

class Repo:
    def fetch(self, project_id): return raw_project()
class Tests(unittest.TestCase):
    def test_initial_dd_keeps_scenario_boundary_and_returns_risks_gaps(self):
        settings = Settings(None, Path('runtime/a'), 'x', 'x', 'spdb_power_finance', Path('/missing'), (), 1, False, False, '', Path('runtime/policy_vector_index/public_effective'))
        out = DueDiligenceOrchestrator(settings, Repo()).run('SZCF016')
        self.assertEqual(out['result_type'], 'INITIAL_DUE_DILIGENCE')
        self.assertEqual(out['scenarios'], [])
        self.assertIn('CFADS', out['scenario_boundary'])
        self.assertTrue(out['risks'] and out['evidence_gaps'])
        self.assertIn('不构成自动授信', out['warning'])
