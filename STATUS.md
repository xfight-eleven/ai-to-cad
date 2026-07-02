# AI CAD 桥梁服务方案 — 开发状态

> 最后更新：2026-06-09

---

## ✅ 已完成

### Phase 1：AI 服务器（Python FastAPI + SQLite）

| 模块 | 文件 | 状态 |
|------|------|------|
| 项目初始化 | server/app/{main,config,database}.py | ✅ |
| 数据模型 | server/app/models/*.py (9个表) | ✅ |
| 用户认证 | JWT 登录/鉴权/权限依赖注入 | ✅ |
| 管理员 API | 用户管理/边界 CRUD/大模型配置/服务器配置 | ✅ |
| 项目管理 | 项目 CRUD/边界多对多/参考项目 | ✅ |
| 会话&版本 | 会话创建/版本树/回滚分支/版本对比 | ✅ |
| DeepSeek 集成 | server/app/services/deepseek_service.py | ✅ |
| DXF 导出 | server/app/services/dxf_service.py + API | ✅ |
| SVG 预览 | server/app/services/preview_service.py + API | ✅ |
| DWG 存档 | 上传/下载/历史扫描 + 文件永久保留 | ✅ |
| WebSocket 流式 | ws://host/api/design/ws/refine 实时对话 | ✅ |
| 服务器配置 | IP/端口/客户端默认地址持久化 | ✅ |

### 初始数据

| 数据 | 内容 |
|------|------|
| 管理员 | admin / admin123 |
| 设计师 | designer01 / newpass456（角色 designer） |
| 边界模板 | 肉制品厂房通用规范、成都地区食品厂房规范 |

### Phase 2：桥梁服务（Python Flask + pywin32）

| 模块 | 文件 | 状态 |
|------|------|------|
| 项目结构 | bridge/app/{config,server,api_client,cad_engine}.py | ✅ |
| PyInstaller 打包 | bridge/bridge.spec | ✅ |

### Phase 3：桌面客户端（Python + PySide6）

| 模块 | 文件 | 状态 |
|------|------|------|
| 项目结构 | client/ 全部 | ✅ |
| API 客户端 | client/app/api_client.py | ✅ |
| 主窗口 UI | client/app/main_window.py | ✅ |
| CAD 引擎 | client/app/cad_engine.py | ✅ |
| 配置管理 | client/app/config_manager.py | ✅ |
| 打包配置 | client/app.spec | ✅ |
| 预览渲染升级 | _building_to_scene 自适应线宽/字号 + 尺寸/面积标注 | ✅ |
| 预览交互 | PreviewView 拖拽/缩放/重置按钮 | ✅ |

---

## 🔜 待办

| 优先级 | 事项 | 状态 |
|--------|------|------|
| P0 | Windows 实机测试（推 CAD 完整链路） | 🟡 Mac 已跑通 |
| P0 | cad_engine 补齐旧版功能（门/窗/柱/面积/标注线/线宽） | 🔴 |
| P1 | 推 CAD 前安全确认弹窗 | 🔴 |
| P1 | 对话 Markdown 渲染 | 🔴 |
| P1 | 客户端异常处理增强（断网/Token 过期/bug 修复） | 🔴 |
| P2 | 版本叠图对比 | 🔴 |
| P2 | 边界规则高级编辑器 | 🔴 |
| P2 | 客户端打包 exe (Windows) | 🔴 |
| P2 | 客户端自动更新 | 🔴 |
| P3 | 服务端单元测试 | 🔴 |
| P3 | 日志系统 | 🔴 |
| P3 | DXF 导出与预览保持一致 | 🔴 |
