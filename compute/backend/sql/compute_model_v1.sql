USE spdb_power_finance;

CREATE TABLE IF NOT EXISTS compute_operation_scenario_v1 (
    scenario_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scenario_code VARCHAR(64) NOT NULL,
    scenario_version VARCHAR(32) NOT NULL,
    scenario_name VARCHAR(128) NOT NULL,
    analysis_year SMALLINT UNSIGNED NOT NULL,
    listing_id BIGINT UNSIGNED NOT NULL,
    facility_v2_id BIGINT UNSIGNED NULL,
    utilization_ratio DECIMAL(12,8) NOT NULL,
    utilization_data_type VARCHAR(24) NOT NULL,
    idle_power_ratio DECIMAL(12,8) NOT NULL,
    accelerator_unit_power_kw DECIMAL(18,8) NOT NULL,
    modeled_accelerator_count DECIMAL(12,4) NOT NULL,
    auxiliary_power_ratio DECIMAL(12,8) NOT NULL,
    pue DECIMAL(12,8) NOT NULL,
    pue_data_type VARCHAR(24) NOT NULL,
    electricity_price_yuan_kwh DECIMAL(16,8) NOT NULL,
    electricity_price_data_type VARCHAR(24) NOT NULL,
    price_realization_ratio DECIMAL(12,8) NOT NULL,
    other_opex_revenue_ratio DECIMAL(12,8) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO',
    assumption_note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_operation_scenario
        (scenario_version, analysis_year, listing_id),
    KEY idx_compute_scenario_facility (facility_v2_id),
    KEY idx_compute_scenario_code (scenario_code),
    CONSTRAINT fk_compute_scenario_listing FOREIGN KEY (listing_id)
        REFERENCES compute_platform_resource_listing_v1(listing_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_scenario_facility FOREIGN KEY (facility_v2_id)
        REFERENCES enterprise_data_center_v2(facility_v2_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_compute_scenario_utilization CHECK
        (utilization_ratio >= 0 AND utilization_ratio <= 1),
    CONSTRAINT chk_compute_scenario_idle CHECK
        (idle_power_ratio >= 0 AND idle_power_ratio <= 1),
    CONSTRAINT chk_compute_scenario_pue CHECK (pue >= 1),
    CONSTRAINT chk_compute_scenario_positive CHECK
        (accelerator_unit_power_kw > 0 AND modeled_accelerator_count > 0
         AND electricity_price_yuan_kwh >= 0),
    CONSTRAINT chk_compute_scenario_ratio CHECK
        (price_realization_ratio >= 0 AND price_realization_ratio <= 1
         AND other_opex_revenue_ratio >= 0 AND other_opex_revenue_ratio <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力商品经营情景V1：缺少企业实测值的利用率、功率、PUE和电价均显式标注';

CREATE TABLE IF NOT EXISTS compute_economics_result_v1 (
    economics_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scenario_id BIGINT UNSIGNED NOT NULL,
    selected_price_snapshot_id BIGINT UNSIGNED NOT NULL,
    price_scope VARCHAR(32) NOT NULL,
    billing_cycle VARCHAR(32),
    price_value DECIMAL(24,8) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    annual_billable_hours DECIMAL(18,4) NOT NULL,
    modeled_max_it_power_kw DECIMAL(24,8) NOT NULL,
    modeled_avg_it_power_kw DECIMAL(24,8) NOT NULL,
    annual_it_energy_kwh DECIMAL(28,4) NOT NULL,
    annual_total_energy_kwh DECIMAL(28,4) NOT NULL,
    annual_revenue_yuan DECIMAL(28,4) NOT NULL,
    annual_electricity_cost_yuan DECIMAL(28,4) NOT NULL,
    annual_other_opex_yuan DECIMAL(28,4) NOT NULL,
    annual_operating_cashflow_yuan DECIMAL(28,4) NOT NULL,
    electricity_cost_ratio DECIMAL(12,8),
    operating_cashflow_margin DECIMAL(12,8),
    break_even_utilization_ratio DECIMAL(12,8),
    result_status VARCHAR(24) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    calculation_formula TEXT NOT NULL,
    model_version VARCHAR(32) NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_economics_scenario (scenario_id),
    KEY idx_compute_economics_cashflow (annual_operating_cashflow_yuan),
    KEY idx_compute_economics_status (result_status),
    CONSTRAINT fk_compute_economics_scenario FOREIGN KEY (scenario_id)
        REFERENCES compute_operation_scenario_v1(scenario_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_economics_price FOREIGN KEY (selected_price_snapshot_id)
        REFERENCES compute_product_price_snapshot_v1(price_snapshot_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力商品经济性V1：公开价格与研究情景共同形成的能源成本及经营现金流';

INSERT INTO compute_operation_scenario_v1 (
    scenario_code, scenario_version, scenario_name, analysis_year,
    listing_id, facility_v2_id, utilization_ratio, utilization_data_type,
    idle_power_ratio, accelerator_unit_power_kw, modeled_accelerator_count,
    auxiliary_power_ratio, pue, pue_data_type,
    electricity_price_yuan_kwh, electricity_price_data_type,
    price_realization_ratio, other_opex_revenue_ratio, data_type, assumption_note
)
SELECT
    CONCAT('BASE_2026_', l.external_product_id),
    'COMPUTE_BASE_V1',
    '公开商品经营基准情景',
    2026,
    l.listing_id,
    l.facility_v2_id,
    COALESCE((
        SELECT m.metric_value
        FROM compute_facility_metric_v1 m
        WHERE m.facility_v2_id=l.facility_v2_id
          AND m.metric_code='RESOURCE_UTILIZATION'
          AND m.usable_for_facility_model=1
          AND m.disclosure_status='DISCLOSED'
        ORDER BY m.as_of_date DESC, m.facility_metric_id DESC LIMIT 1
    ), 0.65),
    CASE WHEN EXISTS (
        SELECT 1 FROM compute_facility_metric_v1 m
        WHERE m.facility_v2_id=l.facility_v2_id
          AND m.metric_code='RESOURCE_UTILIZATION'
          AND m.usable_for_facility_model=1
          AND m.disclosure_status='DISCLOSED'
    ) THEN 'PUBLIC' ELSE 'SCENARIO' END,
    0.25,
    CASE
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%B200%' THEN 1.000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H200%' THEN 0.700
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H100%' THEN 0.700
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H800%' THEN 0.700
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%A800%' THEN 0.400
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%A100%' THEN 0.400
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H20%' THEN 0.400
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%5090%' THEN 0.575
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%4090%' THEN 0.450
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%3090%' THEN 0.350
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%V100%' THEN 0.300
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%ASCEND%910%'
          OR COALESCE(l.accelerator_model,l.product_name) LIKE '%昇腾910%' THEN 0.310
        WHEN COALESCE(l.resource_type,'') LIKE '%CPU%' THEN 0.600
        ELSE 0.350
    END,
    COALESCE(l.accelerator_count,
        CASE
            WHEN l.product_name LIKE '%八卡%' OR l.product_name REGEXP '\\* *8' THEN 8
            WHEN l.product_name LIKE '%四卡%' OR l.product_name REGEXP '\\* *4' THEN 4
            WHEN l.product_name LIKE '%两卡%' OR l.product_name REGEXP '\\* *2' THEN 2
            ELSE 1
        END),
    0.20,
    COALESCE((
        SELECT m.metric_value
        FROM compute_facility_metric_v1 m
        WHERE m.facility_v2_id=l.facility_v2_id
          AND m.metric_code='PUE'
          AND m.usable_for_facility_model=1
          AND m.disclosure_status='DISCLOSED'
        ORDER BY m.as_of_date DESC, m.facility_metric_id DESC LIMIT 1
    ), 1.35),
    CASE WHEN EXISTS (
        SELECT 1 FROM compute_facility_metric_v1 m
        WHERE m.facility_v2_id=l.facility_v2_id
          AND m.metric_code='PUE'
          AND m.usable_for_facility_model=1
          AND m.disclosure_status='DISCLOSED'
    ) THEN 'PUBLIC' ELSE 'SCENARIO' END,
    0.85,
    'SCENARIO',
    1.00,
    0.15,
    'SCENARIO',
    '公开商品配置与公开报价为事实；利用率、空闲功耗、设备功率、辅助功耗、电价及其他运维成本为研究基准情景，不代表设施实测或合同数据。'
FROM compute_platform_resource_listing_v1 l
ON DUPLICATE KEY UPDATE
    facility_v2_id=VALUES(facility_v2_id),
    utilization_ratio=VALUES(utilization_ratio),
    utilization_data_type=VALUES(utilization_data_type),
    pue=VALUES(pue),
    pue_data_type=VALUES(pue_data_type),
    assumption_note=VALUES(assumption_note);

INSERT INTO compute_economics_result_v1 (
    scenario_id, selected_price_snapshot_id, price_scope, billing_cycle,
    price_value, currency, annual_billable_hours,
    modeled_max_it_power_kw, modeled_avg_it_power_kw,
    annual_it_energy_kwh, annual_total_energy_kwh,
    annual_revenue_yuan, annual_electricity_cost_yuan,
    annual_other_opex_yuan, annual_operating_cashflow_yuan,
    electricity_cost_ratio, operating_cashflow_margin,
    break_even_utilization_ratio, result_status, data_type,
    calculation_formula, model_version
)
WITH ranked_price AS (
    SELECT p.*,
           ROW_NUMBER() OVER (
               PARTITION BY p.listing_id
               ORDER BY CASE p.price_scope WHEN 'DETAIL_CONFIG' THEN 0 ELSE 1 END,
                        p.captured_at DESC, p.price_snapshot_id DESC
           ) AS rn
    FROM compute_product_price_snapshot_v1 p
    WHERE p.price_scope IN ('DETAIL_CONFIG','LIST_REFERENCE')
      AND p.price_value IS NOT NULL
), base AS (
    SELECT s.*,
           p.price_snapshot_id, p.price_scope, p.billing_cycle,
           p.price_value, p.currency,
           (s.accelerator_unit_power_kw * s.modeled_accelerator_count
              * (1 + s.auxiliary_power_ratio)) AS max_it_power_kw,
           CASE LOWER(COALESCE(p.billing_cycle,'monthly'))
               WHEN 'hourly' THEN p.price_value * 8760
               WHEN 'daily' THEN p.price_value * 365
               WHEN 'yearly' THEN p.price_value
               ELSE p.price_value * 12
           END AS full_utilization_revenue
    FROM compute_operation_scenario_v1 s
    JOIN ranked_price p ON p.listing_id=s.listing_id AND p.rn=1
    WHERE s.scenario_version='COMPUTE_BASE_V1' AND s.analysis_year=2026
), calc AS (
    SELECT b.*,
           8760 * b.utilization_ratio AS annual_billable_hours_calc,
           b.max_it_power_kw * (b.idle_power_ratio
             + (1-b.idle_power_ratio)*b.utilization_ratio) AS avg_it_power_kw,
           b.full_utilization_revenue * b.utilization_ratio
             * b.price_realization_ratio AS revenue_yuan,
           b.max_it_power_kw * 8760 * b.pue * b.electricity_price_yuan_kwh
             * (b.idle_power_ratio + (1-b.idle_power_ratio)*b.utilization_ratio)
             AS electricity_cost_yuan,
           b.full_utilization_revenue * b.utilization_ratio
             * b.price_realization_ratio * b.other_opex_revenue_ratio
             AS other_opex_yuan,
           b.full_utilization_revenue * b.price_realization_ratio
             * (1-b.other_opex_revenue_ratio)
             - b.max_it_power_kw * 8760 * b.pue * b.electricity_price_yuan_kwh
               * (1-b.idle_power_ratio) AS break_even_denominator,
           b.max_it_power_kw * 8760 * b.pue * b.electricity_price_yuan_kwh
             * b.idle_power_ratio AS idle_energy_cost_yuan
    FROM base b
)
SELECT
    c.scenario_id, c.price_snapshot_id, c.price_scope, c.billing_cycle,
    c.price_value, c.currency, c.annual_billable_hours_calc,
    c.max_it_power_kw, c.avg_it_power_kw,
    c.avg_it_power_kw * 8760,
    c.avg_it_power_kw * 8760 * c.pue,
    c.revenue_yuan, c.electricity_cost_yuan, c.other_opex_yuan,
    c.revenue_yuan-c.electricity_cost_yuan-c.other_opex_yuan,
    CASE WHEN c.revenue_yuan=0 THEN NULL
         ELSE c.electricity_cost_yuan/c.revenue_yuan END,
    CASE WHEN c.revenue_yuan=0 THEN NULL
         ELSE (c.revenue_yuan-c.electricity_cost_yuan-c.other_opex_yuan)/c.revenue_yuan END,
    CASE WHEN c.break_even_denominator<=0 THEN NULL
         ELSE LEAST(1, c.idle_energy_cost_yuan/c.break_even_denominator) END,
    CASE WHEN c.revenue_yuan-c.electricity_cost_yuan-c.other_opex_yuan>0
         THEN 'POSITIVE' ELSE 'NEGATIVE' END,
    'SCENARIO_DERIVED',
    'Revenue=public_price×annual_cycle_factor×utilization×realization; AvgITPower=MaxITPower×[idle+(1-idle)×utilization]; TotalEnergy=AvgITPower×8760×PUE; ElectricityCost=TotalEnergy×electricity_price; OperatingCashflow=Revenue-ElectricityCost-OtherOpex。',
    'COMPUTE_ECONOMICS_V1'
FROM calc c
ON DUPLICATE KEY UPDATE
    selected_price_snapshot_id=VALUES(selected_price_snapshot_id),
    price_scope=VALUES(price_scope),
    billing_cycle=VALUES(billing_cycle),
    price_value=VALUES(price_value),
    annual_billable_hours=VALUES(annual_billable_hours),
    modeled_max_it_power_kw=VALUES(modeled_max_it_power_kw),
    modeled_avg_it_power_kw=VALUES(modeled_avg_it_power_kw),
    annual_it_energy_kwh=VALUES(annual_it_energy_kwh),
    annual_total_energy_kwh=VALUES(annual_total_energy_kwh),
    annual_revenue_yuan=VALUES(annual_revenue_yuan),
    annual_electricity_cost_yuan=VALUES(annual_electricity_cost_yuan),
    annual_other_opex_yuan=VALUES(annual_other_opex_yuan),
    annual_operating_cashflow_yuan=VALUES(annual_operating_cashflow_yuan),
    electricity_cost_ratio=VALUES(electricity_cost_ratio),
    operating_cashflow_margin=VALUES(operating_cashflow_margin),
    break_even_utilization_ratio=VALUES(break_even_utilization_ratio),
    result_status=VALUES(result_status),
    calculation_formula=VALUES(calculation_formula),
    model_version=VALUES(model_version),
    computed_at=CURRENT_TIMESTAMP;
