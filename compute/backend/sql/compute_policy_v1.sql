/*
  Compute policy layer V1

  Purpose:
  - preserve policy documents and atomic rules with official provenance;
  - distinguish facility/operator-side support from compute-buyer-side support;
  - record preliminary eligibility without treating a policy as guaranteed cash flow;
  - keep all policy-derived records out of the public facility/product/price fact tables.

  Important boundary:
  No grant, voucher, green-finance preference or demand-response income in this script
  is written into compute_economics_result_v1, compute_project_economics_result_v1,
  compute_financing_result_v1 or compute_bank_recommendation_v1. A separate,
  evidence-backed policy scenario is required before it can affect NPV, IRR or DSCR.
*/

CREATE TABLE IF NOT EXISTS compute_policy_provider_registry_v1 (
    provider_registry_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    policy_document_id BIGINT UNSIGNED NOT NULL,
    provider_name VARCHAR(255) NOT NULL,
    admission_batch VARCHAR(64) NOT NULL,
    admission_type VARCHAR(48) NOT NULL,
    provider_status VARCHAR(32) NOT NULL,
    service_scope VARCHAR(255),
    source_locator VARCHAR(255),
    official_url VARCHAR(1000),
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC',
    data_quality VARCHAR(24) NOT NULL DEFAULT 'VERIFIED_PUBLIC',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_policy_provider (policy_document_id, provider_name),
    KEY idx_compute_policy_provider_name (provider_name),
    CONSTRAINT fk_compute_policy_provider_document
      FOREIGN KEY (policy_document_id) REFERENCES policy_document_v1(policy_document_id)
      ON DELETE RESTRICT ON UPDATE CASCADE
) COMMENT='训力券等政策公开服务机构名录；是否可向具体客户结算仍须以服务事项和合同核验';

