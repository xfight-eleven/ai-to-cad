"""DeepSeek API 集成 — 设计生成 + 精炼。

★ 零硬编码：
- 设计边界 JSON 从数据库动态读取，原样注入 Prompt
- 不解析、不校验、不修改边界规则内容
- AI 上下文完全由管理员配置的边界 + 用户需求驱动
"""

import json
from typing import Optional

import httpx

from app.database import SessionLocal
from app.models import LlmConfig, Project, ProjectBoundary, Boundary, Version, Message, Session


def _get_active_config() -> Optional[dict]:
    """从数据库获取当前生效的大模型配置。"""
    db = SessionLocal()
    try:
        config = db.query(LlmConfig).filter(LlmConfig.is_active == True).first()
        if not config:
            return None

        from app.api.admin_llm_config import decrypt_api_key
        return {
            "provider": config.provider,
            "api_key": decrypt_api_key(config.api_key_encrypted),
            "api_base": config.api_base.rstrip("/"),
            "model_name": config.model_name,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "timeout_seconds": config.timeout_seconds,
        }
    finally:
        db.close()


def _build_system_prompt(project_id: str) -> str:
    """构建 System Prompt — 动态拼接边界规则。

    ★ 零硬编码：不做任何行业假设，不内置任何规则。
    所有约束均来自管理员在后台配置的设计边界。
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return "你是一个工业厂房 CAD 设计专家。"

        parts = []

        # 拼接设计边界（多个边界合并注入）
        pbs = db.query(ProjectBoundary).filter(ProjectBoundary.project_id == project_id).all()
        boundaries = []
        for pb in pbs:
            b = db.query(Boundary).filter(Boundary.id == pb.boundary_id).first()
            if b and b.is_active:
                boundaries.append(b)

        if boundaries:
            # ★ 选择了设计边界 → AI 是行业专家，受规则约束
            parts.append("你是工业厂房 CAD 设计专家。你必须在以下边界约束内进行设计。")
            parts.append(f"\n── 以下约束由管理员配置，请严格遵守 ──")
            parts.append(f"已选设计边界模板（共 {len(boundaries)} 项）：\n")
            for i, b in enumerate(boundaries, 1):
                parts.append(f"【边界 {i}：{b.name}】")
                parts.append(b.rules_json)
                parts.append("")
            parts.append("多个边界的规则需同时满足，如有冲突以排在前面的边界为准。")
        else:
            # ★ 未选择任何设计边界 → AI 是高级 CAD 制图员，不含设计职能
            parts.append("你是高级 CAD 制图员。你的唯一职责是将用户指令精确转化为图纸。")
            parts.append("你不是设计师——不要做任何设计判断，不要添加用户未提及的任何元素。")
            parts.append("用户说画什么你就画什么，用户说多大尺寸就画多大尺寸。")

        # 拼接参考项目（如有）
        if project.reference_project_id:
            ref = db.query(Project).filter(Project.id == project.reference_project_id).first()
            if ref:
                # 取参考项目的最新版本
                ref_version = db.query(Version).filter(
                    Version.session_id.in_(
                        db.query(Session.id).filter(Session.project_id == ref.id).subquery()
                    )
                ).order_by(Version.created_at.desc()).first()
                if ref_version:
                    parts.append(f"\n── 参考项目：{ref.title} ──")
                    try:
                        ref_json = json.loads(ref_version.design_json)
                        parts.append(json.dumps(ref_json, ensure_ascii=False, indent=2))
                    except json.JSONDecodeError:
                        parts.append(ref_version.design_json)
                    parts.append("请基于以上参考项目的布局逻辑进行适应性调整。")

        parts.append("""
## 输出要求
返回纯 JSON（不要用 markdown 代码块包裹）。
必须包含 "buildings" 字段（数组），buildings 中每个元素含 name 和 dimensions。

【区域划分】如用户要求划分区域/车间/分区，使用 "zones" 数组，每个 zone 格式如下：
{ "name": "区域名", "dimensions": {"width": 数字, "length": 数字}, "position": "top|bottom|left|right|center" }
zones 按 position 字段放置。上下分区纵向排列，左右分区横向排列。

【房间】如用户要求内部房间，使用 "rooms" 数组，每个 room 格式如下：
{ "name": "房间名", "width": 数字, "length": 数字, "x": 数字, "y": 数字 }

用户输入的尺寸数值必须体现在 dimensions 中，不得修改。
如果用户描述非矩形形状（如圆形），可添加 shape、radius 等字段自由表达。
不要自行添加任何用户未要求的内容。纯 JSON 输出。
""")
        return "\n".join(parts)
    finally:
        db.close()


def _build_messages(project_id: str, session_id: str, user_prompt: str) -> list:
    """构建对话消息列表。"""
    db = SessionLocal()
    try:
        system_prompt = _build_system_prompt(project_id)

        messages = [{"role": "system", "content": system_prompt}]

        # 追加历史对话（最多 20 轮）
        history = db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(Message.created_at).limit(40).all()

        for m in history:
            messages.append({"role": m.role, "content": m.content})

        # 当前用户需求
        messages.append({"role": "user", "content": user_prompt})
        return messages
    finally:
        db.close()


def call_deepseek(project_id: str, session_id: str, user_prompt: str) -> dict:
    """调用 DeepSeek API 生成设计方案。

    返回：
        dict: {"design_json": str, "description": str, "token_usage": int}
    """
    config = _get_active_config()
    if not config:
        raise RuntimeError("未配置大模型，请联系管理员在后台配置")

    messages = _build_messages(project_id, session_id, user_prompt)

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model_name"],
        "messages": messages,
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
    }

    with httpx.Client(timeout=config["timeout_seconds"], trust_env=False) as client:
        resp = client.post(
            f"{config['api_base']}/chat/completions",
            headers=headers,
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"DeepSeek API 调用失败: HTTP {resp.status_code} - {resp.text[:300]}")

    try:
        data = resp.json()
    except json.JSONDecodeError:
        raise RuntimeError(f"DeepSeek API 返回非 JSON 响应: {resp.text[:300]}")

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"DeepSeek API 返回空 choices: {json.dumps(data, ensure_ascii=False)[:300]}")

    content = choices[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})

    # 提取 JSON — 尝试多种解析策略
    content = content.strip()

    # 策略1：去掉 ```json ... ``` 包裹
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

    # 策略2：提取第一个 { 到最后一个 } 之间的 JSON
    if not content.startswith("{"):
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start:end+1]

    content = content.strip()

    # 解析 JSON
    try:
        design = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"DeepSeek 返回无法解析为 JSON。\n"
            f"原始内容前200字符: {content[:200]}\n"
            f"错误: {e}"
        )

    # 安全提取描述（兼容 project 字段为字符串或对象）
    project_info = design.get("project", {})
    if isinstance(project_info, str):
        try:
            project_info = json.loads(project_info)
        except Exception:
            project_info = {}
    description = design.get("description", "") or (project_info.get("name", "") if isinstance(project_info, dict) else str(project_info))

    return {
        "design_json": json.dumps(design, ensure_ascii=False),
        "description": description,
        "token_usage": usage.get("total_tokens", 0),
        "llm_provider": config["provider"],
        "llm_model": config["model_name"],
    }
