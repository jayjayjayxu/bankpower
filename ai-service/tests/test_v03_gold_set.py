from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from tools.evaluate_v03 import validate_gold


class V03GoldSetTests(unittest.TestCase):
    def test_gold_evidence_is_versioned_and_traceable_to_public_effective_chunks(self) -> None:
        result = validate_gold(
            SERVICE_ROOT / "eval" / "v03_gold_set.json",
            SERVICE_ROOT / "resources" / "policy_metadata_v03.csv",
            SERVICE_ROOT / "runtime" / "policy_corpus" / "public_effective" / "chunks.jsonl",
        )
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["case_count"], 90)


if __name__ == "__main__":
    unittest.main()
