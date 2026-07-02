# AI CAD — 开发移交记录

> 最后更新：2026-06-12  
> 当前阶段：桌面客户端预览功能完善，待 Windows 实机测试

---

## 项目概述

AI 驱动的工业厂房 CAD 设计系统。设计师通过自然语言描述需求，AI 生成平面图并推送到 AutoCAD。

## 当前进度

### ✅ 已完成

- **服务端** (FastAPI)：用户认证、项目管理、AI 对话、版本树、DXF 导出、SVG 预览、DWG 上传/下载/存档、DeepSeek 集成、WebSocket 流式对话
- **桌面客户端** (PySide6)：登录、项目列表、AI 对话面板、WebSocket 流式聊天、版本管理、AutoCAD COM 引擎
- **客户端预览渲染**：QGraphicsScene 自适应渲染（线宽/字号随场景缩放、建筑名居中、尺寸标注、房间名+面积、区域名居中）
- **客户端预览交互**：拖拽平移、滚轮缩放、重置按钮、双击复位
- **网页管理后台**：用户管理、边界配置、大模型配置、服务器配置、项目记录
- **项目文档**：README.md、STATUS.md、TODO.md、HANDOFF.md

### 🔧 本次修改（2026-06-12）

| 文件 | 改动 |
|------|------|
| `client/app/main_window.py` | 重写 `_building_to_scene`：自适应线宽/字号、补全尺寸标注/房间名/面积；`_render_preview_pixmap` 升级 2x 分辨率+两遍渲染；`_do_update_preview` 同步两遍渲染；补回隐藏的 `version_tree` |
| `client/app/widgets/chat_bubble.py` | PreviewView 增加 `reset_view`/`set_initial_rect`；拖拽改用 scrollbar；ChatBubble 预览区改为 QFrame 容器+重置按钮 |

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

## 架构讨论结论

1. **旧版 bridge vs 新版 client cad_engine 对比**：两者都是 pywin32+COM 推送 AutoCAD，本质相同方案。但新版 cad_engine 相比旧版 bridge 缺少门/窗/柱/面积标注/标注线/图层线宽，待补齐
2. **COM vs .NET API**：AutoCAD .NET API 更强但需加载进 CAD 进程内部，破解版兼容性有风险。当前 COM 方案适合外部遥控场景，够用且安全
3. **技术栈评估**：C# WPF + COM 是未来可能的替代方案，开发体验更好但需团队熟悉 C#，当前 Python 方案先跑通再迭代

## 关键设计决策

1. **DWG 文件永久保留** — 删除项目/会话/版本只清数据库，DWGs 文件不动
2. **区域划分 prompt** — 已更新为统一的 `zones` 数组格式
3. **预览渲染** — 同时支持 `zones`（数组）和 `divisions`（对象）两种格式
4. **httpx 代理问题** — 所有 httpx 调用已加 `trust_env=False`
5. **自适应预览** — `_building_to_scene` 使用 `ref_size` 参数，线宽/字号根据场景范围动态计算（`u = ref_size / 60`）
6. **预览交互** — PreviewView 记录 `_initial_scene_rect`，重置时精准回到初始视图

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

1. 打开本项目，服务端启动：`cd server && uvicorn app.main:app --host 0.0.0.0 --port 3000`
2. 客户端启动：`cd client && .venv/bin/python -m app.main`
3. 优先项：
   - cad_engine 补齐旧版功能（门/窗/柱/面积标注/标注线/图层线宽）
   - Windows 实机测试完整流程
   - 推 CAD 前安全确认弹窗
