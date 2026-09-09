"""Read the explicitly simulated project layer using fixed, bounded queries.

No user text enters SQL and no simulation is passed to credit approval tools.
The company name selects this disclosed project scope, never group accounts.
"""
from __future__ import annotations

import re
from typing import Any

from .config import Settings
from .energy_sql import SpdbReadOnlyExecutor

VERSION = "BWX_SIM_20260908_V2"
ALIASES = ("百旺信", "易信科技", "szcf016", "fac-sz-001")
BOUNDARY = (
    "以下为已入库的 SIMULATED 情景，范围仅为深圳易信科技股份有限公司的百旺信云数据中心三期（SZCF016），不是企业合并财务或项目实测结果。",
    "使用 2025 年合成负荷形状及 2026 年 7 月电价情景，不是历史电费账单；CFADS、税费与 DSCR 均为代理测算，不能作为授信审批依据。",
    "实际负荷、上架率、合同价格、回款、接入批复及贷款条款仍需原始证据。模拟补全只保证情景可计算，不代表真实资料齐全。",
)


class SynergySimulationAgent:
    def __init__(self, settings: Settings, executor=None):
        self.executor = executor or SpdbReadOnlyExecutor(settings)

    @staticmethod
    def supports(question: str) -> bool:
        q = question.casefold()
        target = any(alias in q for alias in ALIASES)
        intent = any(word in q for word in ("模拟", "算电", "情景", "缺失", "缺哪些", "缺什么", "补全", "还缺", "数据缺口"))
        return (target and intent) or ("算电" in q and "模拟" in q)

    def _query(self, sql: str) -> list[dict[str, Any]]:
        result = self.executor.execute(sql)
        return [dict(zip(result.columns, row)) for row in result.rows]

    @staticmethod
    def _response(question, answer, facts=None, sources=None, warnings=None, route="SIMULATION"):
        return {
            "question": question, "route": route,
            "router": {"route": route, "data_type": "SIMULATED", "model_version": VERSION},
            "tool_calls": [], "sources": sources or [], "final_answer": answer,
            "interpretation": {"primary_conclusion": answer, "facts": facts or [],
                               "warnings": warnings or [], "boundaries": list(BOUNDARY)},
        }

    def run(self, question: str) -> dict[str, Any]:
        q = question.casefold()
        if not any(alias in q for alias in ALIASES):
            return self._response(question, "目前已入库的算电模拟案例为百旺信三期。请明确是否查询该案例，不能将其模拟值套用到其他企业。", route="CLARIFICATION")
        years = set(re.findall(r"(?<!\d)(20\d{2})年", q))
        if years - {"2025"}:
            return self._response(question, "当前仅有 2025 年负荷形状的固定模拟版本，未查询到所指定年份的模拟版本；不能将现有结果改标为该年份。", route="IN_SCOPE_DATA_MISSING")
        if any(term in q for term in ("改成", "改为", "调整为", "假设", "如果", "重新模拟", "重新计算")):
            return self._response(question, "当前问答可读取基准、保守、乐观三组已入库情景，不会把自定义参数伪装成已重算结果。需要先通过模拟模型重算并保存新版本后查询。", route="CLARIFICATION")
        names = [("基准", "BASE"), ("保守", "CONSERVATIVE"), ("乐观", "OPTIMISTIC")]
        selected = [code for name, code in names if name in q]
        explicit_selection = bool(selected)
        if not selected:
            selected = [code for _, code in names]
        # Only program-owned constants are used to construct this IN clause.
        codes = ",".join("'" + VERSION + "_" + code + "'" for code in selected)
        scenarios = self._query(
            "SELECT scenario_code,scenario_name,simulation_year,boundary,input_sha256 "
            "FROM compute_synergy_simulation_v2 WHERE facility_code='SZCF016' "
            "AND data_type='SIMULATED' AND scenario_code IN (" + codes + ") ORDER BY scenario_code LIMIT 3"
        )
        annual = self._query(
            "SELECT scenario_code,year_index,annual_energy_kwh,storage_saving_yuan,cfads_proxy_yuan,"
            "debt_service_yuan,dscr_proxy FROM compute_synergy_annual_v2 WHERE scenario_code IN ("
            + codes + ") AND year_index BETWEEN 1 AND 10 ORDER BY scenario_code,year_index LIMIT 30"
        )
        if len(scenarios) != len(selected) or len(annual) != 10 * len(selected):
            return self._response(question, "已入库模拟版本缺少情景或逐年结果，暂不输出不完整测算。请检查模拟数据导入状态。", route="IN_SCOPE_DATA_MISSING")
        facts, warnings = [], []
        for scenario in scenarios:
            rows = [r for r in annual if r["scenario_code"] == scenario["scenario_code"]]
            first = next(r for r in rows if int(r["year_index"]) == 1)
            dscr = [float(r["dscr_proxy"]) for r in rows if r["dscr_proxy"] not in (None, "", "NULL")]
            name = scenario["scenario_name"]
            values = (
                ("energy", "首年设施用电量", f'{float(first["annual_energy_kwh"]) / 10000:,.2f} 万 kWh'),
                ("saving", "首年储能电费节省（未扣储能运维）", f'{float(first["storage_saving_yuan"]) / 10000:,.2f} 万元'),
                ("cfads", "首年 CFADS 代理值", f'{float(first["cfads_proxy_yuan"]) / 10000:,.2f} 万元'),
                ("dscr", "10 年最低 DSCR 代理值", f'{min(dscr):.4f}' if len(dscr) == 10 else "缺失，不能判定偿债覆盖"),
            )
            for key, label, value in values:
                facts.append({"key": scenario["scenario_code"] + key, "label": f"{name} · {label}（模拟）", "value": value, "data_type": "SIMULATED"})
            if dscr and min(dscr) < 1:
                warnings.append(f"{name}最低 DSCR 代理值小于 1，情景现金流不足以覆盖本息；不能据此推荐当前债务比例。")
        gap_question = any(term in q for term in ("缺", "补全", "假定", "参数", "上架率", "pue", "价格", "比例", "利率", "期限", "储能容量"))
        if gap_question:
            gap_codes = codes if explicit_selection else "'" + VERSION + "_BASE'"
            assumptions = self._query(
                "SELECT scenario_code,field_code,field_label,actual_value,simulation_value,unit,input_type,basis "
                "FROM compute_synergy_assumption_v2 WHERE scenario_code IN (" + gap_codes + ") ORDER BY scenario_code,field_code LIMIT 93"
            )
            for row in assumptions:
                actual = row["actual_value"]
                status = "项目实际值未取得" if actual in (None, "", "NULL") else f"实际字段 {actual} {row['unit']}"
                facts.append({"key": row["scenario_code"] + row["field_code"],
                              "label": f"{row['scenario_code']} · {row['field_label']}",
                              "value": f"{status}；情景采用 {row['simulation_value']} {row['unit']}；类型 {row['input_type']}；依据：{row['basis']}",
                              "data_type": row["input_type"], "category": "SIMULATION_ASSUMPTION"})
        if "月" in q:
            monthly = self._query(
                "SELECT scenario_code,month,facility_energy_kwh,grid_energy_kwh FROM v_compute_synergy_monthly_v2 "
                "WHERE scenario_code IN (" + codes + ") ORDER BY scenario_code,month LIMIT 36"
            )
            for row in monthly:
                facts.append({"key": row["scenario_code"] + str(row["month"]), "label": f"{row['scenario_code']} · {row['month']} 月（模拟）",
                              "value": f"设施用电 {float(row['facility_energy_kwh']) / 10000:,.2f} 万 kWh；电网购电 {float(row['grid_energy_kwh']) / 10000:,.2f} 万 kWh", "data_type": "SIMULATED"})
        sources = [{"source_filename": "spdb_power_finance.compute_synergy_simulation_v2",
                    "authority_code": "SIMULATED", "source_locator": r["scenario_code"],
                    "supporting_quote": f"input_sha256={r['input_sha256']}；{r['boundary']}"} for r in scenarios]
        answer = "已读取百旺信三期的" + "、".join(str(r["scenario_name"]) for r in scenarios) + "。所有数值属于情景测算，重要真实资料仍待补证。"
        if gap_question and not explicit_selection:
            answer += "参数缺口清单展示基准情景，可指定保守或乐观情景查询对应参数。"
        if warnings:
            answer += "所查情景存在 DSCR 小于 1 的偿债覆盖缺口。"
        result = self._response(question, answer, facts, sources, warnings)
        result["tool_calls"] = [{"tool": "READ_STORED_SIMULATION", "executed": True, "model_version": VERSION}]
        return result
