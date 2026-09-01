# EnergyComputeAI V0.2 API

该服务将既有 `BankAI V0.4` 封装为可由网页调用的 HTTP API，并新增面向 `spdb_power_finance` 的受控算力问答层。

- 算力设施运营数字走参数受控的只读 SQL 模板；不让模型生成 SQL，也不让模型猜数值。
- 政策问题从已入库的政策原子规则中检索，并返回文件名、定位信息、短引文与官方链接（如有）。
- 绿色贷款等综合问题同时读取项目事实、政策条件和尽调状态；当项目级 CFADS 或债务偿付资料缺失时，融资工具只返回 `INSUFFICIENT_INPUT`，不会输出贷款比例。
- 其它问题仍惰性委托给不改动的 BankAI V0.4 核心。

## 提供的接口

- `GET /api/health`：检查 BankAI 索引、旧版 `bank_ai` 与 `spdb_power_finance` 只读登录路径；不启动模型，也不调用 LLM。
- `POST /api/chat`：返回答案、结构化查询结果、政策/文件定位、融资测算边界、Claim 和风险提示。

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

测试使用注入的假 Agent / 假数据库执行器，不会调用 DeepSeek、FAISS 或 MySQL；覆盖旧 BankAI 的 `RAG`、`SQL`、`BOTH`、`OUT_OF_SCOPE` 四条路径，以及算力 SQL、政策检索、融资拒答、输入校验和审计写入。

```bash
cd /Users/xubolun/codex_project/bank-power/project/ai-service
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  -m unittest discover -s tests -v
```

真实部署前，请确认 `bank_ai_reader` 与 `SPDB_SQL_LOGIN_PATH` 都是只读 MySQL 登录路径，并通过健康检查。以下三类问题可用于本地验收：

```text
深圳百旺信智算中心2025年的上架率和平均机柜价格是多少？
深圳训力券对算力服务商是否构成直接收入？
百旺信这种项目是否适合做绿色贷款，预计能做到多少贷款比例？
```

回答中的 SQL 事实、政策引用与计算边界都会进入审计记录。所有融资与绿色资格结论均为初步研究判断，必须由人工尽调与审批复核。
