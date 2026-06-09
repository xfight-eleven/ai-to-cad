"""FastAPI 依赖 — 用户认证 + 权限控制。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User
from app.services.auth_service import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DbSession = Depends(get_db),
) -> User:
    """验证 Token 并返回当前用户。"""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的 Token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员。"""
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅管理员可执行此操作")
    return current_user
