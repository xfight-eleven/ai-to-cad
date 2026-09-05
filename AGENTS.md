# AGENTS.md — AI CAD 工业厂房设计助手

> 本文面向 AI 编码代理，假设读者对本项目零了解。
> 项目文档与代码注释均使用中文，修改时请保持中文注释风格。

## 一、项目概述

AI 驱动的工业厂房 AutoCAD 出图系统。设计师用自然语言描述需求，AI（DeepSeek）生成平面图结构化 JSON，客户端渲染预览并可一键推送到 AutoCAD 绘制 DWG。

整体架构（C/S 模式，从早期 B/S 迁移而来，见 `CS架构方案.md`）：

```
桌面客户端 (PySide6)  ←HTTP/WebSocket→  AI 服务器 (FastAPI)  →  DeepSeek API
        │ COM (pywin32)
     AutoCAD
```

## 二、目录结构与模块划分

| 模块 | 技术栈 | 职责 |
|------|--------|------|
| `server/` | Python + FastAPI + SQLAlchemy + SQLite | 后端：用户认证、项目/会话/版本管理、AI 对话、SVG 预览、DXF 导出、DWG 存档 |
| `client/` | Python + PySide6 + httpx + websockets + pywin32 | 桌面客户端：登录、AI 对话、QGraphicsScene 预览、AutoCAD COM 控制 |
| `bridge/` | Python + Flask + pywin32 | 旧版桥梁服务，**已废弃**（仅作 `cad_engine` 功能参照，不要在其上开发新功能） |
| `index.html` / `admin.html` | 单文件网页（原生 JS） | 管理后台页面，由服务端在 `/` 路由直接返回，挂载 `/css`、`/js` 静态目录 |
| `css/` `js/` | 静态资源 | 管理后台使用的字体与 svg-pan-zoom 库 |

### server/ 内部结构

- `app/main.py` — FastAPI 入口，注册全部路由；lifespan 中 `Base.metadata.create_all` 建表并创建初始管理员
- `app/config.py` — 全部配置从环境变量/`.env` 读取，零硬编码
- `app/database.py` — SQLAlchemy 引擎；SQLite 开启 WAL + 外键约束；`get_db` 依赖注入
- `app/api/` — 14 个路由模块（auth、projects、sessions、design、dwg、preview、dxf_download、boundaries、reference_projects、admin_*）
- `app/models/` — 9 张表：User、Boundary、LlmConfig、LlmConfigLog、Project、ProjectBoundary、Session、Version、ServerConfig、Message（见 `models/__init__.py`）
- `app/services/` — `deepseek_service.py`（AI 集成）、`preview_service.py`（JSON→SVG）、`dxf_service.py`（DXF 导出）、`auth_service.py`（JWT/密码）
- `data/` — `cad_bridge.db` 数据库 + `dwg/` DWG 永久存档（均被 .gitignore 排除）

### client/ 内部结构

- `app/main.py` — 入口，登录流程（本地 token 自动登录 → 登录对话框 → 主窗口）
- `app/main_window.py` — 主窗口（约 1400 行，核心 UI 都在此）
- `app/api_client.py` — 后端 HTTP 客户端
- `app/cad_engine.py` — AutoCAD COM 引擎（仅 Windows 可用；macOS 可导入不可连接）
- `app/config_manager.py` — 本地配置持久化（`%APPDATA%/hsxb-ai-cad/config.json` 或 `~/Library/Application Support/hsxb-ai-cad/`）
- `app/widgets/chat_bubble.py` — 聊天气泡 + PreviewView 预览控件

## 三、构建与运行命令

本项目没有 `pyproject.toml` / `package.json`，各模块独立使用 `pip + requirements.txt`，各自维护 `.venv/`（已存在）。

**服务端**：

```bash
cd server
cp .env.example .env          # 首次；可改 SECRET_KEY、管理员密码等
pip install -r requirements.txt python-multipart
uvicorn app.main:app --host 0.0.0.0 --port 3000 --log-level info
# 或开发模式：python run.py（读取 .env 中 HOST/PORT，默认 8080，注意与客户端默认 3000 不一致）
```

