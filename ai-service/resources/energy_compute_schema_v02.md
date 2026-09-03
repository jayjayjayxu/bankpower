# EnergyComputeAI V0.2 AI Schema Dictionary

## Scope and execution boundary

Database: spdb_power_finance (MySQL 8). This is the only schema available to V0.2.
The SQL tool can query only the 12 objects documented below. It accepts one read-only query and enforces a maximum of 100 returned detail rows. All database values are returned in their stored unit; presentation code, not the model, performs any optional conversion.

This release answers verifiable electricity, compute-facility, product-mapping, and stored model-result facts only. It does not answer policy interpretation, green-loan eligibility, financing risk, subjective ranking, service quality, ownership beyond listed fields, or any external fact.

## Common data-boundary fields

- data_type — fact origin. PUBLIC is public evidence; SIMULATED is a scenario; MIXED contains both.
- data_quality — source-quality label. It is not a credit or operating-quality rating.
- source_locator — source position for a disclosed fact.
- notes — data-boundary and disclosure caveats; return it when the user asks about scope or uncertainty.

## 1. enterprise_data_center_v2 — compute facility master

One row is one known compute/data-center facility. Facility identity is facility_v2_id; user-facing stable code is facility_code.

Fields:
- facility_v2_id — internal facility key.
- facility_code — stable facility code, for example SZCF016.
- official_name — official facility name.
- facility_alias — separated alternative names; use only for entity resolution.
- facility_kind — AI_COMPUTE, SUPERCOMPUTE, IDC, FINANCIAL_DC, or DISTRIBUTED_CLUSTER.
- locality_scope — LOCAL_SHENZHEN, SHENSHAN, OUT_OF_SHENZHEN, MULTI_REGION, or UNDISCLOSED.
- province_name, city_name, district_name — administrative location text.
- operator_company_id, operator_name, owner_name — disclosed operator/owner identity.
- lifecycle_status, operation_start_date — operation state and start date.
- physical_capacity_countable — 1 means usable as local physical capacity; 0 means aggregate, off-site, or unclear and must not be counted as Shenzhen physical capacity.
- green_certification — disclosed certification text only.
- last_verified_date — most recent verification date.
- data_type, data_quality, notes — provenance and boundary fields.

## 2. compute_facility_metric_v1 — facility metrics

One row is one metric in a stated scope and date. Join facility_v2_id to enterprise_data_center_v2.facility_v2_id.

Fields:
- facility_metric_id — metric key.
- facility_v2_id — facility foreign key.
- metric_code — metric name. PUE, CABINET_COUNT, ANNUAL_ELECTRICITY_CONSUMPTION, COMPUTE_CAPACITY, and GREEN_POWER_RATIO are common values.
- metric_scope — exact measurement scope; never drop it for PUE or capacity.
- metric_value, metric_value_upper, metric_text — numerical, upper-bound, or text value.
- metric_unit — stored unit, such as RATIO, KWH, CABINET, PFLOPS, EFLOPS, WANYUAN.
- compute_precision, value_operator — value precision and operator.
- disclosure_status — DISCLOSED, DERIVED, PLANNED, TARGET, or NOT_DISCLOSED.
- as_of_date — metric date.
- statistical_scope — disclosure coverage.
- usable_for_facility_model — model-input eligibility flag.
- source_locator, evidence_grade, data_quality, notes — evidence boundary.

PUE rule: filter metric_code='PUE'. PUE is a ratio, not a percentage and not an occupancy rate.

## 3. compute_facility_operation_fact_v1 — disclosed facility operations

One row is an operation fact for a facility, scope, year, and period. Join facility_v2_id to enterprise_data_center_v2.facility_v2_id.

Fields:
- operation_fact_id, facility_v2_id — fact key and facility foreign key.
- operation_scope_code, operation_scope_name — mandatory operating scope.
- fact_year, fact_period — time. fact_period includes ANNUAL and H1.
- rack_capacity_count — installed rack capacity, unit cabinet.
- average_occupied_rack_count — annual or period-average occupied racks, unit cabinet.
- rack_utilization_ratio — rack occupancy rate as decimal ratio; aliases include 上架率 and 入住率.
- high_power_occupied_rack_count, high_power_threshold_kw — high-power rack count and threshold, unit kW.
- hosting_revenue_wanyuan, hosting_cost_wanyuan — hosting revenue/cost, unit 万元.
- hosting_gross_margin — hosting margin as decimal ratio.
- average_rack_price_yuan_month, average_rack_cost_yuan_month — price/cost, unit 元/柜/月.
- electricity_consumption_kwh — electricity consumption, unit kWh.
- electricity_purchase_wanyuan, electricity_purchase_tax_included_wanyuan — power purchase amount, unit 万元; tax basis differs and must not be mixed.
- electricity_purchase_price_yuan_kwh — purchase price, unit 元/kWh.
- electricity_purchase_price_tax_included_flag — 1 means tax-included price.
- electricity_cost_revenue_ratio, hosting_revenue_yuan_kwh — ratios and revenue-per-kWh.
- source_locator, data_type, data_quality, notes — source and scope caveats.

