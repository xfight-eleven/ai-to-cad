"""服务器配置模型 — IP/端口等基础设置。"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime
from app.database import Base


class ServerConfig(Base):
    __tablename__ = "server_config"

    key = Column(String(64), primary_key=True)
    value = Column(String(256), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
