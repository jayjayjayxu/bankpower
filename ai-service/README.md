# EnergyComputeAI V0.2 API

该服务将既有 `BankAI V0.4` 封装为可由网页调用的 HTTP API，并在 V0.2 将电力/算力事实问题迁移至 `spdb_power_finance` 的 Text-to-SQL 链路。

- 仅开放 12 个经审计的电力、算力、商品映射和模型结果对象；完整字段、时间、单位及关联定义见 `resources/energy_compute_schema_v02.md`。
- 模型只生成 SQL；每一条 SQL 均须通过 AST 白名单、安全函数、只读、单语句、最多四表和 LIMIT 校验，才会在只读事务执行。
- 数值结果由程序按数据库原始精度和单位转述，不让模型自行换算比率、金额、功率或电量。
- 政策解释、绿色资格、融资风险、授信建议与主观优劣判断在 V0.2 明确拒答，留待后续工具层。
- 商品—设施映射只有 `CONFIRMED` 才能称为确认关系；`INDICATIVE` 和 `UNMAPPED` 仅返回候选与边界说明。

## 提供的接口

- `GET /api/health`：检查 BankAI 索引、旧版 `bank_ai` 与 `spdb_power_finance` 只读登录路径；不启动模型，也不调用 LLM。
- `POST /api/chat`：返回答案、结构化查询结果、数据对象来源与风险提示。公开响应不包含 SQL 原文。
- `POST /api/debug/sql`：仅开发环境使用；默认关闭，启用后仍要求 `X-Admin-Token`。它返回生成 SQL、安全检查和原始结果，且同样写入审计记录。

每个成功或失败请求均会在 `AI_API_AUDIT_DIR/YYYY-MM-DD/<request_id>.json` 留存完整审计记录。前端响应不包含 SQL 原文、模型原始回复、拆解细节或内部 Chain。

## 本地运行

先使用已有 BankAI V0.4 的虚拟环境，安装 API 依赖：

```bash
cd /Users/xubolun/codex_project/bank/bank-ai
.venv/bin/python -m pip install -r /Users/xubolun/codex_project/bank-power/project/ai-service/requirements.txt
```

然后在不提交的环境文件中配置变量（可从 `.env.example` 复制）。`BANKAI_CORE_DIR` 应指向现有 BankAI 根目录；`DEEPSEEK_API_KEY` 仅能来自运行环境。当前本机示例使用已有的 `bank_ai_local` 登录路径；部署前必须将 `SPDB_SQL_LOGIN_PATH` 换成只具备 `spdb_power_finance` 查询权限的专用账户。

```bash
cd /Users/xubolun/codex_project/bank-power/project/ai-service
export BANKAI_CORE_DIR=/Users/xubolun/codex_project/bank/bank-ai
export DEEPSEEK_API_KEY='仅在当前终端设置'
export SPDB_SQL_LOGIN_PATH=bank_ai_local
export SPDB_DATABASE=spdb_power_finance
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

验证健康检查：

```bash
curl http://127.0.0.1:8090/api/health
```

## 测试

测试使用注入的假 Agent / 假数据库执行器，不会调用 DeepSeek、FAISS 或 MySQL；覆盖 V0.2 实体解析、SQL Safety、SQL-only 拒答、输入校验、私有调试接口和审计写入。

```bash
cd /Users/xubolun/codex_project/bank-power/project/ai-service
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  -m unittest discover -s tests -v
```

真实部署前，请确认 `bank_ai_reader` 与 `SPDB_SQL_LOGIN_PATH` 都是只读 MySQL 登录路径，并通过健康检查。固定评测集位于 `eval/v02_gold_set.json`，共有 60 题（50 条 Gold SQL + 10 条拒答）。以下三类问题可用于本地验收：

```text
深圳百旺信智算中心2025年的上架率和平均机柜价格是多少？
哪些算力中心PUE低于1.3？
B200-C4-1对应哪个数据中心？
```

回答中的 SQL 事实、实体解析、SQL Safety 与查询结果都会进入审计记录。所有融资与绿色资格问题均不属于 V0.2，必须在后续工具层结合尽调和审批复核。
