package com.spdb.powerfinance.service;

import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * A read-only business layer for the relationship-manager workbench.
 *
 * It deliberately combines only already-versioned model outputs and public
 * facility facts. It does not turn scenario values into verified facts.
 */
@Service
@Transactional(readOnly = true)
public class BankWorkbenchService {
    private final NamedParameterJdbcTemplate jdbc;

    public BankWorkbenchService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Map<String, Object> getOverview() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("activeRun", normalizeRow(jdbc.queryForMap("""
                SELECT run_id,run_name,analysis_year,model_version,storage_version,finance_version,
                       policy_version,completed_time
                FROM analysis_run
                WHERE status='COMPLETED'
                ORDER BY run_id DESC
                LIMIT 1
                """, Map.of())));
        result.put("summary", normalizeRow(jdbc.queryForMap("""
                SELECT
                  (SELECT COUNT(*) FROM research_focus_enterprise
                    WHERE focus_version='V3' AND active_flag=1) AS power_candidate_count,
                  (SELECT COUNT(*) FROM research_focus_enterprise f
                    JOIN analysis_result_snapshot s ON s.snapshot_id=(
                      SELECT s2.snapshot_id FROM analysis_result_snapshot s2
                      WHERE s2.company_id=f.company_id
                      ORDER BY s2.analysis_date DESC,s2.snapshot_id DESC LIMIT 1)
                    WHERE f.focus_version='V3' AND f.active_flag=1
                      AND s.npv_wanyuan IS NOT NULL) AS power_modelled_count,
                  (SELECT COUNT(*) FROM research_focus_enterprise f
                    JOIN analysis_result_snapshot s ON s.snapshot_id=(
                      SELECT s2.snapshot_id FROM analysis_result_snapshot s2
                      WHERE s2.company_id=f.company_id
                      ORDER BY s2.analysis_date DESC,s2.snapshot_id DESC LIMIT 1)
                    WHERE f.focus_version='V3' AND f.active_flag=1
                      AND s.business_priority='A') AS power_priority_a_count,
                  (SELECT COUNT(*) FROM enterprise_data_center_v2
                    WHERE facility_code='SZCF016') AS compute_focus_customer_count,
                  (SELECT COUNT(*) FROM v_compute_finance_opportunity_summary_v1
                    WHERE business_priority='A') AS compute_priority_a_count
                """, Map.of())));

        List<Map<String, Object>> powerItems = normalizeRows(jdbc.queryForList("""
                SELECT f.display_order,f.focus_role,e.company_id,e.company_name,e.industry_name,
                       e.power_chain_role,s.snapshot_id,s.snapshot_version,s.analysis_date,s.data_type,
                       s.opportunity_level,s.readiness_level,s.risk_level,s.business_priority,
                       s.recommended_product,s.recommendation_text,s.risk_summary,
                       s.npv_wanyuan,s.irr,s.base_min_dscr,s.max_debt_ratio,s.max_loan_amount_wanyuan
                FROM research_focus_enterprise f
                JOIN enterprise_profile e ON e.company_id=f.company_id
                LEFT JOIN analysis_result_snapshot s ON s.snapshot_id=(
                    SELECT s2.snapshot_id FROM analysis_result_snapshot s2
                    WHERE s2.company_id=e.company_id
                    ORDER BY s2.analysis_date DESC,s2.snapshot_id DESC LIMIT 1)
                WHERE f.focus_version='V3' AND f.active_flag=1 AND f.display_order <= 3
                ORDER BY f.display_order
                """, Map.of()));
        result.put("powerItems", powerItems.stream().map(this::enrichPowerItem).toList());

        Map<String, Object> baiwang = normalizeRow(jdbc.queryForMap("""
                SELECT c.facility_code,c.official_name,c.scenario_code,c.scenario_name,
                       c.reference_historical_capex_yuan,c.reference_rack_capacity_count,c.reference_pue,
                       c.reference_annual_energy_cap_kwh,c.year1_revenue_yuan,
                       c.year1_pre_tax_cashflow_proxy_yuan,c.hypothetical_greenfield_npv_proxy_yuan,
                       c.result_status,c.energy_cap_compliance_status,c.data_type,c.data_quality,
                       o.rack_utilization_ratio AS whole_facility_2025_rack_utilization_ratio,
                       o.hosting_revenue_wanyuan AS whole_facility_2025_hosting_revenue_wanyuan,
                       o.electricity_consumption_kwh AS whole_facility_2025_electricity_consumption_kwh,
                       o.electricity_cost_revenue_ratio AS whole_facility_2025_electricity_cost_revenue_ratio,
                       d.verified_count,d.partial_count,d.pending_count,d.blocking_count
                FROM v_compute_facility_project_cashflow_summary_v1 c
                LEFT JOIN v_compute_facility_operation_calibration_v1 o
                  ON o.facility_code=c.facility_code
                 AND o.operation_scope_code='WHOLE_FACILITY_BUILDING_1_4_SELF_BUILT'
                 AND o.fact_year=2025 AND o.fact_period='ANNUAL'
                LEFT JOIN (
                    SELECT d.facility_v2_id,
                           SUM(d.evidence_status='VERIFIED') AS verified_count,
                           SUM(d.evidence_status='PARTIAL') AS partial_count,
                           SUM(d.evidence_status='PENDING') AS pending_count,
                           SUM(d.risk_level='BLOCKING' AND d.evidence_status<>'VERIFIED') AS blocking_count
                    FROM compute_facility_project_due_diligence_v1 d
                    WHERE d.project_scope_code='PHASE_III_EXCHANGE_DISCLOSURE'
                    GROUP BY d.facility_v2_id
                ) d ON d.facility_v2_id=(
                    SELECT f.facility_v2_id FROM enterprise_data_center_v2 f
                    WHERE f.facility_code=c.facility_code LIMIT 1)
                WHERE c.scenario_code='BWX_PHASE3_BASE_V1'
                """, Map.of()));
        baiwang.put("track", "COMPUTE");
        baiwang.put("computeKind", "PROJECT");
        baiwang.put("opportunityLevel", "DUE_DILIGENCE");
        baiwang.put("businessPriority", "A");
        baiwang.put("dataBasis", "PUBLIC + SCENARIO");
        baiwang.put("dataExplanation", "2025年1栋+4栋经营数据为公开事实；三期收入、成本和现金流仅为公开锚定的研究情景，不是项目实际CFADS。");
        baiwang.put("recommendedProduct", "固定资产贷款 / 绿色项目尽调");
        baiwang.put("nextAction", "取得三期单独收入、成本、回款、近12个月电费单与现有债务本息，重建项目级CFADS后再测算DSCR与授信额度。");
        baiwang.put("blockingSummary", "项目级现金流与偿债基础尚未公开，当前不能形成授信额度结论。");
        result.put("computeProject", baiwang);

