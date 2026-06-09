"""管理员 — 大模型配置 API。

支持多 Provider 热切换：DeepSeek V4/V3、OpenAI 兼容、Ollama 本地。
修改后无需重启服务，新请求立即使用新配置。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from cryptography.fernet import Fernet

from app.config import SECRET_KEY
from app.database import get_db
from app.models import User, LlmConfig, LlmConfigLog
from app.schemas import LlmConfigOut, LlmConfigUpdate, LlmConfigTest, LlmTestResult
from app.dependencies import require_admin

router = APIRouter(prefix="/api/admin/llm-config", tags=["管理员-大模型配置"])


def _get_cipher() -> Fernet:
    """使用 SECRET_KEY 派生 Fernet 密钥。"""
    key = Fernet.generate_key() if len(SECRET_KEY) < 32 else None
    # 用 SECRET_KEY 的 SHA256 作为 Fernet 密钥
    import hashlib, base64
    raw = hashlib.sha256(SECRET_KEY.encode()).digest()
    f_key = base64.urlsafe_b64encode(raw)
    return Fernet(f_key)


def encrypt_api_key(key: str) -> str:
    return _get_cipher().encrypt(key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    try:
        return _get_cipher().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted  # fallback: 可能是明文


def mask_key(key: str) -> str:
    """脱敏显示 API Key：只显示前4后4。"""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("", response_model=Optional[LlmConfigOut])
def get_llm_config(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """获取当前大模型配置（API Key 脱敏）。"""
    config = db.query(LlmConfig).filter(LlmConfig.is_active == True).first()
    if not config:
        return None

    out = LlmConfigOut.model_validate(config)
    # 脱敏
    plain = decrypt_api_key(config.api_key_encrypted)
    out.api_key_encrypted = mask_key(plain)
    return out


@router.put("", response_model=LlmConfigOut)
def update_llm_config(
    req: LlmConfigUpdate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """更新大模型配置 — 热切换，新请求立即生效。"""
    old_config = db.query(LlmConfig).filter(LlmConfig.is_active == True).first()

    # 禁用旧的
    if old_config:
        old_config.is_active = False

    # 创建新的
    new_config = LlmConfig(
        provider=req.provider,
        api_key_encrypted=encrypt_api_key(req.api_key),
        api_base=req.api_base,
        model_name=req.model_name,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        timeout_seconds=req.timeout_seconds,
        is_active=True,
        updated_at=datetime.utcnow(),
        updated_by=admin.display_name,
    )
    db.add(new_config)
    db.flush()

    # 记录切换日志
    log = LlmConfigLog(
        old_provider=old_config.provider if old_config else None,
        old_model=old_config.model_name if old_config else None,
        new_provider=req.provider,
        new_model=req.model_name,
        changed_by=admin.display_name,
    )
    db.add(log)
    db.commit()
    db.refresh(new_config)

    out = LlmConfigOut.model_validate(new_config)
    out.api_key_encrypted = mask_key(req.api_key)
    return out


@router.post("/test", response_model=LlmTestResult)
def test_llm_connection(
    req: LlmConfigTest,
    admin: User = Depends(require_admin),
):
    """测试大模型连接连通性。"""
    import time
    import httpx

    headers = {
        "Authorization": f"Bearer {req.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": req.model_name,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
        "temperature": req.temperature,
    }

    start = time.time()
    try:
        resp = httpx.post(
            f"{req.api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=req.timeout_seconds,
            trust_env=False,
        )
        latency = int((time.time() - start) * 1000)

        if resp.status_code == 200:
            return LlmTestResult(success=True, latency_ms=latency)
        else:
            return LlmTestResult(
                success=False,
                latency_ms=latency,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
    except Exception as e:
        return LlmTestResult(success=False, error=str(e)[:200])

@router.post("/test-active", response_model=LlmTestResult)
def test_llm_active(
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """测试当前生效的大模型连接 —— 使用服务器存储的 API Key，无需用户输入。"""
    import time
    import httpx

    config = db.query(LlmConfig).filter(LlmConfig.is_active == True).first()
    if not config:
        return LlmTestResult(success=False, error="未配置大模型")

    api_key = decrypt_api_key(config.api_key_encrypted)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model_name,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
        "temperature": config.temperature,
    }

    start = time.time()
    try:
        resp = httpx.post(
            f"{config.api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=config.timeout_seconds,
            trust_env=False,
        )
        latency = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            return LlmTestResult(success=True, latency_ms=latency)
        else:
            return LlmTestResult(success=False, latency_ms=latency, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        return LlmTestResult(success=False, error=str(e)[:200])
