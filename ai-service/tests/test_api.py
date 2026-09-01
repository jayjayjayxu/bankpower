from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.audit import AuditLogger
from app.config import Settings
from app.core import CoreUnavailableError
from app.main import create_app


class FakeAgent:
    def __init__(self, route: str = "BOTH") -> None:
        self.route = route
        self.questions: list[str] = []

    def run(self, question: str) -> dict:
        self.questions.append(question)
        sql_result = None
        rag_result = None
        synthesis = None
        if self.route in {"SQL", "BOTH"}:
            sql_result = {
                "query_result": {
                    "columns": ["branch_name", "failure_count"],
                    "rows": [["深圳分行", "29"]],
                },
                "safety": {"safe": True},
            }
        if self.route in {"RAG", "BOTH"}:
            rag_result = {
                "answerable": True,
                "references": [
                    {
                        "source_filename": "商业银行业务连续性监管指引.pdf",
                        "page_start": 12,
                        "page_end": 12,
                        "authority_code": "REGULATION",
                        "supporting_quote": "商业银行应建立业务连续性管理体系。",
                    }
                ],
            }
        if self.route == "BOTH":
            synthesis = {
                "claims": [{"claim_type": "SQL_FACT", "text": "失败交易为29笔。", "support_ids": ["SQL"]}],
                "dropped_claims": [{"text": "没有依据的原因"}],
            }
        return {
            "agent_version": "V0.4",
            "question": question,
            "route": self.route,
            "router": {"route": self.route},
            "decomposition": None,
            "tool_calls": [],
            "sql_result": sql_result,
            "rag_result": rag_result,
            "synthesis": synthesis,
            "final_answer": "这是经过证据约束的测试答案。",
        }


def test_settings(audit_dir: Path) -> Settings:
    return Settings(
        core_dir=None,
        audit_dir=audit_dir,
        sql_login_path="unused",
        mysql_binary=Path("/missing/mysql"),
        cors_allowed_origins=("http://localhost:5173",),
        max_concurrency=1,
        database_healthcheck=False,
    )


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = test_settings(Path(self.temp_dir.name) / "audit")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_client(self, agent: FakeAgent) -> TestClient:
        return TestClient(
            create_app(
                settings=self.settings,
                agent_factory=lambda _: agent,
                audit_logger=AuditLogger(self.settings.audit_dir),
                health_checker=lambda _: {"database": "ok", "rag_index": "ok"},
            )
        )

    def test_health_reports_dependencies_without_constructing_agent(self) -> None:
        response = self.make_client(FakeAgent()).get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "agent_version": "V0.4", "database": "ok", "rag_index": "ok"})

    def test_chat_returns_only_public_evidence_and_writes_complete_audit(self) -> None:
        agent = FakeAgent("BOTH")
        response = self.make_client(agent).post(
            "/api/chat",
            headers={"X-Request-ID": "request-test-001"},
            json={"question": "找出失败交易最多的网点，并结合业务连续性要求提出关注点。"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["request_id"], "request-test-001")
        self.assertEqual(body["route"], "BOTH")
        self.assertEqual(body["data"]["sql"]["rows"], [["深圳分行", "29"]])
        self.assertEqual(body["sources"][0]["page_start"], 12)
        self.assertEqual(body["claims"][0]["support_ids"], ["SQL"])
        self.assertEqual(body["warnings"], ["1 条缺乏充分依据的结论未向用户展示。"])
        self.assertEqual(agent.questions, [body["question"]])

        audit_files = list(self.settings.audit_dir.rglob("request-test-001.json"))
        self.assertEqual(len(audit_files), 1)
        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "succeeded")
        self.assertEqual(audit["agent_result"]["router"], {"route": "BOTH"})
        self.assertIn("public_response", audit)

    def test_rag_sql_and_out_of_scope_paths_keep_their_own_evidence(self) -> None:
        expectations = {
            "RAG": (None, 1),
            "SQL": (["branch_name", "failure_count"], 0),
            "OUT_OF_SCOPE": (None, 0),
        }
        for route, (columns, source_count) in expectations.items():
            with self.subTest(route=route):
                response = self.make_client(FakeAgent(route)).post("/api/chat", json={"question": "测试问题"})
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["route"], route)
                if columns is None:
                    self.assertIsNone(body["data"]["sql"])
                else:
                    self.assertEqual(body["data"]["sql"]["columns"], columns)
                self.assertEqual(len(body["sources"]), source_count)

    def test_twenty_http_smoke_requests_cover_all_execution_paths(self) -> None:
        questions_by_route = {
            "RAG": [
                "银行保险机构应如何进行数据分类分级？",
                "监管文件对业务连续性有什么要求？",
                "银行应如何保护个人信息？",
                "金融机构数据安全管理办法的适用范围是什么？",
                "监管规定如何要求管理信息科技风险？",
            ],
            "SQL": [
                "2026年7月成功交易金额最高的3个网点是什么？",
                "查询逾期客户数量。",
                "失败交易最多的网点有哪些？",
                "各网点的交易金额是多少？",
                "有多少客户存在逾期贷款？",
            ],
            "BOTH": [
                "找出失败交易最多的网点，并结合业务连续性要求提出关注点。",
                "查询逾期客户，并结合数据分类分级要求说明保护重点。",
                "交易异常较多的网点应关注哪些监管要求？",
                "分析高风险客户数量并说明相应的数据安全要求。",
                "结合失败交易数据和监管要求提出初步关注点。",
            ],
            "OUT_OF_SCOPE": [
                "深圳今天气温多少？",
                "帮我写一首诗。",
                "推荐一家附近餐厅。",
                "解释量子力学。",
                "明天股市会上涨吗？",
            ],
        }
        requests_sent = 0
        for route, questions in questions_by_route.items():
            client = self.make_client(FakeAgent(route))
            for question in questions:
                with self.subTest(route=route, question=question):
                    response = client.post("/api/chat", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["route"], route)
                    requests_sent += 1
        self.assertEqual(requests_sent, 20)

    def test_invalid_question_is_rejected_before_agent_execution(self) -> None:
        agent = FakeAgent()
        response = self.make_client(agent).post("/api/chat", json={"question": "   "})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(agent.questions, [])

    def test_core_configuration_failure_is_audited_and_returns_503(self) -> None:
        def unavailable(_: Settings) -> FakeAgent:
            raise CoreUnavailableError("未设置 DEEPSEEK_API_KEY。")

        client = TestClient(
            create_app(
                settings=self.settings,
                agent_factory=unavailable,
                audit_logger=AuditLogger(self.settings.audit_dir),
                health_checker=lambda _: {"database": "ok", "rag_index": "ok"},
            )
        )
        response = client.post(
            "/api/chat",
            headers={"X-Request-ID": "request-test-configuration"},
            json={"question": "测试问题"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "core_unavailable")
        audit_files = list(self.settings.audit_dir.rglob("request-test-configuration.json"))
        self.assertEqual(len(audit_files), 1)
        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["error_code"], "core_unavailable")


if __name__ == "__main__":
    unittest.main()