## 4. compute_facility_rack_price_tier_fact_v1 — rack price tiers

One row is a facility building, time, and rack-power price tier. Join facility_v2_id to enterprise_data_center_v2.facility_v2_id.

Fields:
- rack_price_tier_fact_id, facility_v2_id — key and facility foreign key.
- building_scope_code — BUILDING_1 or BUILDING_4.
- fact_year, fact_period — time and period.
- power_tier_code, power_from_kw, power_to_kw, upper_bound_inclusive — tier definition in kW.
- actual_average_price_yuan_rack_month — actual average price, unit 元/柜/月.
- source_locator, data_type, data_quality, notes — evidence boundary.

## 5. compute_platform_resource_listing_v1 — public compute product listing

One row is a platform product listing, not necessarily a known physical facility.

Fields:
- listing_id — listing key.
- platform_id — platform key.
- facility_v2_id — confirmed facility foreign key only when non-null; do not infer from product name.
- external_product_id, product_name, provider_name, resource_type — external listing identity.
- accelerator_model, accelerator_count, accelerator_memory_gb — accelerator specification.
- cpu_cores, system_memory_gb — host specification.
- compute_capacity_value, compute_capacity_unit, compute_precision — listed compute capacity.
- platform_region_label, available_zone, physical_region_text, locality_scope — platform/location labels.
- availability_status, source_updated_at, captured_at — listing time/status.
- source_api_url, data_quality, notes — source/boundary fields.

## 6. compute_listing_candidate_mapping_v1 — product candidate mapping

One row is a candidate relationship between a product listing and an entity. Join listing_id to compute_platform_resource_listing_v1.listing_id; join candidate_facility_v2_id to enterprise_data_center_v2.facility_v2_id when present.

Fields:
- candidate_mapping_id, listing_id — mapping and listing keys.
- candidate_mapping_type — EXTERNAL_SAME_GPU_REFERENCE, PROVIDER_CANDIDATE, or FACILITY_CANDIDATE.
- candidate_entity_type, candidate_name, candidate_facility_v2_id — candidate identity.
- mapping_status — UNMAPPED, INDICATIVE, or CONFIRMED. Only CONFIRMED is an actual mapping.
- confidence_level, confidence_score — evidence confidence, not confirmation.
- direct_sku_evidence_flag, platform_relation_evidence_flag, candidate_asset_evidence_flag — available evidence flags.
- source_locator, evidence_summary, boundary_note — evidence explanation; include these for candidate questions.
- verified_at, data_type, data_quality, model_version, updated_at — record provenance.

## 7. enterprise_profile — electricity enterprise master

One row is one enterprise. Join company_id to enterprise power and model-result objects.

Fields:
- company_id, company_name, company_alias — enterprise identity and aliases.
- city_name, district_name, industry_name, power_chain_role, energy_customer_type — geography and business classification.
- high_power_user_flag, data_center_flag, manufacturing_flag, energy_company_flag — boolean enterprise attributes.
- existing_solar_flag, existing_solar_mw, existing_storage_flag, existing_storage_mwh — installed assets in MW/MWh.
- vpp_participant_flag, green_power_flag, green_power_ratio — disclosed participation and green-power ratio.
- verification_priority, business_verification_status, notes — verification metadata.

## 7A. enterprise_financial — enterprise annual financial facts

One row is one enterprise's disclosed or authorised annual financial record. Join company_id to enterprise_profile.company_id. A missing row means that the financial fact is unavailable; it must never be inferred from an energy or project-model record.

Fields:
- company_id, financial_year — enterprise and reporting-year identity.
- revenue_wanyuan, revenue_growth, net_profit_wanyuan — operating results, in 万元 except the decimal growth ratio.
- total_assets_wanyuan, total_liabilities_wanyuan, total_equity_wanyuan, debt_ratio — balance-sheet facts; debt_ratio is a decimal ratio.
- operating_cashflow_wanyuan — operating cash flow, in 万元.
- currency, source_id, data_quality, statistical_scope, notes — currency, source and disclosure boundary.

## 8. enterprise_monthly_power — monthly enterprise consumption

One row is one company, year, month, and load scenario. Join company_id to enterprise_profile.company_id.

Fields:
- record_id, company_id, load_scenario_id — row, enterprise, and scenario identity.
- year, month — monthly time key.
- power_consumption_kwh — monthly consumption, unit kWh.
- power_yoy, power_mom — decimal growth ratios.
- electricity_cost_yuan, average_price_yuan_kwh — cost in 元 and average price in 元/kWh.
- peak_power_kwh, flat_power_kwh, valley_power_kwh, critical_peak_kwh — time-of-use consumption, unit kWh.
- peak_ratio, valley_ratio — decimal ratios.
- max_demand_kw — maximum demand, unit kW.
- energy_charge_yuan, demand_charge_yuan, basic_charge_method, demand_price — bill components.
- data_type, data_quality, is_derived, calculation_formula, notes — source boundary.

