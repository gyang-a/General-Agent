# Python Backend

这是现有 Node/Express 后端的并行 Python 版本，目标是保持 `/api/*` 协议兼容，同时把核心聊天运行时迁到 FastAPI + LangChain + LangGraph。

## 启动

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端可以通过代理或环境变量把聊天 API 指到 `http://localhost:8000`。当前 Node 后端不会被修改。

## 当前覆盖

- `GET /api/health`
- `/api/auth/*`
- `/api/models*`
- `/api/history`
- `POST /api/chat/stream`
- `POST /api/upload`
- `/api/kb/*` 基础兼容路由

聊天链路使用 `init_chat_model`、`create_agent`、LangChain tools，并预留 MongoDB checkpointer。联网搜索是 agent tool：前端按钮只控制本轮是否挂载 `web_search`，是否调用由 agent 判断。

## 模块边界

```text
app/api/routes       HTTP 接口层，只做协议适配
app/services         业务用例层，不直接依赖 Mongo/PostgreSQL
app/agents           LangChain agent runtime、模型注册和工具包
app/agents/tools     LangChain tools，例如 web_search
app/repositories     业务数据访问抽象，当前实现是 MongoRepository
app/checkpoints      LangGraph checkpointer 工厂，后续可切 PostgreSQL
app/db               当前数据库连接初始化
```

后续如果从 MongoDB 换 PostgreSQL，优先新增 `PostgresRepository` 和 PostgreSQL checkpointer 实现，再在 factory 里切换；`api`、`services`、`agents/runtime.py` 不需要跟着改。
