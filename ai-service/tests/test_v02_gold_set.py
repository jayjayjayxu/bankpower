from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.energy_sql import validate_energy_sql


GOLD_PATH = SERVICE_ROOT / "eval" / "v02_gold_set.json"


class GoldSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(GOLD_PATH.read_text(encoding="utf-8"))

    def test_has_sixty_balanced_cases_with_unique_ids(self) -> None:
        self.assertEqual(len(self.cases), 60)
        self.assertEqual(len({case["id"] for case in self.cases}), 60)
        self.assertEqual(
            Counter(case["category"] for case in self.cases),
            {
                "single_fact": 10,
                "filter_sort": 10,
                "join": 10,
                "aggregate": 10,
                "semantic": 10,
                "not_answerable": 10,
            },
        )

    def test_every_sql_gold_query_passes_the_v02_allow_list(self) -> None:
        failures: list[str] = []
        for case in self.cases:
            sql = case["gold_sql"]
            if sql is None:
                continue
            result = validate_energy_sql(sql)
            if not result.safe:
                failures.append(f"{case['id']}: {result.errors}")
        self.assertEqual(failures, [])

    def test_non_answerable_cases_do_not_have_sql(self) -> None:
        for case in self.cases:
            if case["category"] == "not_answerable":
                self.assertIsNone(case["gold_sql"], case["id"])


if __name__ == "__main__":
    unittest.main()
