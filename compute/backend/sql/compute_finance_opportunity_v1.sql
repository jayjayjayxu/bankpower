USE spdb_power_finance;

/*
  Compute finance opportunity V1

  This is a business-action layer above the public product and scenario model.
  A row is NOT a confirmed construction project or a credit approval.  It is a
  curated candidate that passed the current BASE operating and credit scenario,
  with its physical facility, project owner, contracts and policy eligibility
  explicitly left as due-diligence items where public evidence is absent.
*/

CREATE TABLE IF NOT EXISTS compute_finance_opportunity_v1 (
    opportunity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    opportunity_code VARCHAR(40) NOT NULL,
    bank_recommendation_id BIGINT UNSIGNED NOT NULL,
    project_economics_result_id BIGINT UNSIGNED NOT NULL,
    facility_v2_id BIGINT UNSIGNED NULL,
    platform_id BIGINT UNSIGNED NOT NULL,
    listing_id BIGINT UNSIGNED NOT NULL,

    opportunity_name VARCHAR(255) NOT NULL,
    opportunity_scope VARCHAR(48) NOT NULL COMMENT 'FACILITY_MAPPED_PRODUCT_UNIT/PLATFORM_PRODUCT_UNIT_UNMAPPED_FACILITY',
    project_identity_status VARCHAR(48) NOT NULL COMMENT 'CONFIRMED/PENDING_FACILITY_AND_ASSET_OWNER',
    opportunity_status VARCHAR(48) NOT NULL COMMENT 'PRIORITY_DUE_DILIGENCE/NOT_RECOMMENDED/CLOSED',
    business_priority CHAR(1) NOT NULL COMMENT 'A/B/C; transparent scenario-based triage priority',
    opportunity_rank SMALLINT UNSIGNED NOT NULL,
    ranking_basis VARCHAR(255) NOT NULL,

    scenario_version VARCHAR(40) NOT NULL,
    credit_policy_code VARCHAR(40) NOT NULL,
    total_capex_yuan DECIMAL(28,4) NOT NULL,
    npv_yuan DECIMAL(28,4) NOT NULL,
    irr DECIMAL(12,8) NULL,
    recommended_debt_ratio DECIMAL(12,8) NULL,
    recommended_loan_yuan DECIMAL(28,4) NULL,
    recommended_min_dscr DECIMAL(12,8) NULL,

    policy_readiness_level VARCHAR(48) NOT NULL COMMENT 'READY/EVIDENCE_REQUIRED/NOT_EVALUABLE',
    policy_summary TEXT NOT NULL,
    primary_next_action TEXT NOT NULL,
    key_risk_summary TEXT NOT NULL,
    recommendation_text TEXT NOT NULL,

    as_of_date DATE NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'SCENARIO_DERIVED',
    model_version VARCHAR(40) NOT NULL DEFAULT 'COMPUTE_OPPORTUNITY_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_finance_opportunity_code (opportunity_code),
    UNIQUE KEY uk_compute_finance_opportunity_bank_result (bank_recommendation_id),
    KEY idx_compute_opportunity_status (opportunity_status,business_priority,opportunity_rank),
    KEY idx_compute_opportunity_platform (platform_id,listing_id),
    KEY idx_compute_opportunity_facility (facility_v2_id),
    CONSTRAINT fk_compute_opportunity_bank_result
      FOREIGN KEY (bank_recommendation_id) REFERENCES compute_bank_recommendation_v1(bank_recommendation_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_opportunity_project_result
      FOREIGN KEY (project_economics_result_id) REFERENCES compute_project_economics_result_v1(project_economics_result_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_opportunity_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_opportunity_platform
      FOREIGN KEY (platform_id) REFERENCES compute_service_platform_v1(platform_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_opportunity_listing
      FOREIGN KEY (listing_id) REFERENCES compute_platform_resource_listing_v1(listing_id)
      ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力银行业务机会清单；来源于公开商品和研究情景，不等于实际项目或授信审批';

CREATE TABLE IF NOT EXISTS compute_policy_due_diligence_checklist_v1 (
    checklist_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    opportunity_id BIGINT UNSIGNED NOT NULL,
    policy_rule_id BIGINT UNSIGNED NULL,
    check_code VARCHAR(64) NOT NULL,
    check_group VARCHAR(40) NOT NULL COMMENT 'PROJECT_IDENTITY/COMMERCIAL/ENERGY/POLICY/FINANCING',
    check_name VARCHAR(255) NOT NULL,
    evidence_status VARCHAR(48) NOT NULL COMMENT 'PENDING/NOT_EVALUABLE/OUT_OF_CURRENT_WINDOW/VERIFIED/NOT_APPLICABLE',
    risk_level VARCHAR(16) NOT NULL COMMENT 'BLOCKING/HIGH/MEDIUM/LOW',
    model_treatment VARCHAR(48) NOT NULL COMMENT 'GATE_ONLY/INPUT_REQUIRED/SCENARIO_CANDIDATE/NO_AUTOMATIC_EFFECT',
    required_evidence TEXT NOT NULL,
    known_evidence TEXT NULL,
    due_diligence_action TEXT NOT NULL,
    owner_role VARCHAR(64) NOT NULL,
    sort_order SMALLINT UNSIGNED NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'DUE_DILIGENCE_DERIVED',
    model_version VARCHAR(40) NOT NULL DEFAULT 'COMPUTE_OPPORTUNITY_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_opportunity_check (opportunity_id,check_code,model_version),
    KEY idx_compute_checklist_status (opportunity_id,evidence_status,risk_level),
    KEY idx_compute_checklist_rule (policy_rule_id),
    CONSTRAINT fk_compute_checklist_opportunity
      FOREIGN KEY (opportunity_id) REFERENCES compute_finance_opportunity_v1(opportunity_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_checklist_policy_rule
      FOREIGN KEY (policy_rule_id) REFERENCES policy_rule_v1(policy_rule_id)
      ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力机会的尽调与政策证据清单；不记录虚构证据，不自动调整现金流';

/*
  Seed only products that passed COMPUTE_BASE_V1 + CREDIT_BASE_V1.  The current
  public catalogue maps none of these five candidates to a verified physical
  facility, therefore their project identity is deliberately PENDING.
*/
INSERT INTO compute_finance_opportunity_v1 (
    opportunity_code,bank_recommendation_id,project_economics_result_id,facility_v2_id,platform_id,listing_id,
    opportunity_name,opportunity_scope,project_identity_status,opportunity_status,business_priority,opportunity_rank,
    ranking_basis,scenario_version,credit_policy_code,total_capex_yuan,npv_yuan,irr,
    recommended_debt_ratio,recommended_loan_yuan,recommended_min_dscr,
    policy_readiness_level,policy_summary,primary_next_action,key_risk_summary,recommendation_text,
    as_of_date,data_type,model_version
)
SELECT
    CONCAT('COPP_BASE_',LPAD(s.opportunity_rank,3,'0')),
    s.bank_recommendation_id,s.project_economics_result_id,s.facility_v2_id,s.platform_id,s.listing_id,
    CONCAT('公开算力商品单元候选：',s.product_name),
    CASE WHEN s.facility_v2_id IS NULL THEN 'PLATFORM_PRODUCT_UNIT_UNMAPPED_FACILITY' ELSE 'FACILITY_MAPPED_PRODUCT_UNIT' END,
    CASE WHEN s.facility_v2_id IS NULL THEN 'PENDING_FACILITY_AND_ASSET_OWNER' ELSE 'PENDING_PROJECT_OWNER' END,
    'PRIORITY_DUE_DILIGENCE',
    CASE WHEN s.npv_yuan>=1000000 AND s.recommended_loan_yuan>=2000000 THEN 'A' ELSE 'B' END,
    s.opportunity_rank,
    '在 COMPUTE_BASE_V1 与 CREDIT_BASE_V1 下，NPV为非负且银行规则层建议进入尽调；按建议贷款额降序排序。',
    s.scenario_version,s.credit_policy_code,s.total_capex_yuan,s.npv_yuan,s.irr,
    s.recommended_debt_ratio,s.recommended_loan_yuan,s.recommended_min_dscr,
    CASE WHEN s.facility_v2_id IS NULL THEN 'NOT_EVALUABLE' ELSE 'EVIDENCE_REQUIRED' END,
    CASE WHEN s.facility_v2_id IS NULL
      THEN '公开商品尚未与可核验物理设施、融资主体或资产权属对应，不能确认绿色金融、绿电、虚拟电厂或地方政策资格。'
      ELSE '已识别物理设施，但仍须核验项目级PUE、绿电、可调负荷、资金用途和申报材料。' END,
    CASE WHEN s.facility_v2_id IS NULL
      THEN '先确认实际设施、融资主体、设备资产权属及采购报价；确认后再调取项目级能源和政策材料。'
      ELSE '核验项目级PUE、绿电/绿证、负荷曲线、可调能力、资金用途及合同现金流。' END,
    '公开目录价格不等于实际合同价；利用率、PUE、电价和CAPEX均含研究情景参数；未确认物理设施时不能形成真实资产抵押或绿色属性判断。',
    s.recommendation_text,CURDATE(),'SCENARIO_DERIVED','COMPUTE_OPPORTUNITY_V1'
FROM (
    SELECT
      br.bank_recommendation_id,pe.project_economics_result_id,l.facility_v2_id,l.platform_id,l.listing_id,l.product_name,
      os.scenario_version,cp.policy_code AS credit_policy_code,pe.total_capex_yuan,pe.npv_yuan,pe.irr,
      br.recommended_debt_ratio,br.recommended_loan_yuan,br.recommended_min_dscr,br.recommendation_text,
      ROW_NUMBER() OVER (ORDER BY br.recommended_loan_yuan DESC,pe.npv_yuan DESC,l.listing_id) AS opportunity_rank
    FROM compute_bank_recommendation_v1 br
    JOIN compute_project_economics_result_v1 pe ON pe.project_economics_result_id=br.project_economics_result_id
    JOIN compute_operation_scenario_v1 os ON os.scenario_id=pe.scenario_id
    JOIN compute_platform_resource_listing_v1 l ON l.listing_id=os.listing_id
    JOIN compute_credit_policy_scenario_v1 cp ON cp.credit_policy_id=br.credit_policy_id
    WHERE os.scenario_version='COMPUTE_BASE_V1'
      AND cp.policy_code='CREDIT_BASE_V1'
      AND br.recommendation_status='PROCEED_DUE_DILIGENCE'
) s
ON DUPLICATE KEY UPDATE
  project_economics_result_id=VALUES(project_economics_result_id),facility_v2_id=VALUES(facility_v2_id),platform_id=VALUES(platform_id),listing_id=VALUES(listing_id),
  opportunity_name=VALUES(opportunity_name),opportunity_scope=VALUES(opportunity_scope),project_identity_status=VALUES(project_identity_status),
  opportunity_status=VALUES(opportunity_status),business_priority=VALUES(business_priority),opportunity_rank=VALUES(opportunity_rank),ranking_basis=VALUES(ranking_basis),
  scenario_version=VALUES(scenario_version),credit_policy_code=VALUES(credit_policy_code),total_capex_yuan=VALUES(total_capex_yuan),npv_yuan=VALUES(npv_yuan),irr=VALUES(irr),
  recommended_debt_ratio=VALUES(recommended_debt_ratio),recommended_loan_yuan=VALUES(recommended_loan_yuan),recommended_min_dscr=VALUES(recommended_min_dscr),
  policy_readiness_level=VALUES(policy_readiness_level),policy_summary=VALUES(policy_summary),primary_next_action=VALUES(primary_next_action),
  key_risk_summary=VALUES(key_risk_summary),recommendation_text=VALUES(recommendation_text),as_of_date=VALUES(as_of_date),data_type=VALUES(data_type),updated_at=CURRENT_TIMESTAMP;

/*
  The initial checklist intentionally records missing material rather than
  pretending that a product-listing can establish a project, policy or loan.
*/
INSERT INTO compute_policy_due_diligence_checklist_v1 (
    opportunity_id,policy_rule_id,check_code,check_group,check_name,evidence_status,risk_level,model_treatment,
    required_evidence,known_evidence,due_diligence_action,owner_role,sort_order,data_type,model_version
)
SELECT o.opportunity_id,r.policy_rule_id,c.check_code,c.check_group,c.check_name,c.evidence_status,c.risk_level,c.model_treatment,
       c.required_evidence,c.known_evidence,c.due_diligence_action,c.owner_role,c.sort_order,'DUE_DILIGENCE_DERIVED','COMPUTE_OPPORTUNITY_V1'
FROM compute_finance_opportunity_v1 o
CROSS JOIN (
    SELECT NULL AS rule_code,'PROJECT_IDENTITY' AS check_code,'PROJECT_IDENTITY' AS check_group,'融资主体、实际设施与资产权属' AS check_name,
      'PENDING' AS evidence_status,'BLOCKING' AS risk_level,'GATE_ONLY' AS model_treatment,
      '融资申请主体、项目SPV（如有）、实际部署设施地址、设备采购合同/发票、设备序列号、资产权属和抵押可行性材料。' AS required_evidence,
      '当前仅有公开平台商品与研究情景，未发现可对应的融资主体、物理设施或设备资产证据。' AS known_evidence,
      '客户经理先确认交易结构与资产边界；无法确认时不得将商品单元结果解释为固定资产贷款项目。' AS due_diligence_action,
      '客户经理 / 法务 / 押品评估' AS owner_role,10 AS sort_order
    UNION ALL SELECT NULL,'COMMERCIAL_CASHFLOW','COMMERCIAL','客户合同、实际价格与利用率','PENDING','HIGH','INPUT_REQUIRED',
      '客户合同、结算单、历史利用率、资源池排期、客户集中度、应收账款账龄与退订条款。',
      '公开列表价和详情配置价可用于市场观察；不等于实际合同价、库存或可持续出租率。',
      '以合同和历史结算替换公开价格与利用率情景，并重跑收入、NPV和DSCR。','客户经理 / 授信审查',20
    UNION ALL SELECT 'NAT_GREEN_DC_2025_PUE','ENERGY_BASELINE','ENERGY','项目级PUE、绿电与负荷基线','NOT_EVALUABLE','HIGH','INPUT_REQUIRED',
      '项目级PUE、IT负荷、全年用电量、电价/绿电/绿证合同、分时负荷曲线和能耗计量边界。',
      '当前候选没有与公开物理设施对应，不能引用其他设施的PUE或绿电数据。',
      '确认设施后由技术尽调取得能耗资料；以真实参数替换PUE、电价和利用率情景。','技术尽调 / 绿色金融团队',30
    UNION ALL SELECT 'NAT_GREEN_FINANCE_2025_GREEN_DC','GREEN_FINANCE_SCREENING','POLICY','绿色金融目录适用性','NOT_EVALUABLE','HIGH','GATE_ONLY',
      '资金用途、能效等级或PUE、设备清单、节能/碳减排说明、融资主体及还款来源。',
      '绿色金融目录属于分类依据，不构成已获绿色贷款或优惠利率。',
      '待项目和资金用途确认后，由绿色金融团队完成目录映射与绿色属性核验。','绿色金融团队 / 授信审查',40
    UNION ALL SELECT 'NAT_AI_ENERGY_2026_MARKET','POWER_FLEXIBILITY','POLICY','绿电、需求响应与市场参与条件','NOT_EVALUABLE','MEDIUM','SCENARIO_CANDIDATE',
      '用电户号、负荷可调能力、计量通信条件、聚合或市场合同、绿电/绿证交易及结算凭证。',
      '政策提出支持方向，但没有候选项目的接入、交易或结算证据。',
      '只有在可调能力和实际结算可核验后，才可建立独立需求响应或绿电政策情景。','技术尽调 / 能源业务团队',50
    UNION ALL SELECT 'SZ_TRAINING_VOUCHER_2026_DEMAND','CUSTOMER_SIDE_VOUCHER','POLICY','客户侧训力券收入关联','OUT_OF_CURRENT_WINDOW','MEDIUM','NO_AUTOMATIC_EFFECT',
      '深圳需求方资格、非关联关系、服务机构资格、服务合同、申请/获批/结算材料及下一年度窗口。',
      '2026年度窗口已关闭；且该支持面向需求方，不证明平台商品或融资项目自动获得补贴。',
      '不纳入当前现金流；仅在未来客户订单与有效申报窗口同时满足时，作为需求侧线索跟踪。','客户经理 / 政策研究',60
) c
LEFT JOIN policy_rule_v1 r ON r.rule_code=c.rule_code
WHERE o.model_version='COMPUTE_OPPORTUNITY_V1'
ON DUPLICATE KEY UPDATE
  policy_rule_id=VALUES(policy_rule_id),check_group=VALUES(check_group),check_name=VALUES(check_name),evidence_status=VALUES(evidence_status),
  risk_level=VALUES(risk_level),model_treatment=VALUES(model_treatment),required_evidence=VALUES(required_evidence),known_evidence=VALUES(known_evidence),
  due_diligence_action=VALUES(due_diligence_action),owner_role=VALUES(owner_role),sort_order=VALUES(sort_order),data_type=VALUES(data_type),updated_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_finance_opportunity_summary_v1 AS
SELECT
  o.opportunity_id,o.opportunity_code,o.opportunity_name,o.opportunity_scope,o.project_identity_status,
  o.opportunity_status,o.business_priority,o.opportunity_rank,o.ranking_basis,o.scenario_version,o.credit_policy_code,
  o.total_capex_yuan,o.npv_yuan,o.irr,o.recommended_debt_ratio,o.recommended_loan_yuan,o.recommended_min_dscr,
  o.policy_readiness_level,o.policy_summary,o.primary_next_action,o.key_risk_summary,o.recommendation_text,o.as_of_date,
  o.data_type,o.model_version,o.updated_at,
  p.platform_code,p.platform_name,p.operator_name AS platform_operator_name,
  l.external_product_id,l.product_name,l.resource_type,l.accelerator_model,l.accelerator_count,l.platform_region_label,l.available_zone,
  f.facility_code,f.official_name AS facility_name,
  COUNT(c.checklist_id) AS checklist_count,
  SUM(c.evidence_status IN ('PENDING','NOT_EVALUABLE')) AS open_check_count,
  SUM(c.risk_level='BLOCKING' AND c.evidence_status<>'VERIFIED') AS blocking_check_count,
  SUM(c.risk_level='HIGH' AND c.evidence_status<>'VERIFIED') AS high_risk_check_count
FROM compute_finance_opportunity_v1 o
JOIN compute_service_platform_v1 p ON p.platform_id=o.platform_id
JOIN compute_platform_resource_listing_v1 l ON l.listing_id=o.listing_id
LEFT JOIN enterprise_data_center_v2 f ON f.facility_v2_id=o.facility_v2_id
LEFT JOIN compute_policy_due_diligence_checklist_v1 c
  ON c.opportunity_id=o.opportunity_id AND c.model_version='COMPUTE_OPPORTUNITY_V1'
GROUP BY
  o.opportunity_id,o.opportunity_code,o.opportunity_name,o.opportunity_scope,o.project_identity_status,
  o.opportunity_status,o.business_priority,o.opportunity_rank,o.ranking_basis,o.scenario_version,o.credit_policy_code,
  o.total_capex_yuan,o.npv_yuan,o.irr,o.recommended_debt_ratio,o.recommended_loan_yuan,o.recommended_min_dscr,
  o.policy_readiness_level,o.policy_summary,o.primary_next_action,o.key_risk_summary,o.recommendation_text,o.as_of_date,
  o.data_type,o.model_version,o.updated_at,
  p.platform_code,p.platform_name,p.operator_name,
  l.external_product_id,l.product_name,l.resource_type,l.accelerator_model,l.accelerator_count,l.platform_region_label,l.available_zone,
  f.facility_code,f.official_name;

CREATE OR REPLACE VIEW v_compute_policy_due_diligence_checklist_v1 AS
SELECT
  c.checklist_id,c.opportunity_id,c.check_code,c.check_group,c.check_name,c.evidence_status,c.risk_level,c.model_treatment,
  c.required_evidence,c.known_evidence,c.due_diligence_action,c.owner_role,c.sort_order,c.data_type,c.model_version,c.updated_at,
  r.rule_code,r.rule_title,r.rule_category,r.applicable_region,r.rule_status,d.official_url
FROM compute_policy_due_diligence_checklist_v1 c
LEFT JOIN policy_rule_v1 r ON r.policy_rule_id=c.policy_rule_id
LEFT JOIN policy_document_v1 d ON d.policy_document_id=r.policy_document_id;
