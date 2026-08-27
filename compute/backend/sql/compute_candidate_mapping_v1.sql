USE spdb_power_finance;

/*
  Public-indicative mapping layer V1

  Purpose:
  - preserve a verified physical facility as its own fact record;
  - allow public provider/facility clues to be attached to a marketplace SKU;
  - prevent an indicative clue from overwriting listing.facility_v2_id;
  - retain a real disclosed financing case separately from all scenario outputs.

  A FACILITY_CANDIDATE is deliberately NOT a confirmed deployment location.
  Only a direct SKU / order / provider / location proof may create a direct
  facility_v2_id relationship on compute_platform_resource_listing_v1.
*/

CREATE TABLE IF NOT EXISTS compute_listing_candidate_mapping_v1 (
    candidate_mapping_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    listing_id BIGINT UNSIGNED NOT NULL,
    candidate_mapping_type VARCHAR(48) NOT NULL COMMENT 'EXTERNAL_SAME_GPU_REFERENCE/PROVIDER_CANDIDATE/FACILITY_CANDIDATE',
    candidate_entity_type VARCHAR(32) NOT NULL COMMENT 'PROVIDER/FACILITY/RESOURCE_POOL',
    candidate_name VARCHAR(255) NOT NULL,
    candidate_facility_v2_id BIGINT UNSIGNED NULL,
    mapping_status VARCHAR(32) NOT NULL COMMENT 'UNMAPPED/INDICATIVE/CONFIRMED',
    confidence_level VARCHAR(16) NOT NULL COMMENT 'NONE/LOW/MEDIUM/HIGH',
    confidence_score DECIMAL(5,4) NOT NULL DEFAULT 0,
    direct_sku_evidence_flag TINYINT(1) NOT NULL DEFAULT 0,
    platform_relation_evidence_flag TINYINT(1) NOT NULL DEFAULT 0,
    candidate_asset_evidence_flag TINYINT(1) NOT NULL DEFAULT 0,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    evidence_summary TEXT NOT NULL,
    boundary_note TEXT NOT NULL,
    verified_at DATE NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC_INDICATIVE',
    data_quality VARCHAR(24) NOT NULL DEFAULT 'PUBLIC_INDICATIVE',
    model_version VARCHAR(40) NOT NULL DEFAULT 'COMPUTE_CANDIDATE_MAPPING_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_candidate_mapping (listing_id,candidate_mapping_type,candidate_name,model_version),
    KEY idx_compute_candidate_listing (listing_id,mapping_status,confidence_level),
    KEY idx_compute_candidate_facility (candidate_facility_v2_id),
    KEY idx_compute_candidate_source (source_id),
    CONSTRAINT fk_compute_candidate_listing
      FOREIGN KEY (listing_id) REFERENCES compute_platform_resource_listing_v1(listing_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_candidate_facility
      FOREIGN KEY (candidate_facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_candidate_source
      FOREIGN KEY (source_id) REFERENCES data_source(source_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_candidate_score CHECK (confidence_score>=0 AND confidence_score<=1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='公开线索形成的商品—服务商/设施候选映射；不得替代已确认外键关系';

CREATE TABLE IF NOT EXISTS compute_financing_reference_case_v1 (
    financing_reference_case_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_code VARCHAR(48) NOT NULL,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    borrower_name VARCHAR(255) NOT NULL,
    lender_name VARCHAR(255) NOT NULL,
    financing_type VARCHAR(64) NOT NULL,
    facility_project_name VARCHAR(255) NOT NULL,
    contract_date DATE NULL,
    original_principal_wanyuan DECIMAL(28,4) NOT NULL,
    term_months SMALLINT UNSIGNED NULL,
    outstanding_balance_wanyuan DECIMAL(28,4) NULL,
    balance_as_of_date DATE NULL,
    collateral_structure TEXT NOT NULL,
    case_status VARCHAR(48) NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC',
    data_quality VARCHAR(24) NOT NULL DEFAULT 'EXCHANGE_DISCLOSURE',
    model_treatment VARCHAR(48) NOT NULL DEFAULT 'REFERENCE_ONLY',
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_financing_reference_case (case_code),
    KEY idx_compute_financing_reference_facility (facility_v2_id,balance_as_of_date),
    CONSTRAINT fk_compute_financing_reference_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_financing_reference_source
      FOREIGN KEY (source_id) REFERENCES data_source(source_id)
      ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='公开披露的真实融资结构案例；仅作银行尽调与结构设计参照，不改变情景模型';

/* Raw pages/PDF are saved under etl/sources/compute/2026-08-26/facility/. */
INSERT INTO data_source (
    source_org,source_title,source_url,source_date,source_tier,data_quality,statistical_scope,source_hash,notes
) VALUES
('深圳易信科技股份有限公司','深圳百旺信智算中心设施详情','https://www.esinidc.com/ShenzhenBaiwangxinIntelligentC/96.html',NULL,'B','OPERATOR_DISCLOSURE','深圳百旺信智算中心整体设施与设备部署','65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca','运营商公开披露；设施本身可确认，PUE和绿色属性仍保留运营商披露标签。'),
('深圳易信科技股份有限公司','百旺信智算中心绿色能源案例','https://www.esinidc.com/hangyedongtai/824.html','2024-02-07','B','OPERATOR_DISCLOSURE','深圳百旺信智算中心绿色运营措施','9adce1e99375e363e27a458449bbd671e47d6fef4643aa3a73a8448d0c14b26e','100%海上风电等表述为运营商披露，不等同于第三方审计结论。'),
('北京北龙超级云计算有限责任公司','北京超级云计算中心算力资源','https://www.blsc.cn/computility/',NULL,'B','VERIFIED_PUBLIC','北京超级云计算中心公开资源池','c19acb949ae6a76f9d864df9e7ec90951457c5bea431414f3c65fcad58641677','用于同型GPU资源参考；未证明与CNIX商品编码存在关系。'),
('深圳市前海新型互联网交换中心有限公司','粤港澳大湾区一体化算力服务平台前海专区','https://ai.cnix.cn/market/promotion/qianhai',NULL,'B','PUBLIC_CATALOG','CNIX平台前海专区服务商入口','c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','页面列出服务商专区，不等于具体SKU、资源池或机房归属。'),
('上海证券交易所','易信科技相关公开披露：百旺信项目能耗与融资信息','https://static.sse.com.cn/stock/disclosure/announcement/c/202512/600156_20251230_3AYP.pdf','2025-12-30','A','EXCHANGE_DISCLOSURE','百旺信云数据中心三期项目与融资结构','a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','交易所披露文件；三期项目数据不得与整体设施运营商口径混用。')
ON DUPLICATE KEY UPDATE
  source_org=VALUES(source_org),source_title=VALUES(source_title),source_url=VALUES(source_url),source_date=VALUES(source_date),
  source_tier=VALUES(source_tier),data_quality=VALUES(data_quality),statistical_scope=VALUES(statistical_scope),notes=VALUES(notes);

/* A verified facility fact record.  Its code follows the existing SZCF series; FAC-SZ-001 is retained as an alias. */
INSERT INTO enterprise_data_center_v2 (
    facility_code,region_id,official_name,facility_alias,facility_kind,locality_scope,province_name,city_name,district_name,address_text,
    operator_name,owner_name,lifecycle_status,physical_capacity_countable,green_certification,primary_source_id,last_verified_date,
    data_type,data_quality,notes,model_version
)
SELECT
  'SZCF016',r.region_id,'深圳百旺信智算中心','FAC-SZ-001；深圳百旺信云数据中心；百旺信云数据中心三期','AI_COMPUTE','LOCAL_SHENZHEN','广东省','深圳市','南山区',
  '深圳市南山区松白路1002号百旺信高科技工业园1区1栋1-4楼','深圳易信科技股份有限公司','深圳易信科技股份有限公司','OPERATING',1,
  '国家绿色数据中心；国家能源绿色低碳转型典型案例（运营商公开披露）',ds.source_id,'2026-08-26','PUBLIC','VERIFIED_PUBLIC',
  '整体设施披露与三期项目披露并存：整体运营商披露PUE为1.21；三期交易所披露PUE为1.228。二者统计边界不同，禁止相互替代。','V2.1'
FROM dim_region r
JOIN data_source ds ON ds.source_hash='65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca'
WHERE r.region_code='SZ'
ON DUPLICATE KEY UPDATE
  region_id=VALUES(region_id),facility_alias=VALUES(facility_alias),facility_kind=VALUES(facility_kind),locality_scope=VALUES(locality_scope),
  province_name=VALUES(province_name),city_name=VALUES(city_name),district_name=VALUES(district_name),address_text=VALUES(address_text),
  operator_name=VALUES(operator_name),owner_name=VALUES(owner_name),lifecycle_status=VALUES(lifecycle_status),physical_capacity_countable=VALUES(physical_capacity_countable),
  green_certification=VALUES(green_certification),primary_source_id=VALUES(primary_source_id),last_verified_date=VALUES(last_verified_date),
  data_type=VALUES(data_type),data_quality=VALUES(data_quality),notes=VALUES(notes),model_version=VALUES(model_version);

/* Whole-facility operator disclosure and phase-three exchange disclosure are separate metric scopes. */
INSERT INTO compute_facility_metric_v1 (
    facility_v2_id,metric_code,metric_scope,metric_value,metric_value_upper,metric_text,metric_unit,compute_precision,value_operator,
    disclosure_status,as_of_date,statistical_scope,usable_for_facility_model,source_id,source_locator,evidence_grade,data_quality,notes,model_version
)
SELECT f.facility_v2_id,m.metric_code,m.metric_scope,m.metric_value,m.metric_value_upper,m.metric_text,m.metric_unit,m.compute_precision,m.value_operator,
       m.disclosure_status,m.as_of_date,m.statistical_scope,m.usable_for_facility_model,ds.source_id,m.source_locator,m.evidence_grade,m.data_quality,m.notes,'V1.0'
FROM (
  SELECT '65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca' source_hash,'CABINET_COUNT' metric_code,'WHOLE_FACILITY_OPERATOR_DISCLOSURE' metric_scope,4000 metric_value,NULL metric_value_upper,NULL metric_text,'CABINET' metric_unit,NULL compute_precision,'APPROX' value_operator,'DISCLOSED' disclosure_status,NULL as_of_date,'SZCF016:整体设施运营商公开披露' statistical_scope,1 usable_for_facility_model,'设施详情正文：建设机柜数量4000架' source_locator,'B' evidence_grade,'OPERATOR_PUBLIC' data_quality,'整体设施口径，非三期项目口径。' notes
  UNION ALL SELECT '65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca','PUE','WHOLE_FACILITY_OPERATOR_DISCLOSURE',1.21,NULL,NULL,'RATIO',NULL,'EQ','DISCLOSED',NULL,'SZCF016:整体设施运营商公开披露',1,'设施详情正文：年PUE值1.21','B','OPERATOR_PUBLIC','运营商披露；与三期项目PUE 1.228统计边界不同。'
  UNION ALL SELECT '65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca','CABINET_POWER_RANGE','WHOLE_FACILITY_OPERATOR_DISCLOSURE',6,50,NULL,'KW_PER_CABINET',NULL,'APPROX','DISCLOSED',NULL,'SZCF016:整体设施运营商公开披露',1,'设施详情正文：单柜6-50kW弹性负荷','B','OPERATOR_PUBLIC','范围值，不以单一值替代。'
  UNION ALL SELECT '65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca','AI_COMPUTE_CAPACITY','WHOLE_FACILITY_OPERATOR_DISCLOSURE',4000,NULL,NULL,'PFLOPS',NULL,'GT','DISCLOSED',NULL,'SZCF016:整体设施运营商公开披露',0,'设施详情正文：智慧算力超过4000PFlops','B','OPERATOR_PUBLIC','宣传口径，未纳入物理容量合计。'
  UNION ALL SELECT '9adce1e99375e363e27a458449bbd671e47d6fef4643aa3a73a8448d0c14b26e','GREEN_POWER_RATIO','OPERATOR_GREEN_ENERGY_CASE',1,NULL,NULL,'RATIO',NULL,'EQ','DISCLOSED','2024-02-07','SZCF016:运营商绿色能源案例',0,'绿色能源案例：100%应用海上风电','B','OPERATOR_PUBLIC','运营商公开披露；未取得绿电合同、绿证和结算单，不能按审计比例处理。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','FLOOR_AREA','PHASE_III_EXCHANGE_DISCLOSURE',10000,NULL,NULL,'SQM',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：百旺信云数据中心三期项目','A','EXCHANGE_PUBLIC','三期项目，不代表整体21500平方米设施。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','CABINET_COUNT','PHASE_III_EXCHANGE_DISCLOSURE',1760,NULL,NULL,'CABINET',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：设置1760个机柜','A','EXCHANGE_PUBLIC','三期项目。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','CABINET_RATED_POWER','PHASE_III_EXCHANGE_DISCLOSURE',4,NULL,NULL,'KW_PER_CABINET',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：单台功率4kW','A','EXCHANGE_PUBLIC','三期项目。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','CAPEX','PHASE_III_EXCHANGE_DISCLOSURE',32000,NULL,NULL,'WANYUAN',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：总投资32000万元','A','EXCHANGE_PUBLIC','三期项目历史投资额。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','PUE','PHASE_III_EXCHANGE_DISCLOSURE',1.228,NULL,NULL,'RATIO',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：项目主要能效指标PUE为1.228','A','EXCHANGE_PUBLIC','三期项目；可作为独立能耗样本。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','ANNUAL_ELECTRICITY_CONSUMPTION','PHASE_III_EXCHANGE_DISCLOSURE',48473300,NULL,NULL,'KWH',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：年用电量4847.33万kWh','A','EXCHANGE_PUBLIC','三期项目。'
  UNION ALL SELECT 'a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395','ANNUAL_ENERGY_CONSUMPTION','PHASE_III_EXCHANGE_DISCLOSURE',14286.83,NULL,NULL,'TCE_EQUIVALENT',NULL,'EQ','DISCLOSED',NULL,'SZCF016:百旺信云数据中心三期',1,'上交所披露文件：年综合能源消费14286.83吨标准煤（等价值）','A','EXCHANGE_PUBLIC','三期项目。'
) m
JOIN enterprise_data_center_v2 f ON f.facility_code='SZCF016'
JOIN data_source ds ON ds.source_hash=m.source_hash
ON DUPLICATE KEY UPDATE
  metric_value=VALUES(metric_value),metric_value_upper=VALUES(metric_value_upper),metric_text=VALUES(metric_text),metric_unit=VALUES(metric_unit),
  compute_precision=VALUES(compute_precision),value_operator=VALUES(value_operator),disclosure_status=VALUES(disclosure_status),as_of_date=VALUES(as_of_date),
  statistical_scope=VALUES(statistical_scope),usable_for_facility_model=VALUES(usable_for_facility_model),source_locator=VALUES(source_locator),
  evidence_grade=VALUES(evidence_grade),data_quality=VALUES(data_quality),notes=VALUES(notes),updated_at=CURRENT_TIMESTAMP;

/* A real disclosed financing structure, deliberately stored as a reference case rather than a model assumption. */
INSERT INTO compute_financing_reference_case_v1 (
    case_code,facility_v2_id,borrower_name,lender_name,financing_type,facility_project_name,contract_date,original_principal_wanyuan,term_months,
    outstanding_balance_wanyuan,balance_as_of_date,collateral_structure,case_status,source_id,source_locator,data_type,data_quality,model_treatment,notes
)
SELECT
  'BWX_PHASE3_CCB_2021',f.facility_v2_id,'深圳易百旺科技有限公司','中国银行股份有限公司深圳福永支行','固定资产借款','百旺信云数据中心三期项目',
  '2021-11-10',12000,84,8397.4846,'2025-06-30',
  '项目项下对外销售货物及提供服务产生的应收账款质押；深圳易百旺机器设备抵押（披露评估值9348.443323万元）；易信科技持有的深圳易百旺100%股权质押。',
  'HISTORICAL_ACTIVE_AS_OF_DISCLOSURE',ds.source_id,'上交所披露文件：借款、应收账款质押、设备抵押及股权质押说明','PUBLIC','EXCHANGE_DISCLOSURE','REFERENCE_ONLY',
  '截至2025-06-30披露余额8397.4846万元。该案例用于贷款结构和尽调设计参照，不表示当前余额、授信条件或本平台候选商品的融资结果。'
FROM enterprise_data_center_v2 f
JOIN data_source ds ON ds.source_hash='a279a603da6c27c6747c71c015744a3f0412ed6679c5a5e7c0143f53d2f08395'
WHERE f.facility_code='SZCF016'
ON DUPLICATE KEY UPDATE
  facility_v2_id=VALUES(facility_v2_id),borrower_name=VALUES(borrower_name),lender_name=VALUES(lender_name),financing_type=VALUES(financing_type),
  facility_project_name=VALUES(facility_project_name),contract_date=VALUES(contract_date),original_principal_wanyuan=VALUES(original_principal_wanyuan),term_months=VALUES(term_months),
  outstanding_balance_wanyuan=VALUES(outstanding_balance_wanyuan),balance_as_of_date=VALUES(balance_as_of_date),collateral_structure=VALUES(collateral_structure),
  case_status=VALUES(case_status),source_id=VALUES(source_id),source_locator=VALUES(source_locator),data_quality=VALUES(data_quality),model_treatment=VALUES(model_treatment),notes=VALUES(notes),updated_at=CURRENT_TIMESTAMP;

/*
  Candidate mappings.  None sets compute_platform_resource_listing_v1.facility_v2_id.
  MEDIUM means the public evidence supports a practical lead for outreach, not
  proof that the listed SKU is physically deployed at that facility.
*/
INSERT INTO compute_listing_candidate_mapping_v1 (
    listing_id,candidate_mapping_type,candidate_entity_type,candidate_name,candidate_facility_v2_id,mapping_status,confidence_level,confidence_score,
    direct_sku_evidence_flag,platform_relation_evidence_flag,candidate_asset_evidence_flag,source_id,source_locator,evidence_summary,boundary_note,
    verified_at,data_type,data_quality,model_version
)
SELECT
  l.listing_id,m.candidate_mapping_type,m.candidate_entity_type,m.candidate_name,f.facility_v2_id,m.mapping_status,m.confidence_level,m.confidence_score,
  m.direct_sku_evidence_flag,m.platform_relation_evidence_flag,m.candidate_asset_evidence_flag,ds.source_id,m.source_locator,m.evidence_summary,m.boundary_note,
  '2026-08-26','PUBLIC_INDICATIVE','PUBLIC_INDICATIVE','COMPUTE_CANDIDATE_MAPPING_V1'
FROM (
  SELECT 'B200-C4-1' external_product_id,'EXTERNAL_SAME_GPU_REFERENCE' candidate_mapping_type,'RESOURCE_POOL' candidate_entity_type,'北京超级云计算中心 N61B2B分区' candidate_name,NULL candidate_facility_code,'UNMAPPED' mapping_status,'NONE' confidence_level,0.0000 confidence_score,0 direct_sku_evidence_flag,0 platform_relation_evidence_flag,1 candidate_asset_evidence_flag,'c19acb949ae6a76f9d864df9e7ec90951457c5bea431414f3c65fcad58641677' source_hash,'资源页N61B2B分区' source_locator,'公开资源页显示B200×8、192CPU、2304GB内存，与CNIX候选的八卡B200形态高度相似。' evidence_summary,'未找到B200-C4-1与N61B2B、该中心或CNIX接入关系的直接证据；仅作为同型资源市场参照。' boundary_note
  UNION ALL SELECT 'H100-141GB-sxm-G3-1','PROVIDER_CANDIDATE','PROVIDER','腾讯云',NULL,'INDICATIVE','LOW',0.3000,0,1,0,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：腾讯云专属产品','CNIX前海专区存在腾讯云专属产品入口；H200 141GB为可追踪的公开GPU形态。','专区入口未披露G3-1的SKU、实例编码、资源池或机房；不得视为腾讯云实际归属。'
  UNION ALL SELECT 'H100-141GB-sxm-G3-1','PROVIDER_CANDIDATE','PROVIDER','智星云',NULL,'INDICATIVE','LOW',0.3000,0,1,0,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：智星云专属产品','CNIX前海专区存在智星云专属产品入口；可作为H200商品服务商线索。','专区入口未披露G3-1的SKU、底层资源合作方或实际IDC；不得从服务商名称倒推机房。'
  UNION ALL SELECT 'H100-141GB-sxm-G3-2','PROVIDER_CANDIDATE','PROVIDER','腾讯云',NULL,'INDICATIVE','LOW',0.3000,0,1,0,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：腾讯云专属产品','CNIX前海专区存在腾讯云专属产品入口；H200 141GB为可追踪的公开GPU形态。','专区入口未披露G3-2的SKU、实例编码、资源池或机房；不得视为腾讯云实际归属。'
  UNION ALL SELECT 'H100-141GB-sxm-G3-2','PROVIDER_CANDIDATE','PROVIDER','智星云',NULL,'INDICATIVE','LOW',0.3000,0,1,0,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：智星云专属产品','CNIX前海专区存在智星云专属产品入口；可作为H200商品服务商线索。','专区入口未披露G3-2的SKU、底层资源合作方或实际IDC；不得从服务商名称倒推机房。'
  UNION ALL SELECT 'BMGNH800-32XLARGE2000','PROVIDER_CANDIDATE','PROVIDER','易信科技',NULL,'INDICATIVE','MEDIUM',0.4500,0,1,1,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：易信科技专属产品','CNIX前海专区显示易信科技专属产品；易信公开提供H800算力租赁。','未发现BMGNH800-32XLARGE2000的详情页或订单证据，不能确认该SKU由易信提供。'
  UNION ALL SELECT 'BMGNH800-32XLARGE2000','PROVIDER_CANDIDATE','PROVIDER','超擎数智',NULL,'INDICATIVE','LOW',0.2500,0,1,0,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：超擎数智专属产品','CNIX前海专区显示超擎数智专属产品，可作为设备/服务商外部线索。','未发现SKU与超擎数智的直接关联；且公开线索更偏设备/方案提供，不能当作IDC运营主体。'
  UNION ALL SELECT 'BMGNH800-32XLARGE2000','FACILITY_CANDIDATE','FACILITY','深圳百旺信智算中心','SZCF016','INDICATIVE','MEDIUM',0.6000,0,1,1,'65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca','设施详情：H800规模化部署','易信运营的深圳百旺信智算中心公开披露规模化部署H800；CNIX同时存在易信科技专区。','缺少“BMGNH800-32XLARGE2000→易信→百旺信”的最后一环；候选关系不改变SKU的facility_v2_id。'
  UNION ALL SELECT 'H800-80GB-sxm-G2-1','PROVIDER_CANDIDATE','PROVIDER','易信科技',NULL,'INDICATIVE','MEDIUM',0.4500,0,1,1,'c95651f7b2e6c9c9b9d962e5f2637e4a7e2098ab460e29899a71f9f8e4163a0d','CNIX前海专区：易信科技专属产品','CNIX前海专区显示易信科技专属产品；易信公开提供H800算力租赁。','未发现H800-80GB-sxm-G2-1的详情页或订单证据，不能确认该SKU由易信提供。'
  UNION ALL SELECT 'H800-80GB-sxm-G2-1','FACILITY_CANDIDATE','FACILITY','深圳百旺信智算中心','SZCF016','INDICATIVE','MEDIUM',0.5500,0,1,1,'65998c0c6cd173441e07699e2c653848730f4fef5ae789dfd2b68117572152ca','设施详情：H800规模化部署','易信运营的深圳百旺信智算中心公开披露规模化部署H800；CNIX同时存在易信科技专区。','缺少“H800-80GB-sxm-G2-1→易信→百旺信”的直接证据；候选关系不改变SKU的facility_v2_id。'
  UNION ALL SELECT 'H800-80GB-sxm-G2-1','EXTERNAL_SAME_GPU_REFERENCE','RESOURCE_POOL','北京超级云计算中心 N76H8B分区',NULL,'UNMAPPED','NONE',0.0000,0,0,1,'c19acb949ae6a76f9d864df9e7ec90951457c5bea431414f3c65fcad58641677','资源页N76H8B分区','公开资源页显示H800×8资源，可作为同型资源市场参照。','未发现H800-G2-1与N76H8B、该中心或CNIX接入关系的直接证据；不得作为设施映射。'
) m
JOIN compute_platform_resource_listing_v1 l ON l.external_product_id=m.external_product_id
LEFT JOIN enterprise_data_center_v2 f ON f.facility_code=m.candidate_facility_code
JOIN data_source ds ON ds.source_hash=m.source_hash
ON DUPLICATE KEY UPDATE
  candidate_facility_v2_id=VALUES(candidate_facility_v2_id),mapping_status=VALUES(mapping_status),confidence_level=VALUES(confidence_level),confidence_score=VALUES(confidence_score),
  direct_sku_evidence_flag=VALUES(direct_sku_evidence_flag),platform_relation_evidence_flag=VALUES(platform_relation_evidence_flag),candidate_asset_evidence_flag=VALUES(candidate_asset_evidence_flag),
  source_id=VALUES(source_id),source_locator=VALUES(source_locator),evidence_summary=VALUES(evidence_summary),boundary_note=VALUES(boundary_note),verified_at=VALUES(verified_at),
  data_type=VALUES(data_type),data_quality=VALUES(data_quality),updated_at=CURRENT_TIMESTAMP;

CREATE OR REPLACE VIEW v_compute_listing_candidate_mapping_v1 AS
SELECT
  m.candidate_mapping_id,m.listing_id,m.candidate_mapping_type,m.candidate_entity_type,m.candidate_name,m.mapping_status,m.confidence_level,m.confidence_score,
  m.direct_sku_evidence_flag,m.platform_relation_evidence_flag,m.candidate_asset_evidence_flag,m.source_locator,m.evidence_summary,m.boundary_note,
  m.verified_at,m.data_type,m.data_quality,m.model_version,m.updated_at,
  l.external_product_id,l.product_name,p.platform_code,p.platform_name,
  f.facility_code AS candidate_facility_code,f.official_name AS candidate_facility_name,f.city_name AS candidate_city_name,f.operator_name AS candidate_operator_name,
  ds.source_org,ds.source_title,ds.source_url,ds.source_tier
FROM compute_listing_candidate_mapping_v1 m
JOIN compute_platform_resource_listing_v1 l ON l.listing_id=m.listing_id
JOIN compute_service_platform_v1 p ON p.platform_id=l.platform_id
LEFT JOIN enterprise_data_center_v2 f ON f.facility_v2_id=m.candidate_facility_v2_id
JOIN data_source ds ON ds.source_id=m.source_id;

CREATE OR REPLACE VIEW v_compute_financing_reference_case_v1 AS
SELECT
  c.financing_reference_case_id,c.case_code,c.borrower_name,c.lender_name,c.financing_type,c.facility_project_name,c.contract_date,
  c.original_principal_wanyuan,c.term_months,c.outstanding_balance_wanyuan,c.balance_as_of_date,c.collateral_structure,c.case_status,
  c.data_type,c.data_quality,c.model_treatment,c.notes,c.updated_at,
  f.facility_code,f.official_name AS facility_name,f.city_name,f.district_name,f.operator_name,
  ds.source_title,ds.source_url,ds.source_tier,c.source_locator
FROM compute_financing_reference_case_v1 c
JOIN enterprise_data_center_v2 f ON f.facility_v2_id=c.facility_v2_id
JOIN data_source ds ON ds.source_id=c.source_id;
