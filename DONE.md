# AI CAD — 已完成工作清单

> 最后更新：2026-06-09

---

## 一、服务端（Python FastAPI + SQLite）

### 数据模型（8 张表）

| 模型 | 文件 | 字段 |
|------|------|------|
| User | `server/app/models/user.py` | id, username, password_hash, display_name, role, created_by |
| Boundary | `server/app/models/boundary.py` | id, name, description, rules_json, is_active |
| LlmConfig | `server/app/models/llm_config.py` | id, provider, api_key_encrypted, api_base, model_name, temperature, max_tokens |
| Project | `server/app/models/project.py` | id, title, owner_id, reference_project_id, allow_reference |
| ProjectBoundary | `server/app/models/project.py` | project_id, boundary_id (多对多关联表) |
| Session | `server/app/models/session.py` | id, project_id, title |
| Version | `server/app/models/version.py` | id, session_id, number, parent_version_id, design_json, dwg_file_path, token_usage |
| Message | `server/app/models/message.py` | id, session_id, role, content, version_id |

### API 路由（12 个模块）

| 模块 | 文件 | 接口数 | 功能 |
|------|------|--------|------|
| 认证 | `server/app/api/auth.py` | 2 | 登录 `/api/auth/login`、获取当前用户 `/api/auth/me` |
| 项目管理 | `server/app/api/projects.py` | 5 | CRUD + 参考开关 |
| 参考项目 | `server/app/api/reference_projects.py` | 1 | 列出可参考项目 |
| 会话管理 | `server/app/api/sessions.py` | 4 | 会话 CRUD + 版本管理 + 版本对比 + 回滚 |
| AI 设计 | `server/app/api/design.py` | 2 | 生成 `/api/design/generate`、精炼 `/api/design/refine` |
| SVG 预览 | `server/app/api/preview.py` | 1 | JSON → SVG 渲染 |
| DXF 导出 | `server/app/api/dxf_download.py` | 1 | JSON → DXF 下载 |
| DWG 管理 | `server/app/api/dwg.py` | 3 | 上传、下载、项目历史扫描 |
| 边界管理 | `server/app/api/admin_boundaries.py` | 3 | 管理员边界 CRUD |
| 用户管理 | `server/app/api/admin_users.py` | 3 | 管理员用户 CRUD |
| 大模型配置 | `server/app/api/admin_llm_config.py` | 3 | 配置热切换 + 连接测试 |
| 公开边界 | `server/app/api/boundaries.py` | 1 | 公开边界列表 |

### 业务服务

| 服务 | 文件 | 功能 |
|------|------|------|
| 认证 | `server/app/services/auth_service.py` | 密码哈希、JWT 签发/验证 |
| DeepSeek | `server/app/services/deepseek_service.py` | API 调用、System Prompt 构建、JSON 解析、区域划分 schema |
| SVG 预览 | `server/app/services/preview_service.py` | JSON → SVG（支持矩形/圆/椭圆/三角形/zones/divisions/rooms） |
| DXF 导出 | `server/app/services/dxf_service.py` | JSON → DXF（ezdxf 库） |

### 已修复的问题

| 问题 | 修复内容 |
|------|---------|
| httpx SOCKS 代理报错 | 所有 httpx 调用加 `trust_env=False` |
| 区域划分无法渲染 | preview_service 支持 `zones`（数组）和 `divisions`（对象）两种格式 |
| AI 每次返回不同分区格式 | System prompt 加入统一的 zones JSON schema |
| 分区预览不可见 | 金色虚线框渲染 + 标签文字 + position 关键字定位 |

### 架构特性

- JWT 认证 + 权限依赖注入（普通用户/管理员）
- 设计边界零硬编码：规则从数据库动态读取注入 Prompt
- 大模型热切换：修改配置后新请求立即生效，无需重启
- API Key 加密存储（Fernet + SECRET_KEY 派生密钥）
- DWG 文件永久保留：删除数据库记录不删文件
- 按 `项目ID/会话ID/v{版本号}-{版本ID}.dwg` 组织目录
- python-multipart 支持文件上传

---

## 二、桌面客户端（Python + PySide6）

### 文件结构

