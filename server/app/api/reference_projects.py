"""参考项目 API — 查看他人允许参考的项目。"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc

from app.database import get_db
from app.models import User, Project
from app.schemas import ProjectOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/reference-projects", tags=["参考项目"])


@router.get("", response_model=List[ProjectOut])
def list_reference_projects(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """可参考的项目列表（他人标记为允许参考的活跃项目）。"""
    projects = db.query(Project).filter(
        Project.allow_reference == True,
        Project.owner_id != user.id,
        Project.status == "active",
    ).order_by(desc(Project.updated_at)).all()

    result = []
    for p in projects:
        out = ProjectOut.model_validate(p)
        out.boundary_ids = [pb.boundary_id for pb in p.boundaries]
        result.append(out)
    return result
