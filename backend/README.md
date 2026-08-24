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
