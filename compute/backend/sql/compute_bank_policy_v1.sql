USE spdb_power_finance;

/* 银行业务规则层全部属于研究情景，不代表浦发银行或任何机构的正式信贷政策。 */
CREATE TABLE IF NOT EXISTS compute_credit_policy_scenario_v1 (
    credit_policy_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    policy_code VARCHAR(40) NOT NULL,
    policy_name VARCHAR(128) NOT NULL,
    policy_version VARCHAR(40) NOT NULL,
    max_debt_ratio DECIMAL(12,8) NOT NULL,
    min_equity_ratio DECIMAL(12,8) NOT NULL,
    min_dscr DECIMAL(12,8) NOT NULL,
    revenue_haircut_ratio DECIMAL(12,8) NOT NULL,
    eligible_capex_ratio DECIMAL(12,8) NOT NULL,
    residual_value_haircut_ratio DECIMAL(12,8) NOT NULL,
    annual_interest_rate DECIMAL(12,8) NOT NULL,
    loan_term_year SMALLINT UNSIGNED NOT NULL,
    debt_service_reserve_months DECIMAL(8,2) NOT NULL,
    guarantee_required_flag TINYINT(1) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO',
    policy_note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_credit_policy_code (policy_code,policy_version),
    CONSTRAINT chk_compute_credit_policy_ratios CHECK
      (max_debt_ratio>0 AND max_debt_ratio<=1 AND min_equity_ratio>=0 AND min_equity_ratio<1
       AND revenue_haircut_ratio>=0 AND revenue_haircut_ratio<1
       AND eligible_capex_ratio>0 AND eligible_capex_ratio<=1
       AND residual_value_haircut_ratio>=0 AND residual_value_haircut_ratio<=1),
    CONSTRAINT chk_compute_credit_policy_terms CHECK
      (min_dscr>0 AND annual_interest_rate>=0 AND loan_term_year>0
       AND debt_service_reserve_months>=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力银行业务规则研究情景；非正式信贷制度';

CREATE TABLE IF NOT EXISTS compute_credit_policy_financing_curve_v1 (
    policy_curve_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_economics_result_id BIGINT UNSIGNED NOT NULL,
    credit_policy_id BIGINT UNSIGNED NOT NULL,
    debt_ratio DECIMAL(12,8) NOT NULL,
    loan_amount_yuan DECIMAL(28,4) NOT NULL,
    adjusted_year1_cashflow_yuan DECIMAL(28,4) NOT NULL,
    year1_debt_service_yuan DECIMAL(28,4) NOT NULL,
    year1_dscr DECIMAL(12,8),
    min_dscr DECIMAL(12,8),
    binding_year SMALLINT UNSIGNED,
    dscr_feasible_flag TINYINT(1) NOT NULL,
    policy_limit_feasible_flag TINYINT(1) NOT NULL,
    economic_feasible_flag TINYINT(1) NOT NULL,
    overall_feasible_flag TINYINT(1) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    model_version VARCHAR(40) NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_policy_curve
      (project_economics_result_id,credit_policy_id,debt_ratio),
    KEY idx_compute_policy_curve_feasible
      (credit_policy_id,overall_feasible_flag,debt_ratio),
    CONSTRAINT fk_compute_policy_curve_project FOREIGN KEY (project_economics_result_id)
      REFERENCES compute_project_economics_result_v1(project_economics_result_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_policy_curve_policy FOREIGN KEY (credit_policy_id)
      REFERENCES compute_credit_policy_scenario_v1(credit_policy_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='银行规则下1%-100%债务比例曲线；现金流经过收入折扣';

CREATE TABLE IF NOT EXISTS compute_bank_recommendation_v1 (
    bank_recommendation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    project_economics_result_id BIGINT UNSIGNED NOT NULL,
    credit_policy_id BIGINT UNSIGNED NOT NULL,
    mathematical_dscr_capacity_ratio DECIMAL(12,8),
    policy_cap_ratio DECIMAL(12,8) NOT NULL,
    recommended_debt_ratio DECIMAL(12,8),
    recommended_loan_yuan DECIMAL(28,4),
    recommended_min_dscr DECIMAL(12,8),
    binding_year SMALLINT UNSIGNED,
    binding_rule VARCHAR(40) NOT NULL,
    debt_service_reserve_yuan DECIMAL(28,4),
    guarantee_required_flag TINYINT(1) NOT NULL,
    recommendation_status VARCHAR(40) NOT NULL,
    recommendation_text VARCHAR(1000) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    model_version VARCHAR(40) NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_bank_recommendation
      (project_economics_result_id,credit_policy_id),
    KEY idx_compute_bank_recommendation_status
      (credit_policy_id,recommendation_status,recommended_debt_ratio),
    CONSTRAINT fk_compute_bank_recommendation_project FOREIGN KEY (project_economics_result_id)
      REFERENCES compute_project_economics_result_v1(project_economics_result_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_bank_recommendation_policy FOREIGN KEY (credit_policy_id)
      REFERENCES compute_credit_policy_scenario_v1(credit_policy_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='银行规则层推荐结果：数学容量、政策上限和建议额度分开保存';

INSERT INTO compute_credit_policy_scenario_v1 (
    policy_code,policy_name,policy_version,max_debt_ratio,min_equity_ratio,min_dscr,
    revenue_haircut_ratio,eligible_capex_ratio,residual_value_haircut_ratio,
    annual_interest_rate,loan_term_year,debt_service_reserve_months,
    guarantee_required_flag,data_type,policy_note
) VALUES
('CREDIT_CONSERVATIVE_V1','审慎信贷情景','COMPUTE_CREDIT_POLICY_V1',
 0.50,0.40,1.40,0.25,0.80,0.20,0.075,4,6,1,'SCENARIO',
 '研究用审慎规则：收入折扣25%，最高债务比例50%，最低资本金40%，最低DSCR 1.40。非正式银行制度。'),
('CREDIT_BASE_V1','基准信贷情景','COMPUTE_CREDIT_POLICY_V1',
 0.70,0.30,1.30,0.15,0.90,0.50,0.065,5,3,1,'SCENARIO',
 '研究用基准规则：收入折扣15%，最高债务比例70%，最低资本金30%，最低DSCR 1.30。非正式银行制度。'),
('CREDIT_RELAXED_V1','宽松信贷情景','COMPUTE_CREDIT_POLICY_V1',
 0.80,0.20,1.20,0.05,1.00,0.80,0.055,7,0,0,'SCENARIO',
 '研究用宽松规则：收入折扣5%，最高债务比例80%，最低资本金20%，最低DSCR 1.20。非正式银行制度。')
ON DUPLICATE KEY UPDATE
 max_debt_ratio=VALUES(max_debt_ratio),min_equity_ratio=VALUES(min_equity_ratio),
 min_dscr=VALUES(min_dscr),revenue_haircut_ratio=VALUES(revenue_haircut_ratio),
 eligible_capex_ratio=VALUES(eligible_capex_ratio),
 residual_value_haircut_ratio=VALUES(residual_value_haircut_ratio),
 annual_interest_rate=VALUES(annual_interest_rate),loan_term_year=VALUES(loan_term_year),
 debt_service_reserve_months=VALUES(debt_service_reserve_months),
 guarantee_required_flag=VALUES(guarantee_required_flag),policy_note=VALUES(policy_note);

SET SESSION cte_max_recursion_depth=2500;
INSERT INTO compute_credit_policy_financing_curve_v1 (
    project_economics_result_id,credit_policy_id,debt_ratio,loan_amount_yuan,
    adjusted_year1_cashflow_yuan,year1_debt_service_yuan,year1_dscr,min_dscr,
    binding_year,dscr_feasible_flag,policy_limit_feasible_flag,
    economic_feasible_flag,overall_feasible_flag,data_type,model_version
)
WITH RECURSIVE ratios(n) AS (
    SELECT 1 UNION ALL SELECT n+1 FROM ratios WHERE n<100
), years(y) AS (
    SELECT 1 UNION ALL SELECT y+1 FROM years WHERE y<7
), project_policy AS (
    SELECT pe.project_economics_result_id,pe.total_capex_yuan,pe.npv_yuan,
      pe.annual_cashflow_degradation_rate,s.other_opex_revenue_ratio,
      oe.annual_revenue_yuan,oe.annual_electricity_cost_yuan,
      cp.credit_policy_id,cp.max_debt_ratio,cp.min_equity_ratio,cp.min_dscr,
      cp.revenue_haircut_ratio,cp.eligible_capex_ratio,
      cp.annual_interest_rate,cp.loan_term_year,
      oe.annual_revenue_yuan*(1-cp.revenue_haircut_ratio)
        *(1-s.other_opex_revenue_ratio)-oe.annual_electricity_cost_yuan adjusted_cashflow_y1
    FROM compute_project_economics_result_v1 pe
    JOIN compute_operation_scenario_v1 s ON s.scenario_id=pe.scenario_id
    JOIN compute_economics_result_v1 oe ON oe.scenario_id=s.scenario_id
    CROSS JOIN compute_credit_policy_scenario_v1 cp
    WHERE cp.policy_version='COMPUTE_CREDIT_POLICY_V1'
      AND s.scenario_version IN
        ('COMPUTE_CONSERVATIVE_V1','COMPUTE_BASE_V1','COMPUTE_OPTIMISTIC_V1')
), yearly AS (
    SELECT pp.*,r.n/100.0 debt_ratio,y.y,
      pp.total_capex_yuan*(r.n/100.0) loan,
      pp.total_capex_yuan*(r.n/100.0)/pp.loan_term_year principal,
      pp.adjusted_cashflow_y1*POWER(1-pp.annual_cashflow_degradation_rate,y.y-1) cashflow_y
    FROM project_policy pp CROSS JOIN ratios r
    JOIN years y ON y.y<=pp.loan_term_year
), debt AS (
    SELECT y.*,
      y.principal+(y.loan-y.principal*(y.y-1))*y.annual_interest_rate debt_service_y
    FROM yearly y
), ranked AS (
    SELECT d.*,d.cashflow_y/d.debt_service_y dscr_y,
      ROW_NUMBER() OVER(PARTITION BY d.project_economics_result_id,d.credit_policy_id,d.debt_ratio
        ORDER BY d.cashflow_y/d.debt_service_y,d.y) rn
    FROM debt d
), binding AS (
    SELECT * FROM ranked WHERE rn=1
)
SELECT project_economics_result_id,credit_policy_id,debt_ratio,loan,
  adjusted_cashflow_y1,
  total_capex_yuan*debt_ratio/loan_term_year+loan*annual_interest_rate,
  adjusted_cashflow_y1/(total_capex_yuan*debt_ratio/loan_term_year+loan*annual_interest_rate),
  dscr_y,y,dscr_y>=min_dscr,
  (debt_ratio<=max_debt_ratio AND debt_ratio<=1-min_equity_ratio
    AND loan<=total_capex_yuan*eligible_capex_ratio),
  npv_yuan>=0,
  (dscr_y>=min_dscr AND debt_ratio<=max_debt_ratio
    AND debt_ratio<=1-min_equity_ratio
    AND loan<=total_capex_yuan*eligible_capex_ratio AND npv_yuan>=0),
  'SCENARIO_DERIVED','COMPUTE_CREDIT_POLICY_CURVE_V1'
FROM binding
ON DUPLICATE KEY UPDATE
 loan_amount_yuan=VALUES(loan_amount_yuan),
 adjusted_year1_cashflow_yuan=VALUES(adjusted_year1_cashflow_yuan),
 year1_debt_service_yuan=VALUES(year1_debt_service_yuan),year1_dscr=VALUES(year1_dscr),
 min_dscr=VALUES(min_dscr),binding_year=VALUES(binding_year),
 dscr_feasible_flag=VALUES(dscr_feasible_flag),
 policy_limit_feasible_flag=VALUES(policy_limit_feasible_flag),
 economic_feasible_flag=VALUES(economic_feasible_flag),
 overall_feasible_flag=VALUES(overall_feasible_flag),computed_at=CURRENT_TIMESTAMP;

INSERT INTO compute_bank_recommendation_v1 (
    project_economics_result_id,credit_policy_id,mathematical_dscr_capacity_ratio,
    policy_cap_ratio,recommended_debt_ratio,recommended_loan_yuan,
    recommended_min_dscr,binding_year,binding_rule,debt_service_reserve_yuan,
    guarantee_required_flag,recommendation_status,recommendation_text,
    data_type,model_version
)
WITH capacity AS (
    SELECT c.project_economics_result_id,c.credit_policy_id,
      MAX(CASE WHEN c.dscr_feasible_flag=1 THEN c.debt_ratio END) mathematical_capacity,
      MAX(CASE WHEN c.overall_feasible_flag=1 THEN c.debt_ratio END) recommended_ratio
    FROM compute_credit_policy_financing_curve_v1 c
    GROUP BY c.project_economics_result_id,c.credit_policy_id
), base AS (
    SELECT pe.project_economics_result_id,pe.npv_yuan,cp.credit_policy_id,
      cp.max_debt_ratio,cp.min_equity_ratio,cp.eligible_capex_ratio,
      cp.debt_service_reserve_months,cp.guarantee_required_flag,
      LEAST(cp.max_debt_ratio,1-cp.min_equity_ratio,cp.eligible_capex_ratio) policy_cap_ratio,
      x.mathematical_capacity,x.recommended_ratio
    FROM compute_project_economics_result_v1 pe
    CROSS JOIN compute_credit_policy_scenario_v1 cp
    JOIN capacity x ON x.project_economics_result_id=pe.project_economics_result_id
      AND x.credit_policy_id=cp.credit_policy_id
    WHERE cp.policy_version='COMPUTE_CREDIT_POLICY_V1'
), selected AS (
    SELECT b.*,c.loan_amount_yuan,c.min_dscr,c.binding_year,c.year1_debt_service_yuan
    FROM base b LEFT JOIN compute_credit_policy_financing_curve_v1 c
      ON c.project_economics_result_id=b.project_economics_result_id
     AND c.credit_policy_id=b.credit_policy_id
     AND c.debt_ratio=b.recommended_ratio
)
SELECT project_economics_result_id,credit_policy_id,mathematical_capacity,
  policy_cap_ratio,recommended_ratio,loan_amount_yuan,min_dscr,binding_year,
  CASE
    WHEN npv_yuan<0 THEN 'ECONOMIC_NPV'
    WHEN mathematical_capacity IS NULL THEN 'DSCR_THRESHOLD'
    WHEN recommended_ratio=max_debt_ratio THEN 'MAX_DEBT_POLICY'
    WHEN recommended_ratio=1-min_equity_ratio THEN 'MIN_EQUITY_POLICY'
    WHEN recommended_ratio=eligible_capex_ratio THEN 'CAPEX_ELIGIBILITY'
    ELSE 'DSCR_THRESHOLD' END,
  year1_debt_service_yuan*debt_service_reserve_months/12,
  guarantee_required_flag,
  CASE
    WHEN npv_yuan<0 THEN 'NOT_RECOMMENDED_NEGATIVE_NPV'
    WHEN recommended_ratio IS NULL THEN 'NOT_RECOMMENDED_DSCR'
    ELSE 'PROCEED_DUE_DILIGENCE' END,
  CASE
    WHEN npv_yuan<0 THEN '项目单位NPV为负，即使部分债务比例DSCR可通过，也不建议进入融资推荐。'
    WHEN recommended_ratio IS NULL THEN '收入审慎折扣后没有债务比例满足本情景DSCR门槛。'
    ELSE '建议额度已同时受收入折扣、DSCR、资本金、合格CAPEX和最高债务比例约束；仅建议进入下一步尽调。' END,
  'SCENARIO_DERIVED','COMPUTE_BANK_RECOMMENDATION_V1'
FROM selected
ON DUPLICATE KEY UPDATE
 mathematical_dscr_capacity_ratio=VALUES(mathematical_dscr_capacity_ratio),
 policy_cap_ratio=VALUES(policy_cap_ratio),recommended_debt_ratio=VALUES(recommended_debt_ratio),
 recommended_loan_yuan=VALUES(recommended_loan_yuan),
 recommended_min_dscr=VALUES(recommended_min_dscr),binding_year=VALUES(binding_year),
 binding_rule=VALUES(binding_rule),debt_service_reserve_yuan=VALUES(debt_service_reserve_yuan),
 guarantee_required_flag=VALUES(guarantee_required_flag),
 recommendation_status=VALUES(recommendation_status),
 recommendation_text=VALUES(recommendation_text),computed_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_bank_recommendation_v1 AS
SELECT br.bank_recommendation_id,br.project_economics_result_id,
  pe.scenario_id,s.scenario_version,s.scenario_name,s.listing_id,
  l.external_product_id,l.product_name,l.accelerator_model,p.platform_name,
  cp.credit_policy_id,cp.policy_code,cp.policy_name,cp.max_debt_ratio,
  cp.min_equity_ratio,cp.min_dscr,cp.revenue_haircut_ratio,
  cp.eligible_capex_ratio,cp.annual_interest_rate,cp.loan_term_year,
  cp.debt_service_reserve_months,pe.total_capex_yuan,pe.npv_yuan,pe.irr,
  pe.payback_year,br.mathematical_dscr_capacity_ratio,br.policy_cap_ratio,
  br.recommended_debt_ratio,br.recommended_loan_yuan,br.recommended_min_dscr,
  br.binding_year,br.binding_rule,br.debt_service_reserve_yuan,
  br.guarantee_required_flag,br.recommendation_status,br.recommendation_text,
  br.data_type,br.model_version,br.computed_at
FROM compute_bank_recommendation_v1 br
JOIN compute_project_economics_result_v1 pe
  ON pe.project_economics_result_id=br.project_economics_result_id
JOIN compute_operation_scenario_v1 s ON s.scenario_id=pe.scenario_id
JOIN compute_platform_resource_listing_v1 l ON l.listing_id=s.listing_id
JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
JOIN compute_credit_policy_scenario_v1 cp ON cp.credit_policy_id=br.credit_policy_id;
