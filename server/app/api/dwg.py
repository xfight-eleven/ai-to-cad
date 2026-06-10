"""DWG 文件管理 — 上传/下载/历史扫描。

设计原则：
- 项目/会话/版本删除时，数据库记录可清，文件系统 DWG 文件永久保留。
- 通过文件系统扫描可找回已删除版本对应的 DWG。
"""

import os
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc

from app.database import get_db
from app.models import User, Project, Session, Version
from app.config import DWG_DIR
from app.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["DWG管理"])


def _get_dwg_path(project_id: str, session_id: str, version_id: str, version_number: int = 0) -> Path:
    """构建 DWG 文件存储路径：dwg/{project_id}/{session_id}/v{number}-{version_id}.dwg"""
    dir_path = DWG_DIR / project_id / session_id
    dir_path.mkdir(parents=True, exist_ok=True)
    vnum = version_number if version_number else 0
    return dir_path / f"v{vnum}-{version_id}.dwg"


def _verify_project(project_id: str, user: User, db: DbSession) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")
    return project


# ── 上传 ──

@router.put("/versions/{version_id}/dwg")
async def upload_version_dwg(
    version_id: str,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """上传某版本的 DWG 文件到服务器。"""
    if not file.filename or not file.filename.lower().endswith(".dwg"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 .dwg 文件")

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    # 验证归属
    session = db.query(Session).filter(Session.id == version.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    _verify_project(session.project_id, user, db)

    # 写入文件
    dwg_path = _get_dwg_path(session.project_id, session.id, version_id, version.number)
    content = await file.read()
    dwg_path.write_bytes(content)

    # 记录路径到数据库
    version.dwg_file_path = str(dwg_path.relative_to(DWG_DIR.parent))
    db.commit()

    return {
        "message": "DWG 已上传",
        "version_id": version_id,
        "file_path": version.dwg_file_path,
        "file_size": len(content),
    }


# ── 下载 ──

@router.get("/versions/{version_id}/dwg")
def download_version_dwg(
    version_id: str,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """下载某版本的 DWG 文件。"""
    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    session = db.query(Session).filter(Session.id == version.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    _verify_project(session.project_id, user, db)

    # 优先从数据库路径读取
    if version.dwg_file_path:
        file_path = DWG_DIR.parent / version.dwg_file_path
        if file_path.exists():
            return FileResponse(str(file_path), filename=f"v{version.number}-{version.id[:8]}.dwg")

    # 回退到按命名规则查找
    dwg_path = _get_dwg_path(session.project_id, session.id, version_id, version.number)
    if dwg_path.exists():
        return FileResponse(str(dwg_path), filename=f"v{version.number}-{version.id[:8]}.dwg")

    raise HTTPException(status.HTTP_404_NOT_FOUND, "该版本尚未同步 DWG 文件")


# ── 项目下所有 DWG 扫描（含已删除版本） ──

@router.get("/projects/{project_id}/dwgs")
def list_project_dwgs(
    project_id: str,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """扫描项目下所有存在的 DWG 文件（包括已删除版本的文件）。"""
    _verify_project(project_id, user, db)

    project_dir = DWG_DIR / project_id
    if not project_dir.exists():
        return {"project_id": project_id, "dwgs": []}

    result = []
    for session_dir in sorted(project_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        for dwg_file in sorted(session_dir.glob("*.dwg")):
            stat = dwg_file.stat()
            # 从文件名解析版本号和版本ID: v{number}-{version_id}.dwg
            name = dwg_file.stem  # e.g. "v3-f81f697b-a1dd-49a7-8ec5-2ae575effa9a"
            parts = name.split("-", 1)  # ["v3", "f81f697b-..."]
            version_number = int(parts[0][1:]) if parts[0].startswith("v") else 0
            version_id = parts[1] if len(parts) > 1 else ""

            # 检查数据库里是否还有这个版本
            db_exists = db.query(Version).filter(Version.id == version_id).first() is not None

            result.append({
                "file_name": dwg_file.name,
                "file_path": str(dwg_file.relative_to(DWG_DIR.parent)),
                "file_size": stat.st_size,
                "file_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "session_id": session_dir.name,
                "version_number": version_number,
                "version_id": version_id,
                "db_record_exists": db_exists,  # True=活跃, False=已删除
            })

    return {"project_id": project_id, "dwgs": result}

@router.get("/versions/{version_id}/dwg/download")
def download_version_dwg_by_token(
    version_id: str,
    token: str = None,
    db: DbSession = Depends(get_db),
):
    """通过 token query 参数下载 DWG（用于 <a href> 链接）。"""
    from app.services.auth_service import verify_token
    from app.models import User

    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 token")
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token 无效")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    session = db.query(Session).filter(Session.id == version.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    _verify_project(session.project_id, user, db)

    # 优先从数据库路径读取
    if version.dwg_file_path:
        file_path = DWG_DIR.parent / version.dwg_file_path
        if file_path.exists():
            return FileResponse(str(file_path), filename=f"v{version.number}-{version.id[:8]}.dwg")

    dwg_path = _get_dwg_path(session.project_id, session.id, version_id, version.number)
    if dwg_path.exists():
        return FileResponse(str(dwg_path), filename=f"v{version.number}-{version.id[:8]}.dwg")

    raise HTTPException(status.HTTP_404_NOT_FOUND, "该版本尚未同步 DWG 文件")
