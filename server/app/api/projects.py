"""项目管理 API — 项目 CRUD + 参考开关。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc

from app.database import get_db
from app.models import User, Project, ProjectBoundary, Session
from app.schemas import ProjectOut, ProjectCreate
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


def _verify_ownership(project_id: str, user: User, db: DbSession):
    """验证项目归属——仅创建者可访问。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问此项目")
    return project


@router.get("", response_model=List[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """当前用户的项目列表（仅自己创建的）。"""
    query = db.query(Project).filter(
        Project.owner_id == user.id,
        Project.status == "active",
    ).order_by(desc(Project.updated_at))

    result = []
    for p in query.all():
        out = ProjectOut.model_validate(p)
        out.boundary_ids = [pb.boundary_id for pb in p.boundaries]
        out.session_count = db.query(Session).filter(Session.project_id == p.id).count()
        result.append(out)
    return result


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(req: ProjectCreate, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """新建项目。

    - boundary_ids：设计边界 ID 列表（可多选，空列表则 AI 自由发挥）
    - reference_project_id：参考项目（可选）
    """
    project = Project(
        title=req.title,
        owner_id=user.id,
        reference_project_id=req.reference_project_id,
    )
    db.add(project)
    db.flush()

    # 建立设计边界多对多关联
    for bid in req.boundary_ids:
        db.add(ProjectBoundary(project_id=project.id, boundary_id=bid))

    # 自动创建默认会话
    session = Session(project_id=project.id, title="方案一")
    db.add(session)

    db.commit()
    db.refresh(project)

    out = ProjectOut.model_validate(project)
    out.boundary_ids = req.boundary_ids
    out.session_count = 1
    return out


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """项目详情。"""
    project = _verify_ownership(project_id, user, db)
    out = ProjectOut.model_validate(project)
    out.boundary_ids = [pb.boundary_id for pb in project.boundaries]
    out.session_count = db.query(Session).filter(Session.project_id == project.id).count()
    return out


@router.delete("/{project_id}")
def delete_project(project_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """删除项目——仅创建者和管理员可操作。

    级联删除所有会话、版本、对话记录。
    """
    project = _verify_ownership(project_id, user, db)
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权删除此项目")
    db.delete(project)  # cascade 自动清理关联数据
    db.commit()
    return {"message": "项目已删除", "project_id": project_id}


@router.put("/{project_id}/allow-reference", response_model=ProjectOut)
def toggle_reference(
    project_id: str,
    allow: bool,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """开关"允许参考"——仅项目所有者可操作。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权操作")

    project.allow_reference = allow
    db.commit()
    db.refresh(project)

    out = ProjectOut.model_validate(project)
    out.boundary_ids = [pb.boundary_id for pb in project.boundaries]
    return out
