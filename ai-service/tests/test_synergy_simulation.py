from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.core import HybridAgent, CoreUnavailableError
from app.conversation.service import ConversationService
from app.energy_compute import EnergyComputeAgent
from app.energy_sql import ALLOWED_COLUMNS, QueryResult
from app.main import create_app
from app.synergy_simulation import SynergySimulationAgent, VERSION
from tests.test_router_boundaries import settings

class Executor:
    def __init__(self, missing=False):
        self.queries = []
        self.missing = missing

    def execute(self, sql):
        self.queries.append(sql)
        codes = [VERSION + '_' + code for code in ('BASE', 'CONSERVATIVE', 'OPTIMISTIC') if "'" + VERSION + '_' + code + "'" in sql]
        if 'FROM compute_synergy_simulation_v2' in sql:
            return QueryResult(['scenario_code', 'scenario_name', 'simulation_year', 'boundary', 'input_sha256'],
                               [[code, code.rsplit('_', 1)[1], '2025', 'SIMULATED only', 'a' * 64] for code in codes])
        if 'FROM compute_synergy_annual_v2' in sql:
            return QueryResult(['scenario_code', 'year_index', 'annual_energy_kwh', 'storage_saving_yuan', 'cfads_proxy_yuan', 'debt_service_yuan', 'dscr_proxy'],
                               [[code, str(year), '10000000', '400000', '8000000', '20000000', '0.4'] for code in codes for year in range(1, 10 if self.missing else 11)])
        if 'FROM compute_synergy_assumption_v2' in sql:
            return QueryResult(['scenario_code', 'field_code', 'field_label', 'actual_value', 'simulation_value', 'unit', 'input_type', 'basis'],
                               [[code, 'occupancy', '上架率', 'NULL', '.65', '比例', 'SIMULATED_ASSUMPTION', '研究假设'] for code in codes])
        if 'FROM v_compute_synergy_monthly_v2' in sql:
            return QueryResult(['scenario_code', 'month', 'facility_energy_kwh', 'grid_energy_kwh'],
                               [[code, '1', '10000', '11000'] for code in codes])
        raise AssertionError(sql)

class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.executor = Executor()
        self.agent = SynergySimulationAgent(settings(), self.executor)

    def test_scenarios_and_risk(self):
        result = self.agent.run('易信科技百旺信三期算电模拟对比')
        self.assertEqual(result['route'], 'SIMULATION')
        self.assertEqual(len(result['interpretation']['facts']), 12)
        self.assertEqual(len(result['interpretation']['warnings']), 3)
        self.assertTrue(all(s['authority_code'] == 'SIMULATED' for s in result['sources']))
        self.assertNotIn('finance_result', result)

    def test_gap_preserves_null_actual_values(self):
        result = self.agent.run('百旺信基准情景缺哪些数据')
        self.assertEqual(len(result['sources']), 1)
        self.assertIn('项目实际值未取得', result['interpretation']['facts'][-1]['value'])

    def test_monthly_units(self):
        result = self.agent.run('百旺信基准模拟月度用电')
        self.assertIn('电网购电 1.10 万 kWh', result['interpretation']['facts'][-1]['value'])

    def test_unknown_company_year_and_custom_inputs(self):
        for question, route in [('腾讯算电模拟', 'CLARIFICATION'), ('百旺信2027年模拟', 'IN_SCOPE_DATA_MISSING'), ('百旺信模拟利率改成3%', 'CLARIFICATION')]:
            self.assertEqual(self.agent.run(question)['route'], route)
        self.assertEqual(self.executor.queries, [])

    def test_incomplete_series(self):
        result = SynergySimulationAgent(settings(), Executor(True)).run('百旺信算电模拟')
        self.assertEqual(result['route'], 'IN_SCOPE_DATA_MISSING')
        self.assertEqual(result['interpretation']['facts'], [])

    def test_no_sql_interpolation(self):
        self.agent.run("百旺信基准模拟 ' OR 1=1 --")
        self.assertTrue(all('OR 1=1' not in sql for sql in self.executor.queries))

    def test_hybrid_priority(self):
        hybrid = HybridAgent(settings())
        hybrid._simulation_agent = self.agent
        self.assertEqual(hybrid.run('易信科技百旺信三期算电模拟DSCR是多少')['route'], 'SIMULATION')
        self.assertIsNone(hybrid._legacy_agent)

    def test_followup_and_provenance(self):
        service = ConversationService(self.agent.run)
        state, _, _ = service.run('易信科技算电模拟基准')
        state.active_entities = [{'type': 'COMPANY', 'id': 'C000020', 'name': '深圳地铁'}]
        state, result, effective = service.run('那保守情景呢？', state.session_id)
        self.assertEqual(effective, '百旺信三期算电模拟：那保守情景呢？')
        self.assertEqual(state.active_entities, [])
        self.assertTrue(result['sources'][0]['source_locator'].endswith('_CONSERVATIVE'))
        _, result, _ = service.run('数据来源是什么？', state.session_id)
        self.assertIn('已入库模拟情景', result['final_answer'])
        self.assertEqual(result['interpretation']['primary_conclusion'], result['final_answer'])

    def test_http_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            config = replace(settings(), audit_dir=Path(directory))
            client = TestClient(create_app(settings=config, agent_factory=lambda _: self.agent))
            response = client.post('/api/chat', json={'question': '百旺信基准算电模拟'})
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result['sources'][0]['authority'], 'SIMULATED')
            self.assertTrue(result['structured_data']['facts'])
            self.assertIsNone(result['data']['sql'])

    def test_nonexistent_numeric_source_is_not_invented(self):
        service = ConversationService(self.agent.run)
        state, _, _ = service.run('百旺信基准模拟')
        _, result, _ = service.run('999999这个数据哪里来的？', state.session_id)
        self.assertEqual(result['route'], 'CLARIFICATION')
        self.assertEqual(result['sources'], [])

    def test_formula_explanation_does_not_claim_new_calculation(self):
        service = ConversationService(self.agent.run)
        state, _, _ = service.run('百旺信基准模拟')
        count = len(self.executor.queries)
        _, result, _ = service.run('这个结果怎么算的？', state.session_id)
        self.assertEqual(result['route'], 'CALC_PROVENANCE')
        self.assertIn('未重新计算', result['final_answer'])
        self.assertEqual(len(self.executor.queries), count)

    def test_audited_schema_routing(self):
        for table, columns in ALLOWED_COLUMNS.items():
            for identifier in [table, *columns]:
                self.assertTrue(EnergyComputeAgent.has_sql_fact_signal(f'查询 {identifier} 的值'), identifier)
        self.assertFalse(EnergyComputeAgent.has_sql_fact_signal('unknown_mapping_status_extension'))

    def test_optional_legacy(self):
        for config in (settings(), replace(settings(), core_dir=Path('/missing-optional-core'))):
            with patch('app.core.build_legacy_agent', side_effect=CoreUnavailableError('missing')):
                result = HybridAgent(config).run('帮我写首诗')
                self.assertEqual(result['route'], 'OUT_OF_SCOPE')
                self.assertEqual(result['tool_calls'], [])
