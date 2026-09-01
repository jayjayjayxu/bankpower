# EnergyComputeAI V0.1 API Baseline

该服务将既有 `BankAI V0.4` 封装为可由网页调用的 HTTP API。它不重写 Router、RAG、SQL、BOTH、Claim Grounding 或 SQL 安全校验；这些逻辑仍由 `BANKAI_CORE_DIR/src` 中的原核心执行。

## 提供的接口

- `GET /api/health`：检查 BankAI 索引和旧版只读数据库登录路径；不启动模型，也不调用 LLM。
- `POST /api/chat`：调用 `agent.run(question)`，返回前端所需的答案、SQL 数据、文件页码/短引文、Claim 和警告。

每个成功或失败请求均会在 `AI_API_AUDIT_DIR/YYYY-MM-DD/<request_id>.json` 留存完整审计记录。前端响应不包含 SQL 原文、模型原始回复、拆解细节或内部 Chain。

## 本地运行

先使用已有 BankAI V0.4 的虚拟环境，安装 API 依赖：

```bash
cd /Users/xubolun/codex_project/bank/bank-ai
.venv/bin/python -m pip install -r /Users/xubolun/codex_project/bank-power/project/ai-service/requirements.txt
```

然后在不提交的环境文件中配置变量（可从 `.env.example` 复制）。`BANKAI_CORE_DIR` 应指向现有 BankAI 根目录；`DEEPSEEK_API_KEY` 仅能来自运行环境。

```bash
cd /Users/xubolun/codex_project/bank-power/project/ai-service
export BANKAI_CORE_DIR=/Users/xubolun/codex_project/bank/bank-ai
export DEEPSEEK_API_KEY='仅在当前终端设置'
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

验证健康检查：

```bash
curl http://127.0.0.1:8090/api/health
```

## 测试

测试使用注入的假 Agent，不会调用 DeepSeek、FAISS 或 MySQL；覆盖 `RAG`、`SQL`、`BOTH`、`OUT_OF_SCOPE` 四条路径、输入校验和审计写入。

```bash
cd /Users/xubolun/codex_project/bank-power/project/ai-service
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  -m unittest discover -s tests -v
```

真实调用前，请先确认 `bank_ai_reader` 为只读 MySQL 登录路径，并通过健康检查。V0.1 仍使用旧 `bank_ai` Schema；迁移至 `spdb_power_finance` 属于下一阶段，不能与此基线混在一次变更中。
