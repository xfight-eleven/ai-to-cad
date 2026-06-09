# AI CAD 桥梁服务方案

> 最后更新：2026-06-04

---

## 核心思想

每个设计师自己电脑上跑一个轻量本地服务（桥梁），接收 AI 服务器下发的 JSON 设计数据，然后用 pywin32 指挥本机 AutoCAD 画图。每个人互不干扰，图纸质量与手动绘制完全一致。

## 设计边界设定（核心约束）

**核心设计原则：零硬编码。** 行业类型、边界规则、车间约束等全部由管理员在后台动态配置，代码层面不做任何内置假设。

### 边界是什么

管理员在后台创建**设计边界模板**，每个模板是一份结构化 JSON 配置，用于约束 AI 的出图范围。例如管理员可以创建：

| 边界模板（示例） | 说明 |
|---|---|
| 肉制品厂房 | 管理员配置了屠宰车间、分割车间、冷藏库等规则 |
| 调味品厂房 | 管理员配置了发酵车间、调配车间、灌装车间等规则 |
| ... | 管理员可随时新增、修改、删除任意边界模板 |

**代码不内置任何行业**——系统初始化为空，所有边界规则由管理员按需创建。

### 边界规则的柔性结构

每个边界模板的 JSON 结构完全由管理员定义，系统仅提供通用的结构化字段：

```
边界模板 JSON（管理员自由配置）：
├─ 必选区域清单（名称 + 最小/最大面积 + 数量范围）
├─ 可选区域清单（同上）
├─ 分区约束（如"清洁区/准清洁区/一般作业区"——名称完全自定义）
├─ 流线约束（如"原料→加工→包装→仓储"——节点和方向自定义）
├─ 设备模板（名称 + 尺寸 + 数量，可选配置）
└─ 自定义规则文本（自然语言描述，直接注入 AI prompt）
```

**系统不关心**规则的内容是什么——它只是一个 JSON 容器。管理员配置什么，AI 就遵循什么。

### 设计师如何使用

```
┌──────────────────────────────────────────────┐
│  新建项目                                     │
│                                              │
│  项目名称：[成都肉制品加工厂                ] │
│                                              │
│  设计边界（可多选）：                         │
│  ┌─────────────────────────────────────────┐ │
│  │ ☑ 肉制品厂房通用（管理员配置）          │ │
│  │ ☑ 重庆地区·食品厂房规范（管理员配置）   │ │
│  │ ☐ 成都地区·食品厂房规范（管理员配置）   │ │
│  │ ☐ 调味品厂房通用（管理员配置）          │ │
│  │ ☐ 米面制品厂房通用（管理员配置）        │ │
│  │ ...（管理员可增删改）                    │ │
│  └─────────────────────────────────────────┘ │
│  已选 2 项：肉制品通用 + 重庆地区规范        │
│                                              │
│  不勾选任何边界 → AI 作为通用 CAD 制图员    │
│                                              │
│  参考项目：[▼ 可选，选择相似项目作参考      ] │
│                                              │
│  [创建项目]                                  │
└──────────────────────────────────────────────┘
```

**多选的设计意图**：不同维度的边界可以自由组合——
- **行业维度**：肉制品通用（必选车间、面积范围等）
- **地区维度**：重庆/成都的当地规范（抗震等级、消防要求等）
- 设计师勾选多个边界，AI 会将所有选中边界的规则合并后统一遵循

**典型场景**：做成都肉制品厂的图，勾选"肉制品厂房通用"+"重庆地区规范"——因为成渝两地对厂房要求相近，重庆的边界模板可以直接复用。

列表**动态拉取**管理员配置的边界模板，前端不做任何硬编码。如果管理员从未配置任何边界，列表为空，AI 自由发挥。

- **选择边界** → AI 在行业约束下生成设计方案，确保合规、合理
- **不选择** → AI 作为通用 CAD 制图员，无行业限制自由发挥

**效果**：选边界后，AI 不会给肉制品厂画一个发酵车间，也不会漏掉必备的功能区。

## 会话与版本管理（核心）

设计师和 AI 的每一轮对话都是一个**会话（Session）**，每次点"生成"产生一个**版本（Version）**，所有版本按时间线排列，形成版本树。

### 为什么重要

```
Day 1:  输入需求 → v1 方案  ← 客户：这个好！
Day 2:  修改 → v2 方案
Day 3:  再修改 → v3 方案    ← 客户：还是 v1 好吧
        ─────────────────────
        回滚到 v1 → v4（v1 的复刻，保留 v2/v3 不删）
```

**关键原则**：
- **版本不可删除** — 每个版本都是历史记录，回滚不是覆盖，是创建新分支
- **项目可删除** — 如果设计师不慎创建了错误项目，可以从项目列表中删除整个项目及其所有版本。这是设计师自己的权利，避免无用数据堆积
- **JSON 是唯一真相** — DXF、预览图都是可重建的，存 JSON 就够了
- **每次精炼继承上文** — 追加需求时保留上一轮所有未改参数

### 设计师看到的效果

```
┌──────────────────────────────────────────┐
│  会话：水产品加工厂方案                    │
│                                          │
│  ┌─ 用户: 画一个100×200的水产品加工厂    │
│  │  AI: ✅ v1 已生成                     │
│  │  [预览] [在 CAD 中打开]               │
│  │                                       │
│  ├─ 用户: 增加一个冷藏库，50×30          │
│  │  AI: ✅ v2 已生成                     │
│  │  [预览] [在 CAD 中打开]               │
│  │  [对比 v1→v2]                         │
│  │                                       │
│  ├─ 用户: 把车间改成田字布局             │
│  │  AI: ✅ v3 已生成                     │
│  │  [预览] [在 CAD 中打开]               │
│  │  [对比 v2→v3]                         │
│  │                                       │
│  └─ ☆ 版本列表                          │
│     ├─ v1 ── 初始方案                   │
│     ├─ v2 ── +冷藏库        ← 当前      │
│     └─ v3 ── 田字布局                   │
│     [回滚到 v1] → 生成 v4               │
└──────────────────────────────────────────┘
```

### 版本树结构

```
v1 ──→ v2 ──→ v3        ← 主分支
  └──→ v4               ← 从 v1 回滚产生的分支
         └──→ v5        ← 继续精炼
```

所有版本都有完整对话记录，设计师可以随时切回任意版本查看。

