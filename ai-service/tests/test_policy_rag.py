from __future__ import annotations

import json
import sys
import unittest
from typing import Any
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.policy_rag import PolicyRAGAgent, PolicyRAGAnswerer, PolicyRAGError


EVIDENCE = {
    "chunk_id": "POL-029-C0002",
    "source_filename": "数据中心绿色低碳发展专项行动计划.pdf",
    "title": "数据中心绿色低碳发展专项行动计划",
    "text": "（二）严格新上项目能效水效要求。到2025年底，新建及改扩建大型和超大型数据中心电能利用效率降至1.25以内。",
    "authority_code": "GOV_POLICY",
    "policy_level": "NATIONAL",
    "issuing_authority": "国家发展改革委等",
    "status": "EFFECTIVE",
    "region": "全国",
    "effective_date": "2024-07-03",
    "expiry_date": "",
    "article_no": "（二）",
    "section_title": "（二）严格新上项目能效水效要求",
    "page_start": 2,
    "page_end": 2,
    "source_url": "https://example.test/policy",
    "confidentiality": "PUBLIC",
}


class FakeSearcher:
    def __init__(self, evidence: list[dict[str, Any]]) -> None:
        self.evidence = evidence
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self.queries.append((query, top_k))
        return self.evidence


class FakeBackend:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
        self.prompts.append(user_prompt)
        return json.dumps(self.responses.pop(0), ensure_ascii=False), {"model": "fake"}


class PolicyRAGTests(unittest.TestCase):
    def test_valid_answer_uses_program_owned_quote_and_policy_metadata(self) -> None:
        backend = FakeBackend([{
            "answerable": True,
            "answer": "《数据中心绿色低碳发展专项行动计划》规定了新建及改扩建大型和超大型数据中心的能效目标。",
            "citations": [{"evidence_id": "E1", "supporting_quote_id": "E1-S2"}],
        }])
        answerer = PolicyRAGAnswerer(FakeSearcher([EVIDENCE]), backend)
        result = answerer.answer("新建数据中心 PUE 有什么要求？")
        self.assertTrue(result["answerable"])
        self.assertEqual(result["references"][0]["page_start"], 2)
        self.assertEqual(result["references"][0]["policy_level"], "NATIONAL")
        self.assertEqual(result["references"][0]["status"], "EFFECTIVE")
        self.assertIn("新建及改扩建", result["references"][0]["supporting_quote"])
        self.assertEqual(backend.prompts[0].count("状态：EFFECTIVE"), 1)

    def test_invalid_citation_retries_then_succeeds(self) -> None:
        backend = FakeBackend([
            {"answerable": True, "answer": "错误引用", "citations": [{"evidence_id": "E1", "supporting_quote_id": "E9-S1"}]},
            {"answerable": True, "answer": "已按原文回答。", "citations": [{"evidence_id": "E1", "supporting_quote_id": "E1-S1"}]},
        ])
        result = PolicyRAGAnswerer(FakeSearcher([EVIDENCE]), backend).answer("测试")
        self.assertTrue(result["answerable"])
        self.assertEqual(len(backend.prompts), 2)
        self.assertIn("未通过引文校验", backend.prompts[1])

    def test_public_effective_boundary_is_checked_before_llm_prompt(self) -> None:
        private = dict(EVIDENCE, confidentiality="INTERNAL")
        with self.assertRaises(PolicyRAGError):
            PolicyRAGAnswerer(FakeSearcher([private]), FakeBackend([])).answer("测试")

    def test_policy_intent_router_does_not_capture_plain_sql_question(self) -> None:
        self.assertTrue(PolicyRAGAgent.supports("深圳训力券的申报条件是什么？"))
        self.assertTrue(PolicyRAGAgent.supports("新建数据中心PUE能效要求是多少？"))
        self.assertFalse(PolicyRAGAgent.supports("深圳百旺信智算中心2025年PUE是多少？"))


if __name__ == "__main__":
    unittest.main()
