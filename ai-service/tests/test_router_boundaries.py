from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.core import HybridAgent


def settings() -> Settings:
    return Settings(
        core_dir=None, audit_dir=Path("runtime/audit"), sql_login_path="bank_ai_reader",
        spdb_sql_login_path="bank_ai_local", spdb_database="spdb_power_finance",
        mysql_binary=Path("/usr/local/mysql/bin/mysql"), cors_allowed_origins=("http://localhost:5173",),
        max_concurrency=1, database_healthcheck=False, sql_debug_enabled=False, sql_debug_token="",
        policy_rag_index_dir=SERVICE_ROOT / "runtime" / "policy_vector_index" / "public_effective",
    )


class RouterBoundaryTests(unittest.TestCase):
    def test_final_credit_determination_never_initializes_rag_or_sql(self) -> None:
        agent = HybridAgent(settings())
        result = agent.run("百旺信一定符合绿色贷款条件吗？")
        self.assertEqual(result["route"], "OUT_OF_SCOPE")
        self.assertEqual(result["tool_calls"], [])
        self.assertIn("不能作最终绿色贷款资格", result["final_answer"])

    def test_preliminary_project_policy_question_can_still_use_both_route(self) -> None:
        agent = HybridAgent(settings())
        self.assertFalse(agent._requires_final_credit_determination("百旺信项目是否适合绿色贷款？"))


if __name__ == "__main__":
    unittest.main()
