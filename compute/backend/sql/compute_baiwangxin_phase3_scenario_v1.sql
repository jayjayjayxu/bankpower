USE spdb_power_finance;

/*
  百旺信云数据中心三期：项目级现金流代理情景 V1

  This module is intentionally separate from compute_operation_scenario_v1:
  - No public marketplace SKU has been confirmed at this facility.
  - Whole-facility operating data (Buildings 1 + 4) are calibration anchors,
    not Phase III's actual revenue, occupancy or customer contract.
  - Historical Phase III CAPEX is a reference fact.  The hypothetical
    greenfield NPV below is a screening proxy, not an appraisal, valuation,
    credit recommendation or a measure of the project's actual return.

  Formula boundary:
  Revenue(y) = racks × occupancy(y) × price_per_rack_month × 12
  Energy(y)  = racks × occupancy(y) × IT_load_per_occupied_rack × 8760 × PUE
  Operating surplus proxy(y) = revenue - electricity_cost - other_cost_proxy
  Other-cost proxy uses the disclosed historic non-electric cost/revenue ratio.
  It therefore remains a conservative operating cash-flow proxy before tax,
  working capital, debt service and maintenance/replacement CAPEX.
*/

CREATE TABLE IF NOT EXISTS compute_facility_project_scenario_v1 (
    facility_project_scenario_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scenario_code VARCHAR(64) NOT NULL,
    scenario_version VARCHAR(40) NOT NULL,
    scenario_name VARCHAR(128) NOT NULL,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    project_scope_code VARCHAR(96) NOT NULL,
    project_scope_name VARCHAR(255) NOT NULL,
    base_year SMALLINT UNSIGNED NOT NULL,
    cashflow_start_year SMALLINT UNSIGNED NOT NULL,
    analysis_horizon_year SMALLINT UNSIGNED NOT NULL,

    reference_capex_metric_id BIGINT UNSIGNED NOT NULL,
    reference_rack_capacity_metric_id BIGINT UNSIGNED NOT NULL,
    reference_pue_metric_id BIGINT UNSIGNED NOT NULL,
    reference_annual_energy_metric_id BIGINT UNSIGNED NOT NULL,
    reference_historical_capex_yuan DECIMAL(28,4) NOT NULL,
    reference_rack_capacity_count DECIMAL(18,4) NOT NULL,
    reference_pue DECIMAL(12,8) NOT NULL,
    reference_annual_energy_cap_kwh DECIMAL(28,4) NOT NULL,

    year1_rack_occupancy_ratio DECIMAL(12,8) NOT NULL,
    steady_state_rack_occupancy_ratio DECIMAL(12,8) NOT NULL,
    occupancy_ramp_years SMALLINT UNSIGNED NOT NULL,
    rack_price_yuan_month DECIMAL(20,4) NOT NULL,
    rack_price_input_type VARCHAR(128) NOT NULL,
    avg_it_load_kw_per_occupied_rack DECIMAL(16,8) NOT NULL,
    it_load_input_type VARCHAR(128) NOT NULL,
    electricity_price_yuan_kwh DECIMAL(16,8) NOT NULL,
    electricity_price_input_type VARCHAR(128) NOT NULL,
    other_operating_cost_proxy_ratio DECIMAL(12,8) NOT NULL,
    other_cost_input_type VARCHAR(128) NOT NULL,
    discount_rate DECIMAL(12,8) NOT NULL,

    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO',
    data_quality VARCHAR(32) NOT NULL DEFAULT 'PUBLIC_ANCHORED_SCENARIO',
    assumption_note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_project_scenario (scenario_code),
    KEY idx_compute_facility_project_scenario (facility_v2_id,scenario_version),
    CONSTRAINT fk_compute_facility_project_scenario_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_project_capex_metric
      FOREIGN KEY (reference_capex_metric_id) REFERENCES compute_facility_metric_v1(facility_metric_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_project_rack_metric
      FOREIGN KEY (reference_rack_capacity_metric_id) REFERENCES compute_facility_metric_v1(facility_metric_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_project_pue_metric
      FOREIGN KEY (reference_pue_metric_id) REFERENCES compute_facility_metric_v1(facility_metric_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_project_energy_metric
      FOREIGN KEY (reference_annual_energy_metric_id) REFERENCES compute_facility_metric_v1(facility_metric_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_project_scenario_occupancy CHECK
      (year1_rack_occupancy_ratio>=0 AND year1_rack_occupancy_ratio<=1
       AND steady_state_rack_occupancy_ratio>=0 AND steady_state_rack_occupancy_ratio<=1),
    CONSTRAINT chk_compute_project_scenario_positive CHECK
      (analysis_horizon_year>0 AND reference_historical_capex_yuan>0
       AND reference_rack_capacity_count>0 AND reference_pue>=1
       AND reference_annual_energy_cap_kwh>0 AND rack_price_yuan_month>=0
       AND avg_it_load_kw_per_occupied_rack>=0 AND electricity_price_yuan_kwh>=0
       AND other_operating_cost_proxy_ratio>=0 AND other_operating_cost_proxy_ratio<=1
       AND discount_rate>=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='单一物理设施项目级研究情景：公开项目锚点+显式代理假设，不替代实际现金流';

/* Upgrade early deployments that created these provenance fields at 32 chars. */
ALTER TABLE compute_facility_project_scenario_v1
    MODIFY COLUMN rack_price_input_type VARCHAR(128) NOT NULL,
    MODIFY COLUMN it_load_input_type VARCHAR(128) NOT NULL,
    MODIFY COLUMN electricity_price_input_type VARCHAR(128) NOT NULL,
    MODIFY COLUMN other_cost_input_type VARCHAR(128) NOT NULL;

CREATE TABLE IF NOT EXISTS compute_facility_project_cashflow_year_v1 (
    cashflow_year_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_project_scenario_id BIGINT UNSIGNED NOT NULL,
    cashflow_year_index SMALLINT UNSIGNED NOT NULL,
    calendar_year SMALLINT UNSIGNED NOT NULL,
    modeled_rack_occupancy_ratio DECIMAL(12,8) NOT NULL,
    modeled_occupied_rack_count DECIMAL(20,4) NOT NULL,
    modeled_revenue_yuan DECIMAL(28,4) NOT NULL,
    modeled_it_energy_kwh DECIMAL(28,4) NOT NULL,
    modeled_total_energy_kwh DECIMAL(28,4) NOT NULL,
    reference_annual_energy_cap_kwh DECIMAL(28,4) NOT NULL,
    energy_cap_status VARCHAR(40) NOT NULL COMMENT 'WITHIN_REFERENCE_CAP/EXCEEDS_REFERENCE_CAP',
    modeled_electricity_cost_yuan DECIMAL(28,4) NOT NULL,
    modeled_other_operating_cost_proxy_yuan DECIMAL(28,4) NOT NULL,
    modeled_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    discount_factor DECIMAL(20,12) NOT NULL,
    discounted_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    calculation_formula TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_project_cashflow_year (facility_project_scenario_id,cashflow_year_index),
    KEY idx_compute_facility_project_cashflow_calendar (calendar_year),
    CONSTRAINT fk_compute_facility_project_cashflow_scenario
      FOREIGN KEY (facility_project_scenario_id) REFERENCES compute_facility_project_scenario_v1(facility_project_scenario_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='项目级逐年现金流代理及年电量边界检验；不可解释为真实CFADS';

CREATE TABLE IF NOT EXISTS compute_facility_project_cashflow_result_v1 (
    cashflow_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_project_scenario_id BIGINT UNSIGNED NOT NULL,
    reference_historical_capex_yuan DECIMAL(28,4) NOT NULL,
    year1_revenue_yuan DECIMAL(28,4) NOT NULL,
    year1_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    steady_state_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    total_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    pv_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    hypothetical_greenfield_npv_proxy_yuan DECIMAL(28,4) NOT NULL,
    first_energy_cap_breach_year SMALLINT UNSIGNED NULL,
    energy_cap_compliance_status VARCHAR(40) NOT NULL,
    result_status VARCHAR(48) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    calculation_formula TEXT NOT NULL,
    model_version VARCHAR(40) NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_project_cashflow_result (facility_project_scenario_id),
    KEY idx_compute_facility_project_cashflow_status (energy_cap_compliance_status,result_status),
    CONSTRAINT fk_compute_facility_project_cashflow_result_scenario
      FOREIGN KEY (facility_project_scenario_id) REFERENCES compute_facility_project_scenario_v1(facility_project_scenario_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='项目级现金流代理汇总；假设绿地重建NPV仅作研究筛查，不表示项目真实估值';

/*
  Three public-anchored research scenarios.
  Inputs intentionally remain transparent:
  - occupancy: 2024 / 2025 whole-facility actual values; optimistic is a scenario
    below the disclosed 1F 2025H1 79.26% mature-building observation;
  - price: disclosed 2025H1 low-power (<4.4kW) actual transaction anchors;
  - base IT load: 2025 whole-facility actual annual energy divided by occupied
    racks, hours and disclosed whole-facility PUE (3.055kW);
  - other cost proxy: historical self-built hosting cost less disclosed
    electricity procurement, divided by hosting revenue.
*/
INSERT INTO compute_facility_project_scenario_v1 (
    scenario_code,scenario_version,scenario_name,facility_v2_id,project_scope_code,project_scope_name,
    base_year,cashflow_start_year,analysis_horizon_year,
    reference_capex_metric_id,reference_rack_capacity_metric_id,reference_pue_metric_id,reference_annual_energy_metric_id,
    reference_historical_capex_yuan,reference_rack_capacity_count,reference_pue,reference_annual_energy_cap_kwh,
    year1_rack_occupancy_ratio,steady_state_rack_occupancy_ratio,occupancy_ramp_years,
    rack_price_yuan_month,rack_price_input_type,avg_it_load_kw_per_occupied_rack,it_load_input_type,
    electricity_price_yuan_kwh,electricity_price_input_type,other_operating_cost_proxy_ratio,other_cost_input_type,discount_rate,
    data_type,data_quality,assumption_note
)
SELECT
  cfg.scenario_code,'BWX_PHASE3_CASHFLOW_V1',cfg.scenario_name,f.facility_v2_id,'PHASE_III_EXCHANGE_DISCLOSURE','百旺信云数据中心三期',
  2025,2026,10,
  capex.facility_metric_id,racks.facility_metric_id,pue.facility_metric_id,energy.facility_metric_id,
  capex.metric_value*10000,racks.metric_value,pue.metric_value,energy.metric_value,
  cfg.year1_occupancy,cfg.steady_occupancy,3,
  cfg.rack_price,cfg.rack_price_input_type,cfg.it_load_kw,cfg.it_load_input_type,
  cfg.electricity_price,cfg.electricity_price_input_type,cfg.other_cost_ratio,cfg.other_cost_input_type,0.1024,
  'SCENARIO','PUBLIC_ANCHORED_SCENARIO',cfg.assumption_note
FROM (
  SELECT 'BWX_PHASE3_CONSERVATIVE_V1' scenario_code,'保守情景' scenario_name,
    0.5500 year1_occupancy,0.6000 steady_occupancy,4103.10 rack_price,'PUBLIC_PROXY_2025H1_LOW_POWER_PRICE' rack_price_input_type,
    2.5459 it_load_kw,'PUBLIC_DERIVED_2023_OPERATING_ANCHOR' it_load_input_type,
    0.5800 electricity_price,'PUBLIC_PROXY_2025H1_B4_PRICE_PLUS_ENVIRONMENTAL_PREMIUM' electricity_price_input_type,
    0.4064 other_cost_ratio,'PUBLIC_DERIVED_2023_NON_ELECTRIC_COST_RATIO' other_cost_input_type,
    '以2024年全园区55.50%上架率为起点、三年爬坡至60%；低功率机柜价格取4栋2025H1实际成交均价。单柜IT负载取2023年全园区实际用电按三期公开PUE=1.228反推；非电成本比例取2023年自建托管成本减不含税电力采购后的比例。' assumption_note
  UNION ALL SELECT 'BWX_PHASE3_BASE_V1','基准情景',
    0.6542,0.7000,4170.22,'PUBLIC_PROXY_2025H1_LOW_POWER_PRICE',
    3.0146,'PUBLIC_DERIVED_2025_OPERATING_ANCHOR',
    0.5700,'PUBLIC_PROXY_2025H1_HISTORICAL_BILL',
    0.3266,'PUBLIC_DERIVED_2025_NON_ELECTRIC_COST_RATIO',
    '以2025年全园区65.42%上架率为起点、三年爬坡至70%；低功率机柜价格取1栋2025H1实际成交均价。单柜IT负载取2025年全园区实际用电按三期公开PUE=1.228反推；非电成本比例取2025年自建托管成本减不含税电力采购后的比例。所有指标均为三期代理，非三期实际经营披露。'
  UNION ALL SELECT 'BWX_PHASE3_OPTIMISTIC_V1','乐观情景',
    0.7500,0.8000,4170.22,'PUBLIC_PROXY_2025H1_LOW_POWER_PRICE',
    3.3000,'SCENARIO_BELOW_4KW_RATED_POWER',
    0.5700,'PUBLIC_PROXY_2025H1_HISTORICAL_BILL',
    0.3098,'PUBLIC_DERIVED_2024_NON_ELECTRIC_COST_RATIO',
    '以上架率75%起步、三年爬坡至80%的研究情景；75%低于成熟1栋2025H1披露的79.26%，但仍非三期实际数据。单柜IT负载3.3kW低于项目4kW额定功率；该情景会触及年用电批复边界，不能直接作为扩容或授信结论。'
) cfg
JOIN enterprise_data_center_v2 f ON f.facility_code='SZCF016'
JOIN compute_facility_metric_v1 capex ON capex.facility_v2_id=f.facility_v2_id AND capex.metric_code='CAPEX' AND capex.metric_scope='PHASE_III_EXCHANGE_DISCLOSURE'
JOIN compute_facility_metric_v1 racks ON racks.facility_v2_id=f.facility_v2_id AND racks.metric_code='CABINET_COUNT' AND racks.metric_scope='PHASE_III_EXCHANGE_DISCLOSURE'
JOIN compute_facility_metric_v1 pue ON pue.facility_v2_id=f.facility_v2_id AND pue.metric_code='PUE' AND pue.metric_scope='PHASE_III_EXCHANGE_DISCLOSURE'
JOIN compute_facility_metric_v1 energy ON energy.facility_v2_id=f.facility_v2_id AND energy.metric_code='ANNUAL_ELECTRICITY_CONSUMPTION' AND energy.metric_scope='PHASE_III_EXCHANGE_DISCLOSURE'
ON DUPLICATE KEY UPDATE
  scenario_name=VALUES(scenario_name),facility_v2_id=VALUES(facility_v2_id),project_scope_code=VALUES(project_scope_code),project_scope_name=VALUES(project_scope_name),
  base_year=VALUES(base_year),cashflow_start_year=VALUES(cashflow_start_year),analysis_horizon_year=VALUES(analysis_horizon_year),
  reference_capex_metric_id=VALUES(reference_capex_metric_id),reference_rack_capacity_metric_id=VALUES(reference_rack_capacity_metric_id),
  reference_pue_metric_id=VALUES(reference_pue_metric_id),reference_annual_energy_metric_id=VALUES(reference_annual_energy_metric_id),
  reference_historical_capex_yuan=VALUES(reference_historical_capex_yuan),reference_rack_capacity_count=VALUES(reference_rack_capacity_count),reference_pue=VALUES(reference_pue),reference_annual_energy_cap_kwh=VALUES(reference_annual_energy_cap_kwh),
  year1_rack_occupancy_ratio=VALUES(year1_rack_occupancy_ratio),steady_state_rack_occupancy_ratio=VALUES(steady_state_rack_occupancy_ratio),occupancy_ramp_years=VALUES(occupancy_ramp_years),
  rack_price_yuan_month=VALUES(rack_price_yuan_month),rack_price_input_type=VALUES(rack_price_input_type),avg_it_load_kw_per_occupied_rack=VALUES(avg_it_load_kw_per_occupied_rack),it_load_input_type=VALUES(it_load_input_type),
  electricity_price_yuan_kwh=VALUES(electricity_price_yuan_kwh),electricity_price_input_type=VALUES(electricity_price_input_type),other_operating_cost_proxy_ratio=VALUES(other_operating_cost_proxy_ratio),other_cost_input_type=VALUES(other_cost_input_type),discount_rate=VALUES(discount_rate),
  data_quality=VALUES(data_quality),assumption_note=VALUES(assumption_note),updated_at=CURRENT_TIMESTAMP;

INSERT INTO compute_facility_project_cashflow_year_v1 (
  facility_project_scenario_id,cashflow_year_index,calendar_year,modeled_rack_occupancy_ratio,modeled_occupied_rack_count,
  modeled_revenue_yuan,modeled_it_energy_kwh,modeled_total_energy_kwh,reference_annual_energy_cap_kwh,energy_cap_status,
  modeled_electricity_cost_yuan,modeled_other_operating_cost_proxy_yuan,modeled_pre_tax_cashflow_proxy_yuan,
  discount_factor,discounted_cashflow_proxy_yuan,data_type,calculation_formula
)
WITH RECURSIVE y AS (
  SELECT 1 AS year_index
  UNION ALL
  SELECT year_index+1 FROM y
  WHERE year_index < (SELECT MAX(analysis_horizon_year) FROM compute_facility_project_scenario_v1 WHERE scenario_version='BWX_PHASE3_CASHFLOW_V1')
), base AS (
  SELECT s.*,y.year_index,
    CASE WHEN y.year_index>=s.occupancy_ramp_years+1 THEN s.steady_state_rack_occupancy_ratio
         ELSE s.year1_rack_occupancy_ratio
           +(s.steady_state_rack_occupancy_ratio-s.year1_rack_occupancy_ratio)*((y.year_index-1)/s.occupancy_ramp_years) END AS occupancy
  FROM compute_facility_project_scenario_v1 s
  JOIN y ON y.year_index<=s.analysis_horizon_year
  WHERE s.scenario_version='BWX_PHASE3_CASHFLOW_V1'
), calc AS (
  SELECT b.*,
    b.reference_rack_capacity_count*b.occupancy AS occupied_racks,
    b.reference_rack_capacity_count*b.occupancy*b.rack_price_yuan_month*12 AS revenue_yuan,
    b.reference_rack_capacity_count*b.occupancy*b.avg_it_load_kw_per_occupied_rack*8760 AS it_energy_kwh,
    b.reference_rack_capacity_count*b.occupancy*b.avg_it_load_kw_per_occupied_rack*8760*b.reference_pue AS total_energy_kwh
  FROM base b
)
SELECT c.facility_project_scenario_id,c.year_index,c.cashflow_start_year+c.year_index-1,c.occupancy,c.occupied_racks,
  c.revenue_yuan,c.it_energy_kwh,c.total_energy_kwh,c.reference_annual_energy_cap_kwh,
  CASE WHEN c.total_energy_kwh<=c.reference_annual_energy_cap_kwh THEN 'WITHIN_REFERENCE_CAP' ELSE 'EXCEEDS_REFERENCE_CAP' END,
  c.total_energy_kwh*c.electricity_price_yuan_kwh,c.revenue_yuan*c.other_operating_cost_proxy_ratio,
  c.revenue_yuan-c.total_energy_kwh*c.electricity_price_yuan_kwh-c.revenue_yuan*c.other_operating_cost_proxy_ratio,
  1/POW(1+c.discount_rate,c.year_index),
  (c.revenue_yuan-c.total_energy_kwh*c.electricity_price_yuan_kwh-c.revenue_yuan*c.other_operating_cost_proxy_ratio)/POW(1+c.discount_rate,c.year_index),
  'SCENARIO_DERIVED',
  'Revenue=racks×occupancy×rack_price×12; Energy=racks×occupancy×IT_load×8760×PUE; Pre-tax cashflow proxy=revenue−electricity cost−other operating cost proxy. Excludes tax, working capital, debt service and maintenance/replacement CAPEX.'
FROM calc c
ON DUPLICATE KEY UPDATE
  calendar_year=VALUES(calendar_year),modeled_rack_occupancy_ratio=VALUES(modeled_rack_occupancy_ratio),modeled_occupied_rack_count=VALUES(modeled_occupied_rack_count),
  modeled_revenue_yuan=VALUES(modeled_revenue_yuan),modeled_it_energy_kwh=VALUES(modeled_it_energy_kwh),modeled_total_energy_kwh=VALUES(modeled_total_energy_kwh),reference_annual_energy_cap_kwh=VALUES(reference_annual_energy_cap_kwh),energy_cap_status=VALUES(energy_cap_status),
  modeled_electricity_cost_yuan=VALUES(modeled_electricity_cost_yuan),modeled_other_operating_cost_proxy_yuan=VALUES(modeled_other_operating_cost_proxy_yuan),modeled_pre_tax_cashflow_proxy_yuan=VALUES(modeled_pre_tax_cashflow_proxy_yuan),
  discount_factor=VALUES(discount_factor),discounted_cashflow_proxy_yuan=VALUES(discounted_cashflow_proxy_yuan),calculation_formula=VALUES(calculation_formula),computed_at=CURRENT_TIMESTAMP;

INSERT INTO compute_facility_project_cashflow_result_v1 (
  facility_project_scenario_id,reference_historical_capex_yuan,year1_revenue_yuan,year1_pre_tax_cashflow_proxy_yuan,
  steady_state_pre_tax_cashflow_proxy_yuan,total_pre_tax_cashflow_proxy_yuan,pv_pre_tax_cashflow_proxy_yuan,hypothetical_greenfield_npv_proxy_yuan,
  first_energy_cap_breach_year,energy_cap_compliance_status,result_status,data_type,calculation_formula,model_version
)
SELECT s.facility_project_scenario_id,s.reference_historical_capex_yuan,
  MAX(CASE WHEN y.cashflow_year_index=1 THEN y.modeled_revenue_yuan END),
  MAX(CASE WHEN y.cashflow_year_index=1 THEN y.modeled_pre_tax_cashflow_proxy_yuan END),
  MAX(CASE WHEN y.cashflow_year_index=s.analysis_horizon_year THEN y.modeled_pre_tax_cashflow_proxy_yuan END),
  SUM(y.modeled_pre_tax_cashflow_proxy_yuan),SUM(y.discounted_cashflow_proxy_yuan),
  SUM(y.discounted_cashflow_proxy_yuan)-s.reference_historical_capex_yuan,
  MIN(CASE WHEN y.energy_cap_status='EXCEEDS_REFERENCE_CAP' THEN y.calendar_year END),
  CASE WHEN SUM(y.energy_cap_status='EXCEEDS_REFERENCE_CAP')=0 THEN 'WITHIN_REFERENCE_CAP' ELSE 'EXCEEDS_REFERENCE_CAP' END,
  CASE WHEN SUM(y.energy_cap_status='EXCEEDS_REFERENCE_CAP')=0 THEN 'RESEARCH_SCREENING_ONLY' ELSE 'ENERGY_CAP_EVIDENCE_REQUIRED' END,
  'SCENARIO_DERIVED',
  'PV of ten-year pre-tax cashflow proxy minus publicly disclosed historical Phase III CAPEX. This hypothetical greenfield NPV proxy is not the Phase III actual NPV, appraisal, CFADS or a financing conclusion.',
  'BWX_PHASE3_CASHFLOW_V1'
FROM compute_facility_project_scenario_v1 s
JOIN compute_facility_project_cashflow_year_v1 y ON y.facility_project_scenario_id=s.facility_project_scenario_id
WHERE s.scenario_version='BWX_PHASE3_CASHFLOW_V1'
GROUP BY s.facility_project_scenario_id
ON DUPLICATE KEY UPDATE
  reference_historical_capex_yuan=VALUES(reference_historical_capex_yuan),year1_revenue_yuan=VALUES(year1_revenue_yuan),year1_pre_tax_cashflow_proxy_yuan=VALUES(year1_pre_tax_cashflow_proxy_yuan),
  steady_state_pre_tax_cashflow_proxy_yuan=VALUES(steady_state_pre_tax_cashflow_proxy_yuan),total_pre_tax_cashflow_proxy_yuan=VALUES(total_pre_tax_cashflow_proxy_yuan),pv_pre_tax_cashflow_proxy_yuan=VALUES(pv_pre_tax_cashflow_proxy_yuan),hypothetical_greenfield_npv_proxy_yuan=VALUES(hypothetical_greenfield_npv_proxy_yuan),
  first_energy_cap_breach_year=VALUES(first_energy_cap_breach_year),energy_cap_compliance_status=VALUES(energy_cap_compliance_status),result_status=VALUES(result_status),calculation_formula=VALUES(calculation_formula),model_version=VALUES(model_version),computed_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_facility_project_cashflow_summary_v1 AS
SELECT
  f.facility_code,f.official_name,s.facility_project_scenario_id,s.scenario_code,s.scenario_version,s.scenario_name,
  s.project_scope_code,s.project_scope_name,s.base_year,s.cashflow_start_year,s.analysis_horizon_year,
  s.reference_historical_capex_yuan,s.reference_rack_capacity_count,s.reference_pue,s.reference_annual_energy_cap_kwh,
  s.year1_rack_occupancy_ratio,s.steady_state_rack_occupancy_ratio,s.occupancy_ramp_years,
  s.rack_price_yuan_month,s.rack_price_input_type,s.avg_it_load_kw_per_occupied_rack,s.it_load_input_type,
  s.electricity_price_yuan_kwh,s.electricity_price_input_type,s.other_operating_cost_proxy_ratio,s.other_cost_input_type,s.discount_rate,
  r.year1_revenue_yuan,r.year1_pre_tax_cashflow_proxy_yuan,r.steady_state_pre_tax_cashflow_proxy_yuan,
  r.total_pre_tax_cashflow_proxy_yuan,r.pv_pre_tax_cashflow_proxy_yuan,r.hypothetical_greenfield_npv_proxy_yuan,
  r.first_energy_cap_breach_year,r.energy_cap_compliance_status,r.result_status,r.calculation_formula,r.model_version,
  s.data_type,s.data_quality,s.assumption_note,
  capex.source_id AS capex_source_id,capexds.source_title AS capex_source_title,capexds.source_url AS capex_source_url
FROM compute_facility_project_scenario_v1 s
JOIN enterprise_data_center_v2 f ON f.facility_v2_id=s.facility_v2_id
JOIN compute_facility_project_cashflow_result_v1 r ON r.facility_project_scenario_id=s.facility_project_scenario_id
JOIN compute_facility_metric_v1 capex ON capex.facility_metric_id=s.reference_capex_metric_id
JOIN data_source capexds ON capexds.source_id=capex.source_id;
