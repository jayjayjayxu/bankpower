# 电力能源金融机会分析平台

本目录承载网站相关代码，前端与后端分离，便于本地演示及后续迁移到云服务器。

```text
project/
├── frontend/       Vue 3 + JavaScript 展示页
├── backend/        Spring Boot 只读数据库接口
├── compute/        算力研究前后端及算电协同说明
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
