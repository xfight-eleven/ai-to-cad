# AI CAD — 工业厂房设计助手

AI 驱动的 AutoCAD 出图系统。设计师通过自然语言描述需求，AI 自动生成工业厂房平面图并推送到 AutoCAD。

## 架构

```
桌面客户端 (PySide6)  ←→  AI 服务器 (FastAPI)  →  DeepSeek
        │ COM
   AutoCAD
```

| 模块 | 技术栈 | 职责 |
|------|--------|------|
| `server/` | Python FastAPI + SQLite | 项目/会话/版本管理、AI 对话、DWG 存档 |
| `client/` | Python PySide6 + pywin32 | 桌面 UI、边界配置、AutoCAD COM 控制 |
| `bridge/` | Python Flask + pywin32 | 旧版桥梁服务（客户端上线后废弃） |
| `已删除` | 单文件 SPA | 原型验证用网页版（客户端上线后归档） |

## 快速开始 — 服务端

```bash
cd server

# 配置
cp .env.example .env
# 编辑 .env：修改 SECRET_KEY、管理员密码等（默认 admin/admin123）

# 安装依赖
pip install -r requirements.txt python-multipart
# 或：uv sync

# 启动
uvicorn app.main:app --host 0.0.0.0 --port 3000 --log-level info
```

服务端启动后：
- 前端页面：`http://localhost:3000`
- API 文档：`http://localhost:3000/docs`
- 默认管理员：`admin` / `admin123`

**首次启动自动创建 SQLite 数据库和初始管理员账号。**

## 快速开始 — 桌面客户端

> 客户端需要 **Windows + AutoCAD + pywin32**。在 macOS 上可运行登录和对话功能，但无法控制 AutoCAD。

```bash
cd client

# 安装依赖
pip install -r requirements.txt

# 启动
python -m app.main
```

打包为单个 exe：

```bash
pip install pyinstaller
pyinstaller app.spec
# 输出文件：dist/AICAD.exe
```

## 从 macOS 迁移到 Windows

1. 将整个项目目录复制到 Windows 机器（U 盘 / 共享文件夹 / Git）
2. 复制 `server/data/cad_bridge.db` 到 Windows 对应路径（可选，保留历史数据）
3. 按上述步骤安装依赖并启动服务端和客户端

## 项目结构

```
hsxb-ai-cad/
├── server/                    # AI 后端服务
│   ├── app/
│   │   ├── main.py            # 入口，路由注册
│   │   ├── config.py          # 环境变量配置
│   │   ├── database.py        # SQLAlchemy 引擎
│   │   ├── api/               # API 路由
│   │   │   ├── auth.py        # 登录/鉴权
│   │   │   ├── projects.py    # 项目 CRUD
│   │   │   ├── sessions.py    # 会话/版本管理
│   │   │   ├── design.py      # AI 设计生成/精炼
│   │   │   ├── dwg.py         # DWG 上传/下载/扫描
│   │   │   ├── preview.py     # SVG 预览
│   │   │   └── admin_*.py     # 管理员功能
│   │   ├── models/            # 数据模型（8 张表）
│   │   ├── services/          # 业务逻辑
│   │   │   ├── deepseek_service.py  # DeepSeek API 集成
│   │   │   ├── preview_service.py   # JSON → SVG 渲染
│   │   │   └── dxf_service.py       # DXF 导出
│   │   └── schemas.py         # Pydantic 模型
│   └── data/
│       ├── cad_bridge.db      # SQLite 数据库
│       └── dwg/               # DWG 文件永久存档
│
├── client/                    # 桌面客户端
│   └── app/
│       ├── main.py            # 入口（登录流程）
│       ├── main_window.py     # 主窗口 UI
│       ├── api_client.py      # 后端 HTTP 客户端
│       ├── cad_engine.py      # AutoCAD COM 引擎
│       └── config_manager.py  # 本地配置持久化
│
├── bridge/                    # 旧版桥梁服务（Windows 专用）
├── 已删除                 # 原型网页（可归档）
└── AI-CAD-桥梁服务方案.md      # 详细设计文档
```

## API 接口速览

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 登录 |
| `/api/projects` | GET/POST | 项目列表/新建 |
| `/api/projects/{id}/sessions` | GET/POST | 会话列表/新建 |
| `/api/design/generate` | POST | AI 生成初版 |
| `/api/design/refine` | POST | AI 精炼新版本 |
| `/api/versions/{id}` | GET | 版本详情（含 JSON） |
| `/api/versions/{id}/dwg` | PUT/GET | 上传/下载 DWG |
| `/api/projects/{id}/dwgs` | GET | 扫描项目所有 DWG（含已删除版本） |
| `/api/admin/llm-config` | GET/PUT | 大模型配置 |
| `/api/admin/boundaries` | GET/POST | 设计边界管理 |
