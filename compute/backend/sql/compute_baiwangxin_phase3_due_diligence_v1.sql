USE spdb_power_finance;

/*
  百旺信云数据中心三期：项目级尽调状态 V1

  仅记录已经披露的事实、其口径边界和需要向项目方补取的材料。
  PENDING/PARTIAL 不表示项目不具备条件，只表示公开资料不足以作出确认。
*/
CREATE TABLE IF NOT EXISTS compute_facility_project_due_diligence_v1 (
    project_due_diligence_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    project_scope_code VARCHAR(96) NOT NULL,
    project_scope_name VARCHAR(255) NOT NULL,
    check_code VARCHAR(64) NOT NULL,
    check_group VARCHAR(40) NOT NULL,
    check_name VARCHAR(255) NOT NULL,
    evidence_status VARCHAR(24) NOT NULL COMMENT 'VERIFIED/PARTIAL/PENDING',
    risk_level VARCHAR(16) NOT NULL COMMENT 'LOW/MEDIUM/HIGH/BLOCKING',
    evidence_summary TEXT NOT NULL,
    required_evidence TEXT NOT NULL,
    due_diligence_action TEXT NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    source_locator VARCHAR(255) NULL,
    sort_order SMALLINT UNSIGNED NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'DUE_DILIGENCE_DERIVED',
    model_version VARCHAR(40) NOT NULL DEFAULT 'BWX_PHASE3_DD_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_project_dd (facility_v2_id,project_scope_code,check_code,model_version),
    KEY idx_compute_facility_project_dd_status (facility_v2_id,evidence_status,risk_level),
    CONSTRAINT fk_compute_facility_project_dd_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_project_dd_source
      FOREIGN KEY (source_id) REFERENCES data_source(source_id)
      ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='单一设施项目级尽调状态；公开事实与待补证据分开保存';

INSERT INTO compute_facility_project_due_diligence_v1 (
    facility_v2_id,project_scope_code,project_scope_name,check_code,check_group,check_name,
    evidence_status,risk_level,evidence_summary,required_evidence,due_diligence_action,
    source_id,source_locator,sort_order,data_type,model_version
)
SELECT f.facility_v2_id,'PHASE_III_EXCHANGE_DISCLOSURE','百旺信云数据中心三期',
       c.check_code,c.check_group,c.check_name,c.evidence_status,c.risk_level,
       c.evidence_summary,c.required_evidence,c.due_diligence_action,
       ds.source_id,c.source_locator,c.sort_order,'DUE_DILIGENCE_DERIVED','BWX_PHASE3_DD_V1'
FROM enterprise_data_center_v2 f
JOIN (
  SELECT 'PROJECT_BOUNDARY' check_code,'PROJECT_IDENTITY' check_group,'项目物理边界' check_name,
         'VERIFIED' evidence_status,'LOW' risk_level,
         '公开披露已明确三期项目、建筑面积10,000㎡、1,760个机柜及4kW/柜设计口径。' evidence_summary,
         '项目竣工资料、资产清单、现场平面图及当前运营范围确认。' required_evidence,
         '取得项目竣工与资产清单，确认三期与1栋、4栋经营口径不交叉。' due_diligence_action,
         'PROJECT_FINANCE' source_key,'三期项目规模、能耗与融资说明' source_locator,10 sort_order
  UNION ALL SELECT 'ASSET_AND_ENERGY_ANCHORS','ASSET','投资、PUE与用电锚点','VERIFIED','LOW',
         '公开披露三期历史投资3.2亿元、PUE 1.228、年电量4,847.33万kWh及年综合能耗14,286.83吨标煤。',
         '项目级能耗批复、近12个月电费单、PUE计量口径及设备台账。',
         '核验披露指标的统计期与当前工程状态，作为后续模型输入边界。',
         'PROJECT_FINANCE','三期项目规模、能耗与融资说明',20
  UNION ALL SELECT 'FINANCING_SUBJECT_AND_COLLATERAL','FINANCING','历史融资主体与担保结构','PARTIAL','MEDIUM',
         '公开资料显示深圳易百旺科技有限公司曾取得1.2亿元、84个月固定资产借款，并披露应收账款、设备及股权担保结构。',
         '当前贷款余额、还款计划、授信合同、抵押/质押登记及项目公司最新股权结构。',
         '向项目公司及贷款行核验当前融资存续状态；历史案例仅作结构参照。',
         'PROJECT_FINANCE','借款、应收账款质押、设备抵押及股权质押说明',30
  UNION ALL SELECT 'PHASE3_OPERATING_REVENUE','COMMERCIAL','三期独立收入与上架率','PENDING','HIGH',
         '已取得百旺信1栋+4栋整体自建托管经营数据，但未取得三期单独收入、上架率及客户结构。',
         '三期月度上架机柜、客户合同、收入台账、应收账龄及回款流水。',
         '按三期单独口径重建近24个月收入、上架率与回款曲线；不得按园区比例分摊。',
         'ANNUAL_OPERATIONS','2023—2025年自建服务器托管经营数据',40
  UNION ALL SELECT 'WHOLESALE_CONTRACT_ALLOCATION','COMMERCIAL','客户合同与三期归属','PARTIAL','HIGH',
         '公开深圳移动批发合同可作为定价与空置保护结构参照，但未确认合同机柜是否属于三期。',
         '合同正文、机柜交付清单、三期机房位置、实际用电及应收账款对应关系。',
         '逐份核验客户合同与三期资产、收入及现金流的对应关系。',
         'MOBILE_CONTRACT','深圳移动百旺信IDC机房运营服务框架合作协议',50
  UNION ALL SELECT 'PHASE3_ELECTRICITY_SETTLEMENT','ENERGY','三期电费结算与容量边界','PARTIAL','HIGH',
         '公开资料提供1栋+4栋年度电量及历史/上半年结算价格；三期单独年度账单尚未披露。',
         '三期近12个月电费单、计量点清单、需量/容量合同及增容批复。',
         '核验三期计量边界与可用容量；乐观情景2028年起超过公开年电量边界。',
         'ANNUAL_OPERATIONS','历史电费账单统计与三期年电量披露',60
  UNION ALL SELECT 'GREEN_POWER_AND_CERTIFICATE','GREEN','绿电与绿证可核验性','PENDING','MEDIUM',
         '运营方公开案例可作为绿色能源线索，但未形成三期在统计期内的绿电/绿证结算证据。',
         '绿电合同、绿证凭证、结算单、可再生能源利用率计算表及项目对应关系。',
         '在取得项目级结算证据前，不把绿色标签、绿金支持或绿电溢价计入现金流。',
         'GREEN_CASE','运营方绿色能源案例',70
  UNION ALL SELECT 'PHASE3_CASHFLOW','CASHFLOW','项目级现金流与偿债基础','PENDING','BLOCKING',
         '现有保守/基准/乐观结果为公开锚定的税前经营现金流代理，不是三期实际CFADS。',
         '三期收入、成本、税费、营运资本、维护CAPEX、债务本息及现金流量表。',
         '以项目单独账套重建CFADS，再开展DSCR、期限与授信额度测算。',
         'ANNUAL_OPERATIONS','公开经营事实与三期现金流代理边界',80
  UNION ALL SELECT 'POLICY_ELIGIBILITY','POLICY','绿色与虚拟电厂政策适用','PARTIAL','MEDIUM',
         '设施在当前公开规则下为潜在适用；但项目级PUE、绿电、IT负荷、可调负荷与资金用途仍需证据。',
         '政策申报资格、项目级PUE/绿电/负荷资料、改造方案、资金用途及批复或结算文件。',
         '政策仅进入尽调优先级；取得材料和批复前不计入收入、NPV或贷款额度。',
         'POLICY_RULES','国家绿色数据中心与深圳虚拟电厂规则',90
) c
JOIN data_source ds ON ds.source_id=CASE c.source_key
  WHEN 'PROJECT_FINANCE' THEN 3038
  WHEN 'ANNUAL_OPERATIONS' THEN 3069
  WHEN 'MOBILE_CONTRACT' THEN 3071
  WHEN 'GREEN_CASE' THEN 3035
  WHEN 'POLICY_RULES' THEN 3070
END
WHERE f.facility_code='SZCF016'
ON DUPLICATE KEY UPDATE
  check_group=VALUES(check_group),check_name=VALUES(check_name),evidence_status=VALUES(evidence_status),risk_level=VALUES(risk_level),
  evidence_summary=VALUES(evidence_summary),required_evidence=VALUES(required_evidence),due_diligence_action=VALUES(due_diligence_action),
  source_id=VALUES(source_id),source_locator=VALUES(source_locator),sort_order=VALUES(sort_order),updated_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_facility_project_due_diligence_v1 AS
SELECT f.facility_code,f.official_name,d.project_due_diligence_id,d.project_scope_code,d.project_scope_name,
       d.check_code,d.check_group,d.check_name,d.evidence_status,d.risk_level,
       d.evidence_summary,d.required_evidence,d.due_diligence_action,d.source_locator,d.sort_order,
       d.data_type,d.model_version,d.updated_at,ds.source_title,ds.source_url,ds.source_tier
FROM compute_facility_project_due_diligence_v1 d
JOIN enterprise_data_center_v2 f ON f.facility_v2_id=d.facility_v2_id
LEFT JOIN data_source ds ON ds.source_id=d.source_id;
