"""设计生成 API — 接收需求 → AI 生成 → 存储 → 返回。"""

from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.models import User, Project, Session, Version, Message
from app.schemas import GenerateRequest, GenerateResponse
from app.dependencies import get_current_user
from app.services.deepseek_service import call_deepseek

router = APIRouter(prefix="/api/design", tags=["设计生成"])


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """接收需求 → AI 生成方案 → 存储 → 返回。

    自动读取项目关联的设计边界和参考项目。
    """
    session = db.query(Session).filter(Session.id == req.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    project = db.query(Project).filter(Project.id == session.project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")

    try:
        result = call_deepseek(project.id, session.id, req.prompt)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))

    # 计算版本号
    max_ver = db.query(Version).filter(
        Version.session_id == session.id
    ).order_by(desc(Version.number)).first()
    version_number = (max_ver.number + 1) if max_ver else 1

    # 保存版本
    version = Version(
        session_id=session.id,
        number=version_number,
        design_json=result["design_json"],
        description=result["description"],
        llm_provider=result["llm_provider"],
        llm_model=result["llm_model"],
        token_usage=result["token_usage"],
    )
    db.add(version)
    db.flush()

    # 保存对话记录
    db.add(Message(session_id=session.id, role="user", content=req.prompt))
    db.add(Message(
        session_id=session.id,
        role="assistant",
        content=f"✅ v{version_number} 已生成：{result['description']}",
        version_id=version.id,
    ))

    # 更新项目时间
    db.query(Project).filter(Project.id == project.id).update(
        {"updated_at": __import__("datetime").datetime.utcnow()}
    )

    db.commit()
    db.refresh(version)

    return GenerateResponse(
        project_id=project.id,
        session_id=session.id,
        version_id=version.id,
        version_number=version.number,
        design_json=version.design_json,
        description=result["description"],
        token_usage=result["token_usage"],
    )


@router.post("/refine", response_model=GenerateResponse)
def refine(req: GenerateRequest, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """追加精炼——继承上下文，生成新版本。"""
    session = db.query(Session).filter(Session.id == req.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    project = db.query(Project).filter(Project.id == session.project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")

    try:
        result = call_deepseek(project.id, session.id, req.prompt)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))

    max_ver = db.query(Version).filter(
        Version.session_id == session.id
    ).order_by(desc(Version.number)).first()
    version_number = (max_ver.number + 1) if max_ver else 1

    version = Version(
        session_id=session.id,
        number=version_number,
        parent_version_id=max_ver.id if max_ver else None,
        design_json=result["design_json"],
        description=result["description"],
        llm_provider=result["llm_provider"],
        llm_model=result["llm_model"],
        token_usage=result["token_usage"],
    )
    db.add(version)
    db.flush()

    db.add(Message(session_id=session.id, role="user", content=req.prompt))
    db.add(Message(
        session_id=session.id,
        role="assistant",
        content=f"✅ v{version_number} 已生成：{result['description']}",
        version_id=version.id,
    ))

    db.query(Project).filter(Project.id == project.id).update(
        {"updated_at": __import__("datetime").datetime.utcnow()}
    )

    db.commit()
    db.refresh(version)

    return GenerateResponse(
        project_id=project.id,
        session_id=session.id,
        version_id=version.id,
        version_number=version.number,
        design_json=version.design_json,
        description=result["description"],
        token_usage=result["token_usage"],
    )
