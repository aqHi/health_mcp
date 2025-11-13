# Health MCP

健康数据 MCP Server 的参考实现，使用 FastAPI + SQLAlchemy 构建，同时兼容 MCP JSON-RPC 工具调用与 REST API 调试接口。

## 功能特性

- `health_store_metric` / `health_batch_store_metrics`：写入单条或多条健康指标记录，包含去重逻辑。
- `health_query_metrics`：按用户、指标、时间范围查询历史记录。
- `health_trend_summary`：按日/周/月聚合计算趋势与线性回归斜率。
- `health_delete_record`：删除（软删除）指定记录。
- `health_list_metric_types`：返回内置指标字典。
- 提供 `/api` 下的 RESTful 接口，方便本地调试。
- 自带 `/admin` Web 后台，可视化查看、筛选与删除健康指标数据。

## 快速开始

### 使用 docker-compose

```bash
docker-compose up --build
```

容器会在启动阶段自动等待 MySQL 就绪并执行数据表初始化；服务启动后，REST API 与 MCP Endpoint 均监听在 `http://localhost:8000`。

启动完成后可访问 `http://localhost:8000/admin` 打开管理后台。若未通过环境变量提供管理员账号，将自动生成随机凭据写入数据库并在日志中打印，首次登录后请及时修改密码。

如需在网络较慢或数据库初始化时间较长的环境中调整等待策略，可通过设置环境变量 `DB_INIT_MAX_ATTEMPTS`（默认 30 次）与 `DB_INIT_DELAY_SECONDS`（默认每次间隔 2 秒）来控制入口脚本的重试次数与间隔。

#### Nginx 反向代理示例（health.univasst.cn）

若需要通过自定义域名对外暴露 HTTP 与 MCP（`/mcp/tools`）接口，可参考 `deploy/nginx.health.conf` 的配置，将流量统一转发至本服务：

```nginx
upstream health_mcp_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name health.univasst.cn;

    client_max_body_size 16m;

    location / {
        proxy_pass http://health_mcp_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

将该配置放入 Nginx 的 `conf.d` 目录并重新加载服务，即可通过 `http://health.univasst.cn` 访问 REST API、MCP Endpoint 与管理后台。若部署在其他主机或端口上，只需将 `upstream` 中的地址替换为对应的内网地址与端口。

#### Docker Hub 镜像加速配置

如需配置 Docker Hub 国内镜像源，可在宿主机的 `/etc/docker/daemon.json` 中加入如下内容，并重启 Docker 服务：

```json
{
 "registry-mirrors": [
    "https://docker.m.daocloud.io"
  ]
}
```

该镜像由 DaoCloud 提供，可替代腾讯云镜像以提升拉取速度。

#### Python 包索引加速

镜像构建阶段会默认使用清华大学的 PyPI 镜像源（`https://pypi.tuna.tsinghua.edu.cn/simple`），确保诸如 `uvicorn` 等依赖可在国内环境顺利安装。如需在宿主机或虚拟环境中手动安装依赖，也可执行：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认会根据环境变量连接 MySQL，如需在本地快速试验，可将 `DATABASE_URL` 设置为 `sqlite:///./health.db`。

## MCP JSON-RPC

MCP Endpoint: `POST /mcp/tools`

- `tools.list`：返回可用工具列表
- `tools.call`：按照 `name` + `arguments` 调用具体工具

### SSE 调试通道

- SSE Endpoint：`GET /mcp/stream`
- 首次连接会收到 `ready` 事件，之后每 15 秒发送一次 `heartbeat` 维持长连接。
- 当触发 `tools.list`、`tools.call` 或校验失败时，会推送 `mcp.tools.*` / `mcp.error` 事件，方便在 [MCP Inspector](https://modelcontextprotocol.io/inspector) 中实时查看请求与结果。

请求示例：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools.call",
  "params": {
    "name": "health_store_metric",
    "arguments": {
      "user_id": "user-123",
      "type": "body/weight",
      "value": 72.3,
      "source": "chat_input"
    }
  }
}
```

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `MYSQL_HOST` | MySQL 主机 | `localhost` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户名 | `root` |
| `MYSQL_PASSWORD` | MySQL 密码 | `password` |
| `MYSQL_DB` | 数据库名 | `health_mcp` |
| `MYSQL_DRIVER` | SQLAlchemy 驱动 | `mysql+pymysql` |
| `DATABASE_URL` | 完整数据库连接串（优先级最高） | 空 |
| `REDIS_HOST` | Redis 主机 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `APP_PORT` | 服务监听端口 | `8000` |
| `API_KEY` | 可选的接口访问密钥 | 空 |
| `ADMIN_USERNAME` | （可选）后台管理员用户名 | 空 |
| `ADMIN_PASSWORD` | （可选）后台管理员密码 | 空 |
| `DEFAULT_ADMIN_USERNAME` | 未显式配置时默认创建的管理员用户名 | `admin` |
| `SESSION_SECRET_KEY` | 会话加密密钥，未提供时自动随机生成 | 空 |
| `DB_INIT_MAX_ATTEMPTS` | 入口脚本等待数据库的最大重试次数 | `30` |
| `DB_INIT_DELAY_SECONDS` | 每次重试之间的等待秒数 | `2` |

## 目录结构

```
app/
  ├── api.py              # REST API 路由
  ├── admin_router.py     # 管理后台路由
  ├── admin_service.py    # 管理员账号与仪表盘逻辑
  ├── catalog.py          # 指标字典
  ├── config.py           # 配置
  ├── db.py               # 数据库连接
  ├── db_init.py          # 数据库初始化辅助工具
  ├── main.py             # FastAPI 入口
  ├── mcp.py              # MCP JSON-RPC 路由
  ├── models.py           # SQLAlchemy 实体
  ├── repositories.py     # 数据访问层
  ├── security.py         # 密码哈希与校验工具
  ├── schemas.py          # Pydantic Schema
  └── services.py         # 业务逻辑

app/templates/            # 管理后台 HTML 模板

docker-entrypoint.sh      # 容器入口脚本，负责等待数据库并初始化表结构
```

## 许可协议

MIT
