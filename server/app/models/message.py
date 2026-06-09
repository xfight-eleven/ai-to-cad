"""对话记录模型 — 每条消息可选关联版本。"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    version_id = Column(String, ForeignKey("versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    session = relationship("Session", back_populates="messages")
    version = relationship("Version", back_populates="messages")
