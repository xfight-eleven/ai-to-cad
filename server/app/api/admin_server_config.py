"""管理员 — 服务器配置 API。

配置项：
- server_ip: 服务端绑定 IP（默认 0.0.0.0）
- server_port: 服务端监听端口（默认 3000）
- client_default_server: 客户端默认连接地址（如 http://192.168.10.xxx:3000）
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from datetime import datetime

from app.database import get_db
from app.models import User, ServerConfig
from app.dependencies import require_admin

router = APIRouter(prefix="/api/admin/server-config", tags=["管理员-服务器配置"])

DEFAULTS = {
    "server_ip": "0.0.0.0",
    "server_port": "3000",
    "client_default_server": "http://127.0.0.1:3000",
}


def _ensure_defaults(db: DbSession):
    """确保默认配置项存在。"""
    for key, default_val in DEFAULTS.items():
        if not db.query(ServerConfig).filter(ServerConfig.key == key).first():
            db.add(ServerConfig(key=key, value=default_val))
    db.commit()


@router.get("")
def get_server_config(
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """获取所有服务器配置。"""
    _ensure_defaults(db)
    configs = db.query(ServerConfig).all()
    result = {c.key: c.value for c in configs}
    return {
        "config": result,
        "defaults": dict(DEFAULTS),
    }


@router.put("")
def update_server_config(
    data: dict,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """更新服务器配置（支持批量更新）。

    请求体示例：
    {
        "server_ip": "0.0.0.0",
        "server_port": "8080",
        "client_default_server": "http://192.168.10.100:8080"
    }
    """
    _ensure_defaults(db)
    updated = []
    for key, value in data.items():
        config = db.query(ServerConfig).filter(ServerConfig.key == key).first()
        if config:
            config.value = str(value)
            config.updated_at = datetime.utcnow()
            updated.append(key)
        else:
            db.add(ServerConfig(key=key, value=str(value)))
            updated.append(key)
    db.commit()

    all_configs = db.query(ServerConfig).all()
    result = {c.key: c.value for c in all_configs}
    return {"message": f"已更新: {', '.join(updated)}", "config": result}
