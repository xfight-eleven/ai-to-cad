"""配置管理 — 服务端地址、登录 Token 持久化。"""

import json
import os
from pathlib import Path
from typing import Optional


def _config_dir() -> Path:
    """跨平台配置目录：Windows → %APPDATA%, macOS → ~/Library/Application Support"""
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home()))
    else:
        base = str(Path.home() / "Library" / "Application Support")
    path = Path(base) / "hsxb-ai-cad"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_file() -> Path:
    return _config_dir() / "config.json"


DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:3000",
    "token": None,
    "username": None,
}


def load_config() -> dict:
    """加载配置，文件不存在时返回默认值。"""
    cf = _config_file()
    if cf.exists():
        try:
            with open(cf, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """保存配置到文件。"""
    with open(_config_file(), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_server_url() -> str:
    return load_config().get("server_url", DEFAULT_CONFIG["server_url"])


def get_token() -> Optional[str]:
    return load_config().get("token")


def save_credentials(server_url: str, token: str, username: str):
    config = load_config()
    config["server_url"] = server_url
    config["token"] = token
    config["username"] = username
    save_config(config)


def clear_credentials():
    config = load_config()
    config["token"] = None
    config["username"] = None
    save_config(config)