        List<Map<String, Object>> computeCandidates = normalizeRows(jdbc.queryForList("""
                SELECT opportunity_code,opportunity_name,opportunity_scope,opportunity_status,business_priority,
                       platform_name,external_product_id,product_name,accelerator_model,accelerator_count,
                       npv_yuan,recommended_debt_ratio,recommended_loan_yuan,recommended_min_dscr,
                       primary_next_action,key_risk_summary,recommendation_text,data_type
                FROM v_compute_finance_opportunity_summary_v1
                WHERE business_priority='A'
                ORDER BY opportunity_rank,opportunity_code
                LIMIT 2
                """, Map.of()));
        result.put("computeCandidates", computeCandidates.stream().map(this::enrichComputeCandidate).toList());

        result.put("boundary", "本工作台是客户经理的研究线索与尽调编排层：电力企业的NPV、DSCR及贷款金额来自已固化模型快照；百旺信三期仅展示公开经营锚点和研究情景。所有指标均不构成授信审批、产品报价或融资承诺。");
        return result;
    }

    private Map<String, Object> enrichPowerItem(Map<String, Object> row) {
        String dataType = String.valueOf(row.getOrDefault("dataType", "UNKNOWN"));
        boolean modelAvailable = row.get("npvWanyuan") != null && row.get("baseMinDscr") != null;
        row.put("track", "POWER");
        row.put("modelAvailable", modelAvailable);
        row.put("dataBasis", switch (dataType) {
            case "PUBLIC" -> "PUBLIC";
            case "MIXED" -> "PUBLIC + SCENARIO";
            case "SIMULATED" -> "SCENARIO";
            default -> "TO BE VERIFIED";
        });
        row.put("dataExplanation", switch (dataType) {
            case "PUBLIC" -> "以公开披露和公开资料为主；尚未把未公开的企业用电或项目现金流视为已取得。";
            case "MIXED" -> "公开经营/能源锚点与2025研究情景共同输入；模型结果需由企业账单和工程资料复核。";
            case "SIMULATED" -> "用电、价格或工程参数含研究情景；仅用于筛选和敏感性讨论，不能替代客户原始资料。";
            default -> "数据口径待核验。";
        });
        if (!modelAvailable) {
            row.put("nextAction", "先确认可融资项目边界、近12个月用电/经营资料及融资主体，再决定是否进入储能或绿色项目测算。");
            row.put("blockingSummary", "当前没有可展示的项目级储能与融资结果。" );
        } else if ("SIMULATED".equals(dataType)) {
            row.put("nextAction", "取得近12个月电费单、分时电量、最大需量、变压器容量和场地条件，以实际资料校准模型。" );
            row.put("blockingSummary", "负荷和电价含情景输入，尚不能按当前金额形成授信建议。" );
        } else {
            row.put("nextAction", "核验电费账单、最大需量、接入容量、场地及项目主体；确认后更新工程与融资参数。" );
            row.put("blockingSummary", "需将公开锚点与项目级用电及工程资料逐项核验。" );
        }
        return row;
    }

    private Map<String, Object> enrichComputeCandidate(Map<String, Object> row) {
        row.put("track", "COMPUTE");
        row.put("computeKind", "PRODUCT_CANDIDATE");
        row.put("title", row.get("opportunityName"));
        row.put("industryName", "公开算力商品候选 · " + row.getOrDefault("platformName", "服务平台待核验"));
        row.put("companyId", row.get("opportunityCode"));
        row.put("opportunityLevel", "DUE_DILIGENCE");
        row.put("modelAvailable", true);
        row.put("dataBasis", "SCENARIO");
        row.put("dataExplanation", "公开商品目录与价格快照结合研究性CAPEX、利用率和融资参数；不是已确认的设施项目、资产权属或客户订单。" );
        row.put("recommendedProduct", "算力设备融资 · 进入尽调");
        row.put("blockingSummary", row.getOrDefault("keyRiskSummary", "尚未确认实际设施、融资主体、设备资产权属和采购报价。"));
        row.put("nextAction", row.getOrDefault("primaryNextAction", "先确认实际设施、融资主体、设备资产权属及采购报价。"));
        return row;
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
        StringBuilder result = new StringBuilder();
        boolean capitalize = false;
        for (char character : lower.toCharArray()) {
            if (character == '_') capitalize = true;
            else if (capitalize) { result.append(Character.toUpperCase(character)); capitalize = false; }
            else result.append(character);
        }
        return result.toString();
    }
}
