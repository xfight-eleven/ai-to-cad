"""应用配置 — 所有可配置项全部从环境变量读取，零硬编码。"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 路径 ──
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DWG_DIR = DATA_DIR / "dwg"
DWG_DIR.mkdir(exist_ok=True)

# ── 数据库 ──
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DATA_DIR}/cad_bridge.db",
)

# ── JWT ──
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# ── 服务器 ──
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# ── 初始管理员（首次启动自动创建） ──
INIT_ADMIN_USERNAME = os.getenv("INIT_ADMIN_USERNAME", "admin")
INIT_ADMIN_PASSWORD = os.getenv("INIT_ADMIN_PASSWORD", "admin123")
INIT_ADMIN_DISPLAY_NAME = os.getenv("INIT_ADMIN_DISPLAY_NAME", "管理员")
