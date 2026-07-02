# AI CAD — 待开发工作

> 最后更新：2026-06-12

---

## P0 — 阻塞交付

### 1. Windows 实机测试

- **状态**：🟡 Mac 上已跑通 UI + 对话 + 预览，待 Windows 实测推 CAD
- **描述**：在 Windows + AutoCAD + pywin32 环境下跑通完整链路：登录 → 项目 → AI 对话 → 推 CAD → DWG 上传
- **涉及**：`client/` 全部
- **前置**：Windows 机器

### 2. 客户端 cad_engine 补齐旧版功能

- **状态**：🔴 待开始
- **描述**：新版 `client/app/cad_engine.py` 相比旧版 `bridge/app/cad_engine.py` 缺少以下绘制：
  - 门（`_draw_door`）— 门弧 + 定位到墙面
  - 窗（`_draw_window`）— 双线窗 + 中竖线
  - 柱网（`_draw_column`）— 矩形 + SOLID 填充
  - 房间面积标注 `XXm²`
  - 尺寸标注线（水平 + 端点竖线，不只是文字）
  - 图层线宽（旧版每层设 Lineweight，新版只设 color）
- **涉及**：`client/app/cad_engine.py`

---

## P1 — 体验优化

### 3. 推 CAD 前安全确认弹窗

- **状态**：🔴 待开始
- **描述**：点击"推 CAD"时弹出确认对话框，询问"新建文档"还是"当前文档"，避免覆盖设计师正在编辑的图
- **涉及**：`client/app/main_window.py` `_push_to_cad` 方法
- **预估**：~30 行

### 4. 对话 Markdown 渲染

- **状态**：🔴 待开始
- **描述**：对话区支持 Markdown（代码块、表格、列表），AI 返回的结构化内容正确展示
- **涉及**：`client/app/widgets/chat_bubble.py` 或引入 `QMarkdownPreview`
- **预估**：1-2 天

### 5. 客户端异常处理增强

- **状态**：🔴 待开始
- **描述**：
  - 网络断开提示（当前静默失败）
  - Token 过期自动重登
  - `_push_to_cad` 中有 `return` 在 `self._show_error` 前面的 bug（L1189-1191）
- **涉及**：`client/app/main_window.py`、`client/app/api_client.py`

---

## P2 — 进阶功能

### 6. 版本叠图对比

- **状态**：🔴 待开始
- **描述**：QGraphicsView 上同时渲染两个版本的图元，新版蓝色、旧版灰色半透明，改动区域高亮
- **涉及**：`client/app/main_window.py` 或新建 `preview_compare.py`

### 7. 边界规则高级编辑器

- **状态**：🔴 待开始
- **描述**：树形规则编辑、拖放排序、约束冲突可视化、自定义规则语法高亮
- **涉及**：`client/app/widgets/boundary_editor.py`（新建）
- **当前状态**：管理后台已可文本编辑边界，客户端暂无编辑入口

### 8. 客户端打包 exe (Windows)

- **状态**：🔴 待开始
- **描述**：PyInstaller 打包为单个 exe，含 PySide6 + websockets 依赖
- **涉及**：`client/app.spec`
- **前置**：Windows 实机测试通过后

### 9. 客户端自动更新

- **状态**：🔴 待开始
- **描述**：exe 启动时检查服务器最新版本号，提示下载更新
- **涉及**：客户端 `main.py` 新增检查逻辑 + 服务端 `GET /api/version`
- **前置**：打包 exe 完成后

---

## P3 — 基础设施

### 10. 服务端单元测试

- **状态**：🔴 待开始
- **描述**：核心 API 测试覆盖（认证、项目 CRUD、AI 生成、DWG 上传）
- **预估**：20-30 条测试用例

### 11. 日志系统

- **状态**：🔴 待开始
- **描述**：客户端加结构化日志，当前只有 print；服务端已有 uvicorn 日志可优化

### 12. DXF 导出与预览保持一致

- **状态**：🔴 待开始
- **描述**：`server/app/services/dxf_service.py` 缺少 zones/divisions 绘制、房间面积标注，与 SVG 预览和客户端预览不一致
- **涉及**：`server/app/services/dxf_service.py`

---

## 已完成（2026-06-12）

- [x] 客户端预览图渲染全面升级 (`_building_to_scene` 重写)
  - 线宽/字号根据场景范围自适应（`ref_size` 机制），不再硬编码
  - 建筑名居中 + 尺寸标注（如 `60m × 40m`）
  - 房间名居中显示 + 房间面积标注（如 `120m²`）
  - 区域名居中显示（zones + divisions）
  - `_render_preview_pixmap` 升级为两遍渲染 + 1080×720 2x 分辨率
  - `_do_update_preview` 同步改为两遍渲染
- [x] 预览区交互增强 (`chat_bubble.py` PreviewView)
  - 左键拖拽平移（改用 scrollbar.setValue，更稳定）
  - 滚轮缩放
  - 右上角「⟲ 重置」按钮（一键回到初始视图）
  - 双击也可重置视图
  - 记录初始 `_initial_scene_rect`，重置精准不漂移
  - 预览容器从 QWidget 改为 QFrame，边框+圆角样式可靠
- [x] 隐藏的 version_tree 控件补回（右侧面板移除后遗留引用导致崩溃）
- [x] WebSocket 流式对话（服务端 + 客户端均已接入）

## 已完成（2026-06-10/11）

- [x] PySide6 安装 + 客户端首次在 Mac 上跑通
- [x] 客户端自动登录 bug 修复
- [x] 左侧只放项目列表，会话标签置于顶部
- [x] 会话标签左对齐紧凑排列 + 右键重命名
- [x] 管理后台：边界编辑、用户管理、大模型配置、服务器配置、项目记录
- [x] DWG 下载链接拼接 token 参数
- [x] 版本列表中点击任意版本自动加载预览

---

## 工作量估算

| 优先级 | 事项数 | 预估工时 |
|--------|--------|----------|
| P0 | 2 | 2-3 天（需 Windows 机器） |
| P1 | 3 | 2-3 天 |
| P2 | 4 | 5-7 天 |
| P3 | 3 | 2-3 天 |
| **合计** | **12** | **11-16 天** |