| 文件 | 行数 | 功能 |
|------|------|------|
| `client/app/main.py` | 127 | 入口：自动登录 / 登录窗口 / 启动主窗口 |
| `client/app/main_window.py` | 636 | 主窗口：项目列表 + AI 对话 + 版本树 + 推 CAD |
| `client/app/api_client.py` | 157 | HTTP 客户端：封装全部 15 个后端接口 |
| `client/app/cad_engine.py` | 200 | AutoCAD COM 引擎：连接/绘图/图层/DWG 保存 |
| `client/app/config_manager.py` | 69 | 配置管理：服务器地址、Token 持久化 |

### UI 功能

| 功能 | 状态 |
|------|------|
| 服务器设置对话框（IP + 测试连接） | ✅ |
| 登录界面 + 自动登录（Token 持久化） | ✅ |
| 项目列表 + 新建（边界多选 + 参考项目） | ✅ |
| 会话列表 + 新建会话 + 切换 | ✅ |
| AI 对话（输入框 + 后台线程 + 错误提示） | ✅ |
| 版本树 + 推 CAD 按钮 | ✅ |
| 暗色主题（与网页版一致） | ✅ |
| QGraphicsView 本地预览 | ❌ 待开发 |

### CAD 引擎特性

- 图层管理：WALL / ROOM / ROOM_NAME / TEXT / DIM / WINDOW / DOOR / HATCH / ZONE / ZONE_TEXT
- 支持 zones（数组）和 divisions（对象）两种分区格式
- 自动尺寸标注和缩放
- pywin32 缺失时优雅降级（提示仅支持 Windows）

### 打包配置

- `client/app.spec`：PyInstaller 单文件无终端窗口
- 隐藏导入：win32com.client、pythoncom、pywintypes

---

## 三、网页原型

| 文件 | 功能 |
|------|------|
| `front.html` | 单文件 SPA（1695 行）：登录、项目列表、AI 对话、SVG 预览、版本管理、DXF 下载 |
| `js/svg-pan-zoom.min.js` | SVG 缩放平移库 |
| `css/fonts.css` | Web 字体（DM Sans + JetBrains Mono） |

---

## 四、桥梁服务（旧版）

| 文件 | 行数 | 功能 |
|------|------|------|
| `bridge/app/server.py` | 240 | Flask 本地服务 |
| `bridge/app/cad_engine.py` | 411 | AutoCAD 绘制引擎（含墙体/房间/门窗/标注） |
| `bridge/app/api_client.py` | 127 | 认证 + 拉取版本 JSON |
| `bridge/app/config.py` | 20 | 配置管理 |
| `bridge/bridge.spec` | - | PyInstaller 打包 |

> 注：客户端上线后此模块可废弃

---

## 五、项目文档

| 文件 | 内容 |
|------|------|
| `README.md` | 项目说明 + 快速开始 + API 速查 |
| `CS架构方案.md` | 完整 C/S 架构设计（架构图、数据流、版本规划） |
| `TODO.md` | 待开发工作清单（P0-P3 共 14 项） |
| `HANDOFF.md` | 开发移交记录（换电脑参考） |
| `STATUS.md` | 开发状态跟踪 |
| `AI-CAD-桥梁服务方案.md` | 原始详细设计（BS 架构） |
| `DONE.md` | 本文件 — 已完成工作清单 |


### 服务器配置

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/admin/server-config | GET | 获取所有配置项 |
| /api/admin/server-config | PUT | 批量更新配置项 |

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| server_ip | 0.0.0.0 | 服务端绑定 IP |
| server_port | 3000 | 服务端监听端口 |
| client_default_server | http://127.0.0.1:3000 | 客户端默认连接地址 |

### WebSocket 实时流

| 端点 | 说明 |
|------|------|
| ws://host:3000/api/design/ws/refine?token={jwt} | AI 生成过程中逐 token 推送到客户端 |

### 初始数据

- 设计师账号 designer01 / design123（角色 designer，可停用/启用/改密）
- 肉制品厂房通用规范（5 条规则：功能分区/人货分流/温控/排水/墙面）
- 成都地区食品厂房规范（3 条规则：抗震/防潮/通风）

---

## 六、代码规模

| 模块 | 文件数 | 总行数 |
|------|--------|--------|
| 服务端 | 22 | ~1,800 |
| 客户端 | 7 | ~1,238 |
| 桥梁 | 6 | ~825 |
| 网页 | 3 | ~1,750 |
| 文档 | 7 | ~1,550 |
| **合计** | **45** | **~7,163** |
