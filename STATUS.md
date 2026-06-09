# AI CAD 桥梁服务方案 — 开发状态

> 最后更新：2026-06-09

---

## ✅ 已完成

### Phase 1：AI 服务器（Python FastAPI + SQLite）

| 模块 | 文件 | 状态 |
|------|------|------|
| 项目初始化 | `server/app/{main,config,database}.py` | ✅ |
| 数据模型 | `server/app/models/*.py` (8个表) | ✅ |
| 用户认证 | JWT 登录/鉴权/权限依赖注入 | ✅ |
| 管理员 API | 用户管理/边界 CRUD/大模型配置 | ✅ |
| 项目管理 | 项目 CRUD/边界多对多/参考项目 | ✅ |
| 会话&版本 | 会话创建/版本树/回滚分支/版本对比 | ✅ |
| DeepSeek 集成 | `server/app/services/deepseek_service.py` | ✅ |
| DXF 导出 | `server/app/services/dxf_service.py` + API | ✅ |
| **SVG 预览** | `server/app/services/preview_service.py` + API | ✅ |
| 前端页面 | `front.html` (~85KB, 1695行) | ✅ |

### 前端功能 (front.html)

| 功能 | 状态 |
|------|------|
| 登录页面 | ✅ |
| 项目列表/新建/删除 | ✅ |
| 设计边界多选 | ✅ (零硬编码) |
| 参考项目选择 | ✅ |
| AI 角色区分（有边界=专家，无边界=CAD制图员） | ✅ |
| 思考过程动画 + API 轮询等待 | ✅ |
| 会话管理（多会话切换） | ✅ |
| 版本管理（列表/对比/回滚分支） | ✅ |
| 对话记录持久化 | ✅ |
| 侧边栏折叠 | ✅ |
| **SVG 预览** (服务端渲染 → svg-pan-zoom显示) | ✅ |
| Canvas 缩放/平移（滚轮+拖拽+按钮） | ✅ |
| 椭圆/圆/三角/矩形全部通过SVG正确渲染 | ✅ |
| Per-canvas 独立缩放平移状态 | ✅ |
| DXF 下载 | ✅ |

### Phase 2：桥梁服务（Python Flask + pywin32）

| 模块 | 文件 | 状态 |
|------|------|------|
| 项目结构 | `bridge/app/{config,server,api_client,cad_engine}.py` | ✅ |
| Flask 本地服务 | `localhost:45678` | ✅ |
| API 客户端 | 登录/Token缓存/拉取版本JSON | ✅ |
| AutoCAD 绘制引擎 | pywin32 墙体/房间/门窗/标注 | ✅ |
| PyInstaller 打包 | `bridge/bridge.spec` | ✅ |
| 前端集成 | "在 CAD 中打开" 按钮调用桥梁 | ✅ |

---

## ❌ 待修复

### P0（阻塞）

1. **全屏查看按钮无效**
   - 按钮显示但点击无反应
   - `toggleCanvasFullscreen(versionId)` 函数可能报错或被覆盖
   - 需要打开浏览器 F12 Console 查看具体错误
   - 位置：`front.html` 行 1790-1825, 行 1335（按钮）, 行 780/1313（canvas-fs-btn）

2. **历史消息没有"全屏查看"按钮**
   - `renderMessages` 模板已有 `canvas-fs-btn`，但只在新消息的按钮栏有 `msg-btn`
   - 历史消息渲染模板在行 780

3. **已修复 - Canvas缩放平移问题**
   - ✅ 已用 svg-pan-zoom 替代 Canvas，实现矢量无损缩放

### P1（体验）

4. **已修复 - 圆形/椭圆/三角形渲染问题**
   - ✅ svg-pan-zoom 直接显示 SVG，所有图形正确渲染

5. **已修复 - 全屏 Canvas 的 SVG 加载问题**
   - ✅ 全屏现在也使用 svg-pan-zoom，直接从 API 获取 SVG 并渲染

---

## 架构决策

- **预览方式**: 服务端 JSON → SVG → 前端 svg-pan-zoom（矢量无损缩放）
- **SVG 优势**: 矢量无损、原生椭圆/圆/三角、无 matplotlib 依赖
- **缩放平移**: svg-pan-zoom 库自动管理，支持无限缩放不失真
- **认证**: SVG 预览接口支持 `?token=` query param（img标签不发 Authorization header）

---

## 启动方式

```bash
# AI 服务器
cd server && uv run uvicorn app.main:app --host 127.0.0.1 --port 8080

# 桥梁服务 (Windows + AutoCAD)
cd bridge && uv run python3 run.py

# 浏览器
open http://localhost:8080
# 默认: admin / admin123
```