---

## 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     AI 服务器                                    │
│                     192.168.10.1                                 │
│                                                                  │
│  功能：                                                           │
│  ├─ 接收设计师需求（网页输入）                                     │
│  ├─ 调用 DeepSeek API 生成 JSON 设计方案                          │
│  ├─ 存储会话、版本、历史数据                                       │
│  ├─ ezdxf 生成 .dxf 文件（预览够用，可下载）                       │
│  ├─ 提供网页预览（前端 Canvas 在线渲染）                          │
│  └─ 提供 API 接口供桥梁服务拉取 JSON 数据（精确出图用）             │
└────────────┬─────────────────────────────────────────────────────┘
             │
             │ HTTP（内网）
             │
    ┌────────┴────────────┬────────────────┐
    │                     │                │
    │    ┌────────────────┤                │
    │    ▼                │                │
    │ 下载 .dxf           │                │
    │ 双击打开 AutoCAD     │                │
    │（快速查看）          │                │
    │                     │                │
┌───▼──────────────────────▼────────┐ ┌───▼────────────┐
│ 设计师 A                          │ │ 设计师 B        │
│                                   │ │                 │
│ 浏览器打开网页预览                 │ │ ...             │
│                                   │ │                 │
│ 两套出图方式（任选）：              │ │                 │
│ ① 点 [下载 DXF] → 双击打开       │ │                 │
│ ② 点 [在 CAD 中打开]  → ────┐   │ │                 │
│                              │   │ │                 │
│  ┌───────────────────────────┘   │ │                 │
│  ▼                               │ │                 │
│  本机桥梁服务 localhost:45678      │ │                 │
│  pywin32 直绘 AutoCAD（精确）     │ │                 │
│  同时保存 .dwg 到桌面             │ │                 │
└───────────────────────────────────┘ └─────────────────┘
```

---

## 大模型配置管理

当前使用 DeepSeek V4 云端 API，但后台需要支持灵活切换，以应对将来使用本地大模型的需求。

### 管理入口

管理员在后台可配置：

```
┌──────────────────────────────────────────┐
│  大模型设置                               │
│                                          │
│  模型类型：[▼ DeepSeek V4 (云端)       ] │
│            ├─ DeepSeek V4 (云端)         │
│            ├─ DeepSeek V3 (云端)         │
│            ├─ 自定义 OpenAI 兼容 API     │
│            └─ 本地大模型 (Ollama/vLLM)   │
│                                          │
│  API Key： [sk-0df7940af2344815...... ] │
│                                          │
│  API 地址：[https://api.deepseek.com   ] │
│                                          │
│  模型名称：[deepseek-chat               ] │
│                                          │
│  高级参数：                               │
│  ├─ Temperature：[0.3          ]         │
│  ├─ Max Tokens：[8192         ]          │
│  └─ 超时时间： [120 秒       ]           │
│                                          │
│  [测试连接]  [保存设置]                   │
└──────────────────────────────────────────┘
```

### 设计要点

- **热切换**：修改配置后无需重启服务，新请求立即使用新模型
- **连接测试**：保存前可测试 API 连通性，返回延迟和模型可用性
- **安全存储**：API Key 加密存储于数据库，前端不暴露完整 Key
- **历史记录**：记录每次模型切换日志，方便回溯某版本用了哪个模型生成
- **本地模型适配**：支持标准 OpenAI 兼容接口，Ollama、vLLM 等本地部署方案无缝接入

### 数据库字段

```sql
CREATE TABLE llm_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,           -- deepseek / openai_compatible / local
    api_key TEXT NOT NULL,            -- 加密存储
    api_base TEXT NOT NULL,           -- API 地址
    model_name TEXT NOT NULL,         -- 模型名称
    temperature REAL DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 8192,
    timeout_seconds INTEGER DEFAULT 120,
    is_active BOOLEAN DEFAULT 1,      -- 当前生效的配置
    updated_at TIMESTAMP,
    updated_by TEXT                   -- 操作的管理员
);
```

---

## 多设计师隔离与权限

### 隔离规则

| 规则 | 说明 |
|---|---|
| **项目可见性** | 每个设计师只能看到自己创建的项目 |
| **参考可见性** | 设计师可以将自己的项目标记为"允许参考"，供其他人新建项目时选择 |
| **管理员可见性** | 管理员可以看到所有设计师的项目 |

### 权限模型

```
设计师 A                    设计师 B                    管理员
┌──────────┐              ┌──────────┐              ┌──────────┐
│ 项目 a1  │              │ 项目 b1  │              │ 所有项目 │
│ 项目 a2  │              │ 项目 b2  │              │ 用户管理 │
│ 项目 a3  │              │ 项目 b3  │              │ 边界配置 │
│          │              │          │              │ 模型配置 │
│ [看自己的]│              │ [看自己的]│              │ [全权限 ]│
└──────────┘              └──────────┘              └──────────┘
     │                         │                        │
     └────── 不能互看 ─────────┘                        │
                             └──── 参考：a1 允许参考 ────┘
                                   → B 可以选择 a1 作为参考模板
```

### 项目数据归属

```
项目
├─ 创建者 ID（归属）
├─ 是否允许被参考（开关）
├─ 会话列表（仅创建者可读写）
│   ├─ 版本列表
│   └─ 对话记录
└─ 删除权限：仅创建者和管理员
```

---

## 账号管理

设计师账号由管理员统一分配，不支持自行注册。

### 管理员操作

```
┌──────────────────────────────────────────┐
│  用户管理                                 │
│                                          │
│  [+ 添加用户]                             │
│  ┌─────────────────────────────────────┐ │
│  │ 姓名        │ 角色     │ 状态  │操作│ │
│  ├─────────────────────────────────────┤ │
│  │ 张三        │ 设计师   │ 正常  │··· │ │
│  │ 李四        │ 设计师   │ 正常  │··· │ │
│  │ 王五        │ 设计师   │ 禁用  │··· │ │
│  │ 管理员      │ 管理员   │ 正常  │··· │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

