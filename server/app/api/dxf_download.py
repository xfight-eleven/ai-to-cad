"""DXF 下载 API — JSON 设计数据 → .dxf 文件下载。"""

import io
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User, Version, Session as SessionModel
from app.dependencies import get_current_user
from app.services.dxf_service import json_to_dxf

router = APIRouter(prefix="/api/versions", tags=["DXF 下载"])


@router.get("/{version_id}/download-dxf")
def download_dxf(version_id: str, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """下载版本的 DXF 文件 — 双击可在 AutoCAD 中直接打开。"""
    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    session = db.query(SessionModel).filter(SessionModel.id == version.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    project = session.project
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")

    try:
        dxf_bytes = json_to_dxf(version.design_json)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"DXF 生成失败: {str(e)}")

    # 文件名仅保留 ASCII 字符（避免 latin-1 编码问题），中文用 URL 编码
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', project.title)
    ascii_name = f"{safe_name}_v{version.number}.dxf"
    # RFC 5987 支持中文文件名
    encoded_name = quote(f"{project.title}_v{version.number}.dxf", encoding="utf-8")

    return Response(
        content=dxf_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}",
        },
    )
