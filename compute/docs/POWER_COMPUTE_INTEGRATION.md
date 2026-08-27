# 电力站与算力站集成边界

## 目标结构

两个项目继续独立开发、独立构建，由同一反向代理组成统一门户：

```text
tairan-ecfiplatform.online/
├── power/          电力网站（project）
├── compute/        算力网站（project2）
├── api/power/      电力后端只读接口
└── api/compute/    算力后端只读接口
```

开发环境使用局域网地址，不依赖 `localhost`：

- 电力前端：`http://172.20.10.2:5173`
- 算力前端：`http://<本机局域网IP>:5174`
- 算力后端：`http://<本机局域网IP>:8082`

## 数据边界

共享的基础标识和证据层：

- `enterprise_profile.company_id`：企业统一标识；
- `data_source.source_id`：公开来源统一标识；
- `analysis_run.run_id`：完整模型运行标识；
- `enterprise_data_center_v2.facility_code`：算力设施独立标识。

电力模型表由电力服务维护；算力服务默认只读电价、能源结构和企业主数据，不能直接覆盖电力模型结果。算力设施、商品、价格和算力能源模型由算力服务维护。

## 当前算电协同样本

`compute_power_synergy_v1` 已先以深圳百旺信智算中心三期建立一条设施级结果链：

```text
百旺信三期基准电量与现金流代理
    + 深圳工商业分时电价（区域成本压力）
    + 深圳本地清洁电源装机信号（非设施绿电）
    + 广东发电结构（非设施碳足迹）
    + 绿电采购 / 储能移峰研究参数
    -> 算电协同成本及现金流变化代理
```

其中，项目实测小时负荷、绿电合同及结算、储能工程及接入容量、需求响应注册/测试/结算均未公开取得。它们不会回填为事实：绿电和储能只以 `SCENARIO` 运行，需求响应收益保持为零。电力侧原始表只读，算力侧结果写入独立的 `compute_power_synergy_*_v1` 表。

## 前端互通

两个网站的固定顶部都保留“电力研究 / 算力研究”切换器。算力前端通过
`VITE_POWER_SITE_URL` 配置电力站地址；统一部署时设置为 `/power/`。

企业级深链接后续统一为：

```text
/power/enterprise/{company_id}
/compute/company/{company_id}
/compute/facility/{facility_code}
```

## 联合结果

后续由门户汇总接口组合两边结果，不让前端自行拼接模型逻辑：

```text
GET /api/portal/company/{company_id}/opportunities
```

建议返回：电力机会、算力机会、共同能源成本、绿色属性、融资产品、数据可信度和快照版本。联合快照只保存最终业务结果，不复制8760小时数据或商品原始JSON。
