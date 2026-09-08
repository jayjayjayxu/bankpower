package com.spdb.powerfinance.service;

import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.Map;

@Service
@Transactional(readOnly = true)
public class SynergySimulationService {
    private final NamedParameterJdbcTemplate jdbc;
    public SynergySimulationService(NamedParameterJdbcTemplate jdbc) { this.jdbc = jdbc; }
    public Map<String, Object> overview(String facilityCode) {
        var params = Map.of("facility", facilityCode);
        // Deliberately separate from facts, credit recommendations and V1 overlays.
        return Map.of(
            "scenarios", jdbc.queryForList("SELECT * FROM compute_synergy_simulation_v2 WHERE facility_code=:facility ORDER BY scenario_code", params),
            "assumptions", jdbc.queryForList("SELECT a.* FROM compute_synergy_assumption_v2 a JOIN compute_synergy_simulation_v2 s USING(scenario_code) WHERE s.facility_code=:facility ORDER BY a.scenario_code,a.field_code", params),
            "annual", jdbc.queryForList("SELECT a.* FROM compute_synergy_annual_v2 a JOIN compute_synergy_simulation_v2 s USING(scenario_code) WHERE s.facility_code=:facility ORDER BY a.scenario_code,a.year_index", params),
            "monthly", jdbc.queryForList("SELECT a.* FROM v_compute_synergy_monthly_v2 a JOIN compute_synergy_simulation_v2 s USING(scenario_code) WHERE s.facility_code=:facility ORDER BY a.scenario_code,a.month", params),
            "daily", jdbc.queryForList("SELECT h.scenario_code,HOUR(h.ts) AS hour,AVG(h.facility_load_kw) AS facility_load_kw,AVG(h.grid_import_kw) AS grid_import_kw,AVG(h.charge_kw) AS charge_kw,AVG(h.discharge_kw) AS discharge_kw FROM compute_synergy_hourly_v2 h JOIN compute_synergy_simulation_v2 s USING(scenario_code) WHERE s.facility_code=:facility GROUP BY h.scenario_code,HOUR(h.ts) ORDER BY h.scenario_code,hour", params)
        );
    }
}
