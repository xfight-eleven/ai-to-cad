"""预览图 API — 返回 SVG 矢量图。

支持 ?token=xxx 认证（img 标签用）。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User, Version, Session as SessionModel
from app.services.auth_service import decode_access_token
from app.services.preview_service import json_to_svg

router = APIRouter(prefix="/api/versions", tags=["预览图"])


def _get_user_from_request(token_param: Optional[str], auth_header: Optional[str], db) -> Optional[User]:
    token = token_param
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if token:
        payload = decode_access_token(token)
        if payload:
            return db.query(User).filter(User.id == payload.get("sub")).first()
    return None


@router.get("/{version_id}/preview")
def get_preview(
    version_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    w: int = Query(800),
    h: int = Query(500),
    db: DbSession = Depends(get_db),
):
    """获取版本的 SVG 预览图。"""
    auth_header = request.headers.get("Authorization", "")
    user = _get_user_from_request(token, auth_header, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未认证")

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "版本不存在")

    session = db.query(SessionModel).filter(SessionModel.id == version.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    if session.project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")

    try:
        svg = json_to_svg(version.design_json, width=w, height=h)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"预览生成失败: {str(e)}")

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
