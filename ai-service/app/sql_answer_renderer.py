"""A constrained natural-language renderer over program-owned SQL semantics."""

from __future__ import annotations

from .result_interpreter import InterpretedSQLResult


def deterministic_sql_answer(interpreted: InterpretedSQLResult) -> str:
    blocks = [f"结论\n{interpreted.primary_conclusion}"]
    if interpreted.facts:
        facts = "\n".join(f"- {item['label']}：{item['value']}" for item in interpreted.facts)
        blocks.append(f"关键数据\n{facts}")
    if interpreted.candidates:
        candidates = "\n".join(
            f"- {item['name']}（{item['role']}）：{item['reason']}" for item in interpreted.candidates
        )
        blocks.append(f"候选参照\n{candidates}")
    if interpreted.boundaries:
        boundaries = "\n".join(f"- {item}" for item in interpreted.boundaries)
        blocks.append(f"证据边界\n{boundaries}")
    return "\n\n".join(blocks)


def render_sql_answer(question: str, interpreted: InterpretedSQLResult) -> str:
    """Render only the interpreted object.

    The V0.3.1 default is deterministic, which is the constrained renderer and
    the validator fallback in one.  A future LLM renderer may be inserted here
    only after receiving this exact object, never raw SQL/schema/connection data.
    """

    del question  # The renderer intentionally cannot infer from the raw question.
    return deterministic_sql_answer(interpreted)
