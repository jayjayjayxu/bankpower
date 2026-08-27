# Java API

Spring Boot 只读接口，读取本机 `spdb_power_finance`，不执行数据库写入。

```bash
export DB_USER=root
export DB_PASSWORD='你的本机数据库密码'
./mvnw spring-boot:run
```

默认地址为 `http://127.0.0.1:8081`。数据库地址、账号、密码和端口均通过环境变量配置，便于迁移。

- `GET /api/health`
- `GET /api/power-source-structure/overview`
- `GET /api/enterprises/home-summary`
- `GET /api/enterprises?query=&limit=100`
- `GET /api/enterprises/{companyId}`
- `GET /api/enterprises/{companyId}/load-price-window?year=2025`
- `GET /api/enterprises/{companyId}/hourly-load?year=2025&page=0&size=24`

算力公开事实与V1经营模型接口：

- `GET /api/compute/summary`
- `GET /api/compute/policy/overview`
- `GET /api/compute/opportunities`
- `GET /api/compute/opportunities/{opportunityCode}`
- `GET /api/compute/facilities?query=&page=0&size=20`
- `GET /api/compute/facilities/{facilityCode}`
- `GET /api/compute/facilities/{facilityCode}/operations`（百旺信公开经营事实与三期项目级研究情景）
- `GET /api/compute/power-synergy/{facilityCode}`（区域电价、电源结构与设施级算电协同成本情景）
- `GET /api/compute/products?query=&page=0&size=20`
- `GET /api/compute/products/{listingId}`
- `GET /api/compute/prices?query=&priceScope=&page=0&size=20`
- `GET /api/compute/economics?query=&scenarioVersion=COMPUTE_BASE_V1&page=0&size=20`
- `GET /api/compute/project-economics?query=&scenarioVersion=COMPUTE_BASE_V1&page=0&size=20`
- `GET /api/compute/sensitivity?query=&variableCode=&page=0&size=20`
- `GET /api/compute/financing-capacity?query=&scenarioVersion=COMPUTE_BASE_V1&page=0&size=20`
- `GET /api/compute/financing-capacity/{projectEconomicsResultId}/curve`
- `GET /api/compute/credit-policies`
- `GET /api/compute/bank-recommendations?scenarioVersion=COMPUTE_BASE_V1&policyCode=CREDIT_BASE_V1`
- `GET /api/compute/bank-recommendations/{projectEconomicsResultId}/curve?policyCode=CREDIT_BASE_V1`

首次初始化V1模型表：

```bash
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_model_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_model_v1_phase2.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_bank_policy_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_candidate_mapping_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_policy_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_finance_opportunity_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_baiwangxin_operation_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_baiwangxin_phase3_scenario_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_baiwangxin_phase3_due_diligence_v1.sql
/usr/local/mysql-8.0.42-macos15-arm64/bin/mysql -uroot -p < sql/compute_power_synergy_v1.sql
```

经济性结果使用公开商品报价，但利用率、设备功率、PUE、电价和其他OPEX可能为研究情景；接口会返回数据类型和研究边界，不能直接解释为实际项目现金流或授信结论。

政策接口仅作公开条款、名单和初步适用性呈现。政策支持须以项目级证据和实际申报/结算结果为准，未获批的金额不进入模型现金流。

`compute_baiwangxin_operation_v1.sql` 补入深圳百旺信智算中心的公开经营事实：年度上架率、机柜收入/成本、电量、分功率成交均价和深圳移动合同条款。全园区1栋+4栋经营口径与三期项目口径分表保存；该事实层不自动生成项目NPV、IRR或授信结论。

`compute_baiwangxin_phase3_scenario_v1.sql` 在三期公开CAPEX、机柜数、PUE和年用电批复的基础上，建立保守/基准/乐观三档十年现金流代理情景。它明确区分公共事实与三期代理参数，并逐年检查年用电边界；不等同于三期实际收入、CFADS、估值或授信建议。

`compute_baiwangxin_phase3_due_diligence_v1.sql` 建立三期项目单独的尽调状态清单，逐项区分已核验、口径不完整与待补材料，并保留公开来源与下一步动作。

`compute_power_synergy_v1.sql` 仅以百旺信三期为首个设施级样本：把深圳分时电价、深圳本地清洁电源装机信号、广东发电结构、绿电采购和储能移峰假设写入成本覆盖。未公开的小时负荷、绿电结算、储能工程、需求响应注册/测试/结算一律保留为情景或待补材料；需求响应收益为零，不进入既有融资结果。
