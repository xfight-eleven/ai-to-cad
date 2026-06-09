"""设计边界模型 — 零硬编码核心。

系统不关心 rules_json 的内容是什么——它只是一个 JSON 容器。
管理员配置什么，系统就原样传递什么，不做任何解析和校验。
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Boundary(Base):
    __tablename__ = "boundaries"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    # ★ 核心：自由格式 JSON 字符串，代码不解析、不校验、不修改
    rules_json = Column(Text, nullable=False, default="{}")
    icon = Column(String(64), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
