USE spdb_power_finance;

/*
  深圳百旺信智算中心：公开经营事实层 V1

  This module deliberately sits beside the marketplace-product model.
  It does NOT assign a CNIX SKU to SZCF016 and does NOT turn operating facts
  into a projected NPV / IRR / financing conclusion.

  Important boundaries:
  - Annual operating figures cover the disclosed self-built hosting operation
    of Buildings 1 and 4 (3,780 racks), not Phase III alone.
  - Phase III has a separate physical-project scope already stored in
    compute_facility_metric_v1 (1,760 racks / PUE 1.228 / historical CAPEX).
  - 2025 H1 metered tariff is retained as H1; it is not relabelled as a 2025
    full-year settlement price.
  - The three raw PDFs are public exchange-disclosure documents archived from
    a public mirror. SHA-256 hashes, source URLs and page locators are stored.
*/

CREATE TABLE IF NOT EXISTS compute_facility_operation_fact_v1 (
    operation_fact_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    operation_scope_code VARCHAR(80) NOT NULL,
    operation_scope_name VARCHAR(255) NOT NULL,
    fact_year SMALLINT UNSIGNED NOT NULL,
    fact_period VARCHAR(16) NOT NULL COMMENT 'ANNUAL/H1',
    rack_capacity_count INT UNSIGNED NULL,
    average_occupied_rack_count INT UNSIGNED NULL,
    rack_utilization_ratio DECIMAL(12,8) NULL,
    high_power_occupied_rack_count INT UNSIGNED NULL,
    high_power_threshold_kw DECIMAL(10,4) NULL,
    hosting_revenue_wanyuan DECIMAL(28,4) NULL,
    hosting_cost_wanyuan DECIMAL(28,4) NULL,
    hosting_gross_margin DECIMAL(12,8) NULL,
    average_rack_price_yuan_month DECIMAL(20,4) NULL,
    average_rack_cost_yuan_month DECIMAL(20,4) NULL,
    electricity_consumption_kwh DECIMAL(28,4) NULL,
    electricity_purchase_wanyuan DECIMAL(28,4) NULL COMMENT '与自建托管收入匹配的不含税电力采购额',
    electricity_purchase_tax_included_wanyuan DECIMAL(28,4) NULL COMMENT '电力采购汇总口径含税金额',
    electricity_purchase_price_yuan_kwh DECIMAL(20,8) NULL,
    electricity_purchase_price_tax_included_flag TINYINT(1) NULL,
    electricity_cost_revenue_ratio DECIMAL(12,8) NULL,
    hosting_revenue_yuan_kwh DECIMAL(20,8) NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC',
    data_quality VARCHAR(32) NOT NULL DEFAULT 'EXCHANGE_DISCLOSURE',
    notes TEXT NULL,
    model_version VARCHAR(32) NOT NULL DEFAULT 'COMPUTE_FACILITY_OPERATIONS_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_operation_fact
      (facility_v2_id,operation_scope_code,fact_year,fact_period,source_id,model_version),
    KEY idx_compute_facility_operation_year (facility_v2_id,fact_year,fact_period),
    CONSTRAINT fk_compute_facility_operation_fact_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_operation_fact_source
      FOREIGN KEY (source_id) REFERENCES data_source(source_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_facility_operation_period CHECK (fact_period IN ('ANNUAL','H1')),
    CONSTRAINT chk_compute_facility_operation_utilization CHECK
      (rack_utilization_ratio IS NULL OR (rack_utilization_ratio>=0 AND rack_utilization_ratio<=1)),
    CONSTRAINT chk_compute_facility_operation_margin CHECK
      (hosting_gross_margin IS NULL OR (hosting_gross_margin>=-1 AND hosting_gross_margin<=1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力设施经营事实：上架率、机柜收入/成本与电量按年度和物理口径保存';

/* Required when upgrading a database where the first draft of this V1 table already existed. */
SET @operation_column_sql := (
  SELECT IF(COUNT(*)=0,
    'ALTER TABLE compute_facility_operation_fact_v1 ADD COLUMN electricity_purchase_wanyuan DECIMAL(28,4) NULL COMMENT ''与自建托管收入匹配的不含税电力采购额'' AFTER electricity_consumption_kwh',
    'DO 0')
  FROM information_schema.columns
  WHERE table_schema='spdb_power_finance'
    AND table_name='compute_facility_operation_fact_v1'
    AND column_name='electricity_purchase_wanyuan'
);
PREPARE operation_column_statement FROM @operation_column_sql;
EXECUTE operation_column_statement;
DEALLOCATE PREPARE operation_column_statement;

SET @operation_column_sql := (
  SELECT IF(COUNT(*)=0,
    'ALTER TABLE compute_facility_operation_fact_v1 ADD COLUMN electricity_purchase_tax_included_wanyuan DECIMAL(28,4) NULL COMMENT ''电力采购汇总口径含税金额'' AFTER electricity_purchase_wanyuan',
    'DO 0')
  FROM information_schema.columns
  WHERE table_schema='spdb_power_finance'
    AND table_name='compute_facility_operation_fact_v1'
    AND column_name='electricity_purchase_tax_included_wanyuan'
);
PREPARE operation_column_statement FROM @operation_column_sql;
EXECUTE operation_column_statement;
DEALLOCATE PREPARE operation_column_statement;

SET @operation_column_sql := (
  SELECT IF(COUNT(*)=0,
    'ALTER TABLE compute_facility_operation_fact_v1 ADD COLUMN electricity_purchase_price_yuan_kwh DECIMAL(20,8) NULL AFTER electricity_purchase_tax_included_wanyuan',
    'DO 0')
  FROM information_schema.columns
  WHERE table_schema='spdb_power_finance'
    AND table_name='compute_facility_operation_fact_v1'
    AND column_name='electricity_purchase_price_yuan_kwh'
);
PREPARE operation_column_statement FROM @operation_column_sql;
EXECUTE operation_column_statement;
DEALLOCATE PREPARE operation_column_statement;

SET @operation_column_sql := (
  SELECT IF(COUNT(*)=0,
    'ALTER TABLE compute_facility_operation_fact_v1 ADD COLUMN electricity_purchase_price_tax_included_flag TINYINT(1) NULL AFTER electricity_purchase_price_yuan_kwh',
    'DO 0')
  FROM information_schema.columns
  WHERE table_schema='spdb_power_finance'
    AND table_name='compute_facility_operation_fact_v1'
    AND column_name='electricity_purchase_price_tax_included_flag'
);
PREPARE operation_column_statement FROM @operation_column_sql;
EXECUTE operation_column_statement;
DEALLOCATE PREPARE operation_column_statement;

CREATE TABLE IF NOT EXISTS compute_facility_rack_price_tier_fact_v1 (
    rack_price_tier_fact_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    building_scope_code VARCHAR(48) NOT NULL COMMENT 'BUILDING_1/BUILDING_4',
    fact_year SMALLINT UNSIGNED NOT NULL,
    fact_period VARCHAR(16) NOT NULL COMMENT 'ANNUAL/H1',
    power_tier_code VARCHAR(32) NOT NULL,
    power_from_kw DECIMAL(10,4) NULL,
    power_to_kw DECIMAL(10,4) NULL,
    upper_bound_inclusive TINYINT(1) NOT NULL DEFAULT 0,
    actual_average_price_yuan_rack_month DECIMAL(20,4) NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC',
    data_quality VARCHAR(32) NOT NULL DEFAULT 'EXCHANGE_DISCLOSURE',
    notes TEXT NULL,
    model_version VARCHAR(32) NOT NULL DEFAULT 'COMPUTE_FACILITY_OPERATIONS_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_rack_price_tier
      (facility_v2_id,building_scope_code,fact_year,fact_period,power_tier_code,source_id,model_version),
    KEY idx_compute_rack_price_facility_period (facility_v2_id,fact_year,fact_period),
    CONSTRAINT fk_compute_rack_price_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_rack_price_source
      FOREIGN KEY (source_id) REFERENCES data_source(source_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_rack_price_period CHECK (fact_period IN ('ANNUAL','H1')),
    CONSTRAINT chk_compute_rack_price_positive CHECK (actual_average_price_yuan_rack_month>=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力设施分功率机柜实际成交均价；不使用网页挂牌价替代';

CREATE TABLE IF NOT EXISTS compute_facility_customer_contract_fact_v1 (
    customer_contract_fact_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    contract_fact_code VARCHAR(64) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_name_scope VARCHAR(48) NOT NULL DEFAULT 'PUBLIC_DISCLOSURE_ALIAS',
    contract_name VARCHAR(500) NOT NULL,
    contract_scope VARCHAR(80) NOT NULL,
    contract_start_date DATE NULL,
    contract_end_date DATE NULL,
    contracted_rack_count_approx INT UNSIGNED NULL,
    included_current_amp DECIMAL(12,4) NULL,
    base_price_yuan_rack_month DECIMAL(20,4) NULL,
    excess_price_yuan_amp_rack_month DECIMAL(20,4) NULL,
    vacant_protection_months SMALLINT UNSIGNED NULL,
    first_occupancy_threshold_ratio DECIMAL(12,8) NULL,
    second_occupancy_threshold_ratio DECIMAL(12,8) NULL,
    vacant_fee_yuan_rack_month DECIMAL(20,4) NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    contract_status VARCHAR(64) NOT NULL,
    data_type VARCHAR(24) NOT NULL DEFAULT 'PUBLIC',
    data_quality VARCHAR(32) NOT NULL DEFAULT 'EXCHANGE_DISCLOSURE',
    notes TEXT NULL,
    model_version VARCHAR(32) NOT NULL DEFAULT 'COMPUTE_FACILITY_OPERATIONS_V1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compute_facility_customer_contract
      (facility_v2_id,contract_fact_code,source_id,model_version),
    KEY idx_compute_customer_contract_facility (facility_v2_id,contract_end_date),
    CONSTRAINT fk_compute_customer_contract_facility
      FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_customer_contract_source
      FOREIGN KEY (source_id) REFERENCES data_source(source_id)
      ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_customer_contract_first_ratio CHECK
      (first_occupancy_threshold_ratio IS NULL OR (first_occupancy_threshold_ratio>=0 AND first_occupancy_threshold_ratio<=1)),
    CONSTRAINT chk_compute_customer_contract_second_ratio CHECK
      (second_occupancy_threshold_ratio IS NULL OR (second_occupancy_threshold_ratio>=0 AND second_occupancy_threshold_ratio<=1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='公开披露的大客户IDC合同商业条款；不等同于全部客户或市场零售价';

/* Every source row points to the retained public document and source page. */
INSERT INTO data_source (
  source_org,source_title,source_url,source_date,source_tier,data_quality,statistical_scope,source_hash,notes
) VALUES
('上海证券交易所公开披露文件（镜像存档）','天健会计师事务所关于易信科技问询函财务事项的说明（修订稿）','https://stockmc.xueqiu.com/202606/600156_20260602_FIY7.pdf','2026-06-02','A','EXCHANGE_DISCLOSURE','易信科技自建服务器托管业务与深圳百旺信智算中心1栋、4栋合并运营口径','ffd77fb996e68b792a1a8b055a8e5ed4bad10ff0c87b8faf817bddd35edfaf21','公开交易所问询回复文件镜像；原始PDF已归档。用于2023—2025全年上架、收入、成本、电量和毛利率，不代表三期项目单独经营数据。'),
('上海证券交易所公开披露文件（镜像存档）','北京坤元至诚资产评估有限公司对易信科技问询函的回复（修订版）','https://stockmc.xueqiu.com/202606/600156_20260602_40KM.pdf','2026-06-01','A','EXCHANGE_DISCLOSURE','深圳百旺信1栋、4栋分功率机柜历史单价与历史电费账单统计口径','0605bf4c797afae5df0a4a8edaa733b30e50cb435854211efaa1ed05ee35b765','公开交易所问询回复文件镜像；原始PDF已归档。2025电价仅为1—6月历史账单统计，不能改标为全年实际结算价。'),
('上海证券交易所公开披露文件（镜像存档）','西部证券关于易信科技问询函回复之核查意见','https://stockmc.xueqiu.com/202603/600156_20260313_QD0D.pdf','2026-03-13','A','EXCHANGE_DISCLOSURE','深圳移动与百旺信IDC机房运营服务项目框架合作协议','3bdb44fabf7cf93d2955ba454b81791e75de690ea380bb84e6e4074ee5be39e7','公开交易所问询回复文件镜像；原始PDF已归档。合同条款为披露时点事实，不推定全部机柜、全部客户或当前结算情况。')
ON DUPLICATE KEY UPDATE
  source_org=VALUES(source_org),source_title=VALUES(source_title),source_url=VALUES(source_url),source_date=VALUES(source_date),
  source_tier=VALUES(source_tier),data_quality=VALUES(data_quality),statistical_scope=VALUES(statistical_scope),notes=VALUES(notes);

/* 2023—2025 annual facts, all under the disclosed Buildings 1 + 4 self-built operation scope. */
INSERT INTO compute_facility_operation_fact_v1 (
  facility_v2_id,operation_scope_code,operation_scope_name,fact_year,fact_period,
  rack_capacity_count,average_occupied_rack_count,rack_utilization_ratio,high_power_occupied_rack_count,high_power_threshold_kw,
  hosting_revenue_wanyuan,hosting_cost_wanyuan,hosting_gross_margin,average_rack_price_yuan_month,average_rack_cost_yuan_month,
  electricity_consumption_kwh,electricity_purchase_wanyuan,electricity_purchase_tax_included_wanyuan,electricity_purchase_price_yuan_kwh,electricity_purchase_price_tax_included_flag,
  electricity_cost_revenue_ratio,hosting_revenue_yuan_kwh,
  source_id,source_locator,data_type,data_quality,notes
)
SELECT f.facility_v2_id,'WHOLE_FACILITY_BUILDING_1_4_SELF_BUILT','百旺信1栋+4栋自建服务器托管运营口径',x.fact_year,'ANNUAL',
  3780,x.average_occupied,x.utilization,x.high_power,6.6,x.revenue,x.cost,x.margin,x.price,x.unit_cost,x.electricity_kwh,x.electricity_purchase,x.electricity_purchase_tax_included,x.purchase_price,x.purchase_price_tax_included,x.electricity_cost_ratio,x.revenue_per_kwh,
  ds.source_id,'PDF p.85—86, p.114—116','PUBLIC','EXCHANGE_DISCLOSURE','年均上架机柜、收入和电量为合并经营口径；不含税电力采购额与自建托管收入匹配。含税采购汇总金额和不含税业务匹配金额分口径保留，不得混用；不得与百旺信云数据中心三期（1760柜）混合。'
FROM (
  SELECT 2023 fact_year,1422 average_occupied,0.3762 utilization,110 high_power,8914.91 revenue,6355.60 cost,0.2871 margin,5224.40 price,3685.69 unit_cost,38945000 electricity_kwh,2732.23 electricity_purchase,NULL electricity_purchase_tax_included,NULL purchase_price,NULL purchase_price_tax_included,0.3065 electricity_cost_ratio,2.29 revenue_per_kwh
  UNION ALL SELECT 2024,2098,0.5550,425,13562.31,8453.25,0.3767,5387.00,3330.67,67833000,4251.81,4804.55,0.71,1,0.3135,2.00
  UNION ALL SELECT 2025,2473,0.6542,764,15797.82,9790.02,0.3803,5346.00,3312.96,80196200,4630.67,5232.66,0.65,1,0.2931,1.97
) x
JOIN enterprise_data_center_v2 f ON f.facility_code='SZCF016'
JOIN data_source ds ON ds.source_hash='ffd77fb996e68b792a1a8b055a8e5ed4bad10ff0c87b8faf817bddd35edfaf21'
ON DUPLICATE KEY UPDATE
  rack_capacity_count=VALUES(rack_capacity_count),average_occupied_rack_count=VALUES(average_occupied_rack_count),rack_utilization_ratio=VALUES(rack_utilization_ratio),
  high_power_occupied_rack_count=VALUES(high_power_occupied_rack_count),high_power_threshold_kw=VALUES(high_power_threshold_kw),hosting_revenue_wanyuan=VALUES(hosting_revenue_wanyuan),
  hosting_cost_wanyuan=VALUES(hosting_cost_wanyuan),hosting_gross_margin=VALUES(hosting_gross_margin),average_rack_price_yuan_month=VALUES(average_rack_price_yuan_month),
  average_rack_cost_yuan_month=VALUES(average_rack_cost_yuan_month),electricity_consumption_kwh=VALUES(electricity_consumption_kwh),
  electricity_purchase_wanyuan=VALUES(electricity_purchase_wanyuan),electricity_purchase_price_yuan_kwh=VALUES(electricity_purchase_price_yuan_kwh),
  electricity_purchase_tax_included_wanyuan=VALUES(electricity_purchase_tax_included_wanyuan),
  electricity_purchase_price_tax_included_flag=VALUES(electricity_purchase_price_tax_included_flag),
  electricity_cost_revenue_ratio=VALUES(electricity_cost_revenue_ratio),hosting_revenue_yuan_kwh=VALUES(hosting_revenue_yuan_kwh),source_locator=VALUES(source_locator),notes=VALUES(notes),updated_at=CURRENT_TIMESTAMP;

/* Building-level historical utilization has a different period boundary from the annual consolidated result above. */
INSERT INTO compute_facility_operation_fact_v1 (
  facility_v2_id,operation_scope_code,operation_scope_name,fact_year,fact_period,rack_utilization_ratio,
  source_id,source_locator,data_type,data_quality,notes
)
SELECT f.facility_v2_id,x.scope_code,x.scope_name,x.fact_year,x.fact_period,x.utilization,
  ds.source_id,'PDF p.32—33','PUBLIC','EXCHANGE_DISCLOSURE','分栋上架率披露未提供对应期间年均上架机柜数量；仅保存披露比例。'
FROM (
  SELECT 'BUILDING_1' scope_code,'百旺信智算中心1栋' scope_name,2023 fact_year,'ANNUAL' fact_period,0.6055 utilization
  UNION ALL SELECT 'BUILDING_1','百旺信智算中心1栋',2024,'ANNUAL',0.7317
  UNION ALL SELECT 'BUILDING_1','百旺信智算中心1栋',2025,'H1',0.7926
  UNION ALL SELECT 'BUILDING_4','百旺信智算中心4栋',2023,'ANNUAL',0.1261
  UNION ALL SELECT 'BUILDING_4','百旺信智算中心4栋',2024,'ANNUAL',0.3623
  UNION ALL SELECT 'BUILDING_4','百旺信智算中心4栋',2025,'H1',0.5221
) x
JOIN enterprise_data_center_v2 f ON f.facility_code='SZCF016'
JOIN data_source ds ON ds.source_hash='0605bf4c797afae5df0a4a8edaa733b30e50cb435854211efaa1ed05ee35b765'
ON DUPLICATE KEY UPDATE rack_utilization_ratio=VALUES(rack_utilization_ratio),source_locator=VALUES(source_locator),notes=VALUES(notes),updated_at=CURRENT_TIMESTAMP;

/* Actual average transaction price = hosting revenue / hosted racks, by disclosed rack-power tier. */
INSERT INTO compute_facility_rack_price_tier_fact_v1 (
  facility_v2_id,building_scope_code,fact_year,fact_period,power_tier_code,power_from_kw,power_to_kw,upper_bound_inclusive,
  actual_average_price_yuan_rack_month,source_id,source_locator,data_type,data_quality,notes
)
SELECT f.facility_v2_id,x.building_scope,x.fact_year,x.fact_period,x.tier_code,x.power_from,x.power_to,x.upper_inclusive,x.price,
  ds.source_id,'PDF p.39','PUBLIC','EXCHANGE_DISCLOSURE','实际成交平均价；由该智算中心当期机柜托管收入除以当期机柜托管数量得出。'
FROM (
  SELECT 'BUILDING_1' building_scope,2023 fact_year,'ANNUAL' fact_period,'LT_4_4KW' tier_code,NULL power_from,4.4 power_to,0 upper_inclusive,4583.79 price
  UNION ALL SELECT 'BUILDING_1',2023,'ANNUAL','FROM_4_4_TO_6_6KW',4.4,6.6,0,5475.60
  UNION ALL SELECT 'BUILDING_1',2023,'ANNUAL','FROM_6_6_TO_10KW',6.6,10.0,0,8183.03
  UNION ALL SELECT 'BUILDING_1',2023,'ANNUAL','GT_10KW',10.0,NULL,0,13607.98
  UNION ALL SELECT 'BUILDING_1',2024,'ANNUAL','LT_4_4KW',NULL,4.4,0,4215.83
  UNION ALL SELECT 'BUILDING_1',2024,'ANNUAL','FROM_4_4_TO_6_6KW',4.4,6.6,0,4729.43
  UNION ALL SELECT 'BUILDING_1',2024,'ANNUAL','FROM_6_6_TO_10KW',6.6,10.0,0,6614.85
  UNION ALL SELECT 'BUILDING_1',2024,'ANNUAL','GT_10KW',10.0,NULL,0,8761.50
  UNION ALL SELECT 'BUILDING_1',2025,'H1','LT_4_4KW',NULL,4.4,0,4170.22
  UNION ALL SELECT 'BUILDING_1',2025,'H1','FROM_4_4_TO_6_6KW',4.4,6.6,0,4716.87
  UNION ALL SELECT 'BUILDING_1',2025,'H1','FROM_6_6_TO_10KW',6.6,10.0,0,6711.54
  UNION ALL SELECT 'BUILDING_1',2025,'H1','GT_10KW',10.0,NULL,0,8618.19
  UNION ALL SELECT 'BUILDING_4',2023,'ANNUAL','LT_4_4KW',NULL,4.4,0,4814.32
  UNION ALL SELECT 'BUILDING_4',2023,'ANNUAL','FROM_4_4_TO_6_6KW',4.4,6.6,0,5519.36
  UNION ALL SELECT 'BUILDING_4',2023,'ANNUAL','FROM_6_6_TO_10KW',6.6,10.0,0,8183.03
  UNION ALL SELECT 'BUILDING_4',2023,'ANNUAL','GT_10KW',10.0,NULL,0,12462.89
  UNION ALL SELECT 'BUILDING_4',2024,'ANNUAL','LT_4_4KW',NULL,4.4,0,4134.80
  UNION ALL SELECT 'BUILDING_4',2024,'ANNUAL','FROM_4_4_TO_6_6KW',4.4,6.6,0,4729.43
  UNION ALL SELECT 'BUILDING_4',2024,'ANNUAL','FROM_6_6_TO_10KW',6.6,10.0,0,6614.85
  UNION ALL SELECT 'BUILDING_4',2024,'ANNUAL','GT_10KW',10.0,NULL,0,10343.64
  UNION ALL SELECT 'BUILDING_4',2025,'H1','LT_4_4KW',NULL,4.4,0,4103.10
  UNION ALL SELECT 'BUILDING_4',2025,'H1','FROM_4_4_TO_6_6KW',4.4,6.6,0,4716.87
  UNION ALL SELECT 'BUILDING_4',2025,'H1','FROM_6_6_TO_10KW',6.6,10.0,0,7037.88
  UNION ALL SELECT 'BUILDING_4',2025,'H1','GT_10KW',10.0,NULL,0,10290.08
) x
JOIN enterprise_data_center_v2 f ON f.facility_code='SZCF016'
JOIN data_source ds ON ds.source_hash='0605bf4c797afae5df0a4a8edaa733b30e50cb435854211efaa1ed05ee35b765'
ON DUPLICATE KEY UPDATE
  power_from_kw=VALUES(power_from_kw),power_to_kw=VALUES(power_to_kw),upper_bound_inclusive=VALUES(upper_bound_inclusive),
  actual_average_price_yuan_rack_month=VALUES(actual_average_price_yuan_rack_month),source_locator=VALUES(source_locator),notes=VALUES(notes),updated_at=CURRENT_TIMESTAMP;

INSERT INTO compute_facility_customer_contract_fact_v1 (
  facility_v2_id,contract_fact_code,customer_name,customer_name_scope,contract_name,contract_scope,contract_start_date,contract_end_date,
  contracted_rack_count_approx,included_current_amp,base_price_yuan_rack_month,excess_price_yuan_amp_rack_month,
  vacant_protection_months,first_occupancy_threshold_ratio,second_occupancy_threshold_ratio,vacant_fee_yuan_rack_month,
  source_id,source_locator,contract_status,data_type,data_quality,notes
)
SELECT f.facility_v2_id,'SZCF016_SZMOBILE_WHOLESALE_201908','深圳移动','PUBLIC_DISCLOSURE_ALIAS','关于百旺信IDC机房运营服务项目的框架合作协议','WHOLESALE_IDC_10A_INCLUDED',
  '2019-08-06','2027-08-05',1000,10,4580,230,15,0.50,0.90,2000,
  ds.source_id,'PDF p.275, p.277','DISCLOSED_VALIDITY_TO_2027_08_05','PUBLIC','EXCHANGE_DISCLOSURE',
  '约1000个10A包电机架，以实际交付验收数量为准。15个月后上电率未达50%、30个月后未达90%时，分别按披露的空置服务机制处理；不可推广为零售市场价格或其他客户合同。'
FROM enterprise_data_center_v2 f
JOIN data_source ds ON ds.source_hash='3bdb44fabf7cf93d2955ba454b81791e75de690ea380bb84e6e4074ee5be39e7'
WHERE f.facility_code='SZCF016'
ON DUPLICATE KEY UPDATE
  contract_start_date=VALUES(contract_start_date),contract_end_date=VALUES(contract_end_date),contracted_rack_count_approx=VALUES(contracted_rack_count_approx),
  included_current_amp=VALUES(included_current_amp),base_price_yuan_rack_month=VALUES(base_price_yuan_rack_month),
  excess_price_yuan_amp_rack_month=VALUES(excess_price_yuan_amp_rack_month),vacant_protection_months=VALUES(vacant_protection_months),
  first_occupancy_threshold_ratio=VALUES(first_occupancy_threshold_ratio),second_occupancy_threshold_ratio=VALUES(second_occupancy_threshold_ratio),
  vacant_fee_yuan_rack_month=VALUES(vacant_fee_yuan_rack_month),source_locator=VALUES(source_locator),contract_status=VALUES(contract_status),notes=VALUES(notes),updated_at=CURRENT_TIMESTAMP;

/*
  Calibration view: values labelled DERIVED are calculated only from two
  public facts in the same row.  They are not separately disclosed invoices.
*/
CREATE OR REPLACE VIEW v_compute_facility_operation_calibration_v1 AS
SELECT
  f.facility_code,f.official_name,o.operation_fact_id,o.operation_scope_code,o.operation_scope_name,o.fact_year,o.fact_period,
  o.rack_capacity_count,o.average_occupied_rack_count,o.rack_utilization_ratio,o.high_power_occupied_rack_count,o.high_power_threshold_kw,
  o.hosting_revenue_wanyuan,o.hosting_cost_wanyuan,o.hosting_gross_margin,o.average_rack_price_yuan_month,o.average_rack_cost_yuan_month,
  o.electricity_consumption_kwh,o.electricity_purchase_wanyuan,o.electricity_purchase_tax_included_wanyuan,o.electricity_purchase_price_yuan_kwh,o.electricity_purchase_price_tax_included_flag,
  o.electricity_cost_revenue_ratio,o.hosting_revenue_yuan_kwh,
  CASE WHEN o.hosting_revenue_wanyuan IS NOT NULL AND o.electricity_cost_revenue_ratio IS NOT NULL
    THEN ROUND(o.hosting_revenue_wanyuan*o.electricity_cost_revenue_ratio,4) END AS derived_electricity_cost_wanyuan,
  CASE WHEN o.hosting_revenue_wanyuan IS NOT NULL AND o.electricity_cost_revenue_ratio IS NOT NULL AND o.electricity_consumption_kwh>0
    THEN ROUND(o.hosting_revenue_wanyuan*o.electricity_cost_revenue_ratio*10000/o.electricity_consumption_kwh,8) END AS derived_implied_electricity_price_yuan_kwh,
  CASE WHEN o.electricity_purchase_wanyuan IS NOT NULL AND o.electricity_consumption_kwh>0
    THEN ROUND(o.electricity_purchase_wanyuan*10000/o.electricity_consumption_kwh,8) END AS derived_non_tax_electricity_price_yuan_kwh,
  CASE WHEN o.electricity_purchase_wanyuan IS NOT NULL AND o.hosting_revenue_wanyuan IS NOT NULL AND o.electricity_cost_revenue_ratio IS NOT NULL
    THEN ROUND(o.electricity_purchase_wanyuan-o.hosting_revenue_wanyuan*o.electricity_cost_revenue_ratio,4) END AS derived_electricity_cost_reconciliation_wanyuan,
  CASE WHEN o.hosting_revenue_wanyuan IS NOT NULL AND o.hosting_gross_margin IS NOT NULL
    THEN ROUND(o.hosting_revenue_wanyuan*o.hosting_gross_margin,4) END AS derived_gross_profit_wanyuan,
  CASE WHEN o.average_occupied_rack_count IS NOT NULL AND o.average_rack_price_yuan_month IS NOT NULL
    THEN ROUND(o.average_occupied_rack_count*o.average_rack_price_yuan_month*12/10000,4) END AS derived_price_volume_revenue_wanyuan,
  CASE WHEN o.hosting_revenue_wanyuan IS NOT NULL AND o.average_occupied_rack_count IS NOT NULL AND o.average_rack_price_yuan_month IS NOT NULL
    THEN ROUND((o.average_occupied_rack_count*o.average_rack_price_yuan_month*12/10000-o.hosting_revenue_wanyuan)/o.hosting_revenue_wanyuan,8) END AS derived_price_volume_reconciliation_ratio,
  'PUBLIC + DERIVED_FROM_PUBLIC_FACTS' AS data_treatment,
  ds.source_title,ds.source_url,o.source_locator,o.data_type,o.data_quality,o.notes
FROM compute_facility_operation_fact_v1 o
JOIN enterprise_data_center_v2 f ON f.facility_v2_id=o.facility_v2_id
JOIN data_source ds ON ds.source_id=o.source_id;
