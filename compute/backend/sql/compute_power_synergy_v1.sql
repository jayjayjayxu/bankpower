USE spdb_power_finance;

/*
  算电协同 V1：百旺信云数据中心三期（深圳）

  Purpose
  -------
  Reuse the electricity-side reference data without writing back to the power
  model.  This module answers a narrow, auditable question:

    If the publicly disclosed Phase III base-case electricity volume were
    exposed to Shenzhen's latest matching large-commercial ToU price window,
    what would the directional electricity-cost and operating-cashflow effect
    be?  How large are a green-power procurement and a storage-shift overlay?

  Crucial boundaries
  ------------------
  - Phase III has no public 24-hour load curve, green-power settlement bill,
    storage asset, grid-connection limit, VPP registration, demand-response
    test or settlement record.  All ToU allocation, 20% green purchase and
    2% storage shift inputs below are explicit SCENARIO inputs.
  - Shenzhen's disclosed >=80% local clean-power capacity is a regional supply
    signal, NOT this facility's green-power consumption ratio.
  - Guangdong's 2025 generation mix is a provincial electricity-source proxy,
    NOT a marginal-emissions calculation or a facility carbon footprint.
  - Demand-response revenue is deliberately 0 until a contract, capability
    test and settlement evidence are available.
  - Results are an operating-cost overlay on the existing Phase III base-case
    pre-tax cashflow proxy. They are not actual bills, CFADS, NPV, IRR,
    valuation, investment advice or a credit decision.
*/

