"""API 客户端 — 封装所有后端 HTTP 调用。"""

import json
import httpx
from typing import Optional


class APIClient:
    """与 AI CAD 服务器的 HTTP 客户端。"""

    def __init__(self, base_url: str = "http://127.0.0.1:3000"):
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._user: Optional[dict] = None

    # ── 认证 ──

    def login(self, username: str, password: str) -> dict:
        resp = httpx.post(f"{self.base_url}/api/auth/login", json={
            "username": username, "password": password
        }, trust_env=False)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "登录失败")
            raise RuntimeError(detail)
        data = resp.json()
        self._token = data["access_token"]
        self._user = data["user"]
        return self._user

    def get_me(self) -> dict:
        self._user = self._get("/api/auth/me")
        return self._user

    @property
    def token(self) -> Optional[str]:
        return self._token

    @property
    def user(self) -> Optional[dict]:
        return self._user

    # ── 项目管理 ──

    def list_projects(self) -> list:
        return self._get("/api/projects")

    def create_project(self, title: str, boundary_ids: list = None,
                       reference_project_id: str = None) -> dict:
        return self._post("/api/projects", {
            "title": title,
            "boundary_ids": boundary_ids or [],
            "reference_project_id": reference_project_id,
        })

    def delete_project(self, project_id: str) -> dict:
        return self._delete(f"/api/projects/{project_id}")

    # ── 边界 ──

    def list_boundaries(self) -> list:
        return self._get("/api/boundaries")

    def list_reference_projects(self) -> list:
        return self._get("/api/reference-projects")

    # ── 会话 ──

    def list_sessions(self, project_id: str) -> list:
        return self._get(f"/api/projects/{project_id}/sessions")

    def create_session(self, project_id: str, title: str) -> dict:
        return self._post(f"/api/projects/{project_id}/sessions", {"title": title})

    def get_session(self, session_id: str) -> dict:
        return self._get(f"/api/sessions/{session_id}")

    def rename_session(self, session_id: str, title: str) -> dict:
        return self._patch(f"/api/sessions/{session_id}", {"title": title})

    # ── 设计生成 ──

    def generate(self, session_id: str, prompt: str) -> dict:
        return self._post("/api/design/generate", {
            "session_id": session_id, "prompt": prompt
        })

    def refine(self, session_id: str, prompt: str) -> dict:
        return self._post("/api/design/refine", {
            "session_id": session_id, "prompt": prompt
        })

    # ── 版本 + DWG ──

    def get_version(self, version_id: str) -> dict:
        return self._get(f"/api/versions/{version_id}")

    def upload_dwg(self, version_id: str, file_path: str) -> dict:
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "application/octet-stream")}
            resp = httpx.put(
                f"{self.base_url}/api/versions/{version_id}/dwg",
                files=files,
                headers=self._headers(),
                trust_env=False,
            )
        if resp.status_code != 200:
            raise RuntimeError(resp.json().get("detail", "上传失败"))
        return resp.json()

    def download_dwg(self, version_id: str, save_path: str):
        resp = httpx.get(
            f"{self.base_url}/api/versions/{version_id}/dwg",
            headers=self._headers(),
            follow_redirects=True,
            trust_env=False,
        )
        if resp.status_code != 200:
            raise RuntimeError("下载失败")
        with open(save_path, "wb") as f:
            f.write(resp.content)

    # ── 健康检查 ──

    def health(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/health", trust_env=False)
            return resp.status_code == 200
        except Exception:
            return False

    # ── 内部方法 ──

    def _headers(self) -> dict:
        h = {}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _get(self, path: str) -> dict:
        resp = httpx.get(f"{self.base_url}{path}", headers=self._headers(), trust_env=False)
        if resp.status_code == 401:
            raise RuntimeError("登录已过期")
        if resp.status_code >= 400:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            raise RuntimeError(detail)
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        resp = httpx.post(f"{self.base_url}{path}", json=data,
                          headers=self._headers(), trust_env=False)
        if resp.status_code >= 400:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            raise RuntimeError(detail)
        return resp.json()

    def _patch(self, path: str, data: dict) -> dict:
        resp = httpx.patch(f"{self.base_url}{path}", json=data,
                           headers=self._headers(), trust_env=False)
        if resp.status_code >= 400:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            raise RuntimeError(detail)
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = httpx.delete(f"{self.base_url}{path}", headers=self._headers(), trust_env=False)
        if resp.status_code >= 400:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            raise RuntimeError(detail)
        return resp.json()
