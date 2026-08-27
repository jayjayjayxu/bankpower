CREATE TABLE IF NOT EXISTS enterprise_data_center_v2 (
    facility_v2_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_code VARCHAR(32) NOT NULL,
    legacy_data_center_id BIGINT UNSIGNED NULL,
    operator_company_id VARCHAR(16) NULL,
    owner_company_id VARCHAR(16) NULL,
    region_id SMALLINT UNSIGNED NULL,

    official_name VARCHAR(255) NOT NULL,
    facility_alias VARCHAR(500) NULL,
    facility_kind VARCHAR(40) NOT NULL
        COMMENT 'AI_COMPUTE/SUPERCOMPUTE/IDC/FINANCIAL_DC/DISTRIBUTED_CLUSTER',
    locality_scope VARCHAR(32) NOT NULL
        COMMENT 'LOCAL_SHENZHEN/SHENSHAN/OUT_OF_SHENZHEN/MULTI_REGION/UNDISCLOSED',
    province_name VARCHAR(64) NULL,
    city_name VARCHAR(64) NULL,
    district_name VARCHAR(64) NULL,
    address_text VARCHAR(500) NULL,

    operator_name VARCHAR(255) NULL,
    owner_name VARCHAR(255) NULL,
    lifecycle_status VARCHAR(48) NOT NULL,
    operation_start_date DATE NULL,
    physical_capacity_countable TINYINT(1) NOT NULL DEFAULT 1
        COMMENT '0表示聚合/异地/口径未明，不得汇入深圳本地物理容量',
    green_certification VARCHAR(128) NULL,

    primary_source_id BIGINT UNSIGNED NULL,
    last_verified_date DATE NOT NULL,
    data_type VARCHAR(16) NOT NULL DEFAULT 'PUBLIC',
    data_quality VARCHAR(16) NOT NULL,
    notes TEXT NULL,
    model_version VARCHAR(16) NOT NULL DEFAULT 'V2.0',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_facility_code (facility_code),
    KEY idx_compute_facility_company (operator_company_id),
    KEY idx_compute_facility_region (region_id, locality_scope),
    KEY idx_compute_facility_status (lifecycle_status),
    KEY idx_compute_facility_source (primary_source_id),

    CONSTRAINT fk_compute_facility_legacy
        FOREIGN KEY (legacy_data_center_id) REFERENCES enterprise_data_center(data_center_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_operator
        FOREIGN KEY (operator_company_id) REFERENCES enterprise_profile(company_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_owner
        FOREIGN KEY (owner_company_id) REFERENCES enterprise_profile(company_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_region
        FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_facility_source
        FOREIGN KEY (primary_source_id) REFERENCES data_source(source_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_compute_facility_locality
        CHECK (locality_scope IN ('LOCAL_SHENZHEN','SHENSHAN','OUT_OF_SHENZHEN','MULTI_REGION','UNDISCLOSED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力设施V2主表：物理设施、异地集群与调度口径分离';


CREATE TABLE IF NOT EXISTS compute_facility_metric_v1 (
    facility_metric_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    metric_code VARCHAR(48) NOT NULL,
    metric_scope VARCHAR(64) NOT NULL,
    metric_value DECIMAL(28,8) NULL,
    metric_value_upper DECIMAL(28,8) NULL,
    metric_text VARCHAR(500) NULL,
    metric_unit VARCHAR(32) NULL,
    compute_precision VARCHAR(24) NULL,
    value_operator VARCHAR(8) NOT NULL DEFAULT 'EQ',
    disclosure_status VARCHAR(24) NOT NULL
        COMMENT 'DISCLOSED/DERIVED/PLANNED/TARGET/NOT_DISCLOSED',
    as_of_date DATE NULL,
    statistical_scope VARCHAR(500) NOT NULL,
    usable_for_facility_model TINYINT(1) NOT NULL DEFAULT 1,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    evidence_grade VARCHAR(8) NOT NULL,
    data_quality VARCHAR(16) NOT NULL,
    notes TEXT NULL,
    model_version VARCHAR(16) NOT NULL DEFAULT 'V1.0',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_facility_metric
        (facility_v2_id, metric_code, metric_scope, source_id, model_version),
    KEY idx_compute_metric_code (metric_code, disclosure_status),
    KEY idx_compute_metric_date (as_of_date),
    KEY idx_compute_metric_source (source_id),

    CONSTRAINT fk_compute_metric_facility
        FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_metric_source
        FOREIGN KEY (source_id) REFERENCES data_source(source_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_compute_metric_operator
        CHECK (value_operator IN ('EQ','GT','GE','LT','LE','APPROX','NA')),
    CONSTRAINT chk_compute_metric_status
        CHECK (disclosure_status IN ('DISCLOSED','DERIVED','PLANNED','TARGET','NOT_DISCLOSED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力设施逐字段指标：容量、精度、机柜、PUE、投资等均独立留痕';


CREATE TABLE IF NOT EXISTS compute_service_platform_v1 (
    platform_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    platform_code VARCHAR(32) NOT NULL,
    platform_name VARCHAR(255) NOT NULL,
    operator_name VARCHAR(255) NULL,
    operator_company_id VARCHAR(16) NULL,
    platform_type VARCHAR(40) NOT NULL
        COMMENT 'NATIONAL_SERVICE/NATIONAL_SUPERCOMPUTE/CITY_SCHEDULING/REGIONAL_SERVICE/RESEARCH_NETWORK',
    service_scope VARCHAR(255) NULL,
    website_url VARCHAR(1000) NULL,
    public_api_url VARCHAR(1000) NULL,
    resource_listing_public TINYINT(1) NOT NULL DEFAULT 0,
    price_public TINYINT(1) NOT NULL DEFAULT 0,
    scheduling_capability TINYINT(1) NOT NULL DEFAULT 0,
    transaction_capability TINYINT(1) NOT NULL DEFAULT 0,
    physical_capacity_owner_flag TINYINT(1) NOT NULL DEFAULT 0,
    primary_source_id BIGINT UNSIGNED NULL,
    as_of_date DATE NOT NULL,
    data_quality VARCHAR(16) NOT NULL,
    notes TEXT NULL,
    model_version VARCHAR(16) NOT NULL DEFAULT 'V1.0',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_platform_code (platform_code),
    KEY idx_compute_platform_type (platform_type),
    KEY idx_compute_platform_source (primary_source_id),
    CONSTRAINT fk_compute_platform_company
        FOREIGN KEY (operator_company_id) REFERENCES enterprise_profile(company_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_platform_source
        FOREIGN KEY (primary_source_id) REFERENCES data_source(source_id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力服务/调度/交易平台登记，不代表平台拥有相应物理算力';


CREATE TABLE IF NOT EXISTS compute_facility_platform_relation_v1 (
    relation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facility_v2_id BIGINT UNSIGNED NOT NULL,
    platform_id BIGINT UNSIGNED NOT NULL,
    relation_type VARCHAR(32) NOT NULL
        COMMENT 'CONNECTED/SCHEDULED/LISTED/SERVICE_NODE/RESEARCH_NODE',
    capacity_scope VARCHAR(40) NOT NULL
        COMMENT 'FACILITY_PHYSICAL/PLATFORM_AGGREGATE/PRODUCT_LISTING/UNDISCLOSED',
    relation_status VARCHAR(24) NOT NULL DEFAULT 'VERIFIED',
    included_in_local_capacity_total TINYINT(1) NOT NULL DEFAULT 0,
    as_of_date DATE NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    evidence_grade VARCHAR(8) NOT NULL,
    notes TEXT NULL,
    model_version VARCHAR(16) NOT NULL DEFAULT 'V1.0',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_facility_platform
        (facility_v2_id, platform_id, relation_type, model_version),
    KEY idx_compute_relation_platform (platform_id),
    KEY idx_compute_relation_source (source_id),
    CONSTRAINT fk_compute_relation_facility
        FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_relation_platform
        FOREIGN KEY (platform_id) REFERENCES compute_service_platform_v1(platform_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_relation_source
        FOREIGN KEY (source_id) REFERENCES data_source(source_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='设施与平台多对多关系，防止调度容量与物理容量重复计算';


CREATE TABLE IF NOT EXISTS compute_platform_resource_listing_v1 (
    listing_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    platform_id BIGINT UNSIGNED NOT NULL,
    facility_v2_id BIGINT UNSIGNED NULL,
    external_product_id VARCHAR(128) NOT NULL,
    product_name VARCHAR(500) NOT NULL,
    provider_name VARCHAR(255) NULL,
    resource_type VARCHAR(40) NULL,
    accelerator_model VARCHAR(128) NULL,
    accelerator_count DECIMAL(12,4) NULL,
    accelerator_memory_gb DECIMAL(18,4) NULL,
    cpu_cores DECIMAL(18,4) NULL,
    system_memory_gb DECIMAL(18,4) NULL,
    compute_capacity_value DECIMAL(28,8) NULL,
    compute_capacity_unit VARCHAR(32) NULL,
    compute_precision VARCHAR(24) NULL,
    platform_region_label VARCHAR(255) NULL,
    available_zone VARCHAR(255) NULL,
    physical_region_text VARCHAR(255) NULL,
    locality_scope VARCHAR(32) NOT NULL DEFAULT 'UNDISCLOSED',
    availability_status VARCHAR(32) NULL,
    source_updated_at DATETIME NULL,
    source_api_url VARCHAR(1000) NULL,
    captured_at DATETIME NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    raw_record_hash CHAR(64) NOT NULL,
    data_quality VARCHAR(16) NOT NULL,
    notes TEXT NULL,

    UNIQUE KEY uk_compute_resource_capture
        (platform_id, external_product_id, captured_at, raw_record_hash),
    KEY idx_compute_resource_model (accelerator_model),
    KEY idx_compute_resource_region (locality_scope),
    KEY idx_compute_resource_facility (facility_v2_id),
    CONSTRAINT fk_compute_resource_platform
        FOREIGN KEY (platform_id) REFERENCES compute_service_platform_v1(platform_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_resource_facility
        FOREIGN KEY (facility_v2_id) REFERENCES enterprise_data_center_v2(facility_v2_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_resource_source
        FOREIGN KEY (source_id) REFERENCES data_source(source_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力平台公开商品/资源快照；同一资源可能被多个平台重复展示';


CREATE TABLE IF NOT EXISTS compute_product_price_snapshot_v1 (
    price_snapshot_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    listing_id BIGINT UNSIGNED NULL,
    platform_id BIGINT UNSIGNED NOT NULL,
    external_product_id VARCHAR(128) NOT NULL,
    price_scope VARCHAR(32) NOT NULL
        COMMENT 'LIST_REFERENCE/DETAIL_CONFIG/DETAIL_ADDON/PROMOTION/NEGOTIATED_NOT_PUBLIC',
    billing_method VARCHAR(32) NULL,
    billing_cycle VARCHAR(32) NULL,
    minimum_term VARCHAR(64) NULL,
    price_value DECIMAL(24,8) NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    price_unit VARCHAR(64) NULL,
    tax_included_flag TINYINT(1) NULL,
    promotion_flag TINYINT(1) NOT NULL DEFAULT 0,
    configuration_text VARCHAR(1000) NULL,
    validation_status VARCHAR(32) NOT NULL DEFAULT 'OBSERVED',
    source_api_url VARCHAR(1000) NULL,
    captured_at DATETIME NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    raw_record_hash CHAR(64) NOT NULL,
    data_quality VARCHAR(16) NOT NULL,
    notes TEXT NULL,

    UNIQUE KEY uk_compute_price_capture
        (platform_id, external_product_id, price_scope, captured_at, raw_record_hash),
    KEY idx_compute_price_platform_time (platform_id, captured_at),
    KEY idx_compute_price_billing (billing_method, price_unit),
    CONSTRAINT fk_compute_price_listing
        FOREIGN KEY (listing_id) REFERENCES compute_platform_resource_listing_v1(listing_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compute_price_platform
        FOREIGN KEY (platform_id) REFERENCES compute_service_platform_v1(platform_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_compute_price_source
        FOREIGN KEY (source_id) REFERENCES data_source(source_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力产品价格快照；列表参考价与详情配置价必须分行保存';


CREATE TABLE IF NOT EXISTS compute_field_evidence_v1 (
    evidence_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    object_type VARCHAR(32) NOT NULL,
    object_code VARCHAR(128) NOT NULL,
    field_name VARCHAR(64) NOT NULL,
    field_value_text VARCHAR(1000) NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    source_locator VARCHAR(255) NULL,
    evidence_grade VARCHAR(8) NOT NULL,
    verification_status VARCHAR(24) NOT NULL,
    verified_at DATE NOT NULL,
    notes TEXT NULL,
    model_version VARCHAR(16) NOT NULL DEFAULT 'V1.0',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_compute_field_evidence
        (object_type, object_code, field_name, source_id, model_version),
    KEY idx_compute_evidence_object (object_type, object_code),
    KEY idx_compute_evidence_source (source_id),
    CONSTRAINT fk_compute_evidence_source
        FOREIGN KEY (source_id) REFERENCES data_source(source_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='算力字段级证据：禁止再以整行单一证据等级掩盖字段差异';


CREATE OR REPLACE VIEW v_compute_facility_public_summary_v1 AS
SELECT
    f.facility_code,
    f.official_name,
    f.facility_kind,
    f.locality_scope,
    f.district_name,
    f.operator_name,
    f.lifecycle_status,
    f.physical_capacity_countable,
    f.green_certification,
    f.data_quality,
    f.last_verified_date,
    GROUP_CONCAT(
        CONCAT(m.metric_code, '[', m.metric_scope, ']=',
               COALESCE(CAST(m.metric_value AS CHAR), m.metric_text, 'NULL'),
               COALESCE(CONCAT(' ', m.metric_unit), ''),
               COALESCE(CONCAT(' ', m.compute_precision), ''),
               ' {', m.disclosure_status, '}')
        ORDER BY m.metric_code, m.metric_scope SEPARATOR '; '
    ) AS disclosed_metrics,
    COUNT(m.facility_metric_id) AS disclosed_metric_count,
    f.notes
FROM enterprise_data_center_v2 f
LEFT JOIN compute_facility_metric_v1 m
  ON m.facility_v2_id = f.facility_v2_id
GROUP BY f.facility_v2_id;


CREATE OR REPLACE VIEW v_compute_product_price_conflict_v1 AS
SELECT
    p.platform_code,
    l.external_product_id,
    l.product_name,
    l.accelerator_model,
    l.accelerator_count,
    l.platform_region_label,
    l.available_zone,
    ref.price_value AS list_reference_price,
    ref.price_unit AS list_reference_unit,
    detail.price_value AS detail_config_price,
    detail.price_unit AS detail_config_unit,
    detail.configuration_text,
    CASE
      WHEN ref.price_value IS NULL OR ref.price_value = 0 THEN NULL
      ELSE (detail.price_value - ref.price_value) / ref.price_value
    END AS difference_ratio,
    detail.captured_at
FROM compute_product_price_snapshot_v1 detail
JOIN compute_product_price_snapshot_v1 ref
  ON ref.platform_id = detail.platform_id
 AND ref.external_product_id = detail.external_product_id
 AND ref.captured_at = detail.captured_at
 AND ref.price_scope = 'LIST_REFERENCE'
JOIN compute_platform_resource_listing_v1 l
  ON l.listing_id = detail.listing_id
JOIN compute_service_platform_v1 p
  ON p.platform_id = detail.platform_id
WHERE detail.price_scope = 'DETAIL_CONFIG'
  AND detail.validation_status = 'CONFLICT_WITH_LIST_REFERENCE';