### 用户表结构

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,       -- 登录账号
    password_hash TEXT NOT NULL,         -- 密码哈希
    display_name TEXT NOT NULL,          -- 显示姓名（如"张三"）
    role TEXT NOT NULL DEFAULT 'designer',  -- admin / designer
    status TEXT NOT NULL DEFAULT 'active',  -- active / disabled
    created_at TIMESTAMP,
    created_by TEXT                      -- 创建者（管理员）
);
```

### 关键规则

- **仅管理员**可添加/禁用/删除用户
- **禁用用户**无法登录，但其历史项目数据保留
- **管理员账号**至少保留一个，不可全部删除
- **初始管理员**在系统首次部署时通过命令行参数创建

---

## 参考项目功能

### 场景

> A 设计师做了一个肉制品厂房项目，客户很满意。C 设计师也接了一个肉制品客户，他在新建项目时可以选择 A 的那个肉制品项目作为参考模板，AI 基于已有成果快速出图。

### 价值

| 维度 | 说明 |
|---|---|
| **节省 Token** | 参考项目已包含成熟的车间布局和参数，AI 无需从零推理，大幅减少在线调用量 |
| **出图更快** | 同类型项目一次推理即可完成，减少多轮精炼 |
| **知识复用** | 优秀方案在公司内部沉淀，经验可复制 |
| **保持灵活性** | 参考 ≠ 复制，AI 会根据新项目的具体需求（地块尺寸、产能要求）调整 |

### 工作流程

```
C 设计师新建项目
    │
    ├─ ① 选择设计边界：肉制品
    │
    ├─ ② 选择参考项目（可选）：
    │      ┌──────────────────────────────────────┐
    │      │  选择参考项目                          │
    │      │  ┌──────────────────────────────┐    │
    │      │  │ 筛选：肉制品 ▼                │    │
    │      │  ├──────────────────────────────┤    │
    │      │  │ ○ A设计师 - 牛肉屠宰加工厂   │    │
    │      │  │   v3 · 冷鲜肉工艺 · 5000㎡   │    │
    │      │  │                              │    │
    │      │  │ ● D设计师 - 猪肉分割包装厂   │    │
    │      │  │   v1 · 热鲜肉工艺 · 3000㎡   │    │
    │      │  └──────────────────────────────┘    │
    │      │  [确认选择]  [不参考，自己画]         │
    │      └──────────────────────────────────────┘
    │
    └─ ③ 输入需求描述（可选，不填则直接复用参考方案的布局）
           └─ "客户地块 120×80m，日产 20 吨，需要冷鲜工艺"
              → AI 基于参考项目 JSON + 新需求 → 生成 v1
```

### AI 提示词拼接策略

```
System Prompt:
  你是一个工业厂房 CAD 设计专家。
  
  ── 以下约束由管理员配置，请严格遵守 ──
  已选边界模板（共 {count} 项）：
  
  【边界 1：{boundary_1_name}】
  {boundary_1_rules_json}
  
  【边界 2：{boundary_2_name}】
  {boundary_2_rules_json}
  
  ...（设计师勾选了几个就拼几个）
  
  ── 参考项目（如有）──
  {reference_project_json}
  
  ── 用户需求 ──
  {user_prompt}

请基于以上所有边界约束生成设计方案。
多个边界的规则需同时满足，如有冲突以排在前面的边界为准。
如果用户未提供具体需求，参考项目的布局逻辑进行适应性调整。
```

**关键点**：系统只负责遍历已选边界、拼接 JSON，不解析、不校验、不修改边界规则的内容。设计师勾几个就拼几个，管理员写什么就原样注入什么。改规则完全不需要改代码。

### 参考项目的权限控制

- 设计师可将自己的**任意项目**标记为"允许参考"
- 只有"允许参考"的项目才会出现在其他人的参考选择列表中
- 参考者只能读取参考项目的 JSON 数据，不能修改原项目
- 设计师可以随时**关闭**参考开关，已参考的项目不受影响（快照机制）

---

## 数据模型

```sql
-- 用户表
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'designer',   -- admin / designer
    status TEXT NOT NULL DEFAULT 'active',   -- active / disabled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

