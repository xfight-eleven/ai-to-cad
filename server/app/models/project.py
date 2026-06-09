"""项目模型 — 含边界多对多关联和参考自引用。"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(256), nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    reference_project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    allow_reference = Column(Boolean, default=False)
    status = Column(String(16), default="active")  # active / deleted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    owner = relationship("User", back_populates="projects")
    boundaries = relationship("ProjectBoundary", back_populates="project", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="project", cascade="all, delete-orphan")

    # 参考项目自引用
    reference_project = relationship("Project", remote_side="Project.id", foreign_keys=[reference_project_id])


class ProjectBoundary(Base):
    """项目-边界 多对多关联表。"""

    __tablename__ = "project_boundaries"

    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    boundary_id = Column(String, ForeignKey("boundaries.id"), primary_key=True)

    # 关系
    project = relationship("Project", back_populates="boundaries")
    boundary = relationship("Boundary")
