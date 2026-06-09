"""AI 服务器 API 客户端 — 登录 + 拉取 JSON 设计数据。"""

from typing import Optional, Tuple

import requests

from app.config import AI_SERVER_URL, TOKEN_FILE


class ServerClient:
    """与 AI 服务器通信的客户端。"""

    def __init__(self, server_url: str = AI_SERVER_URL):
        self.server_url = server_url.rstrip("/")
        self.token: Optional[str] = None
        self.user: Optional[dict] = None

    # ── Token 持久化 ──

    def load_token(self) -> bool:
        """从缓存文件加载 Token。"""
        if TOKEN_FILE.exists():
            try:
                data = TOKEN_FILE.read_text().strip()
                if data:
                    self.token = data
                    return True
            except OSError:
                pass
        return False

    def save_token(self):
        """保存 Token 到缓存文件。"""
        if self.token:
            TOKEN_FILE.write_text(self.token)

    def clear_token(self):
        """清除缓存的 Token。"""
        self.token = None
        self.user = None
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()

    # ── 认证 ──

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """登录 AI 服务器并获取 Token。

        Returns:
            (是否成功, 消息)
        """
        try:
            resp = requests.post(
                f"{self.server_url}/api/auth/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["access_token"]
                self.user = data["user"]
                self.save_token()
                return True, f"登录成功 — {self.user['display_name']}"
            else:
                detail = resp.json().get("detail", "未知错误")
                return False, f"登录失败: {detail}"
        except requests.ConnectionError:
            return False, f"无法连接到服务器: {self.server_url}"
        except Exception as e:
            return False, f"网络错误: {e}"

    def ensure_login(self) -> Tuple[bool, str]:
        """确保已登录，如有缓存 Token 则直接使用。"""
        if self.token:
            return True, "已登录"
        if self.load_token():
            return True, "已从缓存恢复登录"
        return False, "未登录"

    # ── 数据拉取 ──

    def get_version_json(self, version_id: str) -> Tuple[bool, str, Optional[dict]]:
        """从服务器拉取版本的完整 JSON 设计数据。

        Returns:
            (是否成功, 消息, 设计数据 dict)
        """
        ok, msg = self.ensure_login()
        if not ok:
            return False, msg, None

        try:
            resp = requests.get(
                f"{self.server_url}/api/versions/{version_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return True, "获取成功", resp.json()
            elif resp.status_code == 401:
                self.clear_token()
                return False, "Token 已过期，请重新登录", None
            else:
                return False, f"获取失败: {resp.json().get('detail', resp.text[:200])}", None
        except requests.ConnectionError:
            return False, f"无法连接到服务器: {self.server_url}", None
        except Exception as e:
            return False, f"网络错误: {e}", None

    def get_project_title(self, version_id: str) -> str:
        """通过版本 ID 获取项目标题（用于文件名）。"""
        ok, msg, data = self.get_version_json(version_id)
        if ok and data:
            return data.get("design_json", "{}")
        return "设计图"

    def verify_connection(self) -> Tuple[bool, str]:
        """测试与服务器的连接。"""
        try:
            resp = requests.get(f"{self.server_url}/api/health", timeout=5)
            if resp.status_code == 200:
                return True, f"服务器连接正常 ({self.server_url})"
            return False, f"服务器返回异常状态: {resp.status_code}"
        except requests.ConnectionError:
            return False, f"无法连接到服务器: {self.server_url}"
        except Exception as e:
            return False, f"连接测试失败: {e}"