CREATE TABLE IF NOT EXISTS compute_power_synergy_scenario_v1 (
    power_synergy_scenario_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scenario_code VARCHAR(72) NOT NULL,
    scenario_name VARCHAR(128) NOT NULL,
    scenario_version VARCHAR(40) NOT NULL,

    facility_v2_id BIGINT UNSIGNED NOT NULL,
    facility_project_scenario_id BIGINT UNSIGNED NOT NULL,
    region_id SMALLINT UNSIGNED NOT NULL,
    project_scope_code VARCHAR(96) NOT NULL,
    project_scope_name VARCHAR(255) NOT NULL,

    reference_year SMALLINT UNSIGNED NOT NULL,
    reference_energy_kwh DECIMAL(28,4) NOT NULL,
    reference_bill_price_yuan_kwh DECIMAL(16,8) NOT NULL,
    reference_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,

    tariff_mode VARCHAR(40) NOT NULL COMMENT 'HISTORICAL_BILL/REGIONAL_TOU_SCENARIO',
    tariff_context_year SMALLINT UNSIGNED NULL,
    tariff_context_month TINYINT UNSIGNED NULL,
    tariff_customer_type VARCHAR(96) NULL,
    tariff_voltage_level VARCHAR(64) NULL,
    tariff_data_type VARCHAR(96) NOT NULL,

    regional_clean_structure_v2_id BIGINT UNSIGNED NOT NULL,
    regional_fossil_structure_v2_id BIGINT UNSIGNED NOT NULL,
    regional_clean_reference_ratio DECIMAL(12,8) NOT NULL,
    regional_fossil_generation_share_ratio DECIMAL(12,8) NOT NULL,
    regional_structure_note TEXT NOT NULL,

    green_power_purchase_ratio DECIMAL(12,8) NOT NULL DEFAULT 0,
    green_power_premium_yuan_kwh DECIMAL(16,8) NOT NULL DEFAULT 0,
    green_power_status VARCHAR(48) NOT NULL,

    storage_shift_ratio DECIMAL(12,8) NOT NULL DEFAULT 0,
    storage_duration_hour DECIMAL(10,4) NOT NULL DEFAULT 0,
    storage_usable_soc_window_ratio DECIMAL(12,8) NOT NULL DEFAULT 0.8,
    storage_cost_curve_id BIGINT UNSIGNED NULL,
    storage_parameter_id BIGINT UNSIGNED NULL,
    storage_status VARCHAR(48) NOT NULL,

    demand_response_target_ratio DECIMAL(12,8) NOT NULL DEFAULT 0.05,
    demand_response_revenue_yuan DECIMAL(28,4) NOT NULL DEFAULT 0,
    demand_response_status VARCHAR(96) NOT NULL,

    data_type VARCHAR(32) NOT NULL DEFAULT 'MIXED_PUBLIC_SCENARIO',
    data_quality VARCHAR(48) NOT NULL DEFAULT 'PUBLIC_ANCHORED_SCENARIO',
    assumption_note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_power_synergy_scenario (scenario_code),
    KEY idx_compute_power_synergy_facility (facility_v2_id, scenario_version),
    KEY idx_compute_power_synergy_region (region_id, reference_year),
    CONSTRAINT fk_compute_power_synergy_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_project_scenario
      FOREIGN KEY (facility_project_scenario_id) REFERENCES compute_facility_project_scenario_v1(facility_project_scenario_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_region
      FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_clean_structure
      FOREIGN KEY (regional_clean_structure_v2_id) REFERENCES power_source_structure_v2(structure_v2_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_fossil_structure
      FOREIGN KEY (regional_fossil_structure_v2_id) REFERENCES power_source_structure_v2(structure_v2_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_storage_curve
      FOREIGN KEY (storage_cost_curve_id) REFERENCES storage_cost_curve_v2(curve_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_storage_parameter
      FOREIGN KEY (storage_parameter_id) REFERENCES storage_system_parameter_v2(parameter_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_power_synergy_ratios CHECK (
      reference_energy_kwh > 0 AND reference_bill_price_yuan_kwh >= 0
      AND regional_clean_reference_ratio >= 0 AND regional_clean_reference_ratio <= 1
      AND regional_fossil_generation_share_ratio >= 0 AND regional_fossil_generation_share_ratio <= 1
      AND green_power_purchase_ratio >= 0 AND green_power_purchase_ratio <= 1
      AND storage_shift_ratio >= 0 AND storage_shift_ratio <= 1
      AND demand_response_target_ratio >= 0 AND demand_response_target_ratio <= 1
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算电协同研究情景：区域电价/电源信号与设施项目现金流代理的显式映射';

/* Allow safe re-runs after an early deployment created the shorter column. */
ALTER TABLE compute_power_synergy_scenario_v1
  MODIFY COLUMN demand_response_status VARCHAR(96) NOT NULL,
  MODIFY COLUMN tariff_data_type VARCHAR(96) NOT NULL;

CREATE TABLE IF NOT EXISTS compute_power_synergy_tariff_segment_v1 (
    power_synergy_tariff_segment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    power_synergy_scenario_id BIGINT UNSIGNED NOT NULL,
    tariff_id BIGINT UNSIGNED NOT NULL,
    load_allocation_ratio DECIMAL(12,8) NOT NULL,
    allocation_basis VARCHAR(96) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_power_synergy_tariff_segment (power_synergy_scenario_id, tariff_id),
    KEY idx_compute_power_synergy_tariff (tariff_id),
    CONSTRAINT fk_compute_power_synergy_segment_scenario
      FOREIGN KEY (power_synergy_scenario_id) REFERENCES compute_power_synergy_scenario_v1(power_synergy_scenario_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_power_synergy_segment_tariff
      FOREIGN KEY (tariff_id) REFERENCES electricity_tariff(tariff_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_power_synergy_tariff_allocation CHECK
      (load_allocation_ratio >= 0 AND load_allocation_ratio <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算电协同情景采用的分时电价及研究性负荷分配；非设施实测曲线';

CREATE TABLE IF NOT EXISTS compute_power_synergy_result_v1 (
    power_synergy_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    power_synergy_scenario_id BIGINT UNSIGNED NOT NULL,

    reference_historical_bill_cost_yuan DECIMAL(28,4) NOT NULL,
    weighted_tou_price_yuan_kwh DECIMAL(16,8) NULL,
    modeled_tou_electricity_cost_yuan DECIMAL(28,4) NOT NULL,
    green_power_premium_cost_yuan DECIMAL(28,4) NOT NULL,

    annual_storage_discharge_kwh DECIMAL(28,4) NOT NULL,
    required_storage_power_kw DECIMAL(24,4) NOT NULL,
    required_storage_capacity_kwh DECIMAL(28,4) NOT NULL,
    storage_gross_arbitrage_yuan DECIMAL(28,4) NOT NULL,
    storage_annual_opex_yuan DECIMAL(28,4) NOT NULL,
    storage_capex_proxy_yuan DECIMAL(28,4) NOT NULL,

    demand_response_target_capacity_kw_proxy DECIMAL(24,4) NOT NULL,
    demand_response_revenue_yuan DECIMAL(28,4) NOT NULL,

    modeled_total_electricity_cost_yuan DECIMAL(28,4) NOT NULL,
    electricity_cost_change_from_reference_yuan DECIMAL(28,4) NOT NULL,
    reference_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    modeled_pre_tax_cashflow_proxy_yuan DECIMAL(28,4) NOT NULL,
    cashflow_change_from_reference_yuan DECIMAL(28,4) NOT NULL,

    result_status VARCHAR(48) NOT NULL,
    data_type VARCHAR(32) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    calculation_formula TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_power_synergy_result (power_synergy_scenario_id),
    KEY idx_compute_power_synergy_result_status (result_status),
    CONSTRAINT fk_compute_power_synergy_result_scenario
      FOREIGN KEY (power_synergy_scenario_id) REFERENCES compute_power_synergy_scenario_v1(power_synergy_scenario_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算电协同成本及现金流影响代理；不替代实测账单或项目CFADS';

/*
  One facility-specific, public-anchored set of scenarios.
  - electricity volume and historical bill price come from BWX Phase III base
    case (which is itself a transparent project proxy);
  - tariff rows 19109-19112 are the latest matching Shenzhen 10kV / >=3001kVA
    first-tier rows available in this database (July 2026);
  - green premium of 0.01 yuan/kWh is a research proxy only: it is the
    disclosed 0.58 vs 0.57 historical-building price difference, which is
    described as including green-power/environmental premium, not a standalone
    green-power quotation.
*/
INSERT INTO compute_power_synergy_scenario_v1 (
  scenario_code,scenario_name,scenario_version,
  facility_v2_id,facility_project_scenario_id,region_id,project_scope_code,project_scope_name,
  reference_year,reference_energy_kwh,reference_bill_price_yuan_kwh,reference_pre_tax_cashflow_proxy_yuan,
  tariff_mode,tariff_context_year,tariff_context_month,tariff_customer_type,tariff_voltage_level,tariff_data_type,
  regional_clean_structure_v2_id,regional_fossil_structure_v2_id,regional_clean_reference_ratio,regional_fossil_generation_share_ratio,regional_structure_note,
  green_power_purchase_ratio,green_power_premium_yuan_kwh,green_power_status,
  storage_shift_ratio,storage_duration_hour,storage_usable_soc_window_ratio,storage_cost_curve_id,storage_parameter_id,storage_status,
  demand_response_target_ratio,demand_response_revenue_yuan,demand_response_status,
  data_type,data_quality,assumption_note
)
SELECT
  cfg.scenario_code,cfg.scenario_name,'COMPUTE_POWER_SYNERGY_V1',
  f.facility_v2_id,ps.facility_project_scenario_id,f.region_id,'PHASE_III_EXCHANGE_DISCLOSURE','百旺信云数据中心三期',
  y.calendar_year,y.modeled_total_energy_kwh,ps.electricity_price_yuan_kwh,y.modeled_pre_tax_cashflow_proxy_yuan,
  cfg.tariff_mode,
  CASE WHEN cfg.tariff_mode='REGIONAL_TOU_SCENARIO' THEN 2026 ELSE NULL END,
  CASE WHEN cfg.tariff_mode='REGIONAL_TOU_SCENARIO' THEN 7 ELSE NULL END,
  CASE WHEN cfg.tariff_mode='REGIONAL_TOU_SCENARIO' THEN '工商业-3001kVA及以上-一档' ELSE NULL END,
  CASE WHEN cfg.tariff_mode='REGIONAL_TOU_SCENARIO' THEN '10千伏' ELSE NULL END,
  CASE WHEN cfg.tariff_mode='REGIONAL_TOU_SCENARIO' THEN 'PUBLIC_TARIFF_PLUS_SCENARIO_ALLOCATION' ELSE 'PUBLIC_HISTORICAL_BILL_PROXY' END,
  clean.structure_v2_id,fossil.structure_v2_id,clean.share_ratio,fossil.share_ratio,
  '深圳本地清洁电源装机“超80%”仅为本地供给结构信号；广东2025规上发电火电占比仅为区域发电结构代理。两者均不等于百旺信三期绿电采购比例、用电来源或碳排放因子。',
  cfg.green_ratio,cfg.green_premium,cfg.green_status,
  cfg.storage_shift_ratio,cfg.storage_duration_hour,0.80000000,
  CASE WHEN cfg.storage_shift_ratio>0 THEN curve.curve_id ELSE NULL END,
  CASE WHEN cfg.storage_shift_ratio>0 THEN param.parameter_id ELSE NULL END,
  cfg.storage_status,
  0.05000000,0,'PENDING_NO_PUBLIC_REGISTRATION_TEST_OR_SETTLEMENT',
  'MIXED_PUBLIC_SCENARIO','PUBLIC_ANCHORED_SCENARIO',cfg.assumption_note
FROM (
  SELECT 'BWX_PHASE3_HISTORICAL_BILL_V1' scenario_code,'历史结算电价参考' scenario_name,
         'HISTORICAL_BILL' tariff_mode,0 green_ratio,0 green_premium,'NO_PUBLIC_GREEN_CONTRACT' green_status,
         0 storage_shift_ratio,0 storage_duration_hour,'NO_STORAGE_ASSET_DISCLOSED' storage_status,
         '以百旺信公开历史账单代理电价0.57元/kWh作为既有三期基准情景的电力成本输入；仅作对照，并非三期实际分时结算单。' assumption_note
  UNION ALL SELECT 'BWX_PHASE3_TOU_GRID_V1','深圳分时电价暴露情景',
         'REGIONAL_TOU_SCENARIO',0,0,'NO_PUBLIC_GREEN_CONTRACT',0,0,'NO_STORAGE_ASSET_DISCLOSED',
         '按数据库内最新可匹配的深圳2026年7月10kV、3001kVA及以上一档代理购电分时电价分配。因无三期小时负荷曲线，负荷按高温季典型日时长及全年3/12比例研究性分配：谷33.33%、平29.17%、峰34.38%、尖峰3.125%。'
  UNION ALL SELECT 'BWX_PHASE3_TOU_GREEN20_V1','分时电价 + 20%绿电采购情景',
         'REGIONAL_TOU_SCENARIO',0.20,0.01,'SCENARIO_NO_PUBLIC_CONTRACT',0,0,'NO_STORAGE_ASSET_DISCLOSED',
         '在分时电价情景上，假设20%电量取得绿电/环境属性，附加0.01元/kWh研究性溢价。0.01元来自百旺信1栋与4栋2025H1账单代理电价差，原披露包含绿电及环境溢价，不能解释为独立绿电报价。'
  UNION ALL SELECT 'BWX_PHASE3_TOU_GREEN_STORAGE2_V1','分时电价 + 20%绿电 + 2%储能移峰情景',
         'REGIONAL_TOU_SCENARIO',0.20,0.01,'SCENARIO_NO_PUBLIC_CONTRACT',0.02,2,'ENGINEERING_AND_GRID_CONNECTION_PENDING',
         '在绿电情景上，假设2%年总电量经2小时LFP储能从峰/尖峰转至谷段，按储能V2研究参数估算成本与运维。容量、接入、消防、备用电源、负荷可中断性及真实调度均未核验；仅展示方向性现金流影响。'
) cfg
JOIN enterprise_data_center_v2 f ON f.facility_code='SZCF016'
JOIN compute_facility_project_scenario_v1 ps ON ps.scenario_code='BWX_PHASE3_BASE_V1'
JOIN compute_facility_project_cashflow_year_v1 y
  ON y.facility_project_scenario_id=ps.facility_project_scenario_id AND y.cashflow_year_index=1
JOIN power_source_structure_v2 clean ON clean.structure_v2_id=301
JOIN power_source_structure_v2 fossil ON fossil.structure_v2_id=239
LEFT JOIN storage_cost_curve_v2 curve
  ON cfg.storage_shift_ratio>0 AND curve.curve_id=9
LEFT JOIN storage_system_parameter_v2 param
  ON cfg.storage_shift_ratio>0 AND param.parameter_version='STORAGE_V2'
ON DUPLICATE KEY UPDATE
  scenario_name=VALUES(scenario_name),facility_v2_id=VALUES(facility_v2_id),facility_project_scenario_id=VALUES(facility_project_scenario_id),region_id=VALUES(region_id),
  reference_year=VALUES(reference_year),reference_energy_kwh=VALUES(reference_energy_kwh),reference_bill_price_yuan_kwh=VALUES(reference_bill_price_yuan_kwh),reference_pre_tax_cashflow_proxy_yuan=VALUES(reference_pre_tax_cashflow_proxy_yuan),
  tariff_mode=VALUES(tariff_mode),tariff_context_year=VALUES(tariff_context_year),tariff_context_month=VALUES(tariff_context_month),tariff_customer_type=VALUES(tariff_customer_type),tariff_voltage_level=VALUES(tariff_voltage_level),tariff_data_type=VALUES(tariff_data_type),
  regional_clean_structure_v2_id=VALUES(regional_clean_structure_v2_id),regional_fossil_structure_v2_id=VALUES(regional_fossil_structure_v2_id),regional_clean_reference_ratio=VALUES(regional_clean_reference_ratio),regional_fossil_generation_share_ratio=VALUES(regional_fossil_generation_share_ratio),regional_structure_note=VALUES(regional_structure_note),
  green_power_purchase_ratio=VALUES(green_power_purchase_ratio),green_power_premium_yuan_kwh=VALUES(green_power_premium_yuan_kwh),green_power_status=VALUES(green_power_status),
  storage_shift_ratio=VALUES(storage_shift_ratio),storage_duration_hour=VALUES(storage_duration_hour),storage_usable_soc_window_ratio=VALUES(storage_usable_soc_window_ratio),storage_cost_curve_id=VALUES(storage_cost_curve_id),storage_parameter_id=VALUES(storage_parameter_id),storage_status=VALUES(storage_status),
  demand_response_target_ratio=VALUES(demand_response_target_ratio),demand_response_revenue_yuan=VALUES(demand_response_revenue_yuan),demand_response_status=VALUES(demand_response_status),
  data_type=VALUES(data_type),data_quality=VALUES(data_quality),assumption_note=VALUES(assumption_note),updated_at=CURRENT_TIMESTAMP;

INSERT INTO compute_power_synergy_tariff_segment_v1 (
  power_synergy_scenario_id,tariff_id,load_allocation_ratio,allocation_basis
)
SELECT s.power_synergy_scenario_id,cfg.tariff_id,cfg.load_allocation_ratio,
       'PUBLIC_TARIFF_2026_07 + SCENARIO_24H_BASELOAD_ALLOCATION'
FROM compute_power_synergy_scenario_v1 s
JOIN (
  SELECT 19109 tariff_id,0.03125000 load_allocation_ratio
  UNION ALL SELECT 19110,0.34375000
  UNION ALL SELECT 19111,0.29166667
  UNION ALL SELECT 19112,0.33333333
) cfg
WHERE s.scenario_version='COMPUTE_POWER_SYNERGY_V1'
  AND s.tariff_mode='REGIONAL_TOU_SCENARIO'
ON DUPLICATE KEY UPDATE
  load_allocation_ratio=VALUES(load_allocation_ratio),allocation_basis=VALUES(allocation_basis);

INSERT INTO compute_power_synergy_result_v1 (
  power_synergy_scenario_id,
  reference_historical_bill_cost_yuan,weighted_tou_price_yuan_kwh,modeled_tou_electricity_cost_yuan,green_power_premium_cost_yuan,
  annual_storage_discharge_kwh,required_storage_power_kw,required_storage_capacity_kwh,storage_gross_arbitrage_yuan,storage_annual_opex_yuan,storage_capex_proxy_yuan,
  demand_response_target_capacity_kw_proxy,demand_response_revenue_yuan,
  modeled_total_electricity_cost_yuan,electricity_cost_change_from_reference_yuan,
  reference_pre_tax_cashflow_proxy_yuan,modeled_pre_tax_cashflow_proxy_yuan,cashflow_change_from_reference_yuan,
  result_status,data_type,calculation_formula
)
WITH tariff AS (
  SELECT s.power_synergy_scenario_id,
    SUM(seg.load_allocation_ratio*t.final_price_yuan_kwh) AS weighted_tou_price_yuan_kwh,
    SUM(CASE WHEN t.time_period IN ('高峰','尖峰') THEN seg.load_allocation_ratio*t.final_price_yuan_kwh ELSE 0 END)
      / NULLIF(SUM(CASE WHEN t.time_period IN ('高峰','尖峰') THEN seg.load_allocation_ratio ELSE 0 END),0) AS peak_critical_price_yuan_kwh,
    MAX(CASE WHEN t.time_period='低谷' THEN t.final_price_yuan_kwh END) AS valley_price_yuan_kwh
  FROM compute_power_synergy_scenario_v1 s
  JOIN compute_power_synergy_tariff_segment_v1 seg ON seg.power_synergy_scenario_id=s.power_synergy_scenario_id
  JOIN electricity_tariff t ON t.tariff_id=seg.tariff_id
  GROUP BY s.power_synergy_scenario_id
), calc AS (
  SELECT s.*,tariff.weighted_tou_price_yuan_kwh,tariff.peak_critical_price_yuan_kwh,tariff.valley_price_yuan_kwh,
    CASE WHEN s.tariff_mode='REGIONAL_TOU_SCENARIO' THEN s.reference_energy_kwh*tariff.weighted_tou_price_yuan_kwh
         ELSE s.reference_energy_kwh*s.reference_bill_price_yuan_kwh END AS tou_cost_yuan,
    s.reference_energy_kwh*s.green_power_purchase_ratio*s.green_power_premium_yuan_kwh AS green_premium_cost_yuan,
    s.reference_energy_kwh*s.storage_shift_ratio AS storage_discharge_kwh,
    CASE WHEN s.storage_shift_ratio>0 THEN s.reference_energy_kwh*s.storage_shift_ratio/365/s.storage_duration_hour ELSE 0 END AS storage_power_kw,
    CASE WHEN s.storage_shift_ratio>0 THEN s.reference_energy_kwh*s.storage_shift_ratio/365/s.storage_usable_soc_window_ratio ELSE 0 END AS storage_capacity_kwh,
    s.reference_rack_capacity_countable_proxy AS demand_response_design_kw_proxy,
    param.charge_efficiency,param.discharge_efficiency,param.fixed_opex_yuan_kw_year,param.variable_opex_yuan_kwh,
    curve.battery_cost_yuan_kwh,curve.pcs_cost_yuan_kw,curve.fixed_cost_wanyuan,curve.grid_connection_cost_wanyuan,curve.construction_cost_ratio
  FROM (
    SELECT s.*,ps.reference_rack_capacity_count*4*ps.reference_pue AS reference_rack_capacity_countable_proxy
    FROM compute_power_synergy_scenario_v1 s
    JOIN compute_facility_project_scenario_v1 ps ON ps.facility_project_scenario_id=s.facility_project_scenario_id
  ) s
  LEFT JOIN tariff ON tariff.power_synergy_scenario_id=s.power_synergy_scenario_id
  LEFT JOIN storage_system_parameter_v2 param ON param.parameter_id=s.storage_parameter_id
  LEFT JOIN storage_cost_curve_v2 curve ON curve.curve_id=s.storage_cost_curve_id
), result AS (
  SELECT c.*,
    CASE WHEN c.storage_discharge_kwh>0
      THEN c.storage_discharge_kwh*(c.peak_critical_price_yuan_kwh-c.valley_price_yuan_kwh/(c.charge_efficiency*c.discharge_efficiency))
      ELSE 0 END AS storage_gross_arbitrage_yuan,
    CASE WHEN c.storage_discharge_kwh>0
      THEN c.storage_power_kw*c.fixed_opex_yuan_kw_year+c.storage_discharge_kwh*c.variable_opex_yuan_kwh
      ELSE 0 END AS storage_annual_opex_yuan,
    CASE WHEN c.storage_capacity_kwh>0
      THEN (c.storage_capacity_kwh*c.battery_cost_yuan_kwh+c.storage_power_kw*c.pcs_cost_yuan_kw
           +c.fixed_cost_wanyuan*10000+c.grid_connection_cost_wanyuan*10000)*(1+c.construction_cost_ratio)
      ELSE 0 END AS storage_capex_proxy_yuan
  FROM calc c
)
SELECT r.power_synergy_scenario_id,
  r.reference_energy_kwh*r.reference_bill_price_yuan_kwh,r.weighted_tou_price_yuan_kwh,r.tou_cost_yuan,r.green_premium_cost_yuan,
  r.storage_discharge_kwh,r.storage_power_kw,r.storage_capacity_kwh,r.storage_gross_arbitrage_yuan,r.storage_annual_opex_yuan,r.storage_capex_proxy_yuan,
  r.demand_response_design_kw_proxy*r.demand_response_target_ratio,r.demand_response_revenue_yuan,
  r.tou_cost_yuan+r.green_premium_cost_yuan-r.storage_gross_arbitrage_yuan,
  r.reference_energy_kwh*r.reference_bill_price_yuan_kwh-(r.tou_cost_yuan+r.green_premium_cost_yuan-r.storage_gross_arbitrage_yuan),
  r.reference_pre_tax_cashflow_proxy_yuan,
  r.reference_pre_tax_cashflow_proxy_yuan+(r.reference_energy_kwh*r.reference_bill_price_yuan_kwh-(r.tou_cost_yuan+r.green_premium_cost_yuan-r.storage_gross_arbitrage_yuan))-r.storage_annual_opex_yuan+r.demand_response_revenue_yuan,
  (r.reference_energy_kwh*r.reference_bill_price_yuan_kwh-(r.tou_cost_yuan+r.green_premium_cost_yuan-r.storage_gross_arbitrage_yuan))-r.storage_annual_opex_yuan+r.demand_response_revenue_yuan,
  CASE WHEN r.storage_shift_ratio>0 THEN 'ENGINEERING_PENDING'
       WHEN r.green_power_purchase_ratio>0 THEN 'GREEN_CONTRACT_PENDING'
       WHEN r.tariff_mode='REGIONAL_TOU_SCENARIO' THEN 'TARIFF_RISK_SCENARIO'
       ELSE 'REFERENCE_HISTORICAL_BILL' END,
  'SCENARIO_DERIVED',
  'Reference bill cost=annual energy×historical bill proxy; ToU cost=annual energy×Σ(segment load share×published tariff); green premium=annual energy×scenario green ratio×scenario premium; storage gross arbitrage=discharged energy×(peak/critical weighted price−valley price/(charge efficiency×discharge efficiency)); storage OPEX=fixed OPEX×required power+variable OPEX×discharged energy; cashflow overlay=reference cashflow+(reference bill cost−modeled electricity cost)−storage OPEX+demand-response revenue. Storage CAPEX is shown separately and is not deducted from annual cashflow.'
FROM result r
ON DUPLICATE KEY UPDATE
  reference_historical_bill_cost_yuan=VALUES(reference_historical_bill_cost_yuan),weighted_tou_price_yuan_kwh=VALUES(weighted_tou_price_yuan_kwh),modeled_tou_electricity_cost_yuan=VALUES(modeled_tou_electricity_cost_yuan),green_power_premium_cost_yuan=VALUES(green_power_premium_cost_yuan),
  annual_storage_discharge_kwh=VALUES(annual_storage_discharge_kwh),required_storage_power_kw=VALUES(required_storage_power_kw),required_storage_capacity_kwh=VALUES(required_storage_capacity_kwh),storage_gross_arbitrage_yuan=VALUES(storage_gross_arbitrage_yuan),storage_annual_opex_yuan=VALUES(storage_annual_opex_yuan),storage_capex_proxy_yuan=VALUES(storage_capex_proxy_yuan),
  demand_response_target_capacity_kw_proxy=VALUES(demand_response_target_capacity_kw_proxy),demand_response_revenue_yuan=VALUES(demand_response_revenue_yuan),
  modeled_total_electricity_cost_yuan=VALUES(modeled_total_electricity_cost_yuan),electricity_cost_change_from_reference_yuan=VALUES(electricity_cost_change_from_reference_yuan),reference_pre_tax_cashflow_proxy_yuan=VALUES(reference_pre_tax_cashflow_proxy_yuan),modeled_pre_tax_cashflow_proxy_yuan=VALUES(modeled_pre_tax_cashflow_proxy_yuan),cashflow_change_from_reference_yuan=VALUES(cashflow_change_from_reference_yuan),result_status=VALUES(result_status),calculation_formula=VALUES(calculation_formula),computed_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_power_synergy_summary_v1 AS
SELECT
  s.power_synergy_scenario_id,s.scenario_code,s.scenario_name,s.scenario_version,
  f.facility_code,f.official_name,s.project_scope_code,s.project_scope_name,
  rgn.region_code,rgn.region_name,
  s.reference_year,s.reference_energy_kwh,s.reference_bill_price_yuan_kwh,
  s.tariff_mode,s.tariff_context_year,s.tariff_context_month,s.tariff_customer_type,s.tariff_voltage_level,s.tariff_data_type,
  s.regional_clean_reference_ratio,s.regional_fossil_generation_share_ratio,s.regional_structure_note,
  s.green_power_purchase_ratio,s.green_power_premium_yuan_kwh,s.green_power_status,
  s.storage_shift_ratio,s.storage_duration_hour,s.storage_status,
  s.demand_response_target_ratio,s.demand_response_status,
  clean.energy_type_name AS clean_structure_name,clean.stat_year AS clean_structure_year,clean.metric_basis AS clean_structure_basis,clean.source_id AS clean_structure_source_id,
  fossil.energy_type_name AS fossil_structure_name,fossil.stat_year AS fossil_structure_year,fossil.metric_basis AS fossil_structure_basis,fossil.source_id AS fossil_structure_source_id,
  r.reference_historical_bill_cost_yuan,r.weighted_tou_price_yuan_kwh,r.modeled_tou_electricity_cost_yuan,r.green_power_premium_cost_yuan,
  r.annual_storage_discharge_kwh,r.required_storage_power_kw,r.required_storage_capacity_kwh,r.storage_gross_arbitrage_yuan,r.storage_annual_opex_yuan,r.storage_capex_proxy_yuan,
  r.demand_response_target_capacity_kw_proxy,r.demand_response_revenue_yuan,
  r.modeled_total_electricity_cost_yuan,r.electricity_cost_change_from_reference_yuan,
  r.reference_pre_tax_cashflow_proxy_yuan,r.modeled_pre_tax_cashflow_proxy_yuan,r.cashflow_change_from_reference_yuan,
  r.result_status,r.data_type,r.calculation_formula,s.assumption_note
FROM compute_power_synergy_scenario_v1 s
JOIN enterprise_data_center_v2 f ON f.facility_v2_id=s.facility_v2_id
JOIN dim_region rgn ON rgn.region_id=s.region_id
JOIN power_source_structure_v2 clean ON clean.structure_v2_id=s.regional_clean_structure_v2_id
JOIN power_source_structure_v2 fossil ON fossil.structure_v2_id=s.regional_fossil_structure_v2_id
JOIN compute_power_synergy_result_v1 r ON r.power_synergy_scenario_id=s.power_synergy_scenario_id;
