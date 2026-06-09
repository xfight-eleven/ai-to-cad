"""会话 & 版本管理 API。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc
from datetime import datetime

from app.database import get_db
from app.models import User, Project, Session, Version, Message
from app.schemas import (
    SessionOut, SessionCreate, SessionDetail,
    VersionOut, VersionDetail,
    MessageOut,
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["会话与版本"])


def _verify_project(project_id: str, user: User, db: DbSession) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")
    return project


def _verify_session(session_id: str, user: User, db: DbSession) -> Session:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    _verify_project(session.project_id, user, db)
    return session


# ── 会话管理 ──


@router.get("/projects/{project_id}/sessions", response_model=List[SessionOut])
def list_sessions(project_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """项目下的所有会话（含版本数）。"""
    _verify_project(project_id, user, db)
    sessions = db.query(Session).filter(
        Session.project_id == project_id
    ).order_by(Session.created_at).all()

    result = []
    for s in sessions:
        out = SessionOut.model_validate(s)
        out.version_count = db.query(Version).filter(Version.session_id == s.id).count()
        result.append(out)
    return result


@router.post("/projects/{project_id}/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    project_id: str,
    req: SessionCreate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """在项目下新建一个设计会话。"""
    _verify_project(project_id, user, db)
    session = Session(project_id=project_id, title=req.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionOut.model_validate(session)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(session_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """会话详情（含完整对话记录 + 版本列表）。"""
    session = _verify_session(session_id, user, db)

    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()

    versions = db.query(Version).filter(
        Version.session_id == session_id
    ).order_by(Version.number).all()

    out = SessionOut.model_validate(session)
    out.version_count = len(versions)

    return SessionDetail(
        session=out,
        messages=[MessageOut.model_validate(m) for m in messages],
        versions=[VersionOut.model_validate(v) for v in versions],
    )


# ── 版本管理 ──


@router.get("/versions/{version_id}", response_model=VersionDetail)
def get_version(version_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """版本详情（含完整的 design_json）。"""
    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")
    # 验证归属
    session = _verify_session(version.session_id, user, db)
    return VersionDetail.model_validate(version)


@router.post("/versions/{version_id}/restore", response_model=VersionDetail)
def restore_version(version_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """回滚到指定版本——不会删除中间版本，而是基于该版本创建一个新分支版本。"""
    old_version = db.query(Version).filter(Version.id == version_id).first()
    if not old_version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    # 验证归属
    _verify_session(old_version.session_id, user, db)

    # 计算新版本号
    max_num = db.query(Version).filter(
        Version.session_id == old_version.session_id
    ).order_by(desc(Version.number)).first()
    new_number = (max_num.number + 1) if max_num else 1

    # 创建分支版本（复制 design_json）
    new_version = Version(
        session_id=old_version.session_id,
        number=new_number,
        parent_version_id=version_id,
        design_json=old_version.design_json,  # 复制旧版本的 JSON
        description=f"从 v{old_version.number} 回滚创建",
        llm_provider=old_version.llm_provider,
        llm_model=old_version.llm_model,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return VersionDetail.model_validate(new_version)


@router.get("/versions/{v1_id}/diff/{v2_id}")
def diff_versions(
    v1_id: str, v2_id: str,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """版本对比——返回两个版本的结构化差异。"""
    v1 = db.query(Version).filter(Version.id == v1_id).first()
    v2 = db.query(Version).filter(Version.id == v2_id).first()
    if not v1 or not v2:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    _verify_session(v1.session_id, user, db)
    _verify_session(v2.session_id, user, db)

    import json

    try:
        d1 = json.loads(v1.design_json)
        d2 = json.loads(v2.design_json)
    except json.JSONDecodeError:
        d1, d2 = {}, {}

    # 简单差异分析
    diff = {
        "description_changed": v1.description != v2.description,
        "v1_description": v1.description,
        "v2_description": v2.description,
        "is_branch": v2.parent_version_id != v1_id,
    }

    # 建筑/房间数量变化
    buildings1 = d1.get("buildings", []) if isinstance(d1, dict) else []
    buildings2 = d2.get("buildings", []) if isinstance(d2, dict) else []
    diff["buildings_count"] = {"v1": len(buildings1), "v2": len(buildings2)}
    diff["rooms_count"] = {
        "v1": sum(len(b.get("rooms", [])) for b in buildings1),
        "v2": sum(len(b.get("rooms", [])) for b in buildings2),
    }

    return {
        "v1": VersionOut.model_validate(v1),
        "v2": VersionOut.model_validate(v2),
        "diff": diff,
    }