-- 设计边界表（零硬编码——所有规则由管理员动态配置）
CREATE TABLE boundaries (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,               -- 管理员命名的边界名称
    description TEXT,                        -- 管理员填写的描述
    rules_json TEXT NOT NULL,                -- 管理员定义的规则 JSON（结构自由，代码不解析）
    icon TEXT,                               -- 前端展示图标（管理员选择）
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 大模型配置表
CREATE TABLE llm_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    api_base TEXT NOT NULL,
    model_name TEXT NOT NULL,
    temperature REAL DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 8192,
    timeout_seconds INTEGER DEFAULT 120,
    is_active BOOLEAN DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- 项目表
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES users(id),
    reference_project_id TEXT REFERENCES projects(id),  -- 参考的项目
    allow_reference BOOLEAN DEFAULT 0,                  -- 是否允许他人参考
    status TEXT DEFAULT 'active',                       -- active / deleted
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 项目-边界 多对多关联表
CREATE TABLE project_boundaries (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    boundary_id TEXT NOT NULL REFERENCES boundaries(id),
    PRIMARY KEY (project_id, boundary_id)
);

-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 版本表（版本不可删除）
CREATE TABLE versions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,                            -- v1, v2, v3...
    parent_version_id TEXT REFERENCES versions(id),     -- NULL = 初始版本
    design_json TEXT NOT NULL,                          -- 完整 JSON 设计数据
    description TEXT,                                   -- 版本描述
    llm_provider TEXT,                                  -- 生成时使用的模型
    llm_model TEXT,
    token_usage INTEGER,                                -- Token 消耗
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话记录表
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                                 -- user / assistant
    content TEXT NOT NULL,
    version_id TEXT REFERENCES versions(id),            -- assistant 消息关联版本
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 大模型切换日志
CREATE TABLE llm_config_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    old_provider TEXT,
    old_model TEXT,
    new_provider TEXT,
    new_model TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 实体关系

```
users 1──N projects
projects N──M boundaries (多对多，通过 project_boundaries)
projects 1──N sessions
sessions 1──N versions
sessions 1──N messages
versions 1──N versions (自引用，版本树)
projects N──1 projects (参考项目，自引用)
```

---

### 组件一：AI 服务器（公司服务器 192.168.10.1）

技术栈：Python FastAPI + SQLite

```python
# 服务器端核心接口（示意）

# ── 用户认证 ──────────────────────────
@app.post("/api/auth/login")
def login(username: str, password: str):
    """设计师/管理员登录，返回 JWT Token"""
    user = authenticate(username, password)
    return {"token": create_jwt(user), "user": user}

@app.get("/api/auth/me")
def me(current_user = Depends(get_current_user)):
    """当前登录用户信息"""
    return current_user

# ── 用户管理（仅管理员）────────────────
@app.get("/api/admin/users")
def list_users(admin = Depends(require_admin)):
    """列出所有用户"""
    return db.query(User).all()

@app.post("/api/admin/users")
def create_user(data: CreateUserRequest, admin = Depends(require_admin)):
    """创建新设计师账号"""
    return db.create(User, **data)

@app.put("/api/admin/users/{id}")
def update_user(id: str, data: UpdateUserRequest, admin = Depends(require_admin)):
    """修改用户（角色、状态等）"""
    ...

@app.delete("/api/admin/users/{id}")
def delete_user(id: str, admin = Depends(require_admin)):
    """删除用户（同时归档其项目数据）"""
    ...

# ── 设计边界管理（仅管理员）────────────
# 注意：系统只存取 JSON 字符串，不解析规则内容
# 管理员写什么，AI 就收到什么——零硬编码
@app.get("/api/boundaries")
def list_boundaries(user = Depends(get_current_user)):
    """所有可用的设计边界列表（所有登录用户可读）"""
    return db.query(Boundary).all()

@app.post("/api/admin/boundaries")
def create_boundary(data: BoundarySchema, admin = Depends(require_admin)):
    """管理员创建/更新设计边界规则
       rules_json 为自由格式，后端不做字段校验"""
    return db.upsert(Boundary, data)

@app.get("/api/admin/boundaries/{id}")
def get_boundary_detail(id: str, admin = Depends(require_admin)):
    """边界详情（含完整规则 JSON）"""
    return db.get(Boundary, id)

# ── 大模型配置（仅管理员）──────────────
@app.get("/api/admin/llm-config")
def get_llm_config(admin = Depends(require_admin)):
    """获取当前大模型配置（API Key 脱敏）"""
    config = db.get_active(LlmConfig)
    return mask_api_key(config)

@app.put("/api/admin/llm-config")
def update_llm_config(data: LlmConfigRequest, admin = Depends(require_admin)):
    """更新大模型配置"""
    ...

@app.post("/api/admin/llm-config/test")
def test_llm_connection(data: LlmConfigRequest, admin = Depends(require_admin)):
    """测试大模型连接"""
    result = test_connection(data)
    return {"success": result.ok, "latency_ms": result.latency_ms}

# ── 项目管理 ──────────────────────────
@app.get("/api/projects")
def list_projects(user = Depends(get_current_user)):
    """当前设计师的项目列表（仅自己的）"""
    return db.query(Project).filter(owner_id=user.id).all()

@app.post("/api/projects")
def create_project(data: CreateProjectRequest, user = Depends(get_current_user)):
    """新建项目
       data.boundary_ids          — 设计边界 ID 列表（可多选，空列表则 AI 自由发挥）
       data.reference_project_id  — 参考项目（可选）"""
    project = db.create(Project,
        title=data.title,
        owner_id=user.id,
        reference_project_id=data.reference_project_id,
    )
    # 建立多对多关联
    for bid in data.boundary_ids:
        db.create(ProjectBoundary, project_id=project.id, boundary_id=bid)
    return project

@app.delete("/api/projects/{id}")
def delete_project(id: str, user = Depends(get_current_user)):
    """删除项目——仅项目创建者可操作
       删除整个项目及所有会话、版本、对话记录"""
    project = db.get(Project, id)
    if project.owner_id != user.id and user.role != 'admin':
        raise HTTPException(403, "无权删除")
    db.delete(project)  # 级联删除
    return {"message": "已删除"}

@app.put("/api/projects/{id}/allow-reference")
def toggle_reference(id: str, allow: bool, user = Depends(get_current_user)):
    """开关"允许参考"——仅项目所有者可操作"""
    project = db.get(Project, id)
    if project.owner_id != user.id:
        raise HTTPException(403, "无权操作")
    project.allow_reference = allow
    db.save(project)
    return project

@app.get("/api/reference-projects")
def list_reference_projects(user = Depends(get_current_user)):
    """可参考的项目列表（他人标记为允许参考的项目）"""
    return db.query(Project).filter(
        Project.allow_reference == True,
        Project.owner_id != user.id,
    ).all()

# ── 会话管理 ──────────────────────────
@app.get("/api/projects/{project_id}/sessions")
def list_sessions(project_id: str, user = Depends(get_current_user)):
    """项目下的所有会话（含版本数）"""
    verify_ownership(project_id, user)
    return db.query(Session).filter(project_id=project_id).all()

@app.post("/api/projects/{project_id}/sessions")
def create_session(project_id: str, title: str, user = Depends(get_current_user)):
    """在项目下新建一个设计会话"""
    verify_ownership(project_id, user)
    return db.create(Session, project_id=project_id, title=title)

@app.get("/api/sessions/{id}")
def get_session(id: str, user = Depends(get_current_user)):
    """会话详情（含完整对话记录 + 版本列表）"""
    session = db.get(Session, id)
    verify_ownership(session.project_id, user)
    return {
        "session": session,
        "messages": session.messages,
        "versions": session.versions,
    }

# ── 设计生成 ──────────────────────────
@app.post("/api/design/generate")
def generate(prompt: str, session_id: str, user = Depends(get_current_user)):
    """接收需求 → AI 生成方案 → 存储 → 返回
       自动读取项目关联的设计边界和参考项目"""
    session = db.get(Session, session_id)
    verify_ownership(session.project_id, user)
    
    project = db.get(Project, session.project_id)
    
    # 构建 AI 上下文
    boundaries = db.query(ProjectBoundary).filter(project_id=project.id).all()
    context = {
        "boundaries": [get_boundary_rules(b.boundary_id) for b in boundaries],  # 多选边界合并
        "reference": get_reference_json(project.reference_project_id),           # 参考项目JSON
        "history": get_recent_messages(session_id),
    }
    
    design = call_deepseek(prompt, context)
    version = save_version(session_id, design)
    save_message(role="user", content=prompt)
    save_message(role="assistant", content="方案已生成", version_id=version.id)
    return {
        "projectId": session.project_id,
        "sessionId": version.session_id,
        "versionId": version.id,
        "versionNumber": version.number,
        "designJson": design,
        "description": design["description"],
    }

@app.post("/api/design/refine")
def refine(prompt: str, session_id: str, user = Depends(get_current_user)):
    """追加精炼——继承上下文，生成新版本"""
    session = db.get(Session, session_id)
    verify_ownership(session.project_id, user)
    
    project = db.get(Project, session.project_id)
    history = get_recent_messages(session_id)
    boundaries = db.query(ProjectBoundary).filter(project_id=project.id).all()
    
    context = {
        "boundaries": [get_boundary_rules(b.boundary_id) for b in boundaries],
        "reference": get_reference_json(project.reference_project_id),
        "history": history,
    }
    
    design = call_deepseek(prompt, context)
    version = save_version(session_id, design, parent=latest)
    return {...}

# ── 版本管理 ──────────────────────────
@app.get("/api/versions/{id}")
def get_version(id: str, user = Depends(get_current_user)):
    """版本详情（含完整的 designJson）"""
    version = db.get(Version, id)
    session = db.get(Session, version.session_id)
    verify_ownership(session.project_id, user)
    return version

@app.post("/api/versions/{id}/restore")
def restore_version(id: str, user = Depends(get_current_user)):
    """回滚到指定版本——不会删除中间版本
       而是基于该版本创建一个新分支版本"""
    version = db.get(Version, id)
    session = db.get(Session, version.session_id)
    verify_ownership(session.project_id, user)
    
    new = db.create(Version,
        session_id=version.session_id,
        design_json=version.design_json,
        parent_version_id=id,
    )
    return {
        "message": f"已回滚到 v{version.number}（创建为 v{new.number}）",
        "designJson": new.design_json
    }

@app.get("/api/versions/{v1}/diff/{v2}")
def diff_versions(v1: str, v2: str, user = Depends(get_current_user)):
    """版本对比"""
    ...
```

### 组件二：设计师本机的桥梁服务

技术栈：Python + Flask + pywin32

```python
# local_bridge.py — 每个设计师电脑上运行
from flask import Flask, request
import win32com.client
import requests
import json

app = Flask(__name__)

AI_SERVER = "http://192.168.10.1"

@app.route("/open-in-cad")
def open_in_cad():
    version_id = request.args["id"]
    
    # 1. 从服务器拉 JSON 设计数据
    resp = requests.get(f"{AI_SERVER}/api/versions/{version_id}")
    design = resp.json()
    
    # 2. 指挥本地 AutoCAD 画图（pywin32）
    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    doc = acad.Documents.Add()
    msp = doc.ModelSpace
    
    draw_design(msp, design)  # 画图函数
    
    # 3. 保存 .dwg 到桌面
    desktop = os.path.expanduser("~/Desktop")
    doc.SaveAs(f"{desktop}/{design['project']['name']}.dwg")
    
    return "✅ 图纸已打开"

def draw_design(msp, design):
    """pywin32 指挥 AutoCAD 画图—和你之前手写脚本完全一样"""
    for building in design["buildings"]:
        x = building["position"]["x"] * 1000
        y = building["position"]["y"] * 1000
        w = building["dimensions"]["width"] * 1000
        h = building["dimensions"]["length"] * 1000
        
        # 外墙
        pts = [x, y, x+w, y, x+w, y+h, x, y+h, x, y]
        wall = msp.AddLightWeightPolyline(pts)
        wall.Closed = True
        wall.Layer = "WALL"
        
        # 房间
        for room in building.get("rooms", []):
            rx = x + room["x"] * 1000
            ry = y + room["y"] * 1000
            rw = room["width"] * 1000
            rh = room["length"] * 1000
            r = msp.AddLightWeightPolyline([
                rx, ry, rx+rw, ry, rx+rw, ry+rh, rx, ry+rh, rx, ry
            ])
            r.Layer = "ROOM"
            
            # 房间名
            txt = msp.AddText(room["name"], (rx+rw/2, ry+rh/2), 500)
            txt.Layer = "TEXT"

app.run(host="127.0.0.1", port=45678)
```

---

## 设计师的完整工作流

```
┌──────────────────────────────────────────────────────────────────────┐
│ ① 浏览器打开 http://192.168.10.1                                    │
│    ┌──────────────────────────────────────────┐                      │
│    │  会话列表                                 │                      │
│    │  ├─ 水产品加工厂（v3）                    │                      │
│    │  ├─ 肉制品厂（v1）                       │                      │
│    │  └─ [新建会话] 画一个300米×300米的...     │                      │
│    └──────────────────────────────────────────┘                      │
│                                                                      │
│ ② 服务器调 AI，返回方案                                             │
│    ┌──────────────────────────────────────────┐                      │
│    │  会话：水产品加工厂   v2 ← 当前          │                      │
│    │  ┌─────────────────────────┐              │                      │
│    │  │  预览图                  │              │                      │
│    │  │  屠宰车间 │ 分割车间     │              │                      │
│    │  │  冷藏库   │ 包装车间     │              │                      │
│    │  └─────────────────────────┘              │                      │
│    │  ⚠️ 预览为示意，请以 AutoCAD 图纸为准   │                      │
│    │  [📐 在 CAD 中打开]  [📋 版本列表]       │                      │
│    └──────────────────────────────────────────┘                      │
│                                                                      │
│ ③ 点击"在 CAD 中打开"                                               │
│    ↓                                                                 │
│    请求 http://localhost:45678/open-in-cad?id=version_xxx            │
│    ↓                                                                 │
│    本机桥梁服务从服务器取 JSON                                        │
│    ↓                                                                 │
│    pywin32 指挥本地 AutoCAD 画图                                      │
│    ↓                                                                 │
│    AutoCAD 自动弹出，图纸画好                                        │
│    ↓                                                                 │
│    设计师直接在 CAD 里修改、标注、出图                                 │
│                                                                      │
│ ④ 追加需求或回滚                                                    │
│    ┌──────────────────────────────────────────┐                      │
│    │  [输入框] 加一个 50×30 的冷藏库          │                      │
│    │  [生成 v3]                               │                      │
│    └──────────────────────────────────────────┘                      │
│    ↓                                                                 │
│    AI 继承 v2 上下文，只新增冷藏库，其他不变                          │
│    ↓                                                                 │
│    生成 v3 → 预览 → 满意就点"在 CAD 中打开"                          │
│                                                                      │
│ ⑤ 客户变了主意，觉得 v1 好                                           │
│    ┌──────────────────────────────────────────┐                      │
│    │  版本列表                                 │                      │
│    │  ├─ v1  初始方案         [回滚到此处]    │                      │
│    │  ├─ v2  +冷藏库          当前            │                      │
│    │  └─ v3  改田字布局                      │                      │
│    └──────────────────────────────────────────┘                      │
│    ↓                                                                 │
│    点"回滚到 v1"                                                     │
│    ↓                                                                 │
│    系统把 v1 的 JSON 复制出来，创建 v4（不是覆盖 v2/v3）               │
│    ↓                                                                 │
│    所有历史版本完好保留，随时能切回去看                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 前端页面布局（参考豆包风格）

整体采用**左侧历史 + 右侧对话**的双栏布局，设计师在一个页面内完成从需求输入到版本浏览的全部操作。

```
┌──────────────────────────────────────────────────────────────────┐
│  Logo    AI CAD 设计助手                      用户名  [设置] [退出] │
├────────────────┬─────────────────────────────────────────────────┤
│                │                                                 │
│  [+ 新建项目]  │  会话：成都肉制品加工厂                           │
│                │                                                 │
│  ┌──────────┐ │  ┌─────────────────────────────────────────────┐ │
│  │ 设计边界  │ │  │  AI                                        │ │
│  │ 已选 2 项 │ │  │  已根据您选择的设计边界生成 v1 方案：        │ │
│  │ 肉制品通用 │ │  │                                            │ │
│  │ 重庆规范   │ │  │  ┌─────────────────────────────────────┐  │ │
│  └──────────┘ │ │  │                                     │  │ │
│                │ │  │        Canvas 预览图                 │  │ │
│  ──────────── │ │  │        (可拖拽/缩放)                 │  │ │
│  历史记录      │ │  │                                     │  │ │
│                │ │  └─────────────────────────────────────┘  │ │
│  ● 成都肉制品  │ │                                            │ │
│    加工厂      │ │  v1 · 2026-06-08 14:30                      │ │
│    v3 · 今天  │ │  [📐 在 CAD 中打开]  [📋 版本列表]          │ │
│                │ │                                             │ │
│  ○ 武汉调味品  │ │  ─────────────────────────────────────────  │ │
│    工厂       │ │                                             │ │
│    v1 · 昨天  │ │  ┌─────────────────────────────────────┐    │ │
│                │ │  │  输入您的需求...                     │    │ │
│  ○ 北京烘焙    │ │  │                                     │    │ │
│    车间       │ │  │  [📎 上传参考图]                     │    │ │
│    v2 · 06/05 │ │  └─────────────────────────────────────┘    │ │
│                │ │  [生成方案]                                 │ │
│                │ │                                             │ │
├────────────────┴─────────────────────────────────────────────────┤
</zqjforward:nested-code>

### 布局说明

| 区域 | 内容 | 说明 |
|---|---|---|
| **顶栏** | Logo、当前项目名、用户头像、设置/退出 | 固定顶部 |
| **左侧栏（~280px）** | 项目列表（按时间排序）、当前项目设计边界标签、新建项目按钮 | 可折叠，选中项目高亮 |
| **右侧主区域（上半）** | 对话流：用户需求 + AI 回复 + Canvas 预览 + 版本号 + 操作按钮 | 滚动查看历史对话 |
| **右侧主区域（下半）** | 输入框 + 附件上传 + 生成按钮 | 固定在底部 |

### 左侧栏交互细节

- **项目列表**：按最后活跃时间倒序排列
- **当前选中项目**：高亮显示，左侧圆点实心（●）
- **项目卡片信息**：项目名 + 当前版本号（如 v3）+ 最后活跃时间（今天/昨天/日期）
- **设计边界标签**：选中项目后，在项目名下方显示该项目的已选边界（小标签形式）
- **新建项目**：顶部按钮，点击弹出新建项目对话框（含边界多选 + 参考项目选择）

### 右侧对话区交互细节

- **对话气泡**：用户消息靠右（蓝色），AI 消息靠左（灰色）
- **Canvas 预览**：嵌入在 AI 回复消息中，支持缩放/拖拽
- **版本信息**：每条 AI 生成回复下方标注版本号和时间戳
- **操作按钮**：`在 CAD 中打开` 和 `版本列表` 紧跟在版本信息后面
- **输入框**：固定在底部，支持多行文本 + 上传参考图，回车发送

### 版本列表弹窗

点击 `版本列表` 后，从右侧滑出抽屉面板：

```
┌─────────────────────────────────┐
│  版本历史                    ✕  │
│                                 │
│  ● v3 — 田字布局                 │
│     2026-06-08 15:20 · 当前     │
│     [回滚到此处]                 │
│  │                              │
│  ○ v2 — +冷藏库                  │
│     2026-06-08 11:05            │
│     [回滚到此处]                 │
│  │                              │
│  ○ v1 — 初始方案                  │
│     2026-06-08 09:30            │
│     [回滚到此处]                 │
│                                 │
│  版本树：v1 → v2 → v3            │
└─────────────────────────────────┘
```

---

## 整体配色方案

参考豆包暗色主题，整体走**深色专业风**，沉稳克制，适合长时间设计工作。

### 色板

```
┌─────────────────────────────────────────────────────────────┐
│  主背景        #1B1C1E    ■■■■■■■■■■■■■■■■■■■■■■■■■  │
│  侧边栏背景    #212327    ■■■■■■■■■■■■■■■■■■■■■■■■■  │
│  卡片/气泡底   #2A2B2F    ■■■■■■■■■■■■■■■■■■■■■■■■■  │
│  悬浮态        #313338    ■■■■■■■■■■■■■■■■■■■■■■■■■  │
│  边框/分割线   #3A3B3F    ─────────────────────────────  │
│                                                             │
│  品牌主色      #4F6EF7    ■■■■■■ 蓝色（按钮、选中态）    │
│  品牌辅色      #7B8CFF    ■■■■■■ 浅蓝（渐变、装饰）      │
│  成功/确认     #34C759    ■■■■■■ 绿色（版本生成成功）    │
│  警告/提示     #FF9F0A    ■■■■■■ 橙色（回滚确认）        │
│                                                             │
│  主文字        #E5E5EA    ■■■■■■■■■■■■■■■■■■■■■■■■■  │
│  次要文字      #98989E    ■■■■■■■■■■■■■■■■■■■■        │
│  辅助/占位     #636368    ■■■■■■■■■■■■■■                │
│  白色文字      #FFFFFF    ■■■■■■■■■■■■■■■■■■■■■■■■■  │
└─────────────────────────────────────────────────────────────┘
```

### 配色映射

| 界面元素 | 色值 | 说明 |
|---|---|---|
| 页面底色 | `#1B1C1E` | 右侧对话区背景 |
| 左侧栏底色 | `#212327` | 与主背景微妙区分 |
| 左侧栏选中项 | `#2A2B2F` | 当前项目高亮 |
| 顶栏底色 | `#212327` | 与侧边栏统一 |
| 用户消息气泡 | `#4F6EF7` | 品牌蓝，白色文字 |
| AI 消息气泡 | `#2A2B2F` | 深灰底，浅色文字 |
| 输入框底色 | `#2A2B2F` | 聚焦时边框变蓝 |
| 版本标签 | `#2A2B2F` 底 + `#98989E` 文字 | 小标签样式 |
| Canvas 预览区 | `#1B1C1E` + `#3A3B3F` 边框 | 与背景融合 |
| 按钮主色 | `#4F6EF7` | 生成方案、在 CAD 中打开 |
| 按钮次色 | `#313338` + `#E5E5EA` 文字 | 版本列表等次要操作 |
| 边界标签 | `#2A2B2F` 底 + `#4F6EF7` 左边框 | 侧边栏中显示已选边界 |
| 分隔线 | `#3A3B3F` | 列表项之间、对话之间 |
| 成功状态 | `#34C759` | 版本生成完成指示 |
| 回滚确认 | `#FF9F0A` | 回滚操作警告色 |

### 字体与排版

| 元素 | 规格 |
|---|---|
| 全局字体 | `-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif` |
| 项目名称 | 14px / `#E5E5EA` / 加粗 |
| 版本号标签 | 12px / `#98989E` |
| 对话内容 | 14px / `#E5E5EA` / 行高 1.6 |
| 输入框文字 | 14px / `#E5E5EA` |
| 时间戳 | 12px / `#636368` |
| 代码/JSON | 13px / `Menlo, Monaco, monospace` / `#7B8CFF` |

### 圆角与间距

| 元素 | 规格 |
|---|---|
| 消息气泡圆角 | 12px（用户），12px（AI） |
| 按钮圆角 | 8px |
| 输入框圆角 | 12px |
| 卡片/面板圆角 | 8px |
| 项目列表项间距 | 4px |
| 对话气泡间距 | 16px |
| 左侧栏宽度 | 280px |
| Canvas 预览圆角 | 8px |

### 与豆包的对标

| 豆包特性 | CAD 方案对应 |
|---|---|
| 左侧对话列表 | 左侧项目历史列表（含版本号） |
| 右侧对话窗口 | 右侧对话 + Canvas 预览 + 版本操作 |
| 新建对话 | 新建项目（含边界多选 + 参考选择） |
| 消息气泡 | 用户需求 / AI 方案回复 |
| 对话内工具调用 | Canvas 预览替换、CAD 打开按钮 |

预览图由前端 Canvas 直接渲染 JSON 数据，不走后端生成图片的流程。

**基础交互**：
- 缩放：滚轮/手势缩放画布
- 平移：按住空白处拖动画布
- 点击选中：点击建筑/房间高亮显示

**元素编辑交互**：
- 位置拖动：选中建筑/房间后，拖拽移动到新的位置，拖动结束后同步更新 JSON 中的坐标字段
- 大小缩放：选中元素后显示 8 个控制手柄，拖动手柄调整宽高，缩放结束后同步更新 JSON 中的尺寸字段
- 编辑反馈：拖动/缩放时实时显示尺寸标注线，松手后数值自动更新

**与 AI 的联动**：
- 设计师在 Canvas 上拖拽调整后，前端生成修改指令发给 AI
- AI 基于修改后的 JSON 继续精炼，保持上下文一致

**预览与 CAD 的差异说明**：
> Canvas 预览图为轻量级示意，图层、线型、标注样式等细节与 AutoCAD 出图存在差异，**请以 AutoCAD 中显示的图纸为准**。

**优势**：
- 零后端开销（不需要 ezdxf / matplotlib）
- 交互体验好（拖拽、缩放、实时反馈）
- 设计师可直接在预览图上微调，降低重新描述需求的成本
- JSON 变更即时反映，无需刷新

---

## 关键优势

| 特性 | 优势 |
|---|---|
| **图纸质量** | pywin32 直控 AutoCAD，与手工绘制完全一致（不是 DXF 转换） |
| **行业合规** | 预设设计边界规则，AI 在约束范围内出图，不会漏掉必备功能区 |
| **并发能力** | 每个设计师用自己电脑的 AutoCAD，互不排队 |
| **知识复用** | 参考项目机制，成熟方案可复用，节省 Token 并加速出图 |
| **部署成本** | 只需一台 AI 服务器（低配即可），不需要 CAD 服务器 |
| **模型灵活** | 支持云端 API / 本地大模型热切换，不绑定单一模型厂商 |
| **权限清晰** | 管理员分配账号，设计师只看自己的项目，可标记参考 |
| **开发环境** | 可以在 macOS 上开发 AI 部分，桥梁服务在 Windows 上调试 |
| **设计师门槛** | 不改变 CAD 使用习惯，多了一个网页按钮 |
| **扩展性** | 几十个设计师直接可用，加人无压力 |

---

## 部署要求

| 组件 | 硬件 | 软件 |
|---|---|---|
| AI 服务器 | 任意服务器（云/内网都可） | Python 3.10+ |
| 设计师电脑 | 已有安装 AutoCAD 即可 | AutoCAD（必需）；桥梁服务（可选，不装也能下载 DXF 用） |

---

## 开发计划

### 输出策略

| 方式 | 质量 | 依赖 | 用途 |
|------|------|------|------|
| **下载 DXF** | ⭐⭐⭐ 基础 | 仅 Auto CAD | 快速预览、双击打开、存档 |
| **在 CAD 中打开** | ⭐⭐⭐⭐⭐ 精确 | 桥梁服务 + AutoCAD | 正式出图，线型/图层/标注全部到位 |

**工作流**：预览满意 → 下载 DXF 双击看效果 / 需要精确出图则点"在 CAD 中打开"走桥梁服务。

---

### Phase 1：AI 服务器（Python FastAPI + SQLite）

**目标**：搭建后端服务器，提供完整 API，集成 DeepSeek + DXF 导出。

#### 1.1 项目初始化
- [ ] 项目结构搭建 (`server/`)
- [ ] 依赖管理 (`requirements.txt` / `pyproject.toml`)
- [ ] SQLAlchemy + SQLite 数据库初始化
- [ ] Alembic 迁移管理
- [ ] 配置文件（环境变量 / `.env`）

#### 1.2 用户认证系统
- [ ] `users` 表模型 + 迁移
- [ ] 密码哈希（passlib / bcrypt）
- [ ] JWT Token 签发 + 验证
- [ ] `POST /api/auth/login` — 登录
- [ ] `POST /api/auth/refresh` — 刷新 Token
- [ ] `GET /api/auth/me` — 当前用户信息
- [ ] 管理员初始账号（命令行创建）

#### 1.3 管理员 — 用户管理
- [ ] 用户列表 `GET /api/admin/users`
- [ ] 创建用户 `POST /api/admin/users`
- [ ] 修改用户 `PUT /api/admin/users/{id}`
- [ ] 删除/禁用用户 `DELETE /api/admin/users/{id}`
- [ ] 多设计师隔离（每人只看自己项目）

#### 1.4 管理员 — 设计边界 CRUD
- [ ] `boundaries` 表模型 + 迁移
- [ ] 边界列表（所有人可读）`GET /api/boundaries`
- [ ] 创建 `POST /api/admin/boundaries`
- [ ] 更新 `PUT /api/admin/boundaries/{id}`
- [ ] 删除 `DELETE /api/admin/boundaries/{id}`
- [ ] 详情 `GET /api/admin/boundaries/{id}`
- [ ] **核心约束**：`rules_json` 自由格式，后端不解析不校验（零硬编码）

#### 1.5 管理员 — 大模型配置
- [ ] `llm_config` 表模型 + 迁移
- [ ] 获取配置（脱敏）`GET /api/admin/llm-config`
- [ ] 更新配置 `PUT /api/admin/llm-config`
- [ ] 支持 Provider：DeepSeek V4 / V3 / OpenAI 兼容 / Ollama 本地
- [ ] 热切换（改配置立即生效，不重启）
- [ ] 连接测试 `POST /api/admin/llm-config/test`
- [ ] 切换日志 `llm_config_log` 表

#### 1.6 DeepSeek API 集成 + AI 生成
- [ ] DeepSeek API 客户端封装
- [ ] System Prompt 构建器（遍历边界 JSON + 参考项目注入 + 历史上下文）
- [ ] `POST /api/design/generate` — 设计生成
- [ ] `POST /api/design/refine` — 追加精炼（继承上下文，增量生成）
- [ ] Token 消耗统计

#### 1.7 项目管理
- [ ] `projects` + `project_boundaries` 表模型
- [ ] 项目列表 `GET /api/projects`（仅自己的）
- [ ] 创建 `POST /api/projects`（边界多选 + 参考项目可选）
- [ ] 删除 `DELETE /api/projects/{id}`（级联删除，仅创建者/管理员）
- [ ] 参考开关 `PUT /api/projects/{id}/allow-reference`
- [ ] 参考项目列表 `GET /api/reference-projects`

#### 1.8 会话与版本管理
- [ ] `sessions` + `versions` + `messages` 表模型
- [ ] 会话列表 `GET /api/projects/{project_id}/sessions`
- [ ] 创建会话 `POST /api/projects/{project_id}/sessions`
- [ ] 会话详情（含消息+版本）`GET /api/sessions/{id}`
- [ ] 版本详情 `GET /api/versions/{id}`
- [ ] 版本回滚 `POST /api/versions/{id}/restore`（分支，不覆盖）
- [ ] 版本对比 `GET /api/versions/{v1}/diff/{v2}`

#### 1.9 DXF 导出引擎
- [ ] `ezdxf` 集成
- [ ] JSON → DXF 转换：墙体（多段线 + 图层）、房间（区域 + 文字）、门窗、尺寸标注
- [ ] DXF 下载 API `GET /api/versions/{id}/download-dxf`
- [ ] 前端新增 `[下载 DXF]` 按钮

#### 1.10 前端对接
- [ ] 所有目前硬编码假数据改为 API 调用
- [ ] 设计边界、参考项目从服务器动态拉取
- [ ] 下载 DXF 流程对接

---

### Phase 2：桥梁服务（Python Flask + pywin32）

**目标**：设计师本机可选服务，一键精确绘制到 AutoCAD。

- [ ] Flask 本地服务 `localhost:45678`
- [ ] 从 AI 服务器拉取 JSON + Token 鉴权
- [ ] `GET /open-in-cad?id={version_id}` — 直绘 AutoCAD
- [ ] 墙体/房间/门窗/标注画图函数（精确线型、图层、颜色）
- [ ] 同时保存 `.dwg` 到桌面
- [ ] 设计师登录（输入服务器账号密码获取 Token）

---

### Phase 3：打包与部署

**目标**：交付可安装的生产环境。

- [ ] 桥梁服务 PyInstaller 打包为 `AI-CAD-Bridge.exe`
- [ ] 设计师双击安装（可选组件，不装也能用下载 DXF）
- [ ] AI 服务器部署到内网（任意 Linux / Windows 机器）
- [ ] Docker 一键部署（可选，提供 `Dockerfile` + `docker-compose.yml`，不强制）
- [ ] 管理员初始化手册（创建账号、配置设计边界、配置大模型）
- [ ] SQLite 数据备份策略

---

## 对比其他方案

| 方案 | 图纸质量 | 并发 | 是否需要 AutoCAD | 是否需要桥梁服务 |
|---|---|---|---|---|
| **本方案（桥梁 + DXF 双输出）** | ⭐⭐⭐⭐⭐ | 无限制 | 需要（双击 DXF 或桥梁直绘） | 可选（不装也能下载 DXF） |
| 桥梁服务单输出 | ⭐⭐⭐⭐⭐ | 无限制 | 需要 | 必须 |
| ezdxf 纯 DXF | ⭐⭐⭐ | 无限制 | 不需要 | 不需要 |
| netDxf 纯 DXF（当前 .NET） | ⭐⭐ | 无限制 | 不需要 | 不需要 |
