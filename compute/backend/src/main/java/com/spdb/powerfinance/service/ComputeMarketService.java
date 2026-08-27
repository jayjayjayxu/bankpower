package com.spdb.powerfinance.service;

import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
@Transactional(readOnly = true)
public class ComputeMarketService {
    private final NamedParameterJdbcTemplate jdbc;

    public ComputeMarketService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Map<String, Object> getSummary() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("coverage", normalizeRow(jdbc.queryForMap("""
                SELECT (SELECT COUNT(*) FROM enterprise_data_center_v2) AS facility_count,
                       (SELECT COUNT(*) FROM compute_service_platform_v1) AS platform_count,
                       (SELECT COUNT(*) FROM compute_platform_resource_listing_v1) AS product_count,
                       (SELECT COUNT(*) FROM compute_product_price_snapshot_v1) AS price_count,
                       (SELECT COUNT(*) FROM compute_field_evidence_v1) AS evidence_count,
                       (SELECT COUNT(*) FROM v_compute_product_price_conflict_v1) AS price_conflict_count,
                       (SELECT COUNT(*) FROM compute_operation_scenario_v1
                         WHERE scenario_version IN ('COMPUTE_CONSERVATIVE_V1','COMPUTE_BASE_V1','COMPUTE_OPTIMISTIC_V1')) AS scenario_count,
                       (SELECT COUNT(*) FROM compute_operation_scenario_v1
                         WHERE scenario_version='COMPUTE_BASE_V1') AS base_scenario_count,
                       (SELECT COUNT(*) FROM compute_economics_result_v1
                         WHERE model_version='COMPUTE_ECONOMICS_V1') AS economics_result_count,
                       (SELECT COUNT(*) FROM compute_capex_parameter_v1) AS capex_scenario_count,
                       (SELECT COUNT(*) FROM compute_project_economics_result_v1) AS project_economics_count,
                       (SELECT COUNT(*) FROM compute_sensitivity_result_v1) AS sensitivity_result_count,
                       (SELECT COUNT(*) FROM compute_financing_scenario_v1) AS financing_scenario_count,
                       (SELECT COUNT(*) FROM compute_financing_result_v1) AS financing_result_count,
                       (SELECT COUNT(*) FROM compute_credit_policy_scenario_v1) AS credit_policy_count,
                       (SELECT COUNT(*) FROM compute_credit_policy_financing_curve_v1) AS credit_policy_curve_count,
                       (SELECT COUNT(*) FROM compute_bank_recommendation_v1) AS bank_recommendation_count,
                       (SELECT COUNT(*) FROM policy_document_v1
                         WHERE policy_category IN ('COMPUTE_INFRASTRUCTURE','GREEN_DATA_CENTER','COMPUTE_ENERGY_SYNERGY','AI_INDUSTRY','COMPUTE_VOUCHER','GREEN_LOW_CARBON')) AS compute_policy_document_count,
                       (SELECT COUNT(*) FROM policy_rule_v1 WHERE rule_code IN (
                         'NAT_GREEN_DC_2025_PUE','NAT_GREEN_DC_2025_RENEWABLE','NAT_GREEN_DC_2025_DEMAND_RESPONSE',
                         'NAT_GREEN_DC_2025_RACK_UTILIZATION','NAT_GREEN_DC_2025_IT_LOAD','NAT_GREEN_FINANCE_2025_GREEN_DC',
                         'NAT_AI_ENERGY_2026_GREEN_POWER','NAT_AI_ENERGY_2026_MARKET','NAT_AI_ENERGY_2026_GREEN_FINANCE',
                         'GD_AI_2025_COMPUTE_VOUCHER','SZ_AI_2026_DEMONSTRATION_GRANT','SZ_TRAINING_VOUCHER_2026_DEMAND',
                         'SZ_TRAINING_VOUCHER_2026_EVIDENCE','LG_AI_2026_COMPUTE_PURCHASE','SZ_COMPUTE_2025_PUE_REFERENCE',
                         'SZ_GREEN_VPP_DATA_CENTER','SZ_GREEN_DC_RECOGNITION','NAT_GREEN_COMPUTE_LIST_2025')) AS compute_policy_rule_count,
                       (SELECT COUNT(*) FROM compute_policy_provider_registry_v1) AS compute_policy_provider_count,
                       (SELECT COUNT(*) FROM compute_policy_provider_platform_match_v1 WHERE match_status='MATCHED') AS compute_policy_provider_match_count,
                       (SELECT COUNT(*) FROM compute_policy_applicability_result_v1) AS compute_policy_applicability_count
                """, Map.of())));
        result.put("priceScopes", normalizeRows(jdbc.queryForList("""
                SELECT price_scope, COUNT(*) AS record_count,
                       MIN(captured_at) AS first_captured_at,
                       MAX(captured_at) AS latest_captured_at
                FROM compute_product_price_snapshot_v1
                GROUP BY price_scope ORDER BY price_scope
                """, Map.of())));
        result.put("economics", normalizeRow(jdbc.queryForMap("""
                SELECT COUNT(*) AS result_count,
                       SUM(result_status='POSITIVE') AS positive_count,
                       SUM(result_status='NEGATIVE') AS negative_count,
                       MIN(annual_revenue_yuan) AS min_annual_revenue_yuan,
                       MAX(annual_revenue_yuan) AS max_annual_revenue_yuan,
                       MIN(annual_electricity_cost_yuan) AS min_annual_electricity_cost_yuan,
                       MAX(annual_electricity_cost_yuan) AS max_annual_electricity_cost_yuan,
                       MIN(annual_operating_cashflow_yuan) AS min_annual_operating_cashflow_yuan,
                       MAX(annual_operating_cashflow_yuan) AS max_annual_operating_cashflow_yuan,
                       MIN(operating_cashflow_margin) AS min_operating_cashflow_margin,
                       MAX(operating_cashflow_margin) AS max_operating_cashflow_margin
                FROM compute_economics_result_v1
                WHERE model_version='COMPUTE_ECONOMICS_V1'
                """, Map.of())));
        result.put("scenarioComparison", normalizeRows(jdbc.queryForList("""
                SELECT s.scenario_version,COUNT(*) AS product_count,
                       SUM(e.result_status='POSITIVE') AS positive_operating_cashflow_count,
                       SUM(pe.npv_yuan>=0) AS nonnegative_npv_count,
                       SUM(v.bankable_flag=1) AS bankable_count,
                       MIN(e.operating_cashflow_margin) AS min_operating_cashflow_margin,
                       MAX(e.operating_cashflow_margin) AS max_operating_cashflow_margin,
                       MIN(pe.npv_yuan) AS min_npv_yuan,MAX(pe.npv_yuan) AS max_npv_yuan
                FROM compute_operation_scenario_v1 s
                JOIN compute_economics_result_v1 e ON e.scenario_id=s.scenario_id
                JOIN compute_project_economics_result_v1 pe ON pe.scenario_id=s.scenario_id
                LEFT JOIN v_compute_financing_capacity_v1 v
                  ON v.project_economics_result_id=pe.project_economics_result_id
                WHERE s.scenario_version IN
                  ('COMPUTE_CONSERVATIVE_V1','COMPUTE_BASE_V1','COMPUTE_OPTIMISTIC_V1')
                GROUP BY s.scenario_version ORDER BY FIELD(s.scenario_version,
                  'COMPUTE_CONSERVATIVE_V1','COMPUTE_BASE_V1','COMPUTE_OPTIMISTIC_V1')
                """, Map.of())));
        result.put("boundary", "设施、商品、配置和报价来自公开资料；51个商品是市场目录而非可同时出租的库存，不得汇总解释为平台收入。经济性结果混合使用公开价格与研究情景参数，不代表实际成交价、设施实测能耗或授信结论。");
        return result;
    }

    public Map<String, Object> getPolicyOverview() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("coverage", normalizeRow(jdbc.queryForMap("""
                SELECT
                  (SELECT COUNT(*) FROM policy_document_v1
                    WHERE policy_category IN ('COMPUTE_INFRASTRUCTURE','GREEN_DATA_CENTER','COMPUTE_ENERGY_SYNERGY','AI_INDUSTRY','COMPUTE_VOUCHER','GREEN_LOW_CARBON')) AS document_count,
                  (SELECT COUNT(*) FROM policy_rule_v1 WHERE rule_code IN (
                    'NAT_GREEN_DC_2025_PUE','NAT_GREEN_DC_2025_RENEWABLE','NAT_GREEN_DC_2025_DEMAND_RESPONSE',
                    'NAT_GREEN_DC_2025_RACK_UTILIZATION','NAT_GREEN_DC_2025_IT_LOAD','NAT_GREEN_FINANCE_2025_GREEN_DC',
                    'NAT_AI_ENERGY_2026_GREEN_POWER','NAT_AI_ENERGY_2026_MARKET','NAT_AI_ENERGY_2026_GREEN_FINANCE',
                    'GD_AI_2025_COMPUTE_VOUCHER','SZ_AI_2026_DEMONSTRATION_GRANT','SZ_TRAINING_VOUCHER_2026_DEMAND',
                    'SZ_TRAINING_VOUCHER_2026_EVIDENCE','LG_AI_2026_COMPUTE_PURCHASE','SZ_COMPUTE_2025_PUE_REFERENCE',
                    'SZ_GREEN_VPP_DATA_CENTER','SZ_GREEN_DC_RECOGNITION','NAT_GREEN_COMPUTE_LIST_2025')) AS rule_count,
                  (SELECT COUNT(*) FROM compute_policy_provider_registry_v1) AS provider_count,
                  (SELECT COUNT(*) FROM compute_policy_provider_platform_match_v1 WHERE match_status='MATCHED') AS exact_provider_platform_match_count,
                  (SELECT COUNT(*) FROM compute_policy_applicability_result_v1 WHERE applicability_status='POTENTIALLY_ELIGIBLE') AS potential_facility_program_count,
                  (SELECT COUNT(*) FROM compute_policy_applicability_result_v1 WHERE applicability_status='INSUFFICIENT_EVIDENCE') AS evidence_gap_count
                """, Map.of())));
        result.put("programs", normalizeRows(jdbc.queryForList("""
                SELECT r.rule_code,r.rule_title,r.rule_category,r.applicable_region,r.applicable_entity_type,
                       r.applicable_asset_type,r.applicability_summary,r.requirement_summary,r.required_evidence,
                       r.rule_value_numeric,r.rule_value_unit,r.rule_value_text,r.model_impact_type,r.model_target,
                       r.rule_status,r.interpretation_confidence,r.source_locator,r.analysis_note,
                       d.document_title,d.document_number,d.issuing_authority,d.issue_date,d.expiry_date,d.policy_status,d.official_url
                FROM policy_rule_v1 r
                JOIN policy_document_v1 d ON d.policy_document_id=r.policy_document_id
                WHERE r.rule_code IN (
                  'NAT_GREEN_DC_2025_PUE','NAT_GREEN_FINANCE_2025_GREEN_DC','NAT_AI_ENERGY_2026_GREEN_POWER',
                  'NAT_AI_ENERGY_2026_MARKET','GD_AI_2025_COMPUTE_VOUCHER','SZ_AI_2026_DEMONSTRATION_GRANT',
                  'SZ_TRAINING_VOUCHER_2026_DEMAND','LG_AI_2026_COMPUTE_PURCHASE','SZ_GREEN_VPP_DATA_CENTER',
                  'SZ_GREEN_DC_RECOGNITION','SZ_COMPUTE_2025_PUE_REFERENCE')
                ORDER BY FIELD(r.rule_code,
                  'NAT_GREEN_FINANCE_2025_GREEN_DC','NAT_GREEN_DC_2025_PUE','NAT_AI_ENERGY_2026_GREEN_POWER',
                  'SZ_GREEN_VPP_DATA_CENTER','SZ_TRAINING_VOUCHER_2026_DEMAND','LG_AI_2026_COMPUTE_PURCHASE',
                  'SZ_AI_2026_DEMONSTRATION_GRANT','GD_AI_2025_COMPUTE_VOUCHER','NAT_AI_ENERGY_2026_MARKET',
                  'SZ_GREEN_DC_RECOGNITION','SZ_COMPUTE_2025_PUE_REFERENCE')
                """, Map.of())));
        result.put("facilitySummary", normalizeRows(jdbc.queryForList("""
                SELECT * FROM v_compute_policy_facility_summary_v1 ORDER BY facility_code
                """, Map.of())));
        result.put("platformProviders", normalizeRows(jdbc.queryForList("""
                SELECT * FROM v_compute_policy_platform_summary_v1 ORDER BY platform_id
                """, Map.of())));
        result.put("voucherProviders", normalizeRows(jdbc.queryForList("""
                SELECT provider_name,admission_batch,admission_type,provider_status,service_scope,
                       source_locator,official_url,data_type,data_quality
                FROM compute_policy_provider_registry_v1
                ORDER BY FIELD(admission_type,'新增入库','新增服务事项'),provider_name
                """, Map.of())));
        result.put("boundary", "政策模块只呈现公开政策条款、名单和初步适用性。训力券、模型券和龙岗算力支持面向需求方；绿色金融、绿色数据中心和虚拟电厂须补充项目级PUE、绿电、可调负荷、资金用途及申报/评审材料。未获批或未结算的政策支持不会写入NPV、IRR、DSCR或建议贷款额度。");
        return result;
    }

    public Map<String, Object> findFinanceOpportunities() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("coverage", normalizeRow(jdbc.queryForMap("""
                SELECT COUNT(*) AS opportunity_count,
                       SUM(business_priority='A') AS priority_a_count,
                       SUM(business_priority='B') AS priority_b_count,
                       SUM(project_identity_status<>'CONFIRMED') AS identity_pending_count,
                       SUM(blocking_check_count>0) AS blocking_evidence_count,
                       SUM(open_check_count) AS open_check_count
                FROM v_compute_finance_opportunity_summary_v1
                """, Map.of())));
        result.put("items", normalizeRows(jdbc.queryForList("""
                SELECT * FROM v_compute_finance_opportunity_summary_v1
                ORDER BY FIELD(business_priority,'A','B','C'),opportunity_rank,opportunity_code
                """, Map.of())));
        result.put("boundary", "机会清单从 COMPUTE_BASE_V1 和 CREDIT_BASE_V1 中筛出当前建议进入尽调的公开商品单元。它不是已确认的设施建设项目：若尚未映射物理设施、融资主体和资产权属，绿色金融、抵押、绿电、虚拟电厂和地方补贴均不得视为已具备。" );
        return result;
    }

    public Map<String, Object> findFinanceOpportunity(String opportunityCode) {
        var params = Map.of("opportunityCode", opportunityCode);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("opportunity", queryOne("""
                SELECT * FROM v_compute_finance_opportunity_summary_v1
                WHERE opportunity_code=:opportunityCode
                """, params, "未找到算力业务机会 " + opportunityCode));
        result.put("checklist", normalizeRows(jdbc.queryForList("""
                SELECT * FROM v_compute_policy_due_diligence_checklist_v1
                WHERE opportunity_id=(
                  SELECT opportunity_id FROM compute_finance_opportunity_v1
                  WHERE opportunity_code=:opportunityCode
                )
                ORDER BY sort_order,checklist_id
                """, params)));
        result.put("candidateMappings", normalizeRows(jdbc.queryForList("""
                SELECT * FROM v_compute_listing_candidate_mapping_v1
                WHERE listing_id=(
                  SELECT listing_id FROM compute_finance_opportunity_v1
                  WHERE opportunity_code=:opportunityCode
                )
                ORDER BY FIELD(mapping_status,'CONFIRMED','INDICATIVE','UNMAPPED'),
                         FIELD(confidence_level,'HIGH','MEDIUM','LOW','NONE'),candidate_mapping_id
                """, params)));
        result.put("referenceCases", normalizeRows(jdbc.queryForList("""
                SELECT DISTINCT c.*
                FROM v_compute_financing_reference_case_v1 c
                JOIN compute_listing_candidate_mapping_v1 m
                  ON m.candidate_facility_v2_id=(
                    SELECT facility_v2_id FROM enterprise_data_center_v2
                    WHERE facility_code=c.facility_code
                  )
                WHERE m.listing_id=(
                  SELECT listing_id FROM compute_finance_opportunity_v1
                  WHERE opportunity_code=:opportunityCode
                )
                ORDER BY c.balance_as_of_date DESC,c.financing_reference_case_id DESC
                """, params)));
        result.put("boundary", "清单记录的是待取得的材料和后续动作，不是缺失事实的替代值。只有合同、项目级能耗、资产权属、申报/获批或结算文件可核验后，才可刷新对应模型输入或建立政策调整情景。" );
        return result;
    }

    public Map<String, Object> findFacilities(String query, int page, int size) {
        String from = """
                enterprise_data_center_v2 f
                LEFT JOIN dim_region r ON r.region_id=f.region_id
                LEFT JOIN data_source ds ON ds.source_id=f.primary_source_id
                """;
        String select = """
                f.facility_v2_id,f.facility_code,f.official_name,f.facility_alias,
                f.facility_kind,f.locality_scope,f.province_name,f.city_name,f.district_name,
                f.operator_name,f.owner_name,f.lifecycle_status,f.operation_start_date,
                f.physical_capacity_countable,f.green_certification,f.last_verified_date,
                f.data_type,f.data_quality,f.notes,f.model_version,r.region_name,
                ds.source_title,ds.source_url,
                (SELECT COUNT(*) FROM compute_facility_metric_v1 m
                  WHERE m.facility_v2_id=f.facility_v2_id) AS metric_count,
                (SELECT COUNT(*) FROM compute_facility_platform_relation_v1 x
                  WHERE x.facility_v2_id=f.facility_v2_id) AS platform_count,
                (SELECT COUNT(*) FROM compute_platform_resource_listing_v1 l
                  WHERE l.facility_v2_id=f.facility_v2_id) AS product_count,
                (SELECT m.metric_value FROM compute_facility_metric_v1 m
                  WHERE m.facility_v2_id=f.facility_v2_id AND m.metric_code='PUE'
                  ORDER BY m.usable_for_facility_model DESC,m.as_of_date DESC,m.facility_metric_id DESC LIMIT 1) AS disclosed_pue
                """;
        String search = "CONCAT_WS(' ',f.facility_code,f.official_name,f.facility_alias,f.operator_name,f.owner_name,f.city_name,f.district_name)";
        return page(select, from, search, query,
                "CASE WHEN f.facility_code='SZCF016' THEN 0 ELSE 1 END, f.official_name", page, size);
    }

    public Map<String, Object> findFacility(String facilityCode) {
        var params = Map.of("facilityCode", facilityCode);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("facility", queryOne("""
                SELECT f.*,r.region_code,r.region_name,ds.source_title,ds.source_url,ds.source_tier
                FROM enterprise_data_center_v2 f
                LEFT JOIN dim_region r ON r.region_id=f.region_id
                LEFT JOIN data_source ds ON ds.source_id=f.primary_source_id
                WHERE f.facility_code=:facilityCode
                """, params, "未找到算力设施 " + facilityCode));
        result.put("metrics", normalizeRows(jdbc.queryForList("""
                SELECT m.*,ds.source_org,ds.source_title,ds.source_url,ds.source_tier
                FROM compute_facility_metric_v1 m
                LEFT JOIN data_source ds ON ds.source_id=m.source_id
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=m.facility_v2_id
                WHERE f.facility_code=:facilityCode
                ORDER BY m.metric_code,m.as_of_date DESC,m.facility_metric_id DESC
                """, params)));
        result.put("platforms", normalizeRows(jdbc.queryForList("""
                SELECT p.platform_id,p.platform_code,p.platform_name,p.operator_name,
                       p.platform_type,p.website_url,x.relation_type,x.capacity_scope,
                       x.relation_status,x.included_in_local_capacity_total,x.as_of_date,
                       x.evidence_grade,x.notes
                FROM compute_facility_platform_relation_v1 x
                JOIN compute_service_platform_v1 p ON p.platform_id=x.platform_id
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=x.facility_v2_id
                WHERE f.facility_code=:facilityCode ORDER BY p.platform_code
                """, params)));
        result.put("products", normalizeRows(jdbc.queryForList("""
                SELECT l.listing_id,l.external_product_id,l.product_name,l.provider_name,
                       l.resource_type,l.accelerator_model,l.accelerator_count,l.accelerator_memory_gb,
                       l.cpu_cores,l.system_memory_gb,l.platform_region_label,l.available_zone,
                       l.availability_status,l.captured_at,l.data_quality
                FROM compute_platform_resource_listing_v1 l
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=l.facility_v2_id
                WHERE f.facility_code=:facilityCode ORDER BY l.product_name
                """, params)));
        result.put("boundary", "平台纳管关系或平台商品不等同于设施自有物理算力；仅在公开证据能够确认时关联具体设施。");
        return result;
    }

    public Map<String, Object> findFacilityOperations(String facilityCode) {
        var params = Map.of("facilityCode", facilityCode);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("facility", queryOne("""
                SELECT f.facility_code,f.official_name,f.operator_name,f.owner_name,
                       f.data_type,f.data_quality
                FROM enterprise_data_center_v2 f
                WHERE f.facility_code=:facilityCode
                """, params, "未找到算力设施 " + facilityCode));
        result.put("annualOperations", normalizeRows(jdbc.queryForList("""
                SELECT c.*
                FROM v_compute_facility_operation_calibration_v1 c
                WHERE c.facility_code=:facilityCode
                  AND c.operation_scope_code='WHOLE_FACILITY_BUILDING_1_4_SELF_BUILT'
                ORDER BY c.fact_year
                """, params)));
        result.put("buildingUtilization", normalizeRows(jdbc.queryForList("""
                SELECT o.operation_scope_code,o.operation_scope_name,o.fact_year,o.fact_period,
                       o.rack_utilization_ratio,ds.source_title,ds.source_url,o.source_locator,
                       o.data_type,o.data_quality,o.notes
                FROM compute_facility_operation_fact_v1 o
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=o.facility_v2_id
                JOIN data_source ds ON ds.source_id=o.source_id
                WHERE f.facility_code=:facilityCode
                  AND o.operation_scope_code IN ('BUILDING_1','BUILDING_4')
                ORDER BY o.operation_scope_code,o.fact_year,o.fact_period
                """, params)));
        result.put("rackPriceTiers", normalizeRows(jdbc.queryForList("""
                SELECT p.building_scope_code,p.fact_year,p.fact_period,p.power_tier_code,
                       p.power_from_kw,p.power_to_kw,p.upper_bound_inclusive,
                       p.actual_average_price_yuan_rack_month,
                       ds.source_title,ds.source_url,p.source_locator,p.data_type,p.data_quality,p.notes
                FROM compute_facility_rack_price_tier_fact_v1 p
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=p.facility_v2_id
                JOIN data_source ds ON ds.source_id=p.source_id
                WHERE f.facility_code=:facilityCode
                ORDER BY p.fact_year,p.fact_period,p.building_scope_code,
                         COALESCE(p.power_from_kw,-1),p.power_to_kw
                """, params)));
        result.put("customerContracts", normalizeRows(jdbc.queryForList("""
                SELECT c.customer_contract_fact_id,c.contract_fact_code,c.customer_name,c.customer_name_scope,
                       c.contract_name,c.contract_scope,c.contract_start_date,c.contract_end_date,
                       c.contracted_rack_count_approx,c.included_current_amp,c.base_price_yuan_rack_month,
                       c.excess_price_yuan_amp_rack_month,c.vacant_protection_months,
                       c.first_occupancy_threshold_ratio,c.second_occupancy_threshold_ratio,
                       c.vacant_fee_yuan_rack_month,c.contract_status,ds.source_title,ds.source_url,
                       c.source_locator,c.data_type,c.data_quality,c.notes
                FROM compute_facility_customer_contract_fact_v1 c
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=c.facility_v2_id
                JOIN data_source ds ON ds.source_id=c.source_id
                WHERE f.facility_code=:facilityCode
                ORDER BY c.contract_end_date DESC,c.customer_contract_fact_id DESC
                """, params)));
        result.put("phase3CashflowScenarios", normalizeRows(jdbc.queryForList("""
                SELECT c.*
                FROM v_compute_facility_project_cashflow_summary_v1 c
                WHERE c.facility_code=:facilityCode
                ORDER BY FIELD(c.scenario_code,
                  'BWX_PHASE3_CONSERVATIVE_V1','BWX_PHASE3_BASE_V1','BWX_PHASE3_OPTIMISTIC_V1')
                """, params)));
        result.put("phase3CashflowYears", normalizeRows(jdbc.queryForList("""
                SELECT s.scenario_code,s.scenario_name,y.cashflow_year_index,y.calendar_year,
                       y.modeled_rack_occupancy_ratio,y.modeled_occupied_rack_count,
                       y.modeled_revenue_yuan,y.modeled_total_energy_kwh,
                       y.reference_annual_energy_cap_kwh,y.energy_cap_status,
                       y.modeled_electricity_cost_yuan,y.modeled_other_operating_cost_proxy_yuan,
                       y.modeled_pre_tax_cashflow_proxy_yuan,y.discount_factor,
                       y.discounted_cashflow_proxy_yuan,y.data_type,y.calculation_formula
                FROM compute_facility_project_cashflow_year_v1 y
                JOIN compute_facility_project_scenario_v1 s
                  ON s.facility_project_scenario_id=y.facility_project_scenario_id
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=s.facility_v2_id
                WHERE f.facility_code=:facilityCode
                ORDER BY FIELD(s.scenario_code,
                  'BWX_PHASE3_CONSERVATIVE_V1','BWX_PHASE3_BASE_V1','BWX_PHASE3_OPTIMISTIC_V1'),
                  y.cashflow_year_index
                """, params)));
        result.put("phase3DueDiligence", normalizeRows(jdbc.queryForList("""
                SELECT d.*
                FROM v_compute_facility_project_due_diligence_v1 d
                WHERE d.facility_code=:facilityCode
                  AND d.project_scope_code='PHASE_III_EXCHANGE_DISCLOSURE'
                ORDER BY d.sort_order
                """, params)));
        result.put("powerSynergy", normalizeRows(jdbc.queryForList("""
                SELECT s.*
                FROM v_compute_power_synergy_summary_v1 s
                WHERE s.facility_code=:facilityCode
                ORDER BY FIELD(s.scenario_code,
                  'BWX_PHASE3_HISTORICAL_BILL_V1','BWX_PHASE3_TOU_GRID_V1',
                  'BWX_PHASE3_TOU_GREEN20_V1','BWX_PHASE3_TOU_GREEN_STORAGE2_V1')
                """, params)));
        result.put("boundary", "年度经营事实覆盖百旺信1栋+4栋的自建服务器托管运营，不能当作三期项目单独经营数据。视图中的电费金额、隐含电价、毛利额和量价收入校验均明确标为由同一行公开事实公式计算；2025年0.57元/kWh仅保存为上半年历史账单单价，不改标为全年实际结算价。公开深圳移动合同属于批发型客户条款，不能作为零售市场价格或全部机柜收入假设。三期情景使用已披露的3.2亿元历史投资、1,760柜、PUE 1.228及年电量边界作为锚点；其上架率、收入、负载及非电成本均是显式代理假设，逐年结果仅为税前经营现金流代理，不是三期真实CFADS、实际NPV、估值或授信结论。");
        return result;
    }

    public Map<String, Object> findPowerSynergy(String facilityCode) {
        var params = Map.of("facilityCode", facilityCode);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("facility", queryOne("""
                SELECT f.facility_code,f.official_name,f.city_name,f.district_name,
                       f.data_type,f.data_quality
                FROM enterprise_data_center_v2 f
                WHERE f.facility_code=:facilityCode
                """, params, "未找到算力设施 " + facilityCode));
        result.put("scenarios", normalizeRows(jdbc.queryForList("""
                SELECT s.*
                FROM v_compute_power_synergy_summary_v1 s
                WHERE s.facility_code=:facilityCode
                ORDER BY FIELD(s.scenario_code,
                  'BWX_PHASE3_HISTORICAL_BILL_V1','BWX_PHASE3_TOU_GRID_V1',
                  'BWX_PHASE3_TOU_GREEN20_V1','BWX_PHASE3_TOU_GREEN_STORAGE2_V1')
                """, params)));
        result.put("tariffSegments", normalizeRows(jdbc.queryForList("""
                SELECT s.scenario_code,s.scenario_name,t.tariff_id,t.year,t.month,
                       t.customer_type,t.voltage_level,t.time_period,t.start_time_text,t.end_time_text,
                       t.final_price_yuan_kwh,seg.load_allocation_ratio,seg.allocation_basis,
                       ds.source_title,ds.source_url
                FROM compute_power_synergy_tariff_segment_v1 seg
                JOIN compute_power_synergy_scenario_v1 s
                  ON s.power_synergy_scenario_id=seg.power_synergy_scenario_id
                JOIN electricity_tariff t ON t.tariff_id=seg.tariff_id
                JOIN enterprise_data_center_v2 f ON f.facility_v2_id=s.facility_v2_id
                LEFT JOIN data_source ds ON ds.source_id=t.source_id
                WHERE f.facility_code=:facilityCode
                ORDER BY FIELD(s.scenario_code,
                  'BWX_PHASE3_TOU_GRID_V1','BWX_PHASE3_TOU_GREEN20_V1','BWX_PHASE3_TOU_GREEN_STORAGE2_V1'),
                  t.tariff_id
                """, params)));
        result.put("policyReadiness", normalizeRows(jdbc.queryForList("""
                SELECT r.rule_code,r.rule_title,r.applicable_region,r.requirement_summary,
                       r.required_evidence,r.rule_value_numeric,r.rule_value_unit,
                       d.document_title,d.official_url
                FROM policy_rule_v1 r
                JOIN policy_document_v1 d ON d.policy_document_id=r.policy_document_id
                WHERE r.rule_code IN (
                  'NAT_GREEN_DC_2025_DEMAND_RESPONSE','SZ_GREEN_VPP_DATA_CENTER',
                  'GD_DEMAND_RESPONSE_PARTICIPATION','GD_VPP_RESOURCE_REGISTRATION',
                  'GD_VPP_CAPABILITY_TEST'
                )
                ORDER BY FIELD(r.rule_code,
                  'NAT_GREEN_DC_2025_DEMAND_RESPONSE','SZ_GREEN_VPP_DATA_CENTER',
                  'GD_DEMAND_RESPONSE_PARTICIPATION','GD_VPP_RESOURCE_REGISTRATION',
                  'GD_VPP_CAPABILITY_TEST')
                """, Map.of())));
        result.put("boundary", "仅百旺信三期当前具备项目边界与公开经营锚点，故先建立设施级算电协同样本。分时电价采用深圳2026年7月可匹配的大工业代理购电价格；无三期实测负荷曲线时，分时分配、20%绿电采购和2%储能移峰均为显式研究情景。深圳本地清洁电源装机占比与广东发电结构仅说明区域供给背景，不等于设施绿电消费或碳排放。需求响应收益保持为0，直至取得可调负荷、注册、测试及结算资料。");
        return result;
    }

    public Map<String, Object> findProducts(String query, int page, int size) {
        String from = """
                compute_platform_resource_listing_v1 l
                JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
                LEFT JOIN enterprise_data_center_v2 f ON f.facility_v2_id=l.facility_v2_id
                LEFT JOIN compute_operation_scenario_v1 s ON s.listing_id=l.listing_id
                  AND s.scenario_version='COMPUTE_BASE_V1'
                LEFT JOIN compute_economics_result_v1 e ON e.scenario_id=s.scenario_id
                """;
        String select = """
                l.listing_id,l.external_product_id,l.product_name,l.provider_name,l.resource_type,
                l.accelerator_model,l.accelerator_count,l.accelerator_memory_gb,l.cpu_cores,
                l.system_memory_gb,l.compute_capacity_value,l.compute_capacity_unit,l.compute_precision,
                l.platform_region_label,l.available_zone,l.physical_region_text,l.locality_scope,
                l.availability_status,l.captured_at,l.data_quality,p.platform_code,p.platform_name,
                f.facility_code,f.official_name AS facility_name,
                e.price_scope,e.billing_cycle,e.price_value,e.annual_revenue_yuan,
                e.annual_electricity_cost_yuan,e.annual_operating_cashflow_yuan,
                e.operating_cashflow_margin,e.result_status,e.data_type AS economics_data_type
                """;
        String search = "CONCAT_WS(' ',l.external_product_id,l.product_name,l.provider_name,l.resource_type,l.accelerator_model,l.platform_region_label,l.available_zone,p.platform_name,f.official_name)";
        return page(select, from, search, query, "l.listing_id", page, size);
    }

    public Map<String, Object> findProduct(long listingId) {
        var params = Map.of("listingId", listingId);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("product", queryOne("""
                SELECT l.*,p.platform_code,p.platform_name,p.website_url,
                       f.facility_code,f.official_name AS facility_name
                FROM compute_platform_resource_listing_v1 l
                JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
                LEFT JOIN enterprise_data_center_v2 f ON f.facility_v2_id=l.facility_v2_id
                WHERE l.listing_id=:listingId
                """, params, "未找到算力商品 " + listingId));
        result.put("prices", normalizeRows(jdbc.queryForList("""
                SELECT price_snapshot_id,price_scope,billing_method,billing_cycle,minimum_term,
                       price_value,currency,price_unit,tax_included_flag,promotion_flag,
                       configuration_text,validation_status,source_api_url,captured_at,
                       data_quality,notes
                FROM compute_product_price_snapshot_v1
                WHERE listing_id=:listingId
                ORDER BY CASE price_scope WHEN 'DETAIL_CONFIG' THEN 0
                         WHEN 'LIST_REFERENCE' THEN 1 ELSE 2 END,
                         captured_at DESC,price_snapshot_id
                """, params)));
        result.put("scenarioAndEconomics", queryOptional("""
                SELECT s.*,e.economics_result_id,e.selected_price_snapshot_id,e.price_scope,
                       e.billing_cycle,e.price_value,e.currency,e.annual_billable_hours,
                       e.modeled_max_it_power_kw,e.modeled_avg_it_power_kw,
                       e.annual_it_energy_kwh,e.annual_total_energy_kwh,
                       e.annual_revenue_yuan,e.annual_electricity_cost_yuan,
                       e.annual_other_opex_yuan,e.annual_operating_cashflow_yuan,
                       e.electricity_cost_ratio,e.operating_cashflow_margin,
                       e.break_even_utilization_ratio,e.result_status,
                       e.data_type AS result_data_type,e.calculation_formula,
                       e.model_version AS economics_model_version,e.computed_at
                FROM compute_operation_scenario_v1 s
                LEFT JOIN compute_economics_result_v1 e ON e.scenario_id=s.scenario_id
                WHERE s.listing_id=:listingId AND s.scenario_version='COMPUTE_BASE_V1'
                ORDER BY s.scenario_id DESC LIMIT 1
                """, params));
        result.put("boundary", "报价为公开快照；利用率、设备功率、PUE、电价和其他OPEX可能为SCENARIO。公式结果不代表实际合同现金流。");
        return result;
    }

    public Map<String, Object> findPrices(String query, String priceScope, int page, int size) {
        String keyword = query == null ? "" : query.trim();
        String scope = priceScope == null ? "" : priceScope.trim().toUpperCase(Locale.ROOT);
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        var params = new MapSqlParameterSource()
                .addValue("likeQuery", "%" + keyword + "%")
                .addValue("scope", scope).addValue("limit", safeSize)
                .addValue("offset", safePage * safeSize);
        String where = """
                WHERE (:scope='' OR p.price_scope=:scope)
                  AND (:likeQuery='%%' OR CONCAT_WS(' ',p.external_product_id,l.product_name,
                       l.accelerator_model,sp.platform_name,p.price_scope,p.billing_cycle,
                       p.price_unit,p.configuration_text) LIKE :likeQuery)
                """;
        String from = """
                compute_product_price_snapshot_v1 p
                LEFT JOIN compute_platform_resource_listing_v1 l ON l.listing_id=p.listing_id
                JOIN compute_service_platform_v1 sp ON sp.platform_id=p.platform_id
                """;
        long total = count("SELECT COUNT(*) FROM " + from + where, params);
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList("""
                SELECT p.price_snapshot_id,p.listing_id,p.external_product_id,l.product_name,
                       l.accelerator_model,sp.platform_code,sp.platform_name,p.price_scope,
                       p.billing_method,p.billing_cycle,p.minimum_term,p.price_value,p.currency,
                       p.price_unit,p.tax_included_flag,p.promotion_flag,p.configuration_text,
                       p.validation_status,p.source_api_url,p.captured_at,p.data_quality,p.notes
                FROM
                """ + from + where + " ORDER BY p.captured_at DESC,p.price_snapshot_id LIMIT :limit OFFSET :offset", params));
        return pagedResponse(items, keyword, safePage, safeSize, total);
    }

    public Map<String, Object> findEconomics(String query, String scenarioVersion, int page, int size) {
        String from = """
                compute_economics_result_v1 e
                JOIN compute_operation_scenario_v1 s ON s.scenario_id=e.scenario_id
                JOIN compute_platform_resource_listing_v1 l ON l.listing_id=s.listing_id
                JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
                LEFT JOIN enterprise_data_center_v2 f ON f.facility_v2_id=s.facility_v2_id
                """;
        String select = """
                e.economics_result_id,e.model_version,e.result_status,e.data_type,
                s.scenario_id,s.scenario_code,s.scenario_version,s.analysis_year,
                s.utilization_ratio,s.utilization_data_type,s.idle_power_ratio,
                s.accelerator_unit_power_kw,s.modeled_accelerator_count,s.auxiliary_power_ratio,
                s.pue,s.pue_data_type,s.electricity_price_yuan_kwh,
                s.electricity_price_data_type,s.price_realization_ratio,s.other_opex_revenue_ratio,
                l.listing_id,l.external_product_id,l.product_name,l.accelerator_model,
                p.platform_code,p.platform_name,f.facility_code,f.official_name AS facility_name,
                e.selected_price_snapshot_id,e.price_scope,e.billing_cycle,e.price_value,
                e.annual_billable_hours,e.modeled_max_it_power_kw,e.modeled_avg_it_power_kw,
                e.annual_it_energy_kwh,e.annual_total_energy_kwh,e.annual_revenue_yuan,
                e.annual_electricity_cost_yuan,e.annual_other_opex_yuan,
                e.annual_operating_cashflow_yuan,e.electricity_cost_ratio,
                e.operating_cashflow_margin,e.break_even_utilization_ratio,
                e.calculation_formula,e.computed_at
                """;
        String keyword = query == null ? "" : query.trim();
        String version = scenarioVersion == null || scenarioVersion.isBlank() ? "COMPUTE_BASE_V1" : scenarioVersion.trim();
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        var params = new MapSqlParameterSource().addValue("likeQuery", "%" + keyword + "%")
                .addValue("scenarioVersion", version).addValue("limit", safeSize)
                .addValue("offset", safePage * safeSize);
        String where = """
                WHERE s.scenario_version=:scenarioVersion
                  AND (:likeQuery='%%' OR CONCAT_WS(' ',l.external_product_id,l.product_name,
                       l.accelerator_model,p.platform_name,f.official_name) LIKE :likeQuery)
                """;
        long total = count("SELECT COUNT(*) FROM " + from + where, params);
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList(
                "SELECT " + select + " FROM " + from + where
                        + " ORDER BY e.annual_operating_cashflow_yuan DESC,l.listing_id LIMIT :limit OFFSET :offset", params));
        Map<String, Object> result = pagedResponse(items, keyword, safePage, safeSize, total);
        result.put("scenarioVersion", version);
        result.put("boundary", "这是公开报价与研究情景形成的经营现金流，不含设备CAPEX、税费、融资成本和实际合同折扣，不能直接解释为可贷金额。");
        return result;
    }

    public Map<String, Object> findProjectEconomics(String query, String scenarioVersion,
                                                    int page, int size) {
        String from = """
                compute_project_economics_result_v1 pe
                JOIN compute_operation_scenario_v1 s ON s.scenario_id=pe.scenario_id
                JOIN compute_economics_result_v1 oe ON oe.scenario_id=s.scenario_id
                JOIN compute_capex_parameter_v1 cp ON cp.capex_parameter_id=pe.capex_parameter_id
                JOIN compute_platform_resource_listing_v1 l ON l.listing_id=s.listing_id
                JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
                """;
        String select = """
                pe.project_economics_result_id,pe.model_version,pe.model_scope,
                s.scenario_id,s.scenario_version,s.scenario_name,s.analysis_year,
                l.listing_id,l.external_product_id,l.product_name,l.accelerator_model,
                p.platform_code,p.platform_name,cp.capex_scenario_version,
                cp.accelerator_unit_capex_yuan,cp.modeled_accelerator_count,
                pe.total_capex_yuan,oe.annual_revenue_yuan,oe.annual_electricity_cost_yuan,
                oe.annual_operating_cashflow_yuan,pe.analysis_horizon_year,pe.discount_rate,
                pe.annual_cashflow_degradation_rate,pe.npv_yuan,pe.irr,pe.payback_year,
                pe.profitability_index,pe.result_status,pe.data_type,pe.calculation_formula,
                pe.computed_at
                """;
        return versionedModelPage(select, from,
                "CONCAT_WS(' ',l.external_product_id,l.product_name,l.accelerator_model,p.platform_name)",
                query, scenarioVersion, "s.scenario_version", "pe.npv_yuan DESC,l.listing_id", page, size,
                "CAPEX与项目经济性均为PRODUCT_UNIT研究情景，不是整个算力设施的真实投资、收入、NPV或IRR。");
    }

    public Map<String, Object> findSensitivity(String query, String variableCode,
                                               int page, int size) {
        String keyword = query == null ? "" : query.trim();
        String variable = variableCode == null ? "" : variableCode.trim().toUpperCase(Locale.ROOT);
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        var params = new MapSqlParameterSource().addValue("likeQuery", "%" + keyword + "%")
                .addValue("variable", variable).addValue("limit", safeSize)
                .addValue("offset", safePage * safeSize);
        String where = """
                WHERE (:variable='' OR x.variable_code=:variable)
                  AND (:likeQuery='%%' OR CONCAT_WS(' ',x.external_product_id,
                       x.product_name,x.variable_code,x.sensitivity_level) LIKE :likeQuery)
                """;
        long total = count("SELECT COUNT(*) FROM v_compute_sensitivity_summary_v1 x " + where, params);
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList("""
                SELECT x.listing_id,x.external_product_id,x.product_name,x.variable_code,
                       x.max_abs_npv_change_ratio,x.sensitivity_level,x.downside_npv_yuan,
                       x.upside_npv_yuan,x.data_type,
                       (SELECT r.result_status FROM compute_sensitivity_result_v1 r
                         JOIN compute_operation_scenario_v1 s ON s.scenario_id=r.base_scenario_id
                         WHERE s.listing_id=x.listing_id AND r.variable_code=x.variable_code
                         ORDER BY r.npv_yuan LIMIT 1) AS downside_status
                FROM v_compute_sensitivity_summary_v1 x
                """ + where + " ORDER BY FIELD(x.sensitivity_level,'HIGH','MEDIUM','LOW'),"
                + "x.max_abs_npv_change_ratio DESC,x.listing_id LIMIT :limit OFFSET :offset", params));
        Map<String, Object> result = pagedResponse(items, keyword, safePage, safeSize, total);
        result.put("variableCode", variable);
        result.put("boundary", "一次只改变一个变量：利用率、公开价格和电价±20%，PUE±10%，CAPEX±20%；不代表联合压力情景或风险发生概率。");
        return result;
    }

    public Map<String, Object> findFinancingCapacity(String query, String scenarioVersion,
                                                     int page, int size) {
        String select = """
                v.project_economics_result_id,v.scenario_id,v.scenario_version,v.listing_id,
                v.external_product_id,v.product_name,v.platform_name,v.total_capex_yuan,
                v.npv_yuan,v.irr,v.payback_year,v.base_debt_ratio,v.base_loan_amount_yuan,
                v.base_min_dscr,v.base_dscr_feasible_flag,v.base_bankable_flag,
                v.max_dscr_feasible_debt_ratio,v.max_dscr_feasible_loan_yuan,
                v.max_tested_dscr_feasible_debt_ratio,v.max_feasible_debt_ratio,
                v.max_feasible_loan_yuan,v.binding_year,v.binding_dscr,
                v.binding_constraint,v.debt_ratio_cap_reached_flag,v.bankable_flag,v.data_type
                """;
        return versionedModelPage(select, "v_compute_financing_capacity_v1 v",
                "CONCAT_WS(' ',v.external_product_id,v.product_name,v.platform_name,v.binding_constraint)",
                query, scenarioVersion, "v.scenario_version",
                "v.bankable_flag DESC,v.npv_yuan DESC,v.listing_id", page, size,
                "DSCR可承受不等于项目可投；bankableFlag同时要求NPV不为负且存在DSCR≥1.20的债务比例。债务比例遍历范围为1%-100%，触及100%时由DEBT_RATIO_CAP而非DSCR约束。");
    }

    public Map<String, Object> findFinancingCurve(long projectEconomicsResultId) {
        var params = Map.of("projectId", projectEconomicsResultId);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("project", queryOne("""
                SELECT v.* FROM v_compute_financing_capacity_v1 v
                WHERE v.project_economics_result_id=:projectId
                """, params, "未找到算力项目经济性结果 " + projectEconomicsResultId));
        result.put("curve", normalizeRows(jdbc.queryForList("""
                SELECT fs.financing_scenario_id,fs.debt_ratio,fs.annual_interest_rate,
                       fs.loan_term_year,fs.repayment_method,fs.dscr_threshold,
                       fr.loan_amount_yuan,fr.year1_debt_service_yuan,fr.year1_dscr,
                       fr.min_dscr,fr.binding_year,fr.feasible_flag,fr.result_status,
                       fr.data_type,fr.model_version
                FROM compute_financing_scenario_v1 fs
                JOIN compute_financing_result_v1 fr
                  ON fr.financing_scenario_id=fs.financing_scenario_id
                WHERE fs.project_economics_result_id=:projectId
                  AND fs.financing_version='FINANCE_V1'
                ORDER BY fs.debt_ratio
                """, params)));
        result.put("boundary", "曲线统一采用6%年利率、5年期、等额本金和DSCR≥1.20；1%-100%债务比例只是模型遍历，不是银行授信报价。");
        return result;
    }

    public Map<String, Object> findCreditPolicies() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("items", normalizeRows(jdbc.queryForList("""
                SELECT cp.*,
                       (SELECT COUNT(*) FROM compute_bank_recommendation_v1 br
                         WHERE br.credit_policy_id=cp.credit_policy_id
                           AND br.recommendation_status='PROCEED_DUE_DILIGENCE') AS proceed_count,
                       (SELECT COUNT(*) FROM compute_bank_recommendation_v1 br
                         WHERE br.credit_policy_id=cp.credit_policy_id) AS result_count
                FROM compute_credit_policy_scenario_v1 cp
                WHERE cp.policy_version='COMPUTE_CREDIT_POLICY_V1'
                ORDER BY FIELD(cp.policy_code,'CREDIT_CONSERVATIVE_V1','CREDIT_BASE_V1','CREDIT_RELAXED_V1')
                """, Map.of())));
        result.put("boundary", "三档信贷规则均为研究情景，不代表浦发银行或任何机构的正式授信政策。规则仅将数学DSCR容量转换为受资本金、收入折扣、合格CAPEX和贷款比例限制的尽调建议。");
        return result;
    }

    public Map<String, Object> findBankRecommendations(String query, String scenarioVersion,
                                                       String policyCode, int page, int size) {
        String keyword = query == null ? "" : query.trim();
        String version = scenarioVersion == null || scenarioVersion.isBlank()
                ? "COMPUTE_BASE_V1" : scenarioVersion.trim();
        String policy = policyCode == null || policyCode.isBlank()
                ? "CREDIT_BASE_V1" : policyCode.trim();
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        var params = new MapSqlParameterSource().addValue("likeQuery", "%" + keyword + "%")
                .addValue("scenarioVersion", version).addValue("policyCode", policy)
                .addValue("limit", safeSize).addValue("offset", safePage * safeSize);
        String where = """
                WHERE v.scenario_version=:scenarioVersion AND v.policy_code=:policyCode
                  AND (:likeQuery='%%' OR CONCAT_WS(' ',v.external_product_id,v.product_name,
                       v.accelerator_model,v.platform_name,v.binding_rule,
                       v.recommendation_status) LIKE :likeQuery)
                """;
        long total = count("SELECT COUNT(*) FROM v_compute_bank_recommendation_v1 v " + where, params);
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList("""
                SELECT v.* FROM v_compute_bank_recommendation_v1 v
                """ + where + " ORDER BY (v.recommendation_status='PROCEED_DUE_DILIGENCE') DESC,"
                + "v.npv_yuan DESC,v.listing_id LIMIT :limit OFFSET :offset", params));
        Map<String, Object> result = pagedResponse(items, keyword, safePage, safeSize, total);
        result.put("scenarioVersion", version);
        result.put("policyCode", policy);
        result.put("boundary", "recommendedDebtRatio=min(收入折扣后DSCR容量,最高债务比例,1-最低资本金比例,合格CAPEX比例)，且项目单位NPV必须不为负。结果仅表示建议进入尽调，不是授信审批。");
        return result;
    }

    public Map<String, Object> findCreditPolicyCurve(long projectEconomicsResultId,
                                                     String policyCode) {
        String policy = policyCode == null || policyCode.isBlank()
                ? "CREDIT_BASE_V1" : policyCode.trim();
        var params = Map.of("projectId", projectEconomicsResultId, "policyCode", policy);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("recommendation", queryOne("""
                SELECT v.* FROM v_compute_bank_recommendation_v1 v
                WHERE v.project_economics_result_id=:projectId AND v.policy_code=:policyCode
                """, params, "未找到对应的银行规则结果"));
        result.put("curve", normalizeRows(jdbc.queryForList("""
                SELECT c.policy_curve_id,c.debt_ratio,c.loan_amount_yuan,
                       c.adjusted_year1_cashflow_yuan,c.year1_debt_service_yuan,
                       c.year1_dscr,c.min_dscr,c.binding_year,c.dscr_feasible_flag,
                       c.policy_limit_feasible_flag,c.economic_feasible_flag,
                       c.overall_feasible_flag,c.data_type,c.model_version
                FROM compute_credit_policy_financing_curve_v1 c
                JOIN compute_credit_policy_scenario_v1 p
                  ON p.credit_policy_id=c.credit_policy_id
                WHERE c.project_economics_result_id=:projectId AND p.policy_code=:policyCode
                ORDER BY c.debt_ratio
                """, params)));
        result.put("boundary", "融资曲线已经应用所选信贷情景的收入折扣、利率、期限、DSCR门槛、资本金和贷款比例限制；仍属于产品单位研究结果。");
        return result;
    }

    private Map<String, Object> versionedModelPage(String select, String from,
                                                   String searchExpression, String query,
                                                   String scenarioVersion, String versionColumn,
                                                   String orderBy, int page, int size,
                                                   String boundary) {
        String keyword = query == null ? "" : query.trim();
        String version = scenarioVersion == null || scenarioVersion.isBlank()
                ? "COMPUTE_BASE_V1" : scenarioVersion.trim();
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        var params = new MapSqlParameterSource().addValue("likeQuery", "%" + keyword + "%")
                .addValue("scenarioVersion", version).addValue("limit", safeSize)
                .addValue("offset", safePage * safeSize);
        String where = " WHERE " + versionColumn + "=:scenarioVersion"
                + (keyword.isEmpty() ? "" : " AND " + searchExpression + " LIKE :likeQuery");
        long total = count("SELECT COUNT(*) FROM " + from + where, params);
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList(
                "SELECT " + select + " FROM " + from + where
                        + " ORDER BY " + orderBy + " LIMIT :limit OFFSET :offset", params));
        Map<String, Object> result = pagedResponse(items, keyword, safePage, safeSize, total);
        result.put("scenarioVersion", version);
        result.put("boundary", boundary);
        return result;
    }

    private Map<String, Object> page(String select, String from, String searchExpression,
                                     String query, String orderBy, int page, int size) {
        String keyword = query == null ? "" : query.trim();
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        var params = new MapSqlParameterSource().addValue("likeQuery", "%" + keyword + "%")
                .addValue("limit", safeSize).addValue("offset", safePage * safeSize);
        String where = keyword.isEmpty() ? "" : " WHERE " + searchExpression + " LIKE :likeQuery";
        long total = count("SELECT COUNT(*) FROM " + from + where, params);
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList(
                "SELECT " + select + " FROM " + from + where
                        + " ORDER BY " + orderBy + " LIMIT :limit OFFSET :offset", params));
        return pagedResponse(items, keyword, safePage, safeSize, total);
    }

    private long count(String sql, MapSqlParameterSource params) {
        Long total = jdbc.queryForObject(sql, params, Long.class);
        return total == null ? 0 : total;
    }

    private Map<String, Object> pagedResponse(List<Map<String, Object>> items, String query,
                                              int page, int size, long total) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("items", items);
        result.put("query", query);
        result.put("page", page);
        result.put("size", size);
        result.put("total", total);
        result.put("totalPages", total == 0 ? 0 : (total + size - 1) / size);
        return result;
    }

    private Map<String, Object> queryOne(String sql, Map<String, ?> params, String notFoundMessage) {
        try {
            return normalizeRow(jdbc.queryForMap(sql, params));
        } catch (EmptyResultDataAccessException error) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, notFoundMessage);
        }
    }

    private Map<String, Object> queryOptional(String sql, Map<String, ?> params) {
        try {
            return normalizeRow(jdbc.queryForMap(sql, params));
        } catch (EmptyResultDataAccessException error) {
            return Map.of();
        }
    }

    private List<Map<String, Object>> normalizeRows(List<Map<String, Object>> rows) {
        return rows.stream().map(this::normalizeRow).toList();
    }

    private Map<String, Object> normalizeRow(Map<String, Object> row) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        row.forEach((key, value) -> normalized.put(toCamelCase(key), value));
        return normalized;
    }

    private String toCamelCase(String value) {
        String lower = value.toLowerCase(Locale.ROOT);
        StringBuilder output = new StringBuilder();
        boolean capitalize = false;
        for (char character : lower.toCharArray()) {
            if (character == '_') capitalize = true;
            else if (capitalize) {
                output.append(Character.toUpperCase(character));
                capitalize = false;
            } else output.append(character);
        }
        return output.toString();
    }
}
