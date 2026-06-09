"""桥梁服务配置 — 从环境变量读取。"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# AI 服务器地址
AI_SERVER_URL = os.getenv("AI_SERVER_URL", "http://192.168.10.1:8080").rstrip("/")

# 本机桥梁服务端口
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "45678"))

# 设计师凭证（可选，留空则启动后手动输入）
DESIGNER_USERNAME = os.getenv("DESIGNER_USERNAME", "")
DESIGNER_PASSWORD = os.getenv("DESIGNER_PASSWORD", "")

# Token 存储
TOKEN_FILE = Path(__file__).resolve().parent.parent / ".token_cache"
