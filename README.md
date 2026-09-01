# 电力能源金融机会分析平台

本目录承载网站相关代码，前端与后端分离，便于本地演示及后续迁移到云服务器。

```text
project/
├── frontend/       Vue 3 + JavaScript 展示页
├── backend/        Spring Boot 只读数据库接口
├── compute/        算力研究前后端及算电协同说明
├── ai-service/     BankAI V0.4 + 算力受控工具的 FastAPI 问答服务（V0.2）
├── tools/          本地开发辅助工具，不存放任何密钥
└── docker-compose.yml
```

## 本地运行

终端一（Java API）：

```bash
cd backend
export DB_PASSWORD='你的本机数据库密码'
./mvnw spring-boot:run
```

终端二（Vue）：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问终端输出的本机局域网地址，例如 `http://172.20.10.2:5173`。

## AI 智能问答（本地 V0.2）

`ai-service/` 在既有 BankAI V0.4 之上增加了受控算力问答路由：设施运营数值走只读
SQL 模板，政策结论走可定位的政策规则检索，绿色融资问题会调用项目尽调与 DSCR 规则边界。
当 CFADS、债务偿付等项目级资料不足时，服务明确拒绝输出贷款比例。网页入口为
`/ai-assistant`；本地 Vite 将 `/ai-api` 转发至 FastAPI 的 `8090` 端口。

BankAI Core、FAISS 索引和模型仍在网站仓库外，需要通过不提交的运行环境变量
`BANKAI_CORE_DIR` 指向。API 密钥仅通过 `DEEPSEEK_API_KEY` 注入；算力数据登录路径仅通过
`SPDB_SQL_LOGIN_PATH` 注入。具体启动、审计和测试命令见 [ai-service/README.md](ai-service/README.md)。

当前 Docker Compose 尚未包含该服务：在完成电力/算力 SQL 和政策库迁移前，不将依赖
旧 `bank_ai` 的基线服务部署到生产容器。

## Docker 预览

```bash
cp .env.example .env
# 编辑未提交的 .env，填写数据库密码
docker compose up --build
```

浏览器访问 `http://localhost:8080`。

## 服务器 Docker 部署

`docker-compose.server.yml` 用于将 MySQL、Java API 和 Vue/Nginx 一起运行。数据库快照不进入 Git，默认从服务器的 `/opt/bankpower-data/spdb_power_finance.sql.gz` 初始化。
国内云服务器如果无法直连 Docker Hub，可将 `deploy/docker-daemon.json` 安装为 `/etc/docker/daemon.json` 后重启 Docker。

```bash
cp server.env.example .env
# 在服务器修改 .env 中的数据库密码
docker compose -f docker-compose.server.yml up -d --build
```

对外只开放网页端口 `80`；两个 Java API 仅在容器网络内提供服务，由前端 Nginx 反向代理。部署后使用同一 IP 访问：

- `/`：电力研究首页；
- `/bank-workbench`：银行工作台；
- `/compute/`：算力研究首页；
- `/api/` 与 `/compute/api/`：分别对应电力与算力只读接口。

该设计不依赖未备案域名，也不会重置既有 MySQL 数据卷。

## 当前边界

企业详情页通过 Java 只读接口查询 MySQL，支持91家企业搜索、月度用电、财务记录及小时负荷分页。首页五家卡片仍是固定展示入口；详情值来自数据库。

所有项目结论均显示为研究情景，不能替代企业工程、电价及授信尽调。数据库密码只允许通过环境变量或已被 Git 忽略的 `.env` 注入，不能写入源码。