Annual rule: SUM(power_consumption_kwh) is permitted only after filtering/grouping an explicit year and scenario/data_type. Prefer v_enterprise_annual_energy_summary when a calendar-year total is requested.

## 9. v_enterprise_annual_energy_summary — annual enterprise energy view

This view has one annual aggregate per company, year, and data_type. Join company_id to enterprise_profile.company_id.

Fields:
- company_id, year, data_type — annual identity and origin.
- annual_power_kwh — annual consumption, unit kWh. Do not sum it again across months.
- annual_electricity_cost_yuan — annual cost, unit 元.
- avg_cost_yuan_kwh — average cost, unit 元/kWh.
- peak_plus_critical_ratio, valley_ratio — annual time-of-use ratios.
- annual_max_demand_kw — annual maximum demand, unit kW.

## 10. electricity_tariff — published electricity tariff

One row is an applicable tariff segment; it is not an enterprise's actual paid bill.

Fields:
- tariff_id, region_id, price_zone_id — tariff identity.
- year, month, effective_date, expiry_date — applicable time.
- customer_type, voltage_level, market_type, time_period, start_time_text, end_time_text — tariff conditions.
- energy_price_yuan_kwh, transmission_price_yuan_kwh, line_loss_price_yuan_kwh, system_operation_yuan_kwh, government_fund_yuan_kwh — component prices in 元/kWh.
- capacity_price, capacity_price_unit, demand_price, demand_price_unit — capacity/demand terms.
- final_price_yuan_kwh — tariff final price, unit 元/kWh.
- statistical_scope, notes — tariff scope and caveats.

## 11. analysis_run — model-run master

One row is one stored analysis run. Join run_id to analysis_result_snapshot.run_id. Only status='COMPLETED' should be used for current result questions.

Fields:
- run_id, run_name — run identity.
- model_version, storage_version, finance_version, policy_version — model versions.
- run_type, analysis_year, description — scenario type and scope.
- created_time, completed_time, created_by, status — lifecycle metadata.

## 12. analysis_result_snapshot — stored enterprise model result

One row is one enterprise result snapshot for a run. It is a model output, not actual cash flow or a credit decision. Join run_id to analysis_run.run_id and company_id to enterprise_profile.company_id.

Fields:
- snapshot_id, run_id, company_id, company_name, snapshot_version, analysis_date — snapshot identity.
- model_version, storage_version, finance_version, policy_version, data_type — model provenance.
- storage_power_mw, storage_capacity_mwh, storage_duration_hour, storage_configuration — storage configuration.
- capex_wanyuan, annual_benefit_wanyuan, npv_wanyuan, irr, payback_year — scenario economics.
- base_debt_ratio, base_loan_amount_wanyuan, base_min_dscr, max_debt_ratio, max_loan_amount_wanyuan — stored scenario finance outputs. They are not lending advice.
- financing_status, tariff_spread_risk, capex_risk, grid_capacity_risk, degradation_risk, overall_risk, overall_sensitivity_risk — scenario labels.
- opportunity_level, readiness_level, risk_level, recommended_product, recommended_product_status, potential_financing_amount_wanyuan, business_priority — research workflow fields, not credit grades.
- summary_title, recommendation_text, risk_summary, created_time — stored scenario text and timestamp.

## Relationships

- compute_facility_metric_v1.facility_v2_id = enterprise_data_center_v2.facility_v2_id
- compute_facility_operation_fact_v1.facility_v2_id = enterprise_data_center_v2.facility_v2_id
- compute_facility_rack_price_tier_fact_v1.facility_v2_id = enterprise_data_center_v2.facility_v2_id
- compute_platform_resource_listing_v1.facility_v2_id = enterprise_data_center_v2.facility_v2_id only when confirmed in the listing
- compute_listing_candidate_mapping_v1.listing_id = compute_platform_resource_listing_v1.listing_id
- compute_listing_candidate_mapping_v1.candidate_facility_v2_id = enterprise_data_center_v2.facility_v2_id
- enterprise_monthly_power.company_id = enterprise_profile.company_id
- v_enterprise_annual_energy_summary.company_id = enterprise_profile.company_id
- analysis_result_snapshot.company_id = enterprise_profile.company_id
- enterprise_financial.company_id = enterprise_profile.company_id
- analysis_result_snapshot.run_id = analysis_run.run_id

## Entity aliases

- 百旺信, 深圳百旺信, 百旺信智算中心, 深圳百旺信智算中心, 深圳百旺信云数据中心, 百旺信云数据中心三期, FAC-SZ-001 -> facility_code SZCF016, official_name 深圳百旺信智算中心.
- Product aliases are listing identifiers only. They must never be converted into a facility without a CONFIRMED mapping.
