"""用户模型 — 设计师和管理员账号。"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(64), nullable=False)
    role = Column(String(16), nullable=False, default="designer")  # admin / designer
    status = Column(String(16), nullable=False, default="active")  # active / disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(64), nullable=True)

    # 关系
    projects = relationship("Project", back_populates="owner")
