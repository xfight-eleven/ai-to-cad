"""公共边界 API — 所有登录用户可读。"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User, Boundary
from app.schemas import BoundaryOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/boundaries", tags=["设计边界"])


@router.get("", response_model=List[BoundaryOut])
def list_active_boundaries(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """所有激活可用的设计边界（所有人可读）。"""
    boundaries = db.query(Boundary).filter(
        Boundary.is_active == True
    ).order_by(Boundary.sort_order, Boundary.name).all()
    return [BoundaryOut.model_validate(b) for b in boundaries]