CREATE TABLE IF NOT EXISTS compute_policy_provider_platform_match_v1 (
    provider_platform_match_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    provider_registry_id BIGINT UNSIGNED NOT NULL,
    platform_id BIGINT UNSIGNED NOT NULL,
    match_status VARCHAR(32) NOT NULL,
    match_method VARCHAR(48) NOT NULL,
    match_basis VARCHAR(500) NOT NULL,
    verified_at DATE NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC_DERIVED',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_provider_platform (provider_registry_id, platform_id),
    KEY idx_compute_provider_platform_platform (platform_id, match_status),
    CONSTRAINT fk_compute_provider_platform_provider
      FOREIGN KEY (provider_registry_id) REFERENCES compute_policy_provider_registry_v1(provider_registry_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_provider_platform_platform
      FOREIGN KEY (platform_id) REFERENCES compute_service_platform_v1(platform_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT='仅保留有明确主体名称证据的平台—训力券服务机构匹配，不做模糊匹配';

CREATE TABLE IF NOT EXISTS compute_policy_applicability_result_v1 (
    applicability_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    policy_rule_id BIGINT UNSIGNED NOT NULL,
    subject_type VARCHAR(32) NOT NULL COMMENT 'FACILITY/PLATFORM/LISTING/PROJECT',
    subject_key VARCHAR(64) NOT NULL,
    facility_v2_id BIGINT UNSIGNED NULL,
    platform_id BIGINT UNSIGNED NULL,
    listing_id BIGINT UNSIGNED NULL,
    applicability_status VARCHAR(40) NOT NULL COMMENT 'ELIGIBLE/POTENTIALLY_ELIGIBLE/INSUFFICIENT_EVIDENCE/NOT_APPLICABLE/REFERENCE_ONLY',
    support_side VARCHAR(32) NOT NULL COMMENT 'FACILITY_OPERATOR/COMPUTE_BUYER/PLATFORM_PROVIDER/PROJECT_OWNER',
    impact_type VARCHAR(40) NOT NULL COMMENT 'GREEN_RECOGNITION/GREEN_FINANCE_SCREENING/ENERGY_FLEXIBILITY/DEMAND_INCENTIVE/DATA_REQUIREMENT',
    model_treatment VARCHAR(40) NOT NULL COMMENT 'NO_AUTOMATIC_EFFECT/INPUT_REQUIRED/GATE_ONLY/SCENARIO_CANDIDATE',
    eligibility_summary TEXT NOT NULL,
    required_evidence TEXT,
    known_evidence TEXT,
    monetary_value_yuan DECIMAL(28,4) NULL,
    monetary_value_note VARCHAR(500) NULL,
    assessment_date DATE NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'POLICY_DERIVED',
    model_version VARCHAR(40) NOT NULL DEFAULT 'COMPUTE_POLICY_V1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_policy_subject_rule (policy_rule_id, subject_type, subject_key, model_version),
    KEY idx_compute_policy_subject (subject_type, subject_key, applicability_status),
    KEY idx_compute_policy_facility (facility_v2_id, applicability_status),
    KEY idx_compute_policy_platform (platform_id, applicability_status),
    CONSTRAINT fk_compute_policy_app_rule
      FOREIGN KEY (policy_rule_id) REFERENCES policy_rule_v1(policy_rule_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compute_policy_app_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_policy_app_platform
      FOREIGN KEY (platform_id) REFERENCES compute_service_platform_v1(platform_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_policy_app_listing
      FOREIGN KEY (listing_id) REFERENCES compute_platform_resource_listing_v1(listing_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT='算力政策初筛结果；仅记录资格和待补证据，不确认获批或自动修改经济模型';

/* Official source snapshots. The local raw file path and SHA-256 are retained in policy_document_v1. */
INSERT INTO data_source (source_org,source_title,source_url,source_date,source_tier,data_quality,statistical_scope,source_hash,notes)
VALUES
('工业和信息化部等六部门','算力基础设施高质量发展行动计划','https://www.miit.gov.cn/','2023-10-08','A','POLICY_TEXT_EXTRACTED','全国算力基础设施政策文件','0a19701a4d99518e4ab172e6a17023851eaa5b14834df584958a1e2f6e247950','本地政策文件夹原件快照'),
('国家发展改革委、国家数据局等','关于深入实施“东数西算”工程加快构建全国一体化算力网的实施意见','https://www.ndrc.gov.cn/','2023-12-29','A','POLICY_TEXT_EXTRACTED','全国一体化算力网','a68866c207b624bf8c2ae4b34a730a42b2da4b8013f1c70e9e4b6c8b0b8e8cc3','本地政策文件夹原件快照'),
('国家发展改革委、工业和信息化部、国家能源局、国家数据局','数据中心绿色低碳发展专项行动计划','https://www.gov.cn/zhengce/zhengceku/202407/P020240724272072479001.pdf','2024-07-24','A','POLICY_TEXT_EXTRACTED','全国数据中心绿色低碳发展','30d310ed765d51abce62ecdaea1dc79d26fc3e1e3966432ce2c50e541480f39e','本地政策文件夹原件快照'),
('工业和信息化部等六部门','2025年度国家绿色数据中心评价指标体系','https://wap.miit.gov.cn/zwgk/zcwj/wjfb/tz/art/2025/art_d7bfc06fa7c24c41a176fa02919a830d.html','2025-07-07','A','POLICY_TEXT_EXTRACTED','国家绿色数据中心年度评价','77c6deb98895fdd49a6a03cd638e5289c178c5a9a4bcb62c24a0027e949b2255','本地政策文件夹原件快照'),
('工业和信息化部等六部门','2025年度国家绿色算力设施名单','https://www.miit.gov.cn/jgsj/jns/gzdt/art/2025/art_d8a6906d6e5048369ae66b3a40ea20b8.html','2025-12-18','A','POLICY_TEXT_EXTRACTED','2025年度国家绿色算力设施公告','043a881ddcfe09b99de5d89d029b01e7fea94df094770acfab5eaf0c718e01f9','本地政策文件夹原件快照'),
('国家发展改革委、国家能源局、工业和信息化部、国家数据局','关于促进人工智能与能源双向赋能的行动方案','https://www.nea.gov.cn/20260408/','2026-04-08','A','POLICY_TEXT_EXTRACTED','人工智能与能源协同','e13ad7261df6f37587ce00066bcd71e9c9f381ad7de398a932673c5faca1c0c7','本地政策文件夹原件快照'),
('广东省人民政府办公厅','广东省人工智能赋能制造业高质量发展行动方案（2025—2027年）','https://www.gd.gov.cn/gkmlpt/content/4/4787/post_4787001.html','2025-09-29','A','POLICY_TEXT_EXTRACTED','广东省人工智能与制造业','00ff8cf4519470671c4dd865f4d64dd0bc72ac1cf262dd368a42d33b66a90e05','本地政策文件夹原件快照'),
('深圳市工业和信息化局','深圳市打造人工智能先锋城市项目扶持计划操作规程（2026年修订版）','https://www.sz.gov.cn/','2026-04-30','A','POLICY_TEXT_EXTRACTED','深圳市人工智能专项资金','9c8d318f2e0fcd4aa7a2e9bd261497fbed8de4e2f6520ef3ffa152d3e2dd3c0b','本地政策文件夹原件快照'),
('深圳市科技创新局','2026年度深圳市训力券申请指南','https://stic.sz.gov.cn/gkmlpt/content/12/12764/post_12764271.html','2026-05-06','A','POLICY_TEXT_EXTRACTED','深圳市训力券需求方年度申报','4f1bff6238569f6b4cf5bc13fd86facae0382316785ecf005b2dde9ffab12fd1','本地政策文件夹原件快照'),
('深圳市科技创新局','2026年度深圳市训力券形式审查要点','https://stic.sz.gov.cn/gkmlpt/content/12/12764/post_12764271.html','2026-05-06','A','POLICY_TEXT_EXTRACTED','深圳市训力券需求方形式审查','6e31485d6147d16a32a70151deead58491af03be8391f81f950bc2b6ad9f30dc','本地政策文件夹原件快照'),
('深圳市龙岗区工业和信息化局','深圳市龙岗区关于支持人工智能产业引领高质量发展若干措施（修订版）','https://www.lg.gov.cn/','2026-06-17','A','POLICY_TEXT_EXTRACTED','龙岗区人工智能产业支持','3bda6f8b0c6dff3bda0645fd79f9530501ab88beb3c15bf72d2e78c52e80fb4b','本地政策文件夹原件快照'),
('深圳市工业和信息化局','深圳市算力基础设施高质量发展行动计划（2024—2025年）','https://www.sz.gov.cn/cn/xxgk/zfxxgj/zcfg/content/post_11028249.html','2023-12-05','A','VERIFIED_PUBLIC','深圳市算力基础设施行动计划','9d85ea62493f1dbdc357e19cccddd25b859a0164782595d738e3090297222b38','官方网页抓取快照'),
('深圳市发展和改革委员会','深圳市促进绿色低碳产业高质量发展若干措施','https://fgw.sz.gov.cn/zwgk/zcjzcjd/zc/content/post_10362642.html','2022-12-30','A','VERIFIED_PUBLIC','深圳市绿色低碳产业支持','447fd3daafa9a53347d488a9febf73e9725d063f583b36d745af5dbc8fea4ba9','官方网页抓取快照'),
('深圳市科技创新局','2026年度深圳市训力券服务机构入库项目申请指南','https://stic.sz.gov.cn/xxgk/tzgg/content/post_12862792.html','2026-06-25','A','VERIFIED_PUBLIC','深圳市训力券服务机构年度入库','03f8d524d44112b054c6a0453f919b04467cf1ba6674678e996e9f5907263e20','官方网页抓取快照'),
('深圳市科技创新局','2025年度第二批深圳市训力券服务机构入库名单','https://stic.sz.gov.cn/gkmlpt/content/12/12726/post_12726950.html','2026-04-09','A','VERIFIED_PUBLIC','深圳市训力券公开服务机构名录','c9a661199dfd20dfc243a4adbe2a8a9fd534cfd33668e674573f2c6d0c52e050','官方附件抓取快照')
ON DUPLICATE KEY UPDATE
 source_org=VALUES(source_org),source_title=VALUES(source_title),source_url=VALUES(source_url),source_date=VALUES(source_date),source_tier=VALUES(source_tier),data_quality=VALUES(data_quality),statistical_scope=VALUES(statistical_scope),notes=VALUES(notes);

INSERT INTO policy_document_v1 (
  source_id,file_name,file_path,file_sha256,document_title,document_number,issuing_authority,
  policy_level,jurisdiction,policy_category,document_type,issue_date,effective_date,expiry_date,
  policy_status,parse_status,extracted_char_count,official_url,document_summary,status_note
)
SELECT ds.source_id,s.file_name,s.file_path,s.file_sha256,s.document_title,s.document_number,s.issuing_authority,
       s.policy_level,s.jurisdiction,s.policy_category,s.document_type,s.issue_date,s.effective_date,s.expiry_date,
       s.policy_status,s.parse_status,s.extracted_char_count,s.official_url,s.document_summary,s.status_note
FROM (
  SELECT '算力基础设施高质量发展行动计划.pdf' file_name,'etl/sources/compute/2026-08-26/policy/算力基础设施高质量发展行动计划.pdf' file_path,'0a19701a4d99518e4ab172e6a17023851eaa5b14834df584958a1e2f6e247950' file_sha256,'算力基础设施高质量发展行动计划' document_title,'工信部联通信〔2023〕180号' document_number,'工业和信息化部、中央网信办、教育部、国家卫生健康委、人民银行、国务院国资委' issuing_authority,'NATIONAL' policy_level,'全国' jurisdiction,'COMPUTE_INFRASTRUCTURE' policy_category,'ACTION_PLAN' document_type,'2023-10-08' issue_date,NULL effective_date,'2025-12-31' expiry_date,'REFERENCE' policy_status,'PARSED' parse_status,9516 extracted_char_count,'https://www.miit.gov.cn/' official_url,'提出算力设施绿色低碳、上架率监测、液冷储能与绿电融合等方向。' document_summary,'目标期截至2025年，仅作为现行项目的政策背景和尽调参照。' status_note
  UNION ALL SELECT '【关于深入实施“东数西算”工程加快构建全国一体化算力网的实施意见(发改数据〔2023〕1779号)】-国家发展和改革委员会.html','etl/sources/compute/2026-08-26/policy/【关于深入实施“东数西算”工程加快构建全国一体化算力网的实施意见(发改数据〔2023〕1779号)】-国家发展和改革委员会.html','a68866c207b624bf8c2ae4b34a730a42b2da4b8013f1c70e9e4b6c8b0b8e8cc3','关于深入实施“东数西算”工程加快构建全国一体化算力网的实施意见','发改数据〔2023〕1779号','国家发展改革委、国家数据局、中央网信办、工业和信息化部、国家能源局','NATIONAL','全国','COMPUTE_INFRASTRUCTURE','IMPLEMENTATION_OPINION','2023-12-29',NULL,'2025-12-31','REFERENCE','PARSED',5950,'https://www.ndrc.gov.cn/','提出国家枢纽布局、绿电使用、柔性负荷与绿色金融支持方向。','目标期截至2025年，不作为2026年直接补贴依据。'
  UNION ALL SELECT '数据中心绿色低碳发展专项行动计划.pdf','etl/sources/compute/2026-08-26/policy/数据中心绿色低碳发展专项行动计划.pdf','30d310ed765d51abce62ecdaea1dc79d26fc3e1e3966432ce2c50e541480f39e','数据中心绿色低碳发展专项行动计划',NULL,'国家发展改革委、工业和信息化部、国家能源局、国家数据局','NATIONAL','全国','GREEN_DATA_CENTER','ACTION_PLAN','2024-07-24',NULL,'2025-12-31','REFERENCE','PARSED',3856,'https://www.gov.cn/zhengce/zhengceku/202407/P020240724272072479001.pdf','提出PUE、绿电、负荷调节、节能改造及绿色金融和转型金融支持方向。','目标期截至2025年；仍可作为绿色改造尽调参照。'
  UNION ALL SELECT '2025年度国家绿色数据中心评价指标体系.doc','etl/sources/compute/2026-08-26/policy/2025年度国家绿色数据中心评价指标体系.doc','77c6deb98895fdd49a6a03cd638e5289c178c5a9a4bcb62c24a0027e949b2255','2025年度国家绿色数据中心评价指标体系','工信厅联节函〔2025〕279号附件1','工业和信息化部等六部门','NATIONAL','全国','GREEN_DATA_CENTER','EVALUATION_STANDARD','2025-07-07',NULL,'2025-12-31','REFERENCE','PARSED',6250,'https://wap.miit.gov.cn/zwgk/zcwj/wjfb/tz/art/2025/art_d7bfc06fa7c24c41a176fa02919a830d.html','以PUE、可再生能源、需求响应、上架率、IT负荷等16项指标评价绿色数据中心。','年度评价指标；用于建立2026年待补证据清单，不代表当前认定。'
  UNION ALL SELECT '2025年度国家绿色算力设施名单.pdf','etl/sources/compute/2026-08-26/policy/2025年度国家绿色算力设施名单.pdf','043a881ddcfe09b99de5d89d029b01e7fea94df094770acfab5eaf0c718e01f9','2025年度国家绿色算力设施名单',NULL,'工业和信息化部、国家发展改革委、商务部、金融监管总局、国管局、国家能源局','NATIONAL','全国','GREEN_DATA_CENTER','RECOGNITION_LIST','2025-12-18',NULL,NULL,'REFERENCE','PARSED',1338,'https://www.miit.gov.cn/jgsj/jns/gzdt/art/2025/art_d8a6906d6e5048369ae66b3a40ea20b8.html','2025年度国家绿色算力设施公告名单。','仅代表名单所列设施，不推断其他设施不符合绿色条件。'
  UNION ALL SELECT '国家发展改革委 国家能源局 工业和信息化部 国家数据局印发《关于促进人工智能与能源双向赋能的行动方案》的通知-国家能源局.html','etl/sources/compute/2026-08-26/policy/国家发展改革委 国家能源局 工业和信息化部 国家数据局印发《关于促进人工智能与能源双向赋能的行动方案》的通知-国家能源局.html','e13ad7261df6f37587ce00066bcd71e9c9f381ad7de398a932673c5faca1c0c7','关于促进人工智能与能源双向赋能的行动方案','国能发科技〔2026〕34号','国家发展改革委、国家能源局、工业和信息化部、国家数据局','NATIONAL','全国','COMPUTE_ENERGY_SYNERGY','ACTION_PLAN','2026-04-08','2026-04-08',NULL,'EFFECTIVE','PARSED',6901,'https://www.nea.gov.cn/20260408/','提出算力设施绿电、绿证、绿电直连、需求响应、绿色金融和REITs方向。','无固定补贴金额，须按地方细则和项目资料逐项核验。'
  UNION ALL SELECT '广东省人民政府办公厅关于印发《广东省人工智能赋能制造业高质量发展行动方案（2025—2027年）》的通知.html','etl/sources/compute/2026-08-26/policy/广东省人民政府办公厅关于印发《广东省人工智能赋能制造业高质量发展行动方案（2025—2027年）》的通知.html','00ff8cf4519470671c4dd865f4d64dd0bc72ac1cf262dd368a42d33b66a90e05','广东省人工智能赋能制造业高质量发展行动方案（2025—2027年）',NULL,'广东省人民政府办公厅','PROVINCIAL','广东省','AI_INDUSTRY','ACTION_PLAN','2025-09-29','2025-09-29','2027-12-31','EFFECTIVE','PARSED',4944,'https://www.gd.gov.cn/gkmlpt/content/4/4787/post_4787001.html','提出算力券、训力券、贴息、风险补偿及融资租赁等支持方向。','资金标准由后续省市申报指南确定，不能直接计入收入。'
  UNION ALL SELECT '深圳市工业和信息化局打造人工智能先锋城市项目扶持计划操作规程（2026年修订版）.html','etl/sources/compute/2026-08-26/policy/深圳市工业和信息化局打造人工智能先锋城市项目扶持计划操作规程（2026年修订版）.html','9c8d318f2e0fcd4aa7a2e9bd261497fbed8de4e2f6520ef3ffa152d3e2dd3c0b','深圳市打造人工智能先锋城市项目扶持计划操作规程（2026年修订版）','深工信规〔2024〕13号配套规程','深圳市工业和信息化局','MUNICIPAL','深圳市','AI_INDUSTRY','OPERATING_RULE','2026-04-30','2026-04-30',NULL,'EFFECTIVE','PARSED',12342,'https://www.sz.gov.cn/','明确模型券、行业应用示范、创新中心等事后奖补规则及反重复资助要求。','面向项目主体，不等同于设施运营商无条件获得补助。'
  UNION ALL SELECT '2026年度深圳市训力券申请指南.docx','etl/sources/compute/2026-08-26/policy/2026年度深圳市训力券申请指南.docx','4f1bff6238569f6b4cf5bc13fd86facae0382316785ecf005b2dde9ffab12fd1','2026年度深圳市训力券申请指南',NULL,'深圳市科技创新局','MUNICIPAL','深圳市（含深汕特别合作区）','COMPUTE_VOUCHER','APPLICATION_GUIDE','2026-05-06','2026-05-06','2026-06-05','APPLICATION_CLOSED','PARSED',3515,'https://stic.sz.gov.cn/gkmlpt/content/12/12764/post_12764271.html','需求方租用非关联智能算力、合同额达到门槛可申请训力券。','2026年度申报窗口已关闭；保留为客户需求和下一年度政策跟踪依据。'
  UNION ALL SELECT '2026年度深圳市训力券形式审查要点.docx','etl/sources/compute/2026-08-26/policy/2026年度深圳市训力券形式审查要点.docx','6e31485d6147d16a32a70151deead58491af03be8391f81f950bc2b6ad9f30dc','2026年度深圳市训力券形式审查要点',NULL,'深圳市科技创新局','MUNICIPAL','深圳市（含深汕特别合作区）','COMPUTE_VOUCHER','APPLICATION_CHECKLIST','2026-05-06','2026-05-06','2026-06-05','APPLICATION_CLOSED','PARSED',526,'https://stic.sz.gov.cn/gkmlpt/content/12/12764/post_12764271.html','明确独立法人、非关联合同、服务机构入库、不得重复资助等形式审查要点。','作为尽调资料清单，不产生自动补贴。'
  UNION ALL SELECT '深圳市龙岗区工业和信息化局关于印发《深圳市龙岗区关于支持人工智能产业引领高质量发展若干措施（修订版）》的通知-通知公告-龙岗政府在线.html','etl/sources/compute/2026-08-26/policy/深圳市龙岗区工业和信息化局关于印发《深圳市龙岗区关于支持人工智能产业引领高质量发展若干措施（修订版）》的通知-通知公告-龙岗政府在线.html','3bda6f8b0c6dff3bda0645fd79f9530501ab88beb3c15bf72d2e78c52e80fb4b','深圳市龙岗区关于支持人工智能产业引领高质量发展若干措施（修订版）',NULL,'深圳市龙岗区工业和信息化局','DISTRICT','深圳市龙岗区','AI_INDUSTRY','MEASURES','2026-06-17','2026-06-29','2029-06-28','EFFECTIVE','PARSED',3682,'https://www.lg.gov.cn/','支持龙岗企业购买算力，每家企业每年最高不超过2000万元。','补贴对象为购算力企业；平台或设施仅可能获得需求带动，不可直接记为运营收入。'
  UNION ALL SELECT 'WEB_深圳市算力基础设施高质量发展行动计划（2024—2025年）.html','etl/sources/compute/2026-08-26/policy/sz_compute_infrastructure_plan_2024_2025.html','9d85ea62493f1dbdc357e19cccddd25b859a0164782595d738e3090297222b38','深圳市算力基础设施高质量发展行动计划（2024—2025年）','深工信〔2023〕300号','深圳市工业和信息化局','MUNICIPAL','深圳市','COMPUTE_INFRASTRUCTURE','ACTION_PLAN','2023-12-05',NULL,'2025-12-31','REFERENCE','PARSED',0,'https://www.sz.gov.cn/cn/xxgk/zfxxgj/zcfg/content/post_11028249.html','提出新建数据中心PUE低于1.25、绿色低碳等级4A级以上等2025目标。','目标期已结束，仅作设施公开指标对照。'
  UNION ALL SELECT 'WEB_深圳市促进绿色低碳产业高质量发展若干措施.html','etl/sources/compute/2026-08-26/policy/sz_green_low_carbon_measures_2022.html','447fd3daafa9a53347d488a9febf73e9725d063f583b36d745af5dbc8fea4ba9','深圳市促进绿色低碳产业高质量发展若干措施',NULL,'深圳市人民政府办公厅','MUNICIPAL','深圳市','GREEN_LOW_CARBON','MEASURES','2022-12-12','2022-12-12',NULL,'EFFECTIVE','PARSED',0,'https://fgw.sz.gov.cn/zwgk/zcjzcjd/zc/content/post_10362642.html','支持数据中心虚拟电厂智能化改造、绿色数据中心建设、节能改造和认定奖励。','金额或比例未在条款中统一明确，须以项目申报和评审结果核验。'
  UNION ALL SELECT 'WEB_2026年度深圳市训力券服务机构入库项目申请指南.html','etl/sources/compute/2026-08-26/policy/sz_training_voucher_provider_guide_2026.html','03f8d524d44112b054c6a0453f919b04467cf1ba6674678e996e9f5907263e20','2026年度深圳市训力券服务机构入库项目申请指南',NULL,'深圳市科技创新局','MUNICIPAL','深圳市','COMPUTE_VOUCHER','APPLICATION_GUIDE','2026-06-25','2026-06-25','2026-07-24','APPLICATION_CLOSED','PARSED',0,'https://stic.sz.gov.cn/xxgk/tzgg/content/post_12862792.html','训力券服务机构年度入库指南。','2026年该批入库窗口已关闭；是否入库以最终公布名单为准。'
  UNION ALL SELECT 'WEB_2025年度第二批深圳市训力券服务机构入库名单.xlsx','etl/sources/compute/2026-08-26/policy/sz_training_voucher_providers_2025_b2.xlsx','c9a661199dfd20dfc243a4adbe2a8a9fd534cfd33668e674573f2c6d0c52e050','2025年度第二批深圳市训力券服务机构入库名单',NULL,'深圳市科技创新局','MUNICIPAL','深圳市','COMPUTE_VOUCHER','PUBLIC_LIST','2026-04-09','2026-04-09',NULL,'EFFECTIVE','PARSED',0,'https://stic.sz.gov.cn/gkmlpt/content/12/12726/post_12726950.html','公布4家新增入库及10家新增服务事项的训力券服务机构。','仅对名单和服务事项有效；未核验服务价格、商品配置与合同资格。'
) s
JOIN data_source ds ON ds.source_hash=s.file_sha256
ON DUPLICATE KEY UPDATE
 source_id=VALUES(source_id),file_path=VALUES(file_path),document_title=VALUES(document_title),document_number=VALUES(document_number),issuing_authority=VALUES(issuing_authority),policy_level=VALUES(policy_level),jurisdiction=VALUES(jurisdiction),policy_category=VALUES(policy_category),document_type=VALUES(document_type),issue_date=VALUES(issue_date),effective_date=VALUES(effective_date),expiry_date=VALUES(expiry_date),policy_status=VALUES(policy_status),parse_status=VALUES(parse_status),extracted_char_count=VALUES(extracted_char_count),official_url=VALUES(official_url),document_summary=VALUES(document_summary),status_note=VALUES(status_note);

/* Atomic rules. Values are policy conditions, not assumptions in the current cash-flow model. */
INSERT INTO policy_rule_v1 (
  policy_document_id,rule_code,rule_category,rule_title,applicable_region,applicable_entity_type,
  applicable_asset_type,applicability_summary,requirement_summary,required_evidence,
  rule_value_numeric,rule_value_unit,rule_value_text,model_impact_type,model_target,
  rule_status,interpretation_confidence,source_locator,analysis_note
)
WITH rule_seed AS (
  SELECT '2025年度国家绿色数据中心评价指标体系.doc' file_name,'NAT_GREEN_DC_2025_PUE' rule_code,'GREEN_RECOGNITION' rule_category,'国家绿色数据中心PUE评价门槛' rule_title,'全国' applicable_region,'数据中心所有者' applicable_entity_type,'IDC/EDC/智算中心/高性能计算中心/超算中心' applicable_asset_type,'国家绿色数据中心年度评价的能源高效利用指标。' applicability_summary,'一般类型数据中心PUE高于1.30不得分；申报还须满足其他15项指标。' requirement_summary,'项目级全年总耗电量、信息设备耗电量、服务器能效及物理边界证明。' required_evidence,1.30 rule_value_numeric,'PUE' rule_value_unit,'一般数据中心评分区间1.30至1.10；不等于认定门槛。' rule_value_text,'GATE' model_impact_type,'compute_policy_applicability_result_v1' model_target,'REFERENCE' rule_status,'HIGH' interpretation_confidence,'指标1' source_locator,'当前仅将披露PUE作为待核验证据，不自动判定绿色数据中心。' analysis_note
  UNION ALL SELECT '2025年度国家绿色数据中心评价指标体系.doc','NAT_GREEN_DC_2025_RENEWABLE','GREEN_RECOGNITION','国家绿色数据中心可再生能源利用要求','全国','数据中心所有者','数据中心','评价要求可再生能源利用率达到所在省消纳责任权重后才计分。','可再生能源利用率需达到所在省消纳责任权重；80%及以上可得该项满分。','绿电/绿证交易凭证、可再生能源利用率计算口径、所在省消纳责任权重。',NULL,NULL,'达到所在地消纳责任权重后计分；80%及以上得8分。','GATE','compute_policy_applicability_result_v1','REFERENCE','HIGH','指标2','缺少项目级绿电比例时不得将绿色金融或绿色标签视为已满足。'
  UNION ALL SELECT '2025年度国家绿色数据中心评价指标体系.doc','NAT_GREEN_DC_2025_DEMAND_RESPONSE','GREEN_RECOGNITION','国家绿色数据中心需求响应能力','全国','数据中心所有者','数据中心','数字化能碳管理评价可计入负荷调节能力。','需求侧响应能力达到最大用电负荷5%或以上可取得相应佐证分。','最大负荷、可调能力测试、聚合/响应合同、计量数据。',0.05,'最大用电负荷比例','达到最大用电负荷5%或以上。','GATE','compute_policy_applicability_result_v1','REFERENCE','HIGH','指标4','用于识别算电协同和虚拟电厂的工程准备度，不作为既有收入。'
  UNION ALL SELECT '2025年度国家绿色数据中心评价指标体系.doc','NAT_GREEN_DC_2025_RACK_UTILIZATION','GREEN_RECOGNITION','国家绿色数据中心上架率评价','全国','数据中心所有者','数据中心','算力资源高效利用评价。','已安装机柜至少达到设计机柜数50%，且上架率60%及以上才可得分。','设计/已安装/有效运行机柜数及统计期证明。',0.60,'上架率','60%至80%对应评分区间；80%及以上满分。','GATE','compute_operation_scenario_v1','REFERENCE','HIGH','指标13','当前利用率为研究情景，不能代替机房实际上架率。'
  UNION ALL SELECT '2025年度国家绿色数据中心评价指标体系.doc','NAT_GREEN_DC_2025_IT_LOAD','GREEN_RECOGNITION','国家绿色数据中心信息设备负荷利用评价','全国','数据中心所有者','数据中心','以机柜年均用电功率与标称功率的比值评价IT负荷。','信息设备负荷使用率达到60%及以上可得该项满分。','项目级IT负荷、标称功率、全年计量数据。',0.60,'IT负荷利用率','30%至60%评分，60%及以上满分。','GATE','compute_operation_scenario_v1','REFERENCE','HIGH','指标14','现有35%/65%/85%为经营情景，不能视为已披露的IT负荷。'
  UNION ALL SELECT '绿色金融支持项目目录（2025 年版）.pdf','NAT_GREEN_FINANCE_2025_GREEN_DC','GREEN_FINANCE','绿色金融目录中的绿色数据中心','全国','项目业主/融资主体','IDC/EDC/智算中心/高性能计算中心/超算中心','目录6.6.2将满足GB 40879二级能效水平的绿色数据中心建设活动纳入支持范围。','贷款或债券资金用途应对应绿色数据中心建设或改造，并满足目录和金融机构尽调要求。','项目用途、PUE/能效等级、设备清单、能耗与碳减排说明、资金使用计划。',2.00,'GB 40879能效等级','数据中心能效不低于GB 40879二级能效水平。','GATE','compute_bank_recommendation_v1','EFFECTIVE','HIGH','目录6.6.2','仅形成绿色金融初筛资格；不承诺利率、期限、额度或授信通过。'
  UNION ALL SELECT '国家发展改革委 国家能源局 工业和信息化部 国家数据局印发《关于促进人工智能与能源双向赋能的行动方案》的通知-国家能源局.html','NAT_AI_ENERGY_2026_GREEN_POWER','COMPUTE_ENERGY','算力设施绿电与绿证消费','全国','算力设施项目业主','算力设施','行动方案支持算力设施参与绿证绿电交易并提升绿电消费比例。','新建及改扩建项目应将可再生能源、PUE、绿电消费比例和余热利用纳入节能降碳审查评价。','绿电交易/绿证凭证、可再生能源方案、PUE、节能审查文件、余热利用方案。',NULL,NULL,'绿电使用占比为重要参考指标。','INPUT_REQUIRED','compute_operation_scenario_v1','EFFECTIVE','HIGH','第（四）（六）项','尚未有项目级绿电采购量，不向电费模型自动施加绿电溢价或折扣。'
  UNION ALL SELECT '国家发展改革委 国家能源局 工业和信息化部 国家数据局印发《关于促进人工智能与能源双向赋能的行动方案》的通知-国家能源局.html','NAT_AI_ENERGY_2026_MARKET','COMPUTE_ENERGY','算力设施参与需求响应等电力市场方向','全国','算力设施项目业主/负荷聚合主体','算力设施/可调负荷','支持具备条件的算力设施参与电能量、辅助服务和需求响应市场。','须满足当地市场注册、计量、可观可测可调可控和调度规则。','接入方案、负荷曲线、可调能力测试、聚合合同、市场注册和结算规则。',NULL,NULL,'支持以多种形式参与相关市场交易。','SCENARIO','compute_policy_applicability_result_v1','EFFECTIVE','HIGH','第（九）项','没有广东/深圳项目级可调能力与市场结算证据前，不计入VPP收入。'
  UNION ALL SELECT '国家发展改革委 国家能源局 工业和信息化部 国家数据局印发《关于促进人工智能与能源双向赋能的行动方案》的通知-国家能源局.html','NAT_AI_ENERGY_2026_GREEN_FINANCE','GREEN_FINANCE','人工智能与能源融合项目绿色融资方向','全国','算力设施项目业主/融资主体','绿色算力基础设施','鼓励对符合绿色金融目录的算力基础设施提供资金支持并探索REITs、绿色债券等。','仍须满足目录、项目合规和金融机构自主风控要求。','绿色项目认定材料、项目现金流、资金用途、环境效益和融资主体信用资料。',NULL,NULL,'鼓励金融机构提供资金支持，不设统一利率或债务比例。','GATE','compute_bank_recommendation_v1','EFFECTIVE','HIGH','第（二十六）项','不改变现有三档研究信贷规则，仅提供绿色金融产品尽调方向。'
  UNION ALL SELECT '广东省人民政府办公厅关于印发《广东省人工智能赋能制造业高质量发展行动方案（2025—2027年）》的通知.html','GD_AI_2025_COMPUTE_VOUCHER','COMPUTE_VOUCHER','广东工业智能算力应用支持方向','广东省','工业企业/人工智能企业','智算资源/边缘数据中心','支持企业利用韶关和各地算力资源训练工业模型，发挥算力券和训力券降低使用成本。','具体对象、比例和额度以省市年度指南为准。','企业所在地、工业模型应用、服务合同、后续申报指南和资金证明。',NULL,NULL,'算力券、训力券、贴息、风险补偿、融资租赁为支持方向。','NO_AUTOMATIC_EFFECT','compute_economics_result_v1','EFFECTIVE','HIGH','第三、十四项','这是需求侧和项目主体支持方向，不能作为平台公开商品的确定收入。'
  UNION ALL SELECT '深圳市工业和信息化局打造人工智能先锋城市项目扶持计划操作规程（2026年修订版）.html','SZ_AI_2026_DEMONSTRATION_GRANT','AI_INCENTIVE','深圳人工智能行业应用示范资助','深圳市','深圳项目建设主体','AI行业应用项目','对符合条件的示范或标杆应用项目实行事后奖补。','核定实际投入30%；示范项目最高200万元，标杆项目最高1000万元；不得与同一建设内容重复申报。','项目实施地、审计投入、建设成果、申报主体信用和非重复资助声明。',0.30,'核定实际投入比例','示范最高200万元；标杆最高1000万元。','SCENARIO','compute_project_economics_result_v1','EFFECTIVE','HIGH','第八、九、十一条','对算力租用或设施项目只有在项目主体、投入和申报类别确定后才可独立建立政策情景。'
  UNION ALL SELECT '2026年度深圳市训力券申请指南.docx','SZ_TRAINING_VOUCHER_2026_DEMAND','COMPUTE_VOUCHER','深圳2026训力券需求方支持','深圳市（含深汕特别合作区）','深圳企业/高校/科研机构','租用智能算力的AI大模型训练推理服务','需求方年租用非关联智能算力达到50万元可申请训力券。','一般单次抵扣不超过合同金额50%，年度累计最高1000万元；须向已入库服务机构采购。','独立法人资格、非关联服务合同、服务机构入库资格、AI训练推理说明、财政资金不重复支持证明。',0.50,'合同金额比例','年度累计最高1000万元；新成立未满一年企业最高60%。','NO_AUTOMATIC_EFFECT','compute_platform_resource_listing_v1','APPLICATION_CLOSED','HIGH','第二部分支持标准','补贴支付给需求方，现有公开算力商品不应自动加计该部分收入；2026申报窗口已关闭。'
  UNION ALL SELECT '2026年度深圳市训力券形式审查要点.docx','SZ_TRAINING_VOUCHER_2026_EVIDENCE','DATA_REQUIREMENT','深圳训力券合同与反重复资助核验','深圳市（含深汕特别合作区）','训力券需求方','智能算力服务合同','指南列明服务合同期限、服务机构批次、非重复支持及材料完整性要求。','申请方不能同时取得服务机构入库资格和申领训力券；同一项目财政支持不得超过合同50%。','合同日期、服务机构批次、合同内容与金额、其他财政资金证明、申请附件。',0.50,'同一项目合同比例','其他智能算力财政支持累计不超过服务合同50%。','GATE','compute_policy_applicability_result_v1','APPLICATION_CLOSED','HIGH','形式审查要点3至5','为后续客户尽调清单，不对当前商品价格做折扣假设。'
  UNION ALL SELECT '深圳市龙岗区工业和信息化局关于印发《深圳市龙岗区关于支持人工智能产业引领高质量发展若干措施（修订版）》的通知-通知公告-龙岗政府在线.html','LG_AI_2026_COMPUTE_PURCHASE','COMPUTE_VOUCHER','龙岗区企业购买算力支持','深圳市龙岗区','龙岗区企业','购买算力服务','支持龙岗企业购买算力，形成区域算力需求侧政策线索。','资金总额控制，具体申报与核验条件以主管部门执行为准。','企业注册/经营地、算力采购合同、项目申报材料、主管部门审核结果。',20000000.00,'元/企业/年','每家企业每年最高不超过2000万元。','NO_AUTOMATIC_EFFECT','compute_platform_resource_listing_v1','EFFECTIVE','HIGH','第一条第（二）项','对象是购算力企业，不能将2000万元作为任一设施或平台的确定收入。'
  UNION ALL SELECT 'WEB_深圳市算力基础设施高质量发展行动计划（2024—2025年）.html','SZ_COMPUTE_2025_PUE_REFERENCE','COMPUTE_ENERGY','深圳算力行动计划PUE目标对照','深圳市','新建数据中心项目主体','新建数据中心','行动计划提出2025年新建数据中心PUE降低至1.25以下。','目标期已结束；仅对照公开PUE，不能将其视为2026直接准入或补贴条件。','项目级PUE、建设投运时间、绿色低碳等级证明。',1.25,'PUE','2025年目标：PUE低于1.25、绿色低碳等级4A级以上。','NO_AUTOMATIC_EFFECT','compute_policy_applicability_result_v1','REFERENCE','HIGH','总体目标绿色安全','在网站展示为历史政策对标，避免对存量设施作错误合规判断。'
  UNION ALL SELECT 'WEB_深圳市促进绿色低碳产业高质量发展若干措施.html','SZ_GREEN_VPP_DATA_CENTER','VPP_INCENTIVE','深圳数据中心虚拟电厂智能化改造支持','深圳市','数据中心业主/运营主体','数据中心可调负荷/智能化改造','将数据中心列入可支持的虚拟电厂场景；可与需求响应、综合能源服务协同。','经评审的智能化改造按设备投资给予一定比例支持；具体比例与获批结果未统一披露。','智能化改造设备清单、可调能力、VPP接入方案、评审/申报材料、市场结算资料。',NULL,NULL,'按设备投资给予一定比例财政支持；比例未在条款统一明确。','SCENARIO','compute_policy_applicability_result_v1','EFFECTIVE','HIGH','第三部分第（六）项','先展示为工程与尽调机会；未有比例、工程量和结算证据前不进入现金流。'
  UNION ALL SELECT 'WEB_深圳市促进绿色低碳产业高质量发展若干措施.html','SZ_GREEN_DC_RECOGNITION','GREEN_RECOGNITION','深圳绿色数据中心建设与认定奖励方向','深圳市','数据中心业主/运营主体','绿色数据中心/节能改造','支持绿色数据中心建设、存量节能降碳改造和绿色数据中心认定奖励。','具体奖励需以认定结果和配套申报要求为准。','绿色数据中心认定、PUE/绿电/能碳数据、节能改造方案、项目验收资料。',NULL,NULL,'支持建设、改造和对国家省市级绿色数据中心给予奖励。','NO_AUTOMATIC_EFFECT','compute_policy_applicability_result_v1','EFFECTIVE','HIGH','第五部分第（二十）项','没有公开获奖/认定或申报指南时，不能量化奖励金额。'
  UNION ALL SELECT '2025年度国家绿色算力设施名单.pdf','NAT_GREEN_COMPUTE_LIST_2025','GREEN_RECOGNITION','2025国家绿色算力设施名单核验','全国','已公告算力设施','数据中心/算力设施','名单是已公告的绿色算力设施事实，不等同于其他设施不符合政策。','仅可按设施名称和运营主体进行精确匹配。','官方名单、设施名称、运营主体和物理边界的匹配证据。',NULL,NULL,'年度名单事实核验。','DATA_GOVERNANCE','compute_policy_applicability_result_v1','REFERENCE','HIGH','公告名单','本轮15个深圳设施未发现与2025名单的精确名称匹配；不输出负面绿色评价。'
)
SELECT d.policy_document_id,s.rule_code,s.rule_category,s.rule_title,s.applicable_region,s.applicable_entity_type,
       s.applicable_asset_type,s.applicability_summary,s.requirement_summary,s.required_evidence,
       s.rule_value_numeric,s.rule_value_unit,s.rule_value_text,s.model_impact_type,s.model_target,
       s.rule_status,s.interpretation_confidence,s.source_locator,s.analysis_note
FROM rule_seed s JOIN policy_document_v1 d ON d.file_name=s.file_name
ON DUPLICATE KEY UPDATE
 policy_document_id=VALUES(policy_document_id),rule_category=VALUES(rule_category),rule_title=VALUES(rule_title),applicable_region=VALUES(applicable_region),applicable_entity_type=VALUES(applicable_entity_type),applicable_asset_type=VALUES(applicable_asset_type),applicability_summary=VALUES(applicability_summary),requirement_summary=VALUES(requirement_summary),required_evidence=VALUES(required_evidence),rule_value_numeric=VALUES(rule_value_numeric),rule_value_unit=VALUES(rule_value_unit),rule_value_text=VALUES(rule_value_text),model_impact_type=VALUES(model_impact_type),model_target=VALUES(model_target),rule_status=VALUES(rule_status),interpretation_confidence=VALUES(interpretation_confidence),source_locator=VALUES(source_locator),analysis_note=VALUES(analysis_note);

/* Public service-provider registry: 4 new registrations + 10 newly approved service scopes. */
INSERT INTO compute_policy_provider_registry_v1 (
  policy_document_id,provider_name,admission_batch,admission_type,provider_status,service_scope,source_locator,official_url,data_type,data_quality,notes
)
SELECT d.policy_document_id,s.provider_name,'2025年度第二批' admission_batch,s.admission_type,'LISTED' provider_status,'智能算力服务；具体服务事项、配置与收费标准以公告附件及合同为准。',s.source_locator,'https://stic.sz.gov.cn/gkmlpt/content/12/12726/post_12726950.html','PUBLIC','VERIFIED_PUBLIC','公开名单仅证明服务机构或新增服务事项；不证明本平台全部商品均适用训力券。'
FROM (
 SELECT '深圳坪山深空引擎科技有限公司' provider_name,'新增入库' admission_type,'名单第1项' source_locator UNION ALL
 SELECT '深圳云天畅想信息科技有限公司','新增入库','名单第2项' UNION ALL
 SELECT '深圳京东云智弘云计算有限公司','新增入库','名单第3项' UNION ALL
 SELECT '深圳首云科技有限公司','新增入库','名单第4项' UNION ALL
 SELECT '金山云（深圳）边缘计算科技有限公司','新增服务事项','名单第5项' UNION ALL
 SELECT '中国移动通信集团广东有限公司深圳分公司','新增服务事项','名单第6项' UNION ALL
 SELECT '深圳天顿数据科技有限公司','新增服务事项','名单第7项' UNION ALL
 SELECT '北京百度网讯科技有限公司深圳分公司','新增服务事项','名单第8项' UNION ALL
 SELECT '深圳华为云计算技术有限公司','新增服务事项','名单第9项' UNION ALL
 SELECT '深圳市智城翼云科技有限公司','新增服务事项','名单第10项' UNION ALL
 SELECT '腾讯云计算（北京）有限责任公司深圳市分公司','新增服务事项','名单第11项' UNION ALL
 SELECT '深圳市前海新型互联网交换中心有限公司','新增服务事项','名单第12项' UNION ALL
 SELECT '中国电信股份有限公司深圳分公司','新增服务事项','名单第13项' UNION ALL
 SELECT '深圳阿里云计算技术有限公司','新增服务事项','名单第14项'
) s JOIN policy_document_v1 d ON d.file_name='WEB_2025年度第二批深圳市训力券服务机构入库名单.xlsx'
ON DUPLICATE KEY UPDATE admission_type=VALUES(admission_type),provider_status=VALUES(provider_status),service_scope=VALUES(service_scope),source_locator=VALUES(source_locator),official_url=VALUES(official_url),data_quality=VALUES(data_quality),notes=VALUES(notes);

INSERT INTO compute_policy_provider_platform_match_v1 (
  provider_registry_id,platform_id,match_status,match_method,match_basis,verified_at,data_type,notes
)
SELECT pr.provider_registry_id,p.platform_id,'MATCHED','EXACT_OPERATOR_NAME',
       '服务机构公开名称与平台运营主体“深圳市智城翼云科技有限公司”完全一致。','2026-08-26','PUBLIC_DERIVED',
       '仅证明该运营主体在2025年度第二批名单中有新增服务事项；具体商品和客户合同仍需核验。'
FROM compute_policy_provider_registry_v1 pr
JOIN compute_service_platform_v1 p ON p.operator_name=pr.provider_name
WHERE pr.provider_name='深圳市智城翼云科技有限公司'
ON DUPLICATE KEY UPDATE match_status=VALUES(match_status),match_method=VALUES(match_method),match_basis=VALUES(match_basis),verified_at=VALUES(verified_at),data_type=VALUES(data_type),notes=VALUES(notes);

/* Facility policy preliminary screening. All financial effects remain inactive until the evidence listed below is supplied. */
INSERT INTO compute_policy_applicability_result_v1 (
  policy_rule_id,subject_type,subject_key,facility_v2_id,platform_id,listing_id,applicability_status,
  support_side,impact_type,model_treatment,eligibility_summary,required_evidence,known_evidence,
  monetary_value_yuan,monetary_value_note,assessment_date,data_type,model_version
)
SELECT r.policy_rule_id,'FACILITY',f.facility_code,f.facility_v2_id,NULL,NULL,
       CASE WHEN f.facility_code IN ('SZCF009','SZCF016') THEN 'POTENTIALLY_ELIGIBLE' ELSE 'INSUFFICIENT_EVIDENCE' END,
       'FACILITY_OPERATOR','GREEN_RECOGNITION','GATE_ONLY',
       CASE
         WHEN f.facility_code='SZCF009' THEN '已披露项目级PUE 1.244，可作为绿色数据中心自评价的单项证据；其余评价指标尚未公开。'
         WHEN f.facility_code='SZCF016' THEN '已披露整体设施PUE 1.21（运营商口径）及三期项目PUE 1.228（交易所披露），可作为绿色数据中心自评价的单项证据；两者统计边界不同，其余指标仍须补充。'
         ELSE '设施类型属于政策可能覆盖范围，但缺少项目级PUE、绿电、上架率、IT负荷和能碳管理证据。'
       END,
       '项目级全年PUE、绿电/绿证、需求响应能力、机柜上架率、IT负荷、能碳管理及绿色运维材料。',
       CASE
         WHEN f.facility_code='SZCF009' THEN '公开披露全年PUE 1.244。'
         WHEN f.facility_code='SZCF016' THEN '整体设施PUE 1.21为运营商公开披露；三期项目PUE 1.228为交易所披露。'
         ELSE '当前没有足以完成国家绿色数据中心16项评价的公开证据。'
       END,
       NULL,NULL,'2026-08-26','POLICY_DERIVED','COMPUTE_POLICY_V1'
FROM enterprise_data_center_v2 f
JOIN policy_rule_v1 r ON r.rule_code='NAT_GREEN_DC_2025_PUE'
ON DUPLICATE KEY UPDATE applicability_status=VALUES(applicability_status),eligibility_summary=VALUES(eligibility_summary),required_evidence=VALUES(required_evidence),known_evidence=VALUES(known_evidence),assessment_date=VALUES(assessment_date),data_type=VALUES(data_type);

INSERT INTO compute_policy_applicability_result_v1 (
  policy_rule_id,subject_type,subject_key,facility_v2_id,applicability_status,support_side,impact_type,model_treatment,
  eligibility_summary,required_evidence,known_evidence,assessment_date,data_type,model_version
)
SELECT r.policy_rule_id,'FACILITY',f.facility_code,f.facility_v2_id,'POTENTIALLY_ELIGIBLE','PROJECT_OWNER','GREEN_FINANCE_SCREENING','GATE_ONLY',
       '绿色金融目录覆盖符合能效要求的绿色数据中心建设活动；当前设施尚无可核验的绿色改造或建设资金用途。',
       '项目资金用途、能效等级/PUE、设备清单、节能或碳减排说明、融资主体和还款来源资料。',
       '设施为公开算力/数据中心事实记录；未将此状态解释为已获绿色贷款。','2026-08-26','POLICY_DERIVED','COMPUTE_POLICY_V1'
FROM enterprise_data_center_v2 f JOIN policy_rule_v1 r ON r.rule_code='NAT_GREEN_FINANCE_2025_GREEN_DC'
ON DUPLICATE KEY UPDATE applicability_status=VALUES(applicability_status),eligibility_summary=VALUES(eligibility_summary),required_evidence=VALUES(required_evidence),known_evidence=VALUES(known_evidence),assessment_date=VALUES(assessment_date),data_type=VALUES(data_type);

INSERT INTO compute_policy_applicability_result_v1 (
  policy_rule_id,subject_type,subject_key,facility_v2_id,applicability_status,support_side,impact_type,model_treatment,
  eligibility_summary,required_evidence,known_evidence,assessment_date,data_type,model_version
)
SELECT r.policy_rule_id,'FACILITY',f.facility_code,f.facility_v2_id,'POTENTIALLY_ELIGIBLE','FACILITY_OPERATOR','ENERGY_FLEXIBILITY','SCENARIO_CANDIDATE',
       '深圳数据中心属于虚拟电厂智能化改造支持场景；当前没有可调负荷、接入方案和评审结果。',
       '可调负荷清单、智能控制设备、计量与通信方案、VPP接入/聚合合同、需求响应测试和评审材料。',
       '设施地点在深圳市或深汕特别合作区；无项目级VPP接入公开证据。','2026-08-26','POLICY_DERIVED','COMPUTE_POLICY_V1'
FROM enterprise_data_center_v2 f JOIN policy_rule_v1 r ON r.rule_code='SZ_GREEN_VPP_DATA_CENTER'
WHERE f.city_name='深圳市' OR f.locality_scope LIKE '%深圳%'
ON DUPLICATE KEY UPDATE applicability_status=VALUES(applicability_status),eligibility_summary=VALUES(eligibility_summary),required_evidence=VALUES(required_evidence),known_evidence=VALUES(known_evidence),assessment_date=VALUES(assessment_date),data_type=VALUES(data_type);

INSERT INTO compute_policy_applicability_result_v1 (
  policy_rule_id,subject_type,subject_key,facility_v2_id,applicability_status,support_side,impact_type,model_treatment,
  eligibility_summary,required_evidence,known_evidence,assessment_date,data_type,model_version
)
SELECT r.policy_rule_id,'FACILITY',f.facility_code,f.facility_v2_id,'INSUFFICIENT_EVIDENCE','FACILITY_OPERATOR','GREEN_RECOGNITION','NO_AUTOMATIC_EFFECT',
       '深圳支持绿色数据中心建设、改造和认定奖励；当前尚未找到该设施已获认定、获奖或已申报的公开证明。',
       '绿色数据中心认定/奖项、PUE与绿电数据、改造方案、验收和申报材料。',
       '未以设施名称匹配到公开认定或奖励文件。','2026-08-26','POLICY_DERIVED','COMPUTE_POLICY_V1'
FROM enterprise_data_center_v2 f JOIN policy_rule_v1 r ON r.rule_code='SZ_GREEN_DC_RECOGNITION'
WHERE f.city_name='深圳市' OR f.locality_scope LIKE '%深圳%'
ON DUPLICATE KEY UPDATE applicability_status=VALUES(applicability_status),eligibility_summary=VALUES(eligibility_summary),required_evidence=VALUES(required_evidence),known_evidence=VALUES(known_evidence),assessment_date=VALUES(assessment_date),data_type=VALUES(data_type);

INSERT INTO compute_policy_applicability_result_v1 (
  policy_rule_id,subject_type,subject_key,facility_v2_id,applicability_status,support_side,impact_type,model_treatment,
  eligibility_summary,required_evidence,known_evidence,assessment_date,data_type,model_version
)
SELECT r.policy_rule_id,'FACILITY',f.facility_code,f.facility_v2_id,'REFERENCE_ONLY','FACILITY_OPERATOR','GREEN_RECOGNITION','NO_AUTOMATIC_EFFECT',
       '未在2025年度国家绿色算力设施名单中发现该设施名称的精确匹配；该结果不构成不符合绿色条件的判断。',
       '设施名称、运营主体、物理边界与后续年度国家名单的精确匹配证据。',
       '已用2025年度60项国家绿色算力设施公告名单进行名称精确比对。','2026-08-26','PUBLIC_DERIVED','COMPUTE_POLICY_V1'
FROM enterprise_data_center_v2 f JOIN policy_rule_v1 r ON r.rule_code='NAT_GREEN_COMPUTE_LIST_2025'
ON DUPLICATE KEY UPDATE applicability_status=VALUES(applicability_status),eligibility_summary=VALUES(eligibility_summary),required_evidence=VALUES(required_evidence),known_evidence=VALUES(known_evidence),assessment_date=VALUES(assessment_date),data_type=VALUES(data_type);

CREATE OR REPLACE VIEW v_compute_policy_facility_summary_v1 AS
SELECT
  f.facility_v2_id,f.facility_code,f.official_name,f.city_name,f.district_name,f.operator_name,
  MAX(CASE WHEN r.rule_code='NAT_GREEN_DC_2025_PUE' THEN a.applicability_status END) AS green_data_center_status,
  MAX(CASE WHEN r.rule_code='NAT_GREEN_FINANCE_2025_GREEN_DC' THEN a.applicability_status END) AS green_finance_status,
  MAX(CASE WHEN r.rule_code='SZ_GREEN_VPP_DATA_CENTER' THEN a.applicability_status END) AS vpp_status,
  MAX(CASE WHEN r.rule_code='SZ_GREEN_DC_RECOGNITION' THEN a.applicability_status END) AS shenzhen_green_program_status,
  MAX(CASE WHEN r.rule_code='NAT_GREEN_COMPUTE_LIST_2025' THEN a.applicability_status END) AS national_list_check_status,
  SUM(a.applicability_status='POTENTIALLY_ELIGIBLE') AS potential_count,
  SUM(a.applicability_status='INSUFFICIENT_EVIDENCE') AS evidence_gap_count,
  MAX(a.assessment_date) AS assessed_at,
  '需补项目级PUE、绿电/绿证、IT负荷/上架率、可调负荷和改造资金用途后，才能进入政策调整情景。' AS priority_action
FROM enterprise_data_center_v2 f
LEFT JOIN compute_policy_applicability_result_v1 a
  ON a.facility_v2_id=f.facility_v2_id AND a.model_version='COMPUTE_POLICY_V1'
LEFT JOIN policy_rule_v1 r ON r.policy_rule_id=a.policy_rule_id
GROUP BY f.facility_v2_id,f.facility_code,f.official_name,f.city_name,f.district_name,f.operator_name;

CREATE OR REPLACE VIEW v_compute_policy_platform_summary_v1 AS
SELECT
  p.platform_id,p.platform_code,p.platform_name,p.operator_name,
  COUNT(m.provider_platform_match_id) AS matched_provider_count,
  MAX(m.match_status) AS provider_match_status,
  GROUP_CONCAT(pr.provider_name ORDER BY pr.provider_name SEPARATOR '；') AS matched_provider_names,
  '服务机构名录只证明主体及已公告服务事项，商品配置、价格、客户资格和合同期限仍须逐笔核验。' AS boundary_note
FROM compute_service_platform_v1 p
LEFT JOIN compute_policy_provider_platform_match_v1 m ON m.platform_id=p.platform_id
LEFT JOIN compute_policy_provider_registry_v1 pr ON pr.provider_registry_id=m.provider_registry_id
GROUP BY p.platform_id,p.platform_code,p.platform_name,p.operator_name;
