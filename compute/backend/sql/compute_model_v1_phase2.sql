USE spdb_power_finance;

/*
  算力模型V1第二阶段。
  本脚本只写入 scenario/result 表，不修改任何公开事实表。
  所有CAPEX、利用率、电价、PUE、成本和融资参数均为研究情景。
*/

CREATE TABLE IF NOT EXISTS compute_capex_parameter_v1 (
    capex_parameter_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    listing_id BIGINT UNSIGNED NOT NULL,
    capex_scenario_version VARCHAR(40) NOT NULL,
    capex_scenario_name VARCHAR(128) NOT NULL,
    model_scope VARCHAR(32) NOT NULL DEFAULT 'PRODUCT_UNIT',
    project_unit_count DECIMAL(12,4) NOT NULL DEFAULT 1,
    accelerator_unit_capex_yuan DECIMAL(24,4) NOT NULL,
    modeled_accelerator_count DECIMAL(12,4) NOT NULL,
    server_base_capex_yuan DECIMAL(24,4) NOT NULL,
    network_storage_cost_ratio DECIMAL(12,8) NOT NULL,
    facility_infrastructure_cost_ratio DECIMAL(12,8) NOT NULL,
    deployment_fixed_cost_yuan DECIMAL(24,4) NOT NULL,
    total_capex_yuan DECIMAL(28,4) NOT NULL,
    useful_life_year SMALLINT UNSIGNED NOT NULL,
    residual_value_ratio DECIMAL(12,8) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO',
    assumption_note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_capex_listing_version (listing_id,capex_scenario_version),
    KEY idx_compute_capex_total (total_capex_yuan),
    CONSTRAINT fk_compute_capex_listing FOREIGN KEY (listing_id)
        REFERENCES compute_platform_resource_listing_v1(listing_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_compute_capex_nonnegative CHECK
        (accelerator_unit_capex_yuan>=0 AND modeled_accelerator_count>0
         AND server_base_capex_yuan>=0 AND deployment_fixed_cost_yuan>=0
         AND total_capex_yuan>0),
    CONSTRAINT chk_compute_capex_ratio CHECK
        (network_storage_cost_ratio>=0 AND facility_infrastructure_cost_ratio>=0
         AND residual_value_ratio>=0 AND residual_value_ratio<=1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力产品单位CAPEX研究情景；不是设施实际投资或设备报价';

CREATE TABLE IF NOT EXISTS compute_project_economics_result_v1 (
    project_economics_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scenario_id BIGINT UNSIGNED NOT NULL,
    capex_parameter_id BIGINT UNSIGNED NOT NULL,
    model_scope VARCHAR(32) NOT NULL DEFAULT 'PRODUCT_UNIT',
    analysis_horizon_year SMALLINT UNSIGNED NOT NULL,
    discount_rate DECIMAL(12,8) NOT NULL,
    annual_cashflow_degradation_rate DECIMAL(12,8) NOT NULL,
    total_capex_yuan DECIMAL(28,4) NOT NULL,
    annual_cashflow_y1_yuan DECIMAL(28,4) NOT NULL,
    annual_cashflow_y2_yuan DECIMAL(28,4) NOT NULL,
    annual_cashflow_y3_yuan DECIMAL(28,4) NOT NULL,
    annual_cashflow_y4_yuan DECIMAL(28,4) NOT NULL,
    annual_cashflow_y5_yuan DECIMAL(28,4) NOT NULL,
    terminal_value_yuan DECIMAL(28,4) NOT NULL,
    npv_yuan DECIMAL(28,4) NOT NULL,
    irr DECIMAL(12,8),
    payback_year DECIMAL(12,6),
    profitability_index DECIMAL(12,8),
    result_status VARCHAR(32) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    calculation_formula TEXT NOT NULL,
    model_version VARCHAR(40) NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_project_economics_scenario (scenario_id),
    KEY idx_compute_project_npv (npv_yuan),
    KEY idx_compute_project_irr (irr),
    CONSTRAINT fk_compute_project_scenario FOREIGN KEY (scenario_id)
        REFERENCES compute_operation_scenario_v1(scenario_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_project_capex FOREIGN KEY (capex_parameter_id)
        REFERENCES compute_capex_parameter_v1(capex_parameter_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力产品单位项目经济性V1：NPV、IRR和回收期均为情景派生';

CREATE TABLE IF NOT EXISTS compute_sensitivity_result_v1 (
    sensitivity_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    base_scenario_id BIGINT UNSIGNED NOT NULL,
    base_project_economics_result_id BIGINT UNSIGNED NOT NULL,
    sensitivity_version VARCHAR(40) NOT NULL,
    variable_code VARCHAR(40) NOT NULL,
    shock_label VARCHAR(32) NOT NULL,
    shock_ratio DECIMAL(12,8) NOT NULL,
    adjusted_utilization_ratio DECIMAL(12,8) NOT NULL,
    adjusted_price_realization_ratio DECIMAL(12,8) NOT NULL,
    adjusted_pue DECIMAL(12,8) NOT NULL,
    adjusted_electricity_price_yuan_kwh DECIMAL(16,8) NOT NULL,
    adjusted_capex_yuan DECIMAL(28,4) NOT NULL,
    annual_revenue_yuan DECIMAL(28,4) NOT NULL,
    annual_total_energy_kwh DECIMAL(28,4) NOT NULL,
    annual_electricity_cost_yuan DECIMAL(28,4) NOT NULL,
    annual_other_opex_yuan DECIMAL(28,4) NOT NULL,
    annual_operating_cashflow_yuan DECIMAL(28,4) NOT NULL,
    operating_cashflow_change_ratio DECIMAL(12,8),
    npv_yuan DECIMAL(28,4) NOT NULL,
    npv_change_ratio DECIMAL(12,8),
    result_status VARCHAR(24) NOT NULL,
    impact_level VARCHAR(16) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    assumption_note TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_sensitivity
        (base_scenario_id,sensitivity_version,variable_code,shock_label),
    KEY idx_compute_sensitivity_variable (variable_code,impact_level),
    CONSTRAINT fk_compute_sensitivity_scenario FOREIGN KEY (base_scenario_id)
        REFERENCES compute_operation_scenario_v1(scenario_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_sensitivity_project FOREIGN KEY (base_project_economics_result_id)
        REFERENCES compute_project_economics_result_v1(project_economics_result_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力单位项目V1单变量敏感性：利用率、价格、电价、PUE与CAPEX';

CREATE TABLE IF NOT EXISTS compute_financing_scenario_v1 (
    financing_scenario_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_economics_result_id BIGINT UNSIGNED NOT NULL,
    financing_version VARCHAR(40) NOT NULL,
    debt_ratio DECIMAL(12,8) NOT NULL,
    annual_interest_rate DECIMAL(12,8) NOT NULL,
    loan_term_year SMALLINT UNSIGNED NOT NULL,
    repayment_method VARCHAR(32) NOT NULL,
    dscr_threshold DECIMAL(12,8) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO',
    assumption_note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_financing_scenario
        (project_economics_result_id,financing_version,debt_ratio),
    KEY idx_compute_financing_ratio (debt_ratio),
    CONSTRAINT fk_compute_financing_project FOREIGN KEY (project_economics_result_id)
        REFERENCES compute_project_economics_result_v1(project_economics_result_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_compute_financing_ratio CHECK (debt_ratio>0 AND debt_ratio<=1),
    CONSTRAINT chk_compute_financing_terms CHECK
        (annual_interest_rate>=0 AND loan_term_year>0 AND dscr_threshold>0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力单位项目融资遍历情景V1：1%-100%债务比例，统一融资条件';

CREATE TABLE IF NOT EXISTS compute_financing_result_v1 (
    financing_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    financing_scenario_id BIGINT UNSIGNED NOT NULL,
    loan_amount_yuan DECIMAL(28,4) NOT NULL,
    annual_principal_yuan DECIMAL(28,4) NOT NULL,
    year1_debt_service_yuan DECIMAL(28,4) NOT NULL,
    year1_dscr DECIMAL(12,8),
    min_dscr DECIMAL(12,8),
    binding_year SMALLINT UNSIGNED,
    feasible_flag TINYINT(1) NOT NULL,
    result_status VARCHAR(24) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    calculation_formula TEXT NOT NULL,
    model_version VARCHAR(40) NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_financing_result (financing_scenario_id),
    KEY idx_compute_financing_feasible (feasible_flag,min_dscr),
    CONSTRAINT fk_compute_financing_result_scenario FOREIGN KEY (financing_scenario_id)
        REFERENCES compute_financing_scenario_v1(financing_scenario_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力单位项目融资结果V1：等额本金、最低DSCR与约束年份';

ALTER TABLE compute_operation_scenario_v1
    DROP CHECK chk_compute_scenario_ratio,
    ADD CONSTRAINT chk_compute_scenario_ratio CHECK
      (price_realization_ratio>=0 AND price_realization_ratio<=1.20
       AND other_opex_revenue_ratio>=0 AND other_opex_revenue_ratio<=1);

/* 三档经营情景；基准情景保留，保守和乐观情景从同一商品事实派生。 */
INSERT INTO compute_operation_scenario_v1 (
    scenario_code,scenario_version,scenario_name,analysis_year,listing_id,facility_v2_id,
    utilization_ratio,utilization_data_type,idle_power_ratio,
    accelerator_unit_power_kw,modeled_accelerator_count,auxiliary_power_ratio,
    pue,pue_data_type,electricity_price_yuan_kwh,electricity_price_data_type,
    price_realization_ratio,other_opex_revenue_ratio,data_type,assumption_note
)
SELECT
    CONCAT(cfg.code_prefix,'_2026_L',b.listing_id),cfg.scenario_version,cfg.scenario_name,
    b.analysis_year,b.listing_id,b.facility_v2_id,
    CASE WHEN b.utilization_data_type='PUBLIC' THEN b.utilization_ratio ELSE cfg.utilization_ratio END,
    CASE WHEN b.utilization_data_type='PUBLIC' THEN 'PUBLIC' ELSE 'SCENARIO' END,
    b.idle_power_ratio,b.accelerator_unit_power_kw,b.modeled_accelerator_count,
    b.auxiliary_power_ratio,
    CASE WHEN b.pue_data_type='PUBLIC' THEN b.pue ELSE cfg.pue END,
    CASE WHEN b.pue_data_type='PUBLIC' THEN 'PUBLIC' ELSE 'SCENARIO' END,
    cfg.electricity_price,'SCENARIO',cfg.price_realization_ratio,
    cfg.other_opex_ratio,'SCENARIO',
    CONCAT('三档经营情景中的',cfg.scenario_name,
      '；公开商品和报价不变，利用率、空闲功耗、设备功率、PUE、电价、报价实现率和OPEX均为研究参数。')
FROM compute_operation_scenario_v1 b
JOIN (
    SELECT 'CONSERVATIVE' code_prefix,'COMPUTE_CONSERVATIVE_V1' scenario_version,
           '保守经营情景' scenario_name,0.35 utilization_ratio,1.50 pue,
           1.00 electricity_price,0.80 price_realization_ratio,0.22 other_opex_ratio
    UNION ALL
    SELECT 'OPTIMISTIC','COMPUTE_OPTIMISTIC_V1','乐观经营情景',0.85,1.25,0.70,1.05,0.12
) cfg
WHERE b.scenario_version='COMPUTE_BASE_V1'
ON DUPLICATE KEY UPDATE
    utilization_ratio=VALUES(utilization_ratio),pue=VALUES(pue),
    electricity_price_yuan_kwh=VALUES(electricity_price_yuan_kwh),
    price_realization_ratio=VALUES(price_realization_ratio),
    other_opex_revenue_ratio=VALUES(other_opex_revenue_ratio),
    assumption_note=VALUES(assumption_note);

/* 重新计算全部三档经营现金流。 */
INSERT INTO compute_economics_result_v1 (
    scenario_id,selected_price_snapshot_id,price_scope,billing_cycle,price_value,currency,
    annual_billable_hours,modeled_max_it_power_kw,modeled_avg_it_power_kw,
    annual_it_energy_kwh,annual_total_energy_kwh,annual_revenue_yuan,
    annual_electricity_cost_yuan,annual_other_opex_yuan,annual_operating_cashflow_yuan,
    electricity_cost_ratio,operating_cashflow_margin,break_even_utilization_ratio,
    result_status,data_type,calculation_formula,model_version
)
WITH ranked_price AS (
    SELECT p.*,ROW_NUMBER() OVER(PARTITION BY p.listing_id
      ORDER BY CASE p.price_scope WHEN 'DETAIL_CONFIG' THEN 0 ELSE 1 END,
               p.captured_at DESC,p.price_snapshot_id DESC) rn
    FROM compute_product_price_snapshot_v1 p
    WHERE p.price_scope IN ('DETAIL_CONFIG','LIST_REFERENCE') AND p.price_value IS NOT NULL
), base AS (
    SELECT s.*,p.price_snapshot_id,p.price_scope,p.billing_cycle,p.price_value,p.currency,
      s.accelerator_unit_power_kw*s.modeled_accelerator_count*(1+s.auxiliary_power_ratio) max_it_power_kw,
      CASE LOWER(COALESCE(p.billing_cycle,'monthly'))
        WHEN 'hourly' THEN p.price_value*8760 WHEN 'daily' THEN p.price_value*365
        WHEN 'yearly' THEN p.price_value ELSE p.price_value*12 END full_revenue
    FROM compute_operation_scenario_v1 s
    JOIN ranked_price p ON p.listing_id=s.listing_id AND p.rn=1
    WHERE s.scenario_version IN
      ('COMPUTE_CONSERVATIVE_V1','COMPUTE_BASE_V1','COMPUTE_OPTIMISTIC_V1')
), calc AS (
    SELECT b.*,
      8760*b.utilization_ratio billable_hours,
      b.max_it_power_kw*(b.idle_power_ratio+(1-b.idle_power_ratio)*b.utilization_ratio) avg_it_power,
      b.full_revenue*b.utilization_ratio*b.price_realization_ratio revenue,
      b.max_it_power_kw*8760*b.pue*b.electricity_price_yuan_kwh
        *(b.idle_power_ratio+(1-b.idle_power_ratio)*b.utilization_ratio) electricity_cost,
      b.full_revenue*b.utilization_ratio*b.price_realization_ratio*b.other_opex_revenue_ratio other_opex,
      b.full_revenue*b.price_realization_ratio*(1-b.other_opex_revenue_ratio)
        -b.max_it_power_kw*8760*b.pue*b.electricity_price_yuan_kwh*(1-b.idle_power_ratio) break_even_denom,
      b.max_it_power_kw*8760*b.pue*b.electricity_price_yuan_kwh*b.idle_power_ratio idle_cost
    FROM base b
)
SELECT scenario_id,price_snapshot_id,price_scope,billing_cycle,price_value,currency,
  billable_hours,max_it_power_kw,avg_it_power,avg_it_power*8760,avg_it_power*8760*pue,
  revenue,electricity_cost,other_opex,revenue-electricity_cost-other_opex,
  CASE WHEN revenue=0 THEN NULL ELSE electricity_cost/revenue END,
  CASE WHEN revenue=0 THEN NULL ELSE (revenue-electricity_cost-other_opex)/revenue END,
  CASE WHEN break_even_denom<=0 THEN NULL ELSE LEAST(1,idle_cost/break_even_denom) END,
  CASE WHEN revenue-electricity_cost-other_opex>0 THEN 'POSITIVE' ELSE 'NEGATIVE' END,
  'SCENARIO_DERIVED',
  'Revenue=public_price×cycle_factor×utilization×realization; TotalEnergy=MaxITPower×[idle+(1-idle)×utilization]×8760×PUE; OperatingCashflow=Revenue-ElectricityCost-OtherOpex。',
  'COMPUTE_ECONOMICS_V1'
FROM calc
ON DUPLICATE KEY UPDATE
  selected_price_snapshot_id=VALUES(selected_price_snapshot_id),price_scope=VALUES(price_scope),
  billing_cycle=VALUES(billing_cycle),price_value=VALUES(price_value),
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
  result_status=VALUES(result_status),computed_at=CURRENT_TIMESTAMP;

/* 独立于租赁收入的设备成本映射；三档CAPEX使用同一硬件逻辑乘以±20%。 */
INSERT INTO compute_capex_parameter_v1 (
    listing_id,capex_scenario_version,capex_scenario_name,model_scope,project_unit_count,
    accelerator_unit_capex_yuan,modeled_accelerator_count,server_base_capex_yuan,
    network_storage_cost_ratio,facility_infrastructure_cost_ratio,deployment_fixed_cost_yuan,
    total_capex_yuan,useful_life_year,residual_value_ratio,data_type,assumption_note
)
WITH unit_cost AS (
    SELECT l.listing_id,l.resource_type,l.accelerator_model,l.product_name,
      COALESCE(s.modeled_accelerator_count,1) modeled_count,
      CASE
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%B200%' THEN 350000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H200%' THEN 280000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H100%' THEN 220000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H800%' THEN 150000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%A800%' THEN 120000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%A100%' THEN 100000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%H20%' THEN 110000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%5090%' THEN 35000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%4090%' THEN 20000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%3090%' THEN 12000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%V100%' THEN 30000
        WHEN UPPER(COALESCE(l.accelerator_model,l.product_name)) LIKE '%ASCEND%910%'
          OR COALESCE(l.accelerator_model,l.product_name) LIKE '%昇腾910%' THEN 80000
        WHEN COALESCE(l.resource_type,'') LIKE '%CPU%' THEN 0
        ELSE 50000 END unit_capex,
      CASE WHEN COALESCE(l.resource_type,'') LIKE '%CPU%' THEN 300000 ELSE 100000 END server_capex
    FROM compute_platform_resource_listing_v1 l
    JOIN compute_operation_scenario_v1 s ON s.listing_id=l.listing_id
      AND s.scenario_version='COMPUTE_BASE_V1'
), configs AS (
    SELECT 'CAPEX_CONSERVATIVE_V1' version,'保守CAPEX情景' name,1.20 factor
    UNION ALL SELECT 'CAPEX_BASE_V1','基准CAPEX情景',1.00
    UNION ALL SELECT 'CAPEX_OPTIMISTIC_V1','乐观CAPEX情景',0.80
)
SELECT u.listing_id,c.version,c.name,'PRODUCT_UNIT',1,
  u.unit_capex,u.modeled_count,u.server_capex,0.15,0.12,50000,
  ((u.unit_capex*u.modeled_count+u.server_capex)*(1+0.15+0.12)+50000)*c.factor,
  5,0.05,'SCENARIO',
  '单个公开算力商品配置的单位项目CAPEX研究情景；GPU/NPU成本、服务器底座、网络存储、基础设施和部署成本均非真实报价，不代表整个算力中心投资。'
FROM unit_cost u CROSS JOIN configs c
WHERE 1=1
ON DUPLICATE KEY UPDATE
  accelerator_unit_capex_yuan=VALUES(accelerator_unit_capex_yuan),
  modeled_accelerator_count=VALUES(modeled_accelerator_count),
  server_base_capex_yuan=VALUES(server_base_capex_yuan),
  total_capex_yuan=VALUES(total_capex_yuan),assumption_note=VALUES(assumption_note);

/* 项目经济性：5年、10%折现率；IRR使用0%-200%的0.1%网格近似。 */
SET SESSION cte_max_recursion_depth=2500;
INSERT INTO compute_project_economics_result_v1 (
    scenario_id,capex_parameter_id,model_scope,analysis_horizon_year,discount_rate,
    annual_cashflow_degradation_rate,total_capex_yuan,
    annual_cashflow_y1_yuan,annual_cashflow_y2_yuan,annual_cashflow_y3_yuan,
    annual_cashflow_y4_yuan,annual_cashflow_y5_yuan,terminal_value_yuan,
    npv_yuan,irr,payback_year,profitability_index,result_status,data_type,
    calculation_formula,model_version
)
WITH RECURSIVE rates(n) AS (
    SELECT 0 UNION ALL SELECT n+1 FROM rates WHERE n<2000
), project_base AS (
    SELECT s.scenario_id,e.annual_operating_cashflow_yuan c1,cp.capex_parameter_id,
      cp.total_capex_yuan capex,cp.residual_value_ratio,
      CASE s.scenario_version WHEN 'COMPUTE_CONSERVATIVE_V1' THEN 0.05
        WHEN 'COMPUTE_OPTIMISTIC_V1' THEN 0.00 ELSE 0.02 END degradation,
      0.10 discount_rate
    FROM compute_operation_scenario_v1 s
    JOIN compute_economics_result_v1 e ON e.scenario_id=s.scenario_id
    JOIN compute_capex_parameter_v1 cp ON cp.listing_id=s.listing_id
      AND cp.capex_scenario_version=CASE s.scenario_version
        WHEN 'COMPUTE_CONSERVATIVE_V1' THEN 'CAPEX_CONSERVATIVE_V1'
        WHEN 'COMPUTE_OPTIMISTIC_V1' THEN 'CAPEX_OPTIMISTIC_V1'
        ELSE 'CAPEX_BASE_V1' END
    WHERE s.scenario_version IN
      ('COMPUTE_CONSERVATIVE_V1','COMPUTE_BASE_V1','COMPUTE_OPTIMISTIC_V1')
), flows AS (
    SELECT p.*,p.c1*(1-p.degradation) c2,p.c1*POWER(1-p.degradation,2) c3,
      p.c1*POWER(1-p.degradation,3) c4,p.c1*POWER(1-p.degradation,4) c5,
      p.capex*p.residual_value_ratio terminal_value
    FROM project_base p
), irr_eval AS (
    SELECT f.scenario_id,r.n,r.n/1000.0 rate_value,
      -f.capex+f.c1/POWER(1+r.n/1000.0,1)+f.c2/POWER(1+r.n/1000.0,2)
       +f.c3/POWER(1+r.n/1000.0,3)+f.c4/POWER(1+r.n/1000.0,4)
       +(f.c5+f.terminal_value)/POWER(1+r.n/1000.0,5) npv_at_rate
    FROM flows f CROSS JOIN rates r
), irr_ranked AS (
    SELECT i.*,ROW_NUMBER() OVER(PARTITION BY i.scenario_id ORDER BY ABS(i.npv_at_rate),i.n) rn,
      MAX(CASE WHEN i.n=0 THEN i.npv_at_rate END) OVER(PARTITION BY i.scenario_id) npv_at_zero,
      MAX(CASE WHEN i.n=2000 THEN i.npv_at_rate END) OVER(PARTITION BY i.scenario_id) npv_at_200
    FROM irr_eval i
), irr_best AS (
    SELECT * FROM irr_ranked WHERE rn=1
), final_calc AS (
    SELECT f.*,i.rate_value,i.npv_at_zero,i.npv_at_200,
      -f.capex+f.c1/POWER(1+f.discount_rate,1)+f.c2/POWER(1+f.discount_rate,2)
       +f.c3/POWER(1+f.discount_rate,3)+f.c4/POWER(1+f.discount_rate,4)
       +(f.c5+f.terminal_value)/POWER(1+f.discount_rate,5) npv,
      CASE
        WHEN f.c1>=f.capex AND f.c1>0 THEN f.capex/f.c1
        WHEN f.c1+f.c2>=f.capex AND f.c2>0 THEN 1+(f.capex-f.c1)/f.c2
        WHEN f.c1+f.c2+f.c3>=f.capex AND f.c3>0 THEN 2+(f.capex-f.c1-f.c2)/f.c3
        WHEN f.c1+f.c2+f.c3+f.c4>=f.capex AND f.c4>0 THEN 3+(f.capex-f.c1-f.c2-f.c3)/f.c4
        WHEN f.c1+f.c2+f.c3+f.c4+f.c5>=f.capex AND f.c5>0 THEN 4+(f.capex-f.c1-f.c2-f.c3-f.c4)/f.c5
        ELSE NULL END payback
    FROM flows f JOIN irr_best i ON i.scenario_id=f.scenario_id
)
SELECT scenario_id,capex_parameter_id,'PRODUCT_UNIT',5,discount_rate,degradation,capex,
  c1,c2,c3,c4,c5,terminal_value,npv,
  CASE WHEN npv_at_zero<0 OR npv_at_200>0 THEN NULL ELSE rate_value END,
  payback,(npv+capex)/capex,
  CASE WHEN npv_at_zero<0 THEN 'NO_POSITIVE_IRR'
       WHEN npv_at_200>0 THEN 'IRR_ABOVE_200'
       WHEN npv>=0 THEN 'FEASIBLE' ELSE 'NEGATIVE_NPV' END,
  'SCENARIO_DERIVED',
  'NPV=-CAPEX+Σ(Cashflow_y/(1+10%)^y)+Residual/(1+10%)^5；IRR为0%-200%范围内0.1%步长近似；回收期按未折现现金流插值。',
  'COMPUTE_PROJECT_ECONOMICS_V1'
FROM final_calc
ON DUPLICATE KEY UPDATE
  capex_parameter_id=VALUES(capex_parameter_id),discount_rate=VALUES(discount_rate),
  annual_cashflow_degradation_rate=VALUES(annual_cashflow_degradation_rate),
  total_capex_yuan=VALUES(total_capex_yuan),annual_cashflow_y1_yuan=VALUES(annual_cashflow_y1_yuan),
  annual_cashflow_y2_yuan=VALUES(annual_cashflow_y2_yuan),annual_cashflow_y3_yuan=VALUES(annual_cashflow_y3_yuan),
  annual_cashflow_y4_yuan=VALUES(annual_cashflow_y4_yuan),annual_cashflow_y5_yuan=VALUES(annual_cashflow_y5_yuan),
  terminal_value_yuan=VALUES(terminal_value_yuan),npv_yuan=VALUES(npv_yuan),irr=VALUES(irr),
  payback_year=VALUES(payback_year),profitability_index=VALUES(profitability_index),
  result_status=VALUES(result_status),computed_at=CURRENT_TIMESTAMP;

/* 基准情景单变量压力：利用率、公开价格、电价、PUE、CAPEX。 */
INSERT INTO compute_sensitivity_result_v1 (
    base_scenario_id,base_project_economics_result_id,sensitivity_version,
    variable_code,shock_label,shock_ratio,adjusted_utilization_ratio,
    adjusted_price_realization_ratio,adjusted_pue,adjusted_electricity_price_yuan_kwh,
    adjusted_capex_yuan,annual_revenue_yuan,annual_total_energy_kwh,
    annual_electricity_cost_yuan,annual_other_opex_yuan,annual_operating_cashflow_yuan,
    operating_cashflow_change_ratio,npv_yuan,npv_change_ratio,result_status,
    impact_level,data_type,assumption_note
)
WITH shocks AS (
    SELECT 'UTILIZATION' variable_code,'DOWN_20' shock_label,-0.20 shock
    UNION ALL SELECT 'UTILIZATION','UP_20',0.20
    UNION ALL SELECT 'PUBLIC_PRICE','DOWN_20',-0.20
    UNION ALL SELECT 'PUBLIC_PRICE','UP_20',0.20
    UNION ALL SELECT 'ELECTRICITY_PRICE','DOWN_20',-0.20
    UNION ALL SELECT 'ELECTRICITY_PRICE','UP_20',0.20
    UNION ALL SELECT 'PUE','DOWN_10',-0.10
    UNION ALL SELECT 'PUE','UP_10',0.10
    UNION ALL SELECT 'CAPEX','DOWN_20',-0.20
    UNION ALL SELECT 'CAPEX','UP_20',0.20
), base AS (
    SELECT s.*,e.economics_result_id,e.annual_revenue_yuan base_revenue,
      e.annual_electricity_cost_yuan base_electricity_cost,
      e.annual_other_opex_yuan base_other_opex,
      e.annual_operating_cashflow_yuan base_cashflow,
      e.modeled_max_it_power_kw,pe.project_economics_result_id,
      pe.total_capex_yuan base_capex,pe.npv_yuan base_npv,pe.discount_rate,
      pe.annual_cashflow_degradation_rate degradation,cp.residual_value_ratio
    FROM compute_operation_scenario_v1 s
    JOIN compute_economics_result_v1 e ON e.scenario_id=s.scenario_id
    JOIN compute_project_economics_result_v1 pe ON pe.scenario_id=s.scenario_id
    JOIN compute_capex_parameter_v1 cp ON cp.capex_parameter_id=pe.capex_parameter_id
    WHERE s.scenario_version='COMPUTE_BASE_V1'
), adjusted_input AS (
    SELECT b.*,x.variable_code,x.shock_label,x.shock,
      CASE WHEN x.variable_code='UTILIZATION' THEN LEAST(1,GREATEST(0,b.utilization_ratio*(1+x.shock))) ELSE b.utilization_ratio END adj_util,
      CASE WHEN x.variable_code='PUBLIC_PRICE' THEN b.price_realization_ratio*(1+x.shock) ELSE b.price_realization_ratio END adj_realization,
      CASE WHEN x.variable_code='PUE' THEN GREATEST(1,b.pue*(1+x.shock)) ELSE b.pue END adj_pue,
      CASE WHEN x.variable_code='ELECTRICITY_PRICE' THEN b.electricity_price_yuan_kwh*(1+x.shock) ELSE b.electricity_price_yuan_kwh END adj_electricity_price,
      CASE WHEN x.variable_code='CAPEX' THEN b.base_capex*(1+x.shock) ELSE b.base_capex END adj_capex
    FROM base b CROSS JOIN shocks x
), adjusted_operation AS (
    SELECT a.*,
      CASE WHEN variable_code='UTILIZATION' THEN base_revenue/utilization_ratio*adj_util
           WHEN variable_code='PUBLIC_PRICE' THEN base_revenue*(1+shock) ELSE base_revenue END adj_revenue,
      modeled_max_it_power_kw*8760*adj_pue
        *(idle_power_ratio+(1-idle_power_ratio)*adj_util) adj_total_energy,
      modeled_max_it_power_kw*8760*adj_pue*adj_electricity_price
        *(idle_power_ratio+(1-idle_power_ratio)*adj_util) adj_electricity_cost
    FROM adjusted_input a
), adjusted_cash AS (
    SELECT a.*,adj_revenue*other_opex_revenue_ratio adj_other_opex,
      adj_revenue-adj_electricity_cost-adj_revenue*other_opex_revenue_ratio adj_cashflow
    FROM adjusted_operation a
), adjusted_npv AS (
    SELECT a.*,
      -adj_capex
      +adj_cashflow/POWER(1+discount_rate,1)
      +adj_cashflow*POWER(1-degradation,1)/POWER(1+discount_rate,2)
      +adj_cashflow*POWER(1-degradation,2)/POWER(1+discount_rate,3)
      +adj_cashflow*POWER(1-degradation,3)/POWER(1+discount_rate,4)
      +(adj_cashflow*POWER(1-degradation,4)+adj_capex*residual_value_ratio)/POWER(1+discount_rate,5) adj_npv
    FROM adjusted_cash a
)
SELECT scenario_id,project_economics_result_id,'COMPUTE_SENSITIVITY_V1',
  variable_code,shock_label,shock,adj_util,adj_realization,adj_pue,
  adj_electricity_price,adj_capex,adj_revenue,adj_total_energy,
  adj_electricity_cost,adj_other_opex,adj_cashflow,
  CASE WHEN base_cashflow=0 THEN NULL ELSE (adj_cashflow-base_cashflow)/ABS(base_cashflow) END,
  adj_npv,CASE WHEN base_npv=0 THEN NULL ELSE (adj_npv-base_npv)/ABS(base_npv) END,
  CASE WHEN adj_cashflow>0 AND adj_npv>=0 THEN 'PASS' ELSE 'FAIL' END,
  CASE
    WHEN base_npv=0 OR ABS((adj_npv-base_npv)/NULLIF(ABS(base_npv),0))>=0.20 THEN 'HIGH'
    WHEN ABS((adj_npv-base_npv)/NULLIF(ABS(base_npv),0))>=0.10 THEN 'MEDIUM'
    ELSE 'LOW' END,
  'SCENARIO_DERIVED',
  '一次仅改变一个参数，其余保持COMPUTE_BASE_V1；用于识别风险方向，不代表联合压力或概率分布。'
FROM adjusted_npv
ON DUPLICATE KEY UPDATE
  adjusted_utilization_ratio=VALUES(adjusted_utilization_ratio),
  adjusted_price_realization_ratio=VALUES(adjusted_price_realization_ratio),
  adjusted_pue=VALUES(adjusted_pue),
  adjusted_electricity_price_yuan_kwh=VALUES(adjusted_electricity_price_yuan_kwh),
  adjusted_capex_yuan=VALUES(adjusted_capex_yuan),annual_revenue_yuan=VALUES(annual_revenue_yuan),
  annual_total_energy_kwh=VALUES(annual_total_energy_kwh),
  annual_electricity_cost_yuan=VALUES(annual_electricity_cost_yuan),
  annual_other_opex_yuan=VALUES(annual_other_opex_yuan),
  annual_operating_cashflow_yuan=VALUES(annual_operating_cashflow_yuan),
  operating_cashflow_change_ratio=VALUES(operating_cashflow_change_ratio),
  npv_yuan=VALUES(npv_yuan),npv_change_ratio=VALUES(npv_change_ratio),
  result_status=VALUES(result_status),impact_level=VALUES(impact_level),computed_at=CURRENT_TIMESTAMP;

/* 1%-100%债务比例按1%步长遍历；融资条件对所有商品单位项目保持一致。 */
ALTER TABLE compute_financing_scenario_v1
  COMMENT='算力单位项目融资遍历情景V1：1%-100%债务比例，统一融资条件';
SET SESSION cte_max_recursion_depth=2500;
INSERT INTO compute_financing_scenario_v1 (
    project_economics_result_id,financing_version,debt_ratio,annual_interest_rate,
    loan_term_year,repayment_method,dscr_threshold,data_type,assumption_note
)
WITH RECURSIVE ratios(n) AS (
    SELECT 1 UNION ALL SELECT n+1 FROM ratios WHERE n<100
)
SELECT pe.project_economics_result_id,'FINANCE_V1',r.n/100.0,0.06,5,
  'EQUAL_PRINCIPAL',1.20,'SCENARIO',
  '统一采用6%年利率、5年期、等额本金；债务比例按1%-100%的1%步长遍历。结果不代表银行报价或授信承诺。'
FROM compute_project_economics_result_v1 pe CROSS JOIN ratios r
WHERE 1=1
ON DUPLICATE KEY UPDATE annual_interest_rate=VALUES(annual_interest_rate),
  loan_term_year=VALUES(loan_term_year),dscr_threshold=VALUES(dscr_threshold),
  assumption_note=VALUES(assumption_note);

INSERT INTO compute_financing_result_v1 (
    financing_scenario_id,loan_amount_yuan,annual_principal_yuan,
    year1_debt_service_yuan,year1_dscr,min_dscr,binding_year,feasible_flag,
    result_status,data_type,calculation_formula,model_version
)
WITH debt AS (
    SELECT fs.*,pe.total_capex_yuan,pe.annual_cashflow_y1_yuan c1,
      pe.annual_cashflow_y2_yuan c2,pe.annual_cashflow_y3_yuan c3,
      pe.annual_cashflow_y4_yuan c4,pe.annual_cashflow_y5_yuan c5,
      pe.total_capex_yuan*fs.debt_ratio loan,
      pe.total_capex_yuan*fs.debt_ratio/fs.loan_term_year principal
    FROM compute_financing_scenario_v1 fs
    JOIN compute_project_economics_result_v1 pe
      ON pe.project_economics_result_id=fs.project_economics_result_id
    WHERE fs.financing_version='FINANCE_V1'
), dscr AS (
    SELECT d.*,
      principal+loan*annual_interest_rate debt1,
      principal+(loan-principal)*annual_interest_rate debt2,
      principal+(loan-principal*2)*annual_interest_rate debt3,
      principal+(loan-principal*3)*annual_interest_rate debt4,
      principal+(loan-principal*4)*annual_interest_rate debt5
    FROM debt d
), ratios AS (
    SELECT d.*,c1/debt1 dscr1,c2/debt2 dscr2,c3/debt3 dscr3,
      c4/debt4 dscr4,c5/debt5 dscr5
    FROM dscr d
), final_calc AS (
    SELECT r.*,LEAST(dscr1,dscr2,dscr3,dscr4,dscr5) min_dscr_calc
    FROM ratios r
)
SELECT financing_scenario_id,loan,principal,debt1,dscr1,min_dscr_calc,
  CASE
    WHEN min_dscr_calc=dscr1 THEN 1 WHEN min_dscr_calc=dscr2 THEN 2
    WHEN min_dscr_calc=dscr3 THEN 3 WHEN min_dscr_calc=dscr4 THEN 4 ELSE 5 END,
  min_dscr_calc>=dscr_threshold,
  CASE WHEN min_dscr_calc>=dscr_threshold THEN 'PASS' ELSE 'FAIL' END,
  'SCENARIO_DERIVED',
  'Loan=CAPEX×DebtRatio；EqualPrincipal=Loan/5；DebtService_y=Principal+OpeningLoan_y×6%；DSCR_y=OperatingCashflow_y/DebtService_y。',
  'COMPUTE_FINANCE_V1'
FROM final_calc
ON DUPLICATE KEY UPDATE
  loan_amount_yuan=VALUES(loan_amount_yuan),annual_principal_yuan=VALUES(annual_principal_yuan),
  year1_debt_service_yuan=VALUES(year1_debt_service_yuan),year1_dscr=VALUES(year1_dscr),
  min_dscr=VALUES(min_dscr),binding_year=VALUES(binding_year),
  feasible_flag=VALUES(feasible_flag),result_status=VALUES(result_status),computed_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_financing_capacity_v1 AS
SELECT pe.project_economics_result_id,pe.scenario_id,s.scenario_version,s.listing_id,
  l.external_product_id,l.product_name,p.platform_name,
  pe.total_capex_yuan,pe.npv_yuan,pe.irr,pe.payback_year,
  base_fs.debt_ratio AS base_debt_ratio,base_fr.loan_amount_yuan AS base_loan_amount_yuan,
  base_fr.min_dscr AS base_min_dscr,
  base_fr.feasible_flag AS base_dscr_feasible_flag,
  (pe.npv_yuan>=0 AND base_fr.feasible_flag=1) AS base_bankable_flag,
  mx.max_feasible_debt_ratio AS max_dscr_feasible_debt_ratio,
  max_fr.loan_amount_yuan AS max_dscr_feasible_loan_yuan,
  mx.max_feasible_debt_ratio AS max_tested_dscr_feasible_debt_ratio,
  CASE WHEN pe.npv_yuan>=0 THEN mx.max_feasible_debt_ratio ELSE NULL END AS max_feasible_debt_ratio,
  CASE WHEN pe.npv_yuan>=0 THEN max_fr.loan_amount_yuan ELSE NULL END AS max_feasible_loan_yuan,
  max_fr.binding_year,max_fr.min_dscr AS binding_dscr,
  CASE WHEN mx.max_feasible_debt_ratio=1.00 THEN 'DEBT_RATIO_CAP'
       WHEN mx.max_feasible_debt_ratio IS NULL THEN 'NO_DSCR_FEASIBLE_RATIO'
       ELSE 'DSCR_THRESHOLD' END AS binding_constraint,
  (mx.max_feasible_debt_ratio=1.00) AS debt_ratio_cap_reached_flag,
  (pe.npv_yuan>=0 AND mx.max_feasible_debt_ratio IS NOT NULL) AS bankable_flag,
  'SCENARIO_DERIVED' AS data_type
FROM compute_project_economics_result_v1 pe
JOIN compute_operation_scenario_v1 s ON s.scenario_id=pe.scenario_id
JOIN compute_platform_resource_listing_v1 l ON l.listing_id=s.listing_id
JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
LEFT JOIN (
    SELECT fs.project_economics_result_id,
      MAX(CASE WHEN fr.feasible_flag=1 THEN fs.debt_ratio END) max_feasible_debt_ratio
    FROM compute_financing_scenario_v1 fs
    JOIN compute_financing_result_v1 fr ON fr.financing_scenario_id=fs.financing_scenario_id
    WHERE fs.financing_version='FINANCE_V1'
    GROUP BY fs.project_economics_result_id
) mx ON mx.project_economics_result_id=pe.project_economics_result_id
LEFT JOIN compute_financing_scenario_v1 max_fs
  ON max_fs.project_economics_result_id=pe.project_economics_result_id
 AND max_fs.financing_version='FINANCE_V1'
 AND max_fs.debt_ratio=mx.max_feasible_debt_ratio
LEFT JOIN compute_financing_result_v1 max_fr
  ON max_fr.financing_scenario_id=max_fs.financing_scenario_id
LEFT JOIN compute_financing_scenario_v1 base_fs
  ON base_fs.project_economics_result_id=pe.project_economics_result_id
 AND base_fs.financing_version='FINANCE_V1' AND base_fs.debt_ratio=0.70
LEFT JOIN compute_financing_result_v1 base_fr
  ON base_fr.financing_scenario_id=base_fs.financing_scenario_id;

CREATE OR REPLACE VIEW v_compute_sensitivity_summary_v1 AS
SELECT s.listing_id,l.external_product_id,l.product_name,r.variable_code,
  MAX(ABS(r.npv_change_ratio)) max_abs_npv_change_ratio,
  CASE
    WHEN MAX(ABS(r.npv_change_ratio))>=0.20 THEN 'HIGH'
    WHEN MAX(ABS(r.npv_change_ratio))>=0.10 THEN 'MEDIUM'
    ELSE 'LOW' END sensitivity_level,
  MIN(r.npv_yuan) downside_npv_yuan,MAX(r.npv_yuan) upside_npv_yuan,
  'SCENARIO_DERIVED' data_type
FROM compute_sensitivity_result_v1 r
JOIN compute_operation_scenario_v1 s ON s.scenario_id=r.base_scenario_id
JOIN compute_platform_resource_listing_v1 l ON l.listing_id=s.listing_id
GROUP BY s.listing_id,l.external_product_id,l.product_name,r.variable_code;
