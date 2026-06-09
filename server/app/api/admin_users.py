"""管理员 — 用户管理 API。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserCreate, UserUpdate
from app.dependencies import require_admin
from app.services.auth_service import hash_password

router = APIRouter(prefix="/api/admin/users", tags=["管理员-用户管理"])


@router.get("", response_model=List[UserOut])
def list_users(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """列出所有用户。"""
    users = db.query(User).order_by(User.created_at).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(req: UserCreate, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """创建新设计师账号。"""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        role=req.role,
        created_by=admin.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: str, req: UserUpdate, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """修改用户（角色、状态、密码等）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")

    if req.display_name is not None:
        user.display_name = req.display_name
    if req.password is not None:
        user.password_hash = hash_password(req.password)
    if req.role is not None:
        user.role = req.role
    if req.status is not None:
        user.status = req.status

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}")
def delete_user(user_id: str, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """删除用户（同时归档其项目数据）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")

    # 至少保留一个管理员
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.status == "active").count()
        if admin_count <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少保留一个管理员账号")

    db.delete(user)
    db.commit()
    return {"message": "用户已删除", "user_id": user_id}
