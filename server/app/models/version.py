"""版本模型 — 不可删除，回滚创建分支。"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Version(Base):
    __tablename__ = "versions"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)  # v1, v2, v3...
    parent_version_id = Column(String, ForeignKey("versions.id"), nullable=True)
    # ★ 完整的 JSON 设计数据，每次独立存档
    design_json = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    llm_provider = Column(String(32), nullable=True)
    llm_model = Column(String(128), nullable=True)
    token_usage = Column(Integer, nullable=True)
    dwg_file_path = Column(String, nullable=True)  # 服务端 DWG 文件路径
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    session = relationship("Session", back_populates="versions")
    # 版本树自引用
    parent_version = relationship("Version", remote_side="Version.id", foreign_keys=[parent_version_id])
    messages = relationship("Message", back_populates="version")
