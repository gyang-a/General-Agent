# Generate Agent

一个前后端分离的通用智能体聊天项目。前端负责交互与展示，后端负责认证、会话、消息持久化、LangChain Agent 执行、工具调用和 LangGraph checkpointer。

## 技术栈

### Frontend

- React 19
- Vite 8
- Tailwind CSS
- Radix UI
- Zustand
- react-markdown
- react-virtuoso
- lucide-react
- sonner

### Backend

- Python 3.13 recommended
- FastAPI
- uv
- LangChain `init_chat_model`
- LangChain `create_agent`
- LangGraph checkpointer
- MongoDB / Motor
- Tavily web search tool, optional

## 项目结构

```text
.
├─ frontend/                 React 前端
│  ├─ src/components          页面与业务组件
│  ├─ src/hooks               SSE 聊天、滚动、快捷键等 hooks
│  ├─ src/services            前端 API 调用层
│  ├─ src/stores              前端运行时状态
│  └─ vite.config.js          Vite 与后端代理配置
├─ backend/                  FastAPI 后端
│  ├─ app/api/routes          HTTP 路由
│  ├─ app/services            业务用例层
│  ├─ app/agents              LangChain Agent 运行时、模型适配、工具
│  ├─ app/checkpoints         LangGraph checkpointer 工厂
│  ├─ app/repositories        数据访问抽象
│  ├─ app/db                  MongoDB 初始化
│  └─ pyproject.toml          Python 依赖与 uv 配置
└─ uploads/                  上传文件目录
```

## 核心设计

- 前端只负责 UI 状态和当前会话的即时渲染。
- 聊天消息由 `/api/chat/stream` 写入后端。
- 历史记录由 `/api/history` 从后端读取。
- 前端不通过 `PUT /api/history` 推送历史快照。
- 会话重命名、置顶、删除使用明确的后端 mutation 接口。
- LangGraph checkpointer 接入 MongoDB，用于 Agent 状态和上下文延续。
- MongoDB 当前作为实现细节封装在 repository/checkpoint 层，后续可替换 PostgreSQL。
- 没有内置默认模型，用户必须自行配置 OpenAI-compatible 模型 endpoint、model name 和 API key。

## 环境要求

- Node.js 20+
- Python 3.13 recommended
- uv
- MongoDB

## 后端启动

```powershell
cd backend
uv sync
uv run fastapi dev app/main.py --host 127.0.0.1 --port 8000
```

后端默认读取：

- 根目录 `.env.server`
- `backend/.env`

可参考 `.env.server.example` 或 `backend/.env.example` 配置：

```env
SERVER_PORT=8000
CORS_ORIGIN=http://localhost:5173,http://localhost:5174,http://localhost:5175

AUTH_USERNAME=admin
AUTH_PASSWORD=123456
AUTH_SECRET=change_me

MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=chat_app

UPSTREAM_TIMEOUT_MS=120000
UPSTREAM_TEMPERATURE=1
UPSTREAM_TOP_P=1
UPSTREAM_SYSTEM_PROMPT=你是一个专业、简洁、准确的中文 AI 助手。

TAVILY_API_KEY=
```

## 前端启动

```powershell
cd frontend
npm install
npm run dev
```

前端开发服务器默认绑定：

```text
http://127.0.0.1:5173
```

Vite 默认代理到：

```text
http://localhost:8000
```

如需修改后端地址，可以在前端环境变量中设置：

```env
VITE_BACKEND_TARGET=http://127.0.0.1:8000
```

## 模型配置

系统不提供任何内置默认模型。

登录后在前端模型管理中添加模型：

- 模型名称：例如 `qwen-plus`、`gpt-4.1-mini`、`deepseek-chat`
- API Key：对应供应商密钥
- Endpoint：OpenAI-compatible base URL，例如 `https://api.example.com/v1`

聊天前必须在顶部模型下拉框中选择一个已配置模型。没有选择模型时，前端会禁止发送。

后端当前按 OpenAI-compatible 协议接入模型。后续接其他 LangChain provider 时，优先扩展 provider 配置，而不是改聊天链路。

## 联网搜索

前端的联网搜索按钮只控制本轮是否挂载 `web_search` tool。

实际是否调用搜索工具由 LangChain Agent 决定，不在业务代码中手写工具调用流程。

如需启用联网搜索，配置：

```env
TAVILY_API_KEY=your_tavily_key
```

## 主要 API

### Auth

- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `GET /api/auth/profile`

### Chat

- `POST /api/chat/stream`

SSE 返回增量内容、引用来源、RAG 信息和结束标记。

### Models

- `GET /api/models`
- `GET /api/models/custom`
- `POST /api/models/custom`
- `DELETE /api/models/custom/{model_name}`

### History

- `GET /api/history`
- `PATCH /api/history/conversations/{conversation_id}`
- `DELETE /api/history/conversations/{conversation_id}`
- `DELETE /api/history/conversations/{conversation_id}/messages`
- `DELETE /api/history`

### Upload / KB

- `POST /api/upload`
- `/api/kb/*`

知识库与 RAG 相关接口当前保留基础兼容结构，后续可以继续演进为 Agentic RAG。

## 验证命令

后端：

```powershell
cd backend
uv run python -m compileall app
```

前端：

```powershell
cd frontend
npm run build
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## 后续方向

- 完善 RAG：从当前基础检索接口演进到 Agentic RAG。
- 增加更多 LangChain provider 配置。
- 将 MongoDB repository/checkpointer 替换或扩展为 PostgreSQL。
- 增加多智能体编排能力，将搜索、RAG、文件分析等能力拆成可组合的小智能体。
