package com.spdb.powerfinance.service;

import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
@Transactional(readOnly = true)
public class PowerSourceStructureService {
    private static final String MODEL_VERSION = "V2.0";
    private final NamedParameterJdbcTemplate jdbc;

    public PowerSourceStructureService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Map<String, Object> getOverview() {
        var params = Map.of("modelVersion", MODEL_VERSION);
        List<Map<String, Object>> records = normalizeRows(jdbc.queryForList("""
                SELECT v.structure_v2_id, r.region_code, r.region_name, r.region_level,
                       v.stat_year, v.metric_basis, v.scope_code, v.statistical_scope,
                       v.energy_type_code, v.energy_type_name, v.parent_category,
                       v.metric_value, v.metric_unit, v.share_ratio, v.value_operator,
                       v.disclosure_status, v.is_total, v.is_fossil, v.is_renewable,
                       v.is_clean_energy, v.is_storage, v.reported_growth_rate,
                       v.utilization_hours, v.source_locator, v.metric_is_derived,
                       v.share_is_derived, v.calculation_formula, v.data_quality,
                       v.confidence_level, v.notes, v.model_version,
                       s.source_org, s.source_title, s.source_url, s.source_date, s.source_tier
                FROM power_source_structure_v2 v
                JOIN dim_region r ON r.region_id=v.region_id
                LEFT JOIN data_source s ON s.source_id=v.source_id
                WHERE v.model_version=:modelVersion AND r.region_code IN ('CN','GD','SZ')
                ORDER BY FIELD(r.region_code,'CN','GD','SZ'), v.stat_year,
                         FIELD(v.metric_basis,'INSTALLED_CAPACITY','GROSS_GENERATION','DISCLOSED_SHARE'),
                         v.is_total DESC, v.share_ratio DESC, v.energy_type_code
                """, params));

        List<Map<String, Object>> coverage = normalizeRows(jdbc.queryForList("""
                SELECT r.region_code, r.region_name, v.metric_basis, v.scope_code,
                       MIN(v.stat_year) AS min_year, MAX(v.stat_year) AS max_year,
                       COUNT(DISTINCT v.stat_year) AS year_count, COUNT(*) AS record_count,
                       MIN(v.data_quality) AS minimum_data_quality
                FROM power_source_structure_v2 v
                JOIN dim_region r ON r.region_id=v.region_id
                WHERE v.model_version=:modelVersion AND r.region_code IN ('CN','GD','SZ')
                GROUP BY r.region_code, r.region_name, v.metric_basis, v.scope_code
                ORDER BY FIELD(r.region_code,'CN','GD','SZ'), max_year DESC, v.metric_basis
                """, params));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("modelVersion", MODEL_VERSION);
        result.put("recordCount", records.size());
        result.put("coverage", coverage);
        result.put("records", records);
        result.put("boundary", "装机结构、发电结构和供电来源是不同统计口径；深圳本地发电不等于深圳全市用电来源。");
        return result;
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
            else if (capitalize) {
                result.append(Character.toUpperCase(character));
                capitalize = false;
            } else result.append(character);
        }
        return result.toString();
    }
}
