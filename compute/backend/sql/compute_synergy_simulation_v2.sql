-- Additive model layer. No UPDATE/INSERT into public facts or due-diligence evidence.
CREATE TABLE IF NOT EXISTS compute_synergy_simulation_v2 (
 scenario_code VARCHAR(80) PRIMARY KEY,
 facility_code VARCHAR(32) NOT NULL,
 scenario_name VARCHAR(128) NOT NULL,
 project_scope VARCHAR(96) NOT NULL,
 model_version VARCHAR(40) NOT NULL,
 simulation_year SMALLINT NOT NULL,
 data_type VARCHAR(32) NOT NULL DEFAULT 'SIMULATED',
 input_sha256 CHAR(64) NOT NULL,
 parameters JSON NOT NULL,
 boundary TEXT NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS compute_synergy_assumption_v2 (
 scenario_code VARCHAR(80) NOT NULL,
 field_code VARCHAR(80) NOT NULL,
 field_label VARCHAR(128) NOT NULL,
 actual_value DECIMAL(28,8) NULL COMMENT 'NULL when project actual has not been obtained',
 simulation_value DECIMAL(28,8) NOT NULL,
 unit VARCHAR(48) NOT NULL,
 input_type VARCHAR(48) NOT NULL,
 basis TEXT NOT NULL,
 PRIMARY KEY(scenario_code,field_code),
 FOREIGN KEY(scenario_code) REFERENCES compute_synergy_simulation_v2(scenario_code)
);
CREATE TABLE IF NOT EXISTS compute_synergy_hourly_v2 (
 scenario_code VARCHAR(80) NOT NULL,
 ts DATETIME NOT NULL,
 it_load_kw DECIMAL(18,6) NOT NULL,
 pue DECIMAL(10,6) NOT NULL,
 facility_load_kw DECIMAL(18,6) NOT NULL,
 tariff_yuan_kwh DECIMAL(12,8) NOT NULL,
 charge_kw DECIMAL(18,6) NOT NULL,
 discharge_kw DECIMAL(18,6) NOT NULL,
 soc_kwh DECIMAL(18,6) NOT NULL,
 grid_import_kw DECIMAL(18,6) NOT NULL,
 baseline_cost_yuan DECIMAL(20,6) NOT NULL,
 optimized_cost_yuan DECIMAL(20,6) NOT NULL,
 data_type VARCHAR(32) NOT NULL DEFAULT 'SIMULATED',
 PRIMARY KEY(scenario_code,ts),
 FOREIGN KEY(scenario_code) REFERENCES compute_synergy_simulation_v2(scenario_code)
);
CREATE TABLE IF NOT EXISTS compute_synergy_annual_v2 (
 scenario_code VARCHAR(80) NOT NULL,
 year_index SMALLINT NOT NULL,
 annual_energy_kwh DECIMAL(24,4) NOT NULL,
 grid_energy_kwh DECIMAL(24,4) NOT NULL,
 peak_grid_kw DECIMAL(20,4) NOT NULL,
 energy_cap_status VARCHAR(40) NOT NULL,
 revenue_yuan DECIMAL(24,4) NOT NULL,
 baseline_electricity_cost_yuan DECIMAL(24,4) NOT NULL,
 optimized_electricity_cost_yuan DECIMAL(24,4) NOT NULL,
 storage_saving_yuan DECIMAL(24,4) NOT NULL,
 green_premium_yuan DECIMAL(24,4) NOT NULL,
 other_cost_yuan DECIMAL(24,4) NOT NULL,
 storage_opex_yuan DECIMAL(24,4) NOT NULL,
 maintenance_reserve_yuan DECIMAL(24,4) NOT NULL,
 tax_proxy_yuan DECIMAL(24,4) NOT NULL,
 cfads_proxy_yuan DECIMAL(24,4) NOT NULL,
 debt_service_yuan DECIMAL(24,4) NOT NULL,
 dscr_proxy DECIMAL(18,8) NULL,
 PRIMARY KEY(scenario_code,year_index),
 FOREIGN KEY(scenario_code) REFERENCES compute_synergy_simulation_v2(scenario_code)
);
CREATE OR REPLACE VIEW v_compute_synergy_monthly_v2 AS
 SELECT scenario_code,MONTH(ts) AS month,COUNT(*) AS hour_count,
 SUM(facility_load_kw) AS facility_energy_kwh,SUM(grid_import_kw) AS grid_energy_kwh,
 SUM(baseline_cost_yuan) AS baseline_cost_yuan,SUM(optimized_cost_yuan) AS optimized_cost_yuan,
 SUM(charge_kw) AS charge_kwh,SUM(discharge_kw) AS discharge_kwh,
 MAX(grid_import_kw) AS peak_grid_kw
 FROM compute_synergy_hourly_v2 GROUP BY scenario_code,MONTH(ts);
