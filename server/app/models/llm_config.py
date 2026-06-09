"""大模型配置模型 — 支持多 Provider 热切换。"""

from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime

from app.database import Base


class LlmConfig(Base):
    __tablename__ = "llm_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False)  # deepseek / openai_compatible / local
    api_key_encrypted = Column(Text, nullable=False)
    api_base = Column(String(256), nullable=False)
    model_name = Column(String(128), nullable=False)
    temperature = Column(Float, default=0.3)
    max_tokens = Column(Integer, default=8192)
    timeout_seconds = Column(Integer, default=120)
    is_active = Column(Boolean, default=True)  # 当前生效的配置
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(64), nullable=True)


class LlmConfigLog(Base):
    """大模型切换日志。"""

    __tablename__ = "llm_config_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    old_provider = Column(String(32), nullable=True)
    old_model = Column(String(128), nullable=True)
    new_provider = Column(String(32), nullable=False)
    new_model = Column(String(128), nullable=False)
    changed_by = Column(String(64), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)
