# EnergyComputeAI V0.3 政策知识库

原始政策、银行制度和企业披露文件不进入 Git。它们由部署环境以只读方式挂载，根目录通过
`POLICY_CORPUS_ROOT` 指定；登记清单位于 `../resources/policy_metadata_v03.csv`。

目录逻辑由 metadata 的 `policy_level`、`region`、`topic` 与 `confidentiality` 决定，而不是把所有
文件混在一个向量库中。公开网站只构建并访问 `PUBLIC` 且在查询日 `EFFECTIVE` 的独立索引；未来的
`INTERNAL` 与 `RESTRICTED` 文档必须建立物理隔离的索引，绝不能先全量检索再由模型遮蔽。

首批来源文件目前位于本机 `政策文件/` 与 `算力政策文件/`。构建时执行：

```bash
cd /Users/xubolun/codex_project/bank-power/project/ai-service
export POLICY_CORPUS_ROOT=/Users/xubolun/codex_project/bank-power
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  tools/build_policy_corpus.py --as-of 2026-09-01
```

然后建立只包含 `PUBLIC + EFFECTIVE` 文档的独立索引：

```bash
export BANKAI_CORE_DIR=/Users/xubolun/codex_project/bank/bank-ai
PYTHONPATH=. /Users/xubolun/codex_project/bank/bank-ai/.venv/bin/python \
  tools/build_policy_faiss_index.py
```

`PUBLIC + EFFECTIVE` 与未来的 `INTERNAL`、`RESTRICTED` 索引必须物理分离；RAG API 会在 V0.3-B 接入这一访问边界。
