# AI CAD — 开发移交记录

> 最后更新：2026-06-09  
> 当前阶段：桌面客户端最小可用版本代码完成，待 Windows 测试

---

## 项目概述

AI 驱动的工业厂房 CAD 设计系统。设计师通过自然语言描述需求，AI 生成平面图并推送到 AutoCAD。

## 当前进度

### ✅ 已完成

- **服务端** (FastAPI)：用户认证、项目管理、AI 对话、版本树、DXF 导出、SVG 预览、DWG 上传/下载/存档、DeepSeek 集成
- **桌面客户端** (PySide6)：完整代码已写好，约 1238 行，包含登录、项目列表、AI 对话面板、版本管理、AutoCAD COM 引擎
- **网页原型** (已删除)：可正常运行，供参考
- **项目文档**：README.md、STATUS.md、AI-CAD-桥梁服务方案.md

### ❌ 待完成

1. **Windows 验证** — 客户端需要在 Windows 上跑通完整流程
2. **PySide6 安装测试** — Mac 上未安装，需在 Windows 上 pip install
3. **推 CAD 功能实测** — 需要 Windows + AutoCAD + pywin32 环境
4. **打包 exe** — 最终交付前在 Windows 上运行 `pyinstaller app.spec`

## 如何在 Windows 上继续

### 第一步：解压项目

把 `hsxb-ai-cad.zip` 拷贝到 Windows，解压到任意目录（如 `D:\projects\`）。

### 第二步：启动服务端

```powershell
cd D:\projects\hsxb-ai-cad\server
pip install -r requirements.txt python-multipart
copy .env.example .env
:: 编辑 .env，可选修改 SECRET_KEY 和密码
uvicorn app.main:app --host 0.0.0.0 --port 3000 --log-level info
```

服务端启动后访问：
- 前端：`http://localhost:3000`
- API 文档：`http://localhost:3000/docs`
- 默认账号：`admin` / `admin123`

### 第三步：启动客户端

```powershell
cd D:\projects\hsxb-ai-cad\client
pip install -r requirements.txt
python -m app.main
```

首次运行弹出登录框，填入服务器地址和账号即可。后续自动登录。

### 第四步：验证推 CAD

1. 打开 AutoCAD
2. 客户端中选择一个版本 → 点击"推 CAD"
3. CAD 中应自动绘制并保存 DWG
4. DWG 自动上传到服务器 `server/data/dwg/` 目录

### 第五步：打包交付

```powershell
cd D:\projects\hsxb-ai-cad\client
pip install pyinstaller
pyinstaller app.spec
# 输出：dist/AICAD.exe
```

## 服务端 API 速查

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 登录 |
| `/api/health` | GET | 健康检查 |
| `/api/projects` | GET/POST | 项目列表/新建 |
| `/api/projects/{id}/sessions` | GET/POST | 会话列表/新建 |
| `/api/sessions/{id}` | GET | 会话详情（含对话+版本） |
| `/api/design/refine` | POST | AI 生成新版本 |
| `/api/versions/{id}` | GET | 版本详情（含 design_json） |
| `/api/versions/{id}/dwg` | PUT/GET | 上传/下载 DWG |
| `/api/projects/{id}/dwgs` | GET | 扫描项目所有 DWG |
| `/api/admin/llm-config` | GET/PUT | 大模型配置（API Key 等） |
| `/api/admin/boundaries` | GET/POST | 设计边界管理 |

## 关键设计决策

1. **DWG 文件永久保留** — 删除项目/会话/版本只清数据库，DWGs 文件不动。可通过 API 扫描找回
2. **区域划分 prompt** — 已更新为统一的 `zones` 数组格式，避免 AI 每次返回不同结构
3. **预览渲染** — 同时支持 `zones`（数组）和 `divisions`（对象）两种格式
4. **httpx 代理问题** — 所有 httpx 调用已加 `trust_env=False`，避免 SOCKS 代理报错

## 项目结构速览

```
hsxb-ai-cad/
├── server/              # AI 后端（FastAPI + SQLite）
├── client/              # 桌面客户端（PySide6）
│   └── app/
│       ├── main.py          # 入口
│       ├── main_window.py   # 主窗口 UI
│       ├── api_client.py    # 后端 HTTP 调用
│       ├── cad_engine.py    # AutoCAD COM 引擎
│       └── config_manager.py # 本地配置
├── bridge/              # 旧版桥梁（废弃待定）
├── 已删除           # 网页原型（可归档）
├── README.md            # 项目说明
├── STATUS.md            # 开发状态
└── AI-CAD-桥梁服务方案.md # 详细设计文档
```

## 下次继续时

打开这个文件，从"如何在 Windows 上继续"的第二步开始执行。
