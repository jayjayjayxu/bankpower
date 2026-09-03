-- TEST ONLY: Synthetic data for EnergyComputeAI demonstrations.
-- These values are fictional and must never be presented as Shenzhen Metro's
-- audited disclosures, operating statistics, or a real credit opinion.

CREATE TABLE IF NOT EXISTS enterprise_operational_statistic_v1 (
    statistic_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    company_id VARCHAR(32) NOT NULL,
    statistic_year INT NOT NULL,
    metric_code VARCHAR(64) NOT NULL,
    metric_value DECIMAL(24,4) NOT NULL,
    metric_unit VARCHAR(32) NOT NULL,
    data_type VARCHAR(32) NOT NULL,
    source_id VARCHAR(128) NOT NULL,
    data_quality VARCHAR(64) NOT NULL,
    statistical_scope VARCHAR(255) NOT NULL,
    notes VARCHAR(1000) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (statistic_id),
    UNIQUE KEY uq_enterprise_operation_test (company_id, statistic_year, metric_code, data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO data_source (
    source_id, source_org, source_title, source_url, source_date, source_tier,
    data_quality, statistical_scope, source_hash, notes
) VALUES (
    902025001, 'EnergyComputeAI Test Data', 'TEST-SEED-SZMETRO-2025-V1', NULL, '2025-12-31', 'TEST',
    'SIMULATED_TEST_ONLY', 'Synthetic corporate credit-analysis scenario for demonstration only',
    '9020250010f1c7b9434d6e8a0b2c4d6e8f1029384756aabbccddeeff00112233',
    'TEST ONLY. Fictional source registry entry; not an enterprise disclosure or third-party source.'
)
ON DUPLICATE KEY UPDATE source_id=source_id;

INSERT INTO enterprise_financial (
    company_id, financial_year, revenue_wanyuan, revenue_growth, net_profit_wanyuan,
    total_assets_wanyuan, total_liabilities_wanyuan, total_equity_wanyuan, debt_ratio,
    operating_cashflow_wanyuan, currency, source_id, data_quality, statistical_scope, notes
) VALUES (
    'C000020', 2025, 2200000.0000, 0.0450, 80000.0000,
    18000000.0000, 11400000.0000, 6600000.0000, 0.63333333,
    360000.0000, 'CNY', 902025001, 'SIMULATED_TEST_ONLY',
    'Synthetic consolidated annual scenario for demonstration only',
    'TEST ONLY. Fictional values generated for EnergyComputeAI credit-analysis demonstration; not Shenzhen Metro disclosures.'
)
ON DUPLICATE KEY UPDATE
    revenue_wanyuan=IF(source_id=902025001, VALUES(revenue_wanyuan), revenue_wanyuan),
    revenue_growth=IF(source_id=902025001, VALUES(revenue_growth), revenue_growth),
    net_profit_wanyuan=IF(source_id=902025001, VALUES(net_profit_wanyuan), net_profit_wanyuan),
    total_assets_wanyuan=IF(source_id=902025001, VALUES(total_assets_wanyuan), total_assets_wanyuan),
    total_liabilities_wanyuan=IF(source_id=902025001, VALUES(total_liabilities_wanyuan), total_liabilities_wanyuan),
    total_equity_wanyuan=IF(source_id=902025001, VALUES(total_equity_wanyuan), total_equity_wanyuan),
    debt_ratio=IF(source_id=902025001, VALUES(debt_ratio), debt_ratio),
    operating_cashflow_wanyuan=IF(source_id=902025001, VALUES(operating_cashflow_wanyuan), operating_cashflow_wanyuan),
    currency=IF(source_id=902025001, VALUES(currency), currency),
    source_id=IF(source_id=902025001, VALUES(source_id), source_id),
    data_quality=IF(source_id=902025001, VALUES(data_quality), data_quality),
    statistical_scope=IF(source_id=902025001, VALUES(statistical_scope), statistical_scope),
    notes=IF(source_id=902025001, VALUES(notes), notes);

INSERT INTO enterprise_operational_statistic_v1 (
    company_id, statistic_year, metric_code, metric_value, metric_unit, data_type,
    source_id, data_quality, statistical_scope, notes
) VALUES (
    'C000020', 2025, 'PASSENGER_VOLUME', 1900000000.0000, 'PERSON_TRIPS', 'SIMULATED',
    'TEST-SEED-SZMETRO-2025-V1', 'SIMULATED_TEST_ONLY',
    'Synthetic annual network passenger-volume scenario for demonstration only',
    'TEST ONLY. Fictional passenger-volume value; not an actual Shenzhen Metro operating statistic.'
)
ON DUPLICATE KEY UPDATE
    metric_value=VALUES(metric_value), metric_unit=VALUES(metric_unit), source_id=VALUES(source_id),
    data_quality=VALUES(data_quality), statistical_scope=VALUES(statistical_scope), notes=VALUES(notes);
