"""Pydantic Schemas — 请求/响应数据模型。"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ── 用户 ──
class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)
    role: str = "designer"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


# ── 登录 ──
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── 设计边界（零硬编码）──
class BoundaryOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    rules_json: str  # 自由格式 JSON 字符串
    icon: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BoundaryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = None
    rules_json: str = "{}"  # 自由格式 JSON，系统不解析
    icon: Optional[str] = None
    sort_order: int = 0


class BoundaryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rules_json: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ── 大模型配置 ──
class LlmConfigOut(BaseModel):
    id: int
    provider: str
    api_base: str
    model_name: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    is_active: bool
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    # API Key 脱敏输出
    api_key_encrypted: str = ""

    class Config:
        from_attributes = True


class LlmConfigUpdate(BaseModel):
    provider: str = "deepseek"
    api_key: str = Field(min_length=1)
    api_base: str = "https://api.deepseek.com"
    model_name: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout_seconds: int = 120


class LlmConfigTest(BaseModel):
    provider: str
    api_key: str
    api_base: str
    model_name: str
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout_seconds: int = 120


class LlmTestResult(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None


# ── 项目 ──
class ProjectOut(BaseModel):
    id: str
    title: str
    owner_id: str
    reference_project_id: Optional[str] = None
    allow_reference: bool
    status: str
    created_at: datetime
    updated_at: datetime
    # 关联数据
    boundary_ids: list[str] = []
    session_count: int = 0

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    boundary_ids: list[str] = []  # 可空，空则 AI 自由发挥
    reference_project_id: Optional[str] = None


# ── 会话 ──
class SessionOut(BaseModel):
    id: str
    project_id: str
    title: Optional[str] = None
    created_at: datetime
    version_count: int = 0

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionDetail(BaseModel):
    session: SessionOut
    messages: list["MessageOut"] = []
    versions: list["VersionOut"] = []


# ── 版本 ──
class VersionOut(BaseModel):
    id: str
    session_id: str
    number: int
    parent_version_id: Optional[str] = None
    description: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    token_usage: Optional[int] = None
    dwg_file_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VersionDetail(BaseModel):
    id: str
    session_id: str
    number: int
    parent_version_id: Optional[str] = None
    design_json: str  # 完整 JSON
    description: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    token_usage: Optional[int] = None
    dwg_file_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VersionDiff(BaseModel):
    v1: VersionOut
    v2: VersionOut
    description_changed: bool
    design_diff: Optional[dict] = None


# ── 对话 ──
class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    version_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── 设计生成 ──
class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    session_id: str


class GenerateResponse(BaseModel):
    project_id: str
    session_id: str
    version_id: str
    version_number: int
    design_json: str
    description: str
    token_usage: int
