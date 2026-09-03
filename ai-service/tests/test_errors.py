from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.errors import ErrorCode, audit_error_details, classify_exception
from app.policy_rag import PolicyRAGError


class ErrorTaxonomyTests(unittest.TestCase):
    def test_timeouts_connections_rag_and_calculation_map_to_stable_codes(self) -> None:
        class APIConnectionError(ConnectionError):
            pass

        self.assertEqual(classify_exception(TimeoutError("upstream timed out")).code, ErrorCode.MODEL_TIMEOUT)
        self.assertEqual(classify_exception(APIConnectionError("network unavailable")).code, ErrorCode.MODEL_CONNECTION_ERROR)
        self.assertEqual(classify_exception(PolicyRAGError("政策索引记录缺失")).code, ErrorCode.RAG_INDEX_ERROR)
        self.assertEqual(classify_exception(PolicyRAGError("引文校验失败")).code, ErrorCode.RAG_VALIDATION_ERROR)
        self.assertEqual(classify_exception(ZeroDivisionError()).code, ErrorCode.CALCULATION_ERROR)

    def test_audit_technical_error_redacts_credentials_and_keeps_traceback_out_of_public_contract(self) -> None:
        details = audit_error_details(RuntimeError("Authorization: Bearer token-value password=bad sk-abcdefghijklmnop"))
        self.assertIn("[REDACTED]", details["exception_message"])
        self.assertNotIn("token-value", str(details))
        self.assertNotIn("abcdefghijklmnop", str(details))


if __name__ == "__main__":
    unittest.main()
