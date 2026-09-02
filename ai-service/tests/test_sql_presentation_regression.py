from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.answer_validator import validate_sql_answer
from app.energy_sql import QueryResult
from app.result_interpreter import interpret_sql_result
from app.sql_answer_renderer import render_sql_answer


GOLD_PATH = SERVICE_ROOT / "eval" / "v031_sql_presentation_set.json"
EXPECTED = {
    "FACT_LOOKUP": 8, "LIST": 5, "RANKING": 5, "COMPARISON": 5,
    "AGGREGATION": 4, "TIME_SERIES": 5, "ENTITY_MAPPING": 5, "NULL_NO_DATA": 3,
}


class SQLPresentationRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(GOLD_PATH.read_text(encoding="utf-8"))

    def test_presentation_set_has_forty_balanced_cases(self) -> None:
        self.assertEqual(len(self.cases), 40)
        self.assertEqual(len({item["id"] for item in self.cases}), 40)
        self.assertEqual(Counter(item["category"] for item in self.cases), EXPECTED)

    def test_every_case_keeps_status_numbers_and_boundaries_program_owned(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                result = QueryResult(case["columns"], case["rows"])
                interpreted = interpret_sql_result(case["question"], result)
                answer = render_sql_answer(case["question"], interpreted)
                self.assertEqual(interpreted.response_mode, case["expected_response_mode"])
                self.assertEqual(interpreted.answer_status, case["expected_answer_status"])
                self.assertTrue(validate_sql_answer(answer, interpreted).valid)
                self.assertNotIn("NULL", answer)
                self.assertNotIn("mapping_status=", answer)
                if case["required_conclusion_text"]:
                    self.assertIn(case["required_conclusion_text"], interpreted.primary_conclusion)


if __name__ == "__main__":
    unittest.main()
