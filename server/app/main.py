"""AI CAD 桥梁服务方案 — 服务器入口。

FastAPI 应用，自动注册所有路由、初始化数据库、创建初始管理员。
"""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import engine, SessionLocal, Base
from app.models import User
from app.services.auth_service import hash_password
from app.config import (
    INIT_ADMIN_USERNAME, INIT_ADMIN_PASSWORD, INIT_ADMIN_DISPLAY_NAME,
    DATA_DIR,
)

# ── 前端文件路径 ──
INDEX_HTML = Path(__file__).resolve().parent.parent.parent / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库 + 创建初始管理员。"""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == INIT_ADMIN_USERNAME).first()
        if not existing:
            admin = User(
                username=INIT_ADMIN_USERNAME,
                password_hash=hash_password(INIT_ADMIN_PASSWORD),
                display_name=INIT_ADMIN_DISPLAY_NAME,
                role="admin",
                created_by="system",
            )
            db.add(admin)
            db.commit()
            print(f"✅ 初始管理员已创建: {INIT_ADMIN_USERNAME}")
        else:
            print(f"ℹ️  管理员 {INIT_ADMIN_USERNAME} 已存在，跳过创建")
    finally:
        db.close()

    yield


app = FastAPI(
    title="AI CAD 桥梁服务方案",
    description="AI CAD 设计助手 — 后端 API 服务",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 静态文件 ──
STATIC_DIR = Path(__file__).resolve().parent.parent.parent
app.mount("/css", StaticFiles(directory=str(STATIC_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(STATIC_DIR / "js")), name="js")

# ── 注册 API 路由 ──
from app.api import auth
from app.api import admin_users
from app.api import admin_boundaries
from app.api import admin_llm_config
from app.api import admin_server_config
from app.api import admin_projects
from app.api import boundaries as boundaries_public
from app.api import projects
from app.api import reference_projects
from app.api import sessions
from app.api import design
from app.api import dxf_download
from app.api import preview
from app.api import dwg

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_boundaries.router)
app.include_router(admin_llm_config.router)
app.include_router(admin_server_config.router)
app.include_router(admin_projects.router)
app.include_router(boundaries_public.router)
app.include_router(projects.router)
app.include_router(reference_projects.router)
app.include_router(sessions.router)
app.include_router(design.router)
app.include_router(dxf_download.router)
app.include_router(preview.router)
app.include_router(dwg.router)


# ── 健康检查 ──
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── 前端页面 ──
@app.get("/")
def index():
    """项目首页。"""
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return {"error": "index.html 未找到"}
