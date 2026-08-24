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
public class EnterpriseQueryService {
    private final NamedParameterJdbcTemplate jdbc;
    public EnterpriseQueryService(NamedParameterJdbcTemplate jdbc) { this.jdbc = jdbc; }

    public Map<String, Object> getHomeSummary() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("coverage", normalizeRow(jdbc.queryForMap("""
                SELECT (SELECT COUNT(*) FROM regional_power_statistics) AS regional_power_statistics,
                       (SELECT COUNT(*) FROM electricity_tariff) AS electricity_tariff,
                       (SELECT COUNT(*) FROM power_market_trade) AS power_market_trade,
                       (SELECT COUNT(*) FROM policy_rule_v1) AS policy_rule,
                       (SELECT COUNT(*) FROM policy_document_v1) AS policy_document,
                       (SELECT COUNT(*) FROM enterprise_public_energy_metric) AS public_energy_metric,
                       (SELECT COUNT(*) FROM research_focus_enterprise
                        WHERE focus_version='V3' AND active_flag=1) AS focus_company,
                       (SELECT COUNT(*) FROM (SELECT h.company_id FROM enterprise_hourly_load h
                          JOIN research_focus_enterprise f ON f.company_id=h.company_id AND f.focus_version='V3' AND f.active_flag=1
                          WHERE YEAR(h.ts)=(SELECT analysis_year FROM analysis_run WHERE status='COMPLETED' ORDER BY run_id DESC LIMIT 1)
                          GROUP BY h.company_id HAVING COUNT(*)=8760) complete_load) AS complete_load_company,
                       (SELECT COUNT(*) FROM enterprise_hourly_load h
                          JOIN research_focus_enterprise f ON f.company_id=h.company_id AND f.focus_version='V3' AND f.active_flag=1
                          WHERE YEAR(h.ts)=(SELECT analysis_year FROM analysis_run WHERE status='COMPLETED' ORDER BY run_id DESC LIMIT 1)) AS load_hour,
                       (SELECT COUNT(*) FROM enterprise_hourly_generation g
                          JOIN research_focus_enterprise f ON f.company_id=g.company_id AND f.focus_version='V3' AND f.active_flag=1
                          WHERE YEAR(g.ts)=(SELECT analysis_year FROM analysis_run WHERE status='COMPLETED' ORDER BY run_id DESC LIMIT 1)) AS generation_hour
                """, Map.of())));
        result.put("activeRun", normalizeRow(jdbc.queryForMap("""
                SELECT run_id, run_name, model_version, storage_version, finance_version, policy_version,
                       analysis_year, status, completed_time
                FROM analysis_run WHERE status='COMPLETED' ORDER BY run_id DESC LIMIT 1
                """, Map.of())));
        result.put("companies", normalizeRows(jdbc.queryForList("""
                SELECT f.display_order, f.focus_role, e.company_id, e.company_name, e.industry_name,
                       e.power_chain_role, s.snapshot_version, s.data_type, s.storage_power_mw,
                       s.storage_capacity_mwh, s.storage_duration_hour, s.npv_wanyuan, s.irr,
                       s.base_min_dscr, s.max_debt_ratio, s.max_loan_amount_wanyuan,
                       s.opportunity_level, s.readiness_level, s.risk_level, s.business_priority,
                       s.recommended_product, s.recommendation_text, s.risk_summary,
                       ef.analysis_year AS feature_analysis_year, ef.annual_power_kwh,
                       (SELECT m.metric_value FROM enterprise_public_energy_metric m
                        WHERE m.company_id=e.company_id AND m.metric_code='INSTALLED_CAPACITY'
                        ORDER BY m.report_year DESC,m.metric_id DESC LIMIT 1) AS installed_capacity_10k_kw,
                       (SELECT m.metric_value FROM enterprise_public_energy_metric m
                        WHERE m.company_id=e.company_id AND m.metric_code='GROSS_GENERATION'
                        ORDER BY m.report_year DESC,m.metric_id DESC LIMIT 1) AS gross_generation_100m_kwh,
                       (SELECT m.metric_value FROM enterprise_public_energy_metric m
                        WHERE m.company_id=e.company_id AND m.metric_code='ON_GRID_ELECTRICITY'
                        ORDER BY m.report_year DESC,m.metric_id DESC LIMIT 1) AS on_grid_electricity_100m_kwh,
                       (SELECT m.metric_value FROM enterprise_public_energy_metric m
                        WHERE m.company_id=e.company_id AND m.metric_code='MARKET_TRADED_RATIO'
                        ORDER BY m.report_year DESC,m.metric_id DESC LIMIT 1) AS market_trade_ratio_pct,
                       (SELECT m.metric_value FROM enterprise_public_energy_metric m
                        WHERE m.company_id=e.company_id AND m.metric_code='AVERAGE_ON_GRID_PRICE'
                        ORDER BY m.report_year DESC,m.metric_id DESC LIMIT 1) AS average_on_grid_price,
                       (SELECT m.metric_value FROM enterprise_public_energy_metric m
                        WHERE m.company_id=e.company_id AND m.metric_code='RENEWABLE_CAPACITY_RATIO'
                        ORDER BY m.report_year DESC,m.metric_id DESC LIMIT 1) AS renewable_capacity_ratio_pct,
                       (SELECT x.debt_ratio FROM enterprise_financial x WHERE x.company_id=e.company_id
                        ORDER BY x.financial_year DESC LIMIT 1) AS latest_debt_ratio
                FROM research_focus_enterprise f
                JOIN enterprise_profile e ON e.company_id=f.company_id
                LEFT JOIN analysis_result_snapshot s ON s.snapshot_id=(
                    SELECT s2.snapshot_id FROM analysis_result_snapshot s2 WHERE s2.company_id=e.company_id
                    ORDER BY s2.analysis_date DESC,s2.snapshot_id DESC LIMIT 1)
                LEFT JOIN enterprise_energy_features ef ON ef.feature_id=(
                    SELECT ef2.feature_id FROM enterprise_energy_features ef2 WHERE ef2.company_id=e.company_id
                    ORDER BY CASE WHEN ef2.feature_version='V3_2025' THEN 0 ELSE 1 END,
                             ef2.analysis_year DESC,ef2.feature_id DESC LIMIT 1)
                WHERE f.focus_version='V3' AND f.active_flag=1 ORDER BY f.display_order
                """, Map.of())));
        return result;
    }

    public List<Map<String, Object>> findEnterprises(String query, int limit) {
        String keyword = query == null ? "" : query.trim();
        var params = new MapSqlParameterSource().addValue("keyword", keyword)
                .addValue("likeKeyword", "%" + keyword + "%").addValue("limit", Math.min(Math.max(limit, 1), 200));
        String sql = """
                SELECT e.company_id, e.company_name, e.industry_name, e.city_name, e.district_name,
                       e.ownership_type, e.data_center_flag, e.manufacturing_flag, e.verification_priority,
                       s.snapshot_id, s.analysis_date, s.opportunity_level, s.readiness_level, s.risk_level,
                       s.business_priority, s.storage_power_mw, s.storage_capacity_mwh, s.npv_wanyuan,
                       s.base_min_dscr, s.max_debt_ratio, s.max_loan_amount_wanyuan
                FROM enterprise_profile e
                LEFT JOIN analysis_result_snapshot s ON s.snapshot_id = (
                    SELECT s2.snapshot_id FROM analysis_result_snapshot s2
                    WHERE s2.company_id = e.company_id
                    ORDER BY s2.analysis_date DESC, s2.snapshot_id DESC LIMIT 1)
                WHERE (:keyword = '' OR e.company_id LIKE :likeKeyword OR e.company_name LIKE :likeKeyword
                    OR COALESCE(e.company_alias, '') LIKE :likeKeyword OR COALESCE(e.industry_name, '') LIKE :likeKeyword)
                ORDER BY CASE WHEN s.business_priority IS NULL THEN 1 ELSE 0 END, s.business_priority, e.company_id
                LIMIT :limit
                """;
        return normalizeRows(jdbc.queryForList(sql, params));
    }

    public Map<String, Object> findEnterpriseDetail(String companyId) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("profile", queryOne("SELECT * FROM enterprise_profile WHERE company_id = :companyId", companyId, true));
        result.put("energyFeature", queryOne("""
                SELECT * FROM enterprise_energy_features WHERE company_id = :companyId
                ORDER BY CASE WHEN feature_version='V3_2025' THEN 0 ELSE 1 END,
                         CASE data_type WHEN 'ACTUAL' THEN 0 WHEN 'MIXED' THEN 1 WHEN 'PUBLIC' THEN 2 ELSE 3 END,
                         analysis_year DESC, created_at DESC, feature_id DESC LIMIT 1
                """, companyId, false));
        result.put("energyFeatureProvenance", normalizeRows(jdbc.queryForList("""
                SELECT field_name, provenance_type, source_year, source_feature_version,
                       calculation_formula, notes
                FROM enterprise_energy_feature_provenance
                WHERE company_id = :companyId AND feature_version=(
                    SELECT feature_version FROM enterprise_energy_features
                    WHERE company_id=:companyId
                    ORDER BY CASE WHEN feature_version='V3_2025' THEN 0 ELSE 1 END,
                             analysis_year DESC,feature_id DESC LIMIT 1)
                ORDER BY field_name
                """, Map.of("companyId", companyId))));
        result.put("snapshot", queryOne("""
                SELECT s.*, r.run_name, r.run_type, r.description AS run_description,
                       r.created_time AS run_created_time, r.status AS run_status
                FROM analysis_result_snapshot s JOIN analysis_run r ON r.run_id = s.run_id
                WHERE s.company_id = :companyId ORDER BY s.analysis_date DESC, s.snapshot_id DESC LIMIT 1
                """, companyId, false));
        result.put("snapshotFieldProvenance", normalizeRows(jdbc.queryForList("""
                SELECT p.field_name, p.field_label, p.provenance_type, p.source_table,
                       p.source_field, p.formula_text, p.notes
                FROM analysis_snapshot_field_provenance p
                JOIN analysis_result_snapshot s ON s.snapshot_id=p.snapshot_id
                WHERE s.snapshot_id=(SELECT s2.snapshot_id FROM analysis_result_snapshot s2
                    WHERE s2.company_id=:companyId ORDER BY s2.analysis_date DESC,s2.snapshot_id DESC LIMIT 1)
                ORDER BY p.provenance_id
                """, Map.of("companyId", companyId))));
        result.put("monthlyPower", normalizeRows(jdbc.queryForList("""
                SELECT * FROM enterprise_monthly_power WHERE company_id = :companyId ORDER BY year DESC, month ASC
                """, Map.of("companyId", companyId))));
        result.put("monthlyGeneration", normalizeRows(jdbc.queryForList("""
                SELECT * FROM enterprise_monthly_generation WHERE company_id = :companyId ORDER BY year DESC, month ASC
                """, Map.of("companyId", companyId))));
        result.put("publicEnergyMetrics", normalizeRows(jdbc.queryForList("""
                SELECT m.metric_id, m.company_id, m.report_year, m.metric_code, m.metric_name,
                       m.metric_value, m.metric_unit, m.normalized_value_kwh, m.reporting_scope,
                       m.replacement_eligibility, m.source_page, m.calculation_formula,
                       m.data_type, m.verification_status, m.data_version, m.notes,
                       s.source_org, s.source_title, s.source_url, s.source_date, s.source_tier
                FROM enterprise_public_energy_metric m
                JOIN data_source s ON s.source_id = m.source_id
                WHERE m.company_id = :companyId
                ORDER BY m.report_year DESC, m.metric_id
                """, Map.of("companyId", companyId))));
        result.put("powerAnchors", normalizeRows(jdbc.queryForList("""
                SELECT a.anchor_id, a.anchor_year, a.metric_type, a.public_value_kwh,
                       a.relation_to_total, a.calculation_formula, a.data_type, a.data_quality,
                       a.notes, s.source_title, s.source_url
                FROM enterprise_power_anchor a
                LEFT JOIN data_source s ON s.source_id = a.source_id
                WHERE a.company_id = :companyId
                ORDER BY a.anchor_year DESC, a.anchor_id
                """, Map.of("companyId", companyId))));
        result.put("financials", normalizeRows(jdbc.queryForList("""
                SELECT * FROM enterprise_financial WHERE company_id = :companyId ORDER BY financial_year DESC
                """, Map.of("companyId", companyId))));
        result.put("hourlyCoverage", normalizeRows(jdbc.queryForList("""
                SELECT CAST(YEAR(ts) AS UNSIGNED) AS analysis_year, COUNT(*) AS row_count, MIN(ts) AS start_time,
                       MAX(ts) AS end_time, COUNT(DISTINCT DATE(ts)) AS day_count,
                       MIN(data_type) AS data_type, MIN(data_quality) AS data_quality
                FROM enterprise_hourly_load WHERE company_id = :companyId
                GROUP BY YEAR(ts) ORDER BY analysis_year DESC
                """, Map.of("companyId", companyId))));
        result.put("generationCoverage", normalizeRows(jdbc.queryForList("""
                SELECT CAST(YEAR(ts) AS UNSIGNED) AS analysis_year, COUNT(*) AS row_count, MIN(ts) AS start_time,
                       MAX(ts) AS end_time, COUNT(DISTINCT DATE(ts)) AS day_count,
                       MIN(data_type) AS data_type, MIN(data_quality) AS data_quality
                FROM enterprise_hourly_generation WHERE company_id = :companyId
                GROUP BY YEAR(ts) ORDER BY analysis_year DESC
                """, Map.of("companyId", companyId))));
        return result;
    }

    public Map<String, Object> findHourlyLoad(String companyId, Integer year, int page, int size) {
        ensureCompanyExists(companyId);
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 744);
        var params = new MapSqlParameterSource().addValue("companyId", companyId).addValue("year", year)
                .addValue("limit", safeSize).addValue("offset", safePage * safeSize);
        String yearFilter = year == null ? "" : " AND YEAR(ts) = :year";
        Long totalValue = jdbc.queryForObject("SELECT COUNT(*) FROM enterprise_hourly_load WHERE company_id = :companyId" + yearFilter, params, Long.class);
        long total = totalValue == null ? 0L : totalValue;
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList("""
                SELECT load_id, company_id, ts, power_consumption_kwh, load_kw, time_period,
                       electricity_price_yuan_kwh, electricity_cost_yuan, max_demand_kw,
                       production_day, holiday_flag, temperature_c, data_type, data_quality, is_derived
                FROM enterprise_hourly_load WHERE company_id = :companyId
                """ + yearFilter + " ORDER BY ts LIMIT :limit OFFSET :offset", params));
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("items", items); response.put("page", safePage); response.put("size", safeSize);
        response.put("total", total); response.put("totalPages", total == 0 ? 0 : (total + safeSize - 1) / safeSize);
        return response;
    }

    public Map<String, Object> findLoadPriceWindow(String companyId, int year) {
        ensureCompanyExists(companyId);
        var params = Map.of("companyId", companyId, "year", year);
        Map<String, Object> company = normalizeRow(jdbc.queryForMap("""
                SELECT company_id, company_name FROM enterprise_profile WHERE company_id = :companyId
                """, params));
        List<Map<String, Object>> series = normalizeRows(jdbc.queryForList("""
                SELECT HOUR(ts) AS hour_of_day,
                       AVG(load_kw) AS avg_load_kw,
                       AVG(electricity_price_yuan_kwh) AS avg_price_yuan_kwh,
                       MIN(time_period) AS time_period,
                       COUNT(*) AS sample_count,
                       MIN(data_type) AS data_type,
                       MIN(data_quality) AS data_quality
                FROM enterprise_hourly_load
                WHERE company_id = :companyId AND YEAR(ts) = :year
                GROUP BY HOUR(ts)
                ORDER BY hour_of_day
                """, params));
        long sampleCount = series.stream()
                .mapToLong(row -> ((Number) row.getOrDefault("sampleCount", 0)).longValue())
                .sum();
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("companyId", company.get("companyId"));
        response.put("companyName", company.get("companyName"));
        response.put("analysisYear", year);
        response.put("sampleCount", sampleCount);
        response.put("series", series);
        response.put("boundary", "负荷曲线为该企业全年同一小时的均值；电价为小时记录中的研究情景价格，不代表企业实际结算价格。");
        return response;
    }

    public Map<String, Object> findHourlyGeneration(String companyId, Integer year, int page, int size) {
        ensureCompanyExists(companyId);
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 744);
        var params = new MapSqlParameterSource().addValue("companyId", companyId).addValue("year", year)
                .addValue("limit", safeSize).addValue("offset", safePage * safeSize);
        String yearFilter = year == null ? "" : " AND YEAR(ts) = :year";
        Long totalValue = jdbc.queryForObject("SELECT COUNT(*) FROM enterprise_hourly_generation WHERE company_id = :companyId" + yearFilter, params, Long.class);
        long total = totalValue == null ? 0L : totalValue;
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList("""
                SELECT generation_id, company_id, ts, gross_generation_kwh, on_grid_generation_kwh,
                       gross_generation_kw, capacity_factor, data_type, data_quality, is_derived
                FROM enterprise_hourly_generation WHERE company_id = :companyId
                """ + yearFilter + " ORDER BY ts LIMIT :limit OFFSET :offset", params));
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("items", items); response.put("page", safePage); response.put("size", safeSize);
        response.put("total", total); response.put("totalPages", total == 0 ? 0 : (total + safeSize - 1) / safeSize);
        return response;
    }

    private void ensureCompanyExists(String companyId) {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM enterprise_profile WHERE company_id = :companyId", Map.of("companyId", companyId), Integer.class);
        if (count == null || count == 0) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "未找到企业 " + companyId);
    }

    private Map<String, Object> queryOne(String sql, String companyId, boolean required) {
        try { return normalizeRow(jdbc.queryForMap(sql, Map.of("companyId", companyId))); }
        catch (EmptyResultDataAccessException exception) {
            if (required) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "未找到企业 " + companyId);
            return Map.of();
        }
    }

    private List<Map<String, Object>> normalizeRows(List<Map<String, Object>> rows) { return rows.stream().map(this::normalizeRow).toList(); }
    private Map<String, Object> normalizeRow(Map<String, Object> row) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        row.forEach((key, value) -> normalized.put(toCamelCase(key), value));
        return normalized;
    }
    private String toCamelCase(String value) {
        String lower = value.toLowerCase(Locale.ROOT); StringBuilder result = new StringBuilder(); boolean capitalize = false;
        for (char character : lower.toCharArray()) {
            if (character == '_') capitalize = true;
            else if (capitalize) { result.append(Character.toUpperCase(character)); capitalize = false; }
            else result.append(character);
        }
        return result.toString();
    }
}
