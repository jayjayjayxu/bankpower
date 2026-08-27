package com.spdb.powerfinance.service;

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
public class ReferenceDataService {
    private final NamedParameterJdbcTemplate jdbc;
    public ReferenceDataService(NamedParameterJdbcTemplate jdbc) { this.jdbc = jdbc; }

    private record Dataset(String title, String subtitle, String fromSql, String selectSql, String searchSql, String orderSql) {}

    private Dataset dataset(String code) {
        return switch (code) {
            case "regional-power-statistics" -> new Dataset(
                    "区域电力统计", "全国、广东、广州与深圳的年度发电、用电、产业结构和最大负荷记录。",
                    "regional_power_statistics x JOIN dim_region r ON r.region_id=x.region_id LEFT JOIN data_source s ON s.source_id=x.source_id",
                    "x.stat_id,r.region_name,r.region_level,x.year,x.total_generation_gwh,x.total_consumption_gwh,x.primary_industry_gwh,x.secondary_industry_gwh,x.tertiary_industry_gwh,x.residential_gwh,x.industrial_gwh,x.max_load_mw,x.power_growth_rate,x.peak_load_growth_rate,x.unit_original,x.is_derived,x.calculation_formula,x.data_quality,x.notes,s.source_title,s.source_url,s.source_tier",
                    "CONCAT_WS(' ',r.region_name,r.region_level,x.year,x.data_quality,s.source_title,x.notes) LIKE :likeQuery",
                    "x.year DESC,r.region_id");
            case "electricity-tariff" -> new Dataset(
                    "电价记录", "分地区、月份、用户类型、电压等级和时段保存的电价明细。",
                    "electricity_tariff x JOIN dim_region r ON r.region_id=x.region_id LEFT JOIN power_price_zone z ON z.price_zone_id=x.price_zone_id LEFT JOIN data_source s ON s.source_id=x.source_id",
                    "x.tariff_id,r.region_name,z.price_zone_name AS price_zone,x.year,x.month,x.effective_date,x.expiry_date,x.customer_type,x.voltage_level,x.market_type,x.time_period,x.start_time_text,x.end_time_text,x.energy_price_yuan_kwh,x.transmission_price_yuan_kwh,x.line_loss_price_yuan_kwh,x.system_operation_yuan_kwh,x.government_fund_yuan_kwh,x.capacity_price,x.capacity_price_unit,x.demand_price,x.demand_price_unit,x.final_price_yuan_kwh,x.statistical_scope,x.notes,s.source_title,s.source_url,s.source_tier",
                    "CONCAT_WS(' ',r.region_name,z.price_zone_name,x.year,x.month,x.customer_type,x.voltage_level,x.market_type,x.time_period,s.source_title,x.notes) LIKE :likeQuery",
                    "x.year DESC,x.month DESC,x.tariff_id DESC");
            case "power-market-trade" -> new Dataset(
                    "电力市场交易", "广东电力市场中长期、现货和绿电交易的成交量、价格与交付周期。",
                    "power_market_trade x JOIN dim_region r ON r.region_id=x.region_id LEFT JOIN data_source s ON s.source_id=x.source_id",
                    "x.trade_id,r.region_name,x.year,x.month,x.trade_date,x.delivery_start,x.delivery_end,x.market_category,x.trade_cycle,x.trade_type,x.energy_type,x.buyer_type,x.seller_type,x.transaction_volume_gwh,x.average_price_yuan_mwh,x.weighted_avg_price_yuan_mwh,x.high_price_yuan_mwh,x.low_price_yuan_mwh,x.green_premium_yuan_mwh,x.renewable_volume_gwh,x.participant_count,x.statistical_scope,x.data_quality,x.is_derived,x.calculation_formula,x.notes,s.source_title,s.source_url,s.source_tier",
                    "CONCAT_WS(' ',r.region_name,x.year,x.month,x.market_category,x.trade_cycle,x.trade_type,x.energy_type,x.buyer_type,x.seller_type,s.source_title,x.notes) LIKE :likeQuery",
                    "x.year DESC,x.month DESC,x.trade_id DESC");
            case "policy-rules" -> new Dataset(
                    "政策规则库", "从政策文件提取的适用对象、准入条件、证据要求和模型影响规则。",
                    "policy_rule_v1 x JOIN policy_document_v1 d ON d.policy_document_id=x.policy_document_id LEFT JOIN data_source s ON s.source_id=d.source_id",
                    "x.policy_rule_id,x.rule_code,x.rule_category,x.rule_title,x.applicable_region,x.applicable_entity_type,x.applicable_asset_type,x.applicability_summary,x.requirement_summary,x.required_evidence,x.rule_value_numeric,x.rule_value_unit,x.rule_value_text,x.model_impact_type,x.model_target,x.rule_status,x.interpretation_confidence,x.source_locator,x.analysis_note,d.document_title,d.document_number,d.issuing_authority,d.policy_level,d.jurisdiction,d.policy_category,d.issue_date,d.effective_date,d.expiry_date,d.policy_status,d.official_url,s.source_tier",
                    "CONCAT_WS(' ',x.rule_code,x.rule_category,x.rule_title,x.applicable_region,x.applicable_entity_type,x.applicable_asset_type,x.requirement_summary,x.required_evidence,d.document_title,d.issuing_authority) LIKE :likeQuery",
                    "x.rule_category,x.policy_rule_id");
            default -> throw new ResponseStatusException(HttpStatus.NOT_FOUND, "未知数据集 " + code);
        };
    }

    public Map<String, Object> findDataset(String code, String query, int page, int size) {
        Dataset dataset = dataset(code);
        int safePage = Math.max(page, 0), safeSize = Math.min(Math.max(size, 1), 100);
        String keyword = query == null ? "" : query.trim();
        String where = keyword.isEmpty() ? "" : " WHERE " + dataset.searchSql();
        var params = new MapSqlParameterSource().addValue("likeQuery", "%" + keyword + "%")
                .addValue("limit", safeSize).addValue("offset", safePage * safeSize);
        Long totalValue = jdbc.queryForObject("SELECT COUNT(*) FROM " + dataset.fromSql() + where, params, Long.class);
        long total = totalValue == null ? 0 : totalValue;
        List<Map<String, Object>> items = normalizeRows(jdbc.queryForList(
                "SELECT " + dataset.selectSql() + " FROM " + dataset.fromSql() + where
                        + " ORDER BY " + dataset.orderSql() + " LIMIT :limit OFFSET :offset", params));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("dataset", code); result.put("title", dataset.title()); result.put("subtitle", dataset.subtitle());
        result.put("query", keyword); result.put("page", safePage); result.put("size", safeSize);
        result.put("total", total); result.put("totalPages", total == 0 ? 0 : (total + safeSize - 1) / safeSize);
        result.put("items", items);
        return result;
    }

    private List<Map<String, Object>> normalizeRows(List<Map<String, Object>> rows) { return rows.stream().map(this::normalizeRow).toList(); }
    private Map<String, Object> normalizeRow(Map<String, Object> row) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        row.forEach((key, value) -> normalized.put(toCamelCase(key), value)); return normalized;
    }
    private String toCamelCase(String value) {
        String lower=value.toLowerCase(Locale.ROOT); StringBuilder out=new StringBuilder(); boolean upper=false;
        for(char ch:lower.toCharArray()){ if(ch=='_') upper=true; else if(upper){out.append(Character.toUpperCase(ch));upper=false;} else out.append(ch); }
        return out.toString();
    }
}
