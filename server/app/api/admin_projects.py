"""管理员 — 项目记录查询 API。

可查看所有用户的项目、对话记录、版本图纸。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User, Project, Session, Version, Message
from app.dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["管理员-项目记录"])


@router.get("/projects")
def list_all_projects(
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
    user_id: str = Query(None, description="按用户筛选"),
):
    """列出所有用户的项目（含所有者信息）。"""
    q = db.query(Project).order_by(Project.updated_at.desc())
    if user_id:
        q = q.filter(Project.owner_id == user_id)

    result = []
    for p in q.all():
        owner = db.query(User).filter(User.id == p.owner_id).first()
        session_count = db.query(Session).filter(Session.project_id == p.id).count()
        result.append({
            "id": p.id,
            "title": p.title,
            "owner_id": p.owner_id,
            "owner_name": owner.display_name if owner else "未知",
            "owner_username": owner.username if owner else "未知",
            "session_count": session_count,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
    return result


@router.get("/projects/{project_id}/sessions")
def list_project_sessions(
    project_id: str,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """列出项目的所有会话。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "项目不存在")

    sessions = db.query(Session).filter(
        Session.project_id == project_id
    ).order_by(Session.created_at).all()

    result = []
    for s in sessions:
        vcount = db.query(Version).filter(Version.session_id == s.id).count()
        mcount = db.query(Message).filter(Message.session_id == s.id).count()
        # 获取最后一条消息内容
        last_msg = db.query(Message).filter(
            Message.session_id == s.id
        ).order_by(Message.created_at.desc()).first()

        result.append({
            "id": s.id,
            "title": s.title,
            "version_count": vcount,
            "message_count": mcount,
            "last_message": last_msg.content[:100] if last_msg else "",
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result


@router.get("/sessions/{session_id}/detail")
def get_session_detail_admin(
    session_id: str,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """管理员查看会话详情（对话 + 版本 + DWG）。"""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(404, "会话不存在")

    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()

    versions = db.query(Version).filter(
        Version.session_id == session_id
    ).order_by(Version.number).all()

    from app.config import DWG_DIR
    import os

    project = db.query(Project).filter(Project.id == session.project_id).first()

    return {
        "session": {
            "id": session.id,
            "title": session.title,
            "project_id": session.project_id,
            "project_title": project.title if project else "",
            "created_at": session.created_at.isoformat() if session.created_at else None,
        },
        "messages": [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "version_id": m.version_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in messages],
        "versions": [{
            "id": v.id,
            "number": v.number,
            "description": v.description or "",
            "parent_version_id": v.parent_version_id,
            "dwg_file_path": v.dwg_file_path,
            "token_usage": v.token_usage,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        } for v in versions],
    }
