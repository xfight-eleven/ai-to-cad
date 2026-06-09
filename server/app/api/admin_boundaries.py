"""管理员 — 设计边界 API。

★ 零硬编码核心：
- rules_json 为自由格式 JSON 字符串，系统不解析、不校验、不修改
- 系统只是一个容器，管理员配置什么就存储什么
- 代码层面不做任何设计假设
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User, Boundary
from app.schemas import BoundaryOut, BoundaryCreate, BoundaryUpdate
from app.dependencies import require_admin

router = APIRouter(prefix="/api/admin/boundaries", tags=["管理员-设计边界"])


@router.get("", response_model=List[BoundaryOut])
def list_boundaries(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """所有设计边界列表（含未激活）。"""
    boundaries = db.query(Boundary).order_by(Boundary.sort_order, Boundary.name).all()
    return [BoundaryOut.model_validate(b) for b in boundaries]


@router.get("/{boundary_id}", response_model=BoundaryOut)
def get_boundary(boundary_id: str, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """边界详情（含完整 rules_json）。"""
    b = db.query(Boundary).filter(Boundary.id == boundary_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "边界不存在")
    return BoundaryOut.model_validate(b)


@router.post("", response_model=BoundaryOut, status_code=status.HTTP_201_CREATED)
def create_boundary(req: BoundaryCreate, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """创建设计边界。

    rules_json 为自由格式 JSON，后端不做任何字段校验。
    管理员写什么，AI 就收到什么——零硬编码。
    """
    existing = db.query(Boundary).filter(Boundary.name == req.name).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "边界名称已存在")

    boundary = Boundary(
        name=req.name,
        description=req.description,
        rules_json=req.rules_json,
        icon=req.icon,
        sort_order=req.sort_order,
    )
    db.add(boundary)
    db.commit()
    db.refresh(boundary)
    return BoundaryOut.model_validate(boundary)


@router.put("/{boundary_id}", response_model=BoundaryOut)
def update_boundary(
    boundary_id: str,
    req: BoundaryUpdate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """更新设计边界。rules_json 可随时修改，无需修改代码。"""
    boundary = db.query(Boundary).filter(Boundary.id == boundary_id).first()
    if not boundary:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "边界不存在")

    if req.name is not None:
        boundary.name = req.name
    if req.description is not None:
        boundary.description = req.description
    if req.rules_json is not None:
        boundary.rules_json = req.rules_json  # 自由格式，不校验
    if req.icon is not None:
        boundary.icon = req.icon
    if req.sort_order is not None:
        boundary.sort_order = req.sort_order
    if req.is_active is not None:
        boundary.is_active = req.is_active

    db.commit()
    db.refresh(boundary)
    return BoundaryOut.model_validate(boundary)


@router.delete("/{boundary_id}")
def delete_boundary(boundary_id: str, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """删除设计边界。"""
    boundary = db.query(Boundary).filter(Boundary.id == boundary_id).first()
    if not boundary:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "边界不存在")
    db.delete(boundary)
    db.commit()
    return {"message": "边界已删除", "boundary_id": boundary_id}