启动后：管理后台 `http://localhost:3000`，API 文档 `http://localhost:3000/docs`，默认管理员 `admin` / `admin123`。首次启动自动建库建管理员。

**客户端**：

```bash
cd client
pip install -r requirements.txt
python -m app.main            # 必须从 client/ 目录以模块方式运行
```

打包 exe（需 Windows）：`pyinstaller app.spec` → `dist/AICAD.exe`。

**注意**：客户端功能完整的链路（推 CAD、DWG 上传）要求 **Windows + AutoCAD + pywin32**；macOS 上可运行登录、对话、预览，但无法控制 AutoCAD。

## 四、测试

**项目目前没有任何测试代码**（服务端单元测试在 TODO 中为 P3 待办）。验证方式为手动跑通完整链路：启动服务端 → 启动客户端 → 登录 → AI 对话 → 预览 → 推 CAD。修改后至少应确认服务端能启动（`uvicorn app.main:app`）且 `/api/health` 返回 `{"status":"ok"}`。

数据库迁移：虽然安装了 alembic 且有 `alembic/` 目录，但 `versions/` 为空，**实际不使用迁移**——schema 变更靠 `Base.metadata.create_all`（只增不改），改动模型时注意 SQLite 存量数据的兼容性。

## 五、代码风格与约定

- **语言**：所有文档、docstring、注释使用中文；模块级 docstring 说明职责；用 `# ── 区块名 ──` 风格的分节注释；print 日志可带 emoji（✅⚠️ℹ️）
- **Python**：Python 3，无强制格式化工具/linter 配置；FastAPI 路由用中文 tags；类型注解按需使用（非全覆盖）
- **配置零硬编码**：所有可配置项从环境变量读取（`server/app/config.py` 是范例）；大模型配置（API Key、模型名等）存数据库 `LlmConfig` 表，由管理后台维护，代码中不得硬编码
- **设计边界零硬编码**：DeepSeek 的 system prompt 动态拼接数据库中的边界规则，代码不内置任何行业规则（见 `deepseek_service.py` 头部注释）
- **httpx 调用一律加 `trust_env=False`**，避免系统代理干扰内网请求
- **单位约定**：设计 JSON 中单位为**米**，CAD 中单位为**毫米**，`SCALE = 1000.0`（见 `client/app/cad_engine.py`）
- **设计 JSON 两种区域格式**：`zones`（数组，新格式）和 `divisions`（对象，旧格式），渲染/预览代码必须同时兼容两者
- **DWG 文件永久保留**：删除项目/会话/版本只清数据库记录，`server/data/dwg/` 中的文件不动
- 敏感文件不入库：`.env`、`*.db`、`*.dwg`、`bridge/.token_cache` 均在 `.gitignore` 中

## 六、安全注意事项

- 认证为 JWT Bearer Token（python-jose），密码用 bcrypt（passlib）；角色分 `admin` / `designer`
- `SECRET_KEY`、管理员初始密码、DeepSeek API Key（加密存储于 `LlmConfig` 表，cryptography 加解密）均属敏感信息，不得提交或泄露
- CORS 当前为 `allow_origins=["*"]`（内网部署场景），公网部署前需收紧
- 默认口令 `admin/admin123` 仅供本地开发，部署时必须通过 `.env` 修改
- DWG 下载接口支持 query 参数携带 token（供浏览器直接下载），改动鉴权逻辑时注意保持兼容

## 七、文档地图

- `README.md` — 快速开始与项目结构
- `STATUS.md` — 已完成模块清单
- `TODO.md` — 待开发工作（P0–P3 优先级）
- `HANDOFF.md` — 开发移交记录、关键设计决策、API 速查
- `AI-CAD-桥梁服务方案.md` — 详细设计文档
- `CS架构方案.md` — B/S → C/S 迁移的背景与架构论证

修改代码时如涉及 STATUS/TODO/HANDOFF 中记录的事项，请同步更新对应文档。
