"""设计生成 API — 接收需求 → AI 生成 → 存储 → 返回。"""

from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Query

import json
from app.database import get_db
from app.models import User, Project, Session, Version, Message
from app.schemas import GenerateRequest, GenerateResponse
from app.dependencies import get_current_user
from app.services.auth_service import verify_token
from app.services.deepseek_service import call_deepseek, stream_deepseek

router = APIRouter(prefix="/api/design", tags=["设计生成"])


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """接收需求 → AI 生成方案 → 存储 → 返回。

    自动读取项目关联的设计边界和参考项目。
    """
    session = db.query(Session).filter(Session.id == req.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    project = db.query(Project).filter(Project.id == session.project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")

    try:
        result = call_deepseek(project.id, session.id, req.prompt)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))

    # 计算版本号
    max_ver = db.query(Version).filter(
        Version.session_id == session.id
    ).order_by(desc(Version.number)).first()
    version_number = (max_ver.number + 1) if max_ver else 1

    # 保存版本
    version = Version(
        session_id=session.id,
        number=version_number,
        design_json=result["design_json"],
        description=result["description"],
        llm_provider=result["llm_provider"],
        llm_model=result["llm_model"],
        token_usage=result["token_usage"],
    )
    db.add(version)
    db.flush()

    # 保存对话记录
    db.add(Message(session_id=session.id, role="user", content=req.prompt))
    db.add(Message(
        session_id=session.id,
        role="assistant",
        content=f"✅ v{version_number} 已生成：{result['description']}",
        version_id=version.id,
    ))

    # 更新项目时间
    db.query(Project).filter(Project.id == project.id).update(
        {"updated_at": __import__("datetime").datetime.utcnow()}
    )

    db.commit()
    db.refresh(version)

    return GenerateResponse(
        project_id=project.id,
        session_id=session.id,
        version_id=version.id,
        version_number=version.number,
        design_json=version.design_json,
        description=result["description"],
        token_usage=result["token_usage"],
    )


@router.post("/refine", response_model=GenerateResponse)
def refine(req: GenerateRequest, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """追加精炼——继承上下文，生成新版本。"""
    session = db.query(Session).filter(Session.id == req.session_id).first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    project = db.query(Project).filter(Project.id == session.project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if project.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")

    try:
        result = call_deepseek(project.id, session.id, req.prompt)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))

    max_ver = db.query(Version).filter(
        Version.session_id == session.id
    ).order_by(desc(Version.number)).first()
    version_number = (max_ver.number + 1) if max_ver else 1

    version = Version(
        session_id=session.id,
        number=version_number,
        parent_version_id=max_ver.id if max_ver else None,
        design_json=result["design_json"],
        description=result["description"],
        llm_provider=result["llm_provider"],
        llm_model=result["llm_model"],
        token_usage=result["token_usage"],
    )
    db.add(version)
    db.flush()

    db.add(Message(session_id=session.id, role="user", content=req.prompt))
    db.add(Message(
        session_id=session.id,
        role="assistant",
        content=f"✅ v{version_number} 已生成：{result['description']}",
        version_id=version.id,
    ))

    db.query(Project).filter(Project.id == project.id).update(
        {"updated_at": __import__("datetime").datetime.utcnow()}
    )

    db.commit()
    db.refresh(version)

    return GenerateResponse(
        project_id=project.id,
        session_id=session.id,
        version_id=version.id,
        version_number=version.number,
        design_json=version.design_json,
        description=result["description"],
        token_usage=result["token_usage"],
    )


# ── WebSocket 流式对话 ──

@router.websocket("/ws/refine")
async def ws_refine(websocket: WebSocket, token: str = Query(...)):
    """WebSocket 流式精炼：AI 边生成边推送 token。

    客户端连接后发送 JSON: {"session_id": "...", "prompt": "..."}
    服务端逐 token 推送，最后推送 result。
    """
    await websocket.accept()

    # 验证 Token
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_text('{"type":"error","message":"Token 无效"}')
            await websocket.close()
            return
    except Exception as e:
        await websocket.send_text(f'{{"type":"error","message":"认证失败: {str(e)}"}}')
        await websocket.close()
        return

    # 接收请求
    try:
        raw = await websocket.receive_text()
        req_data = json.loads(raw)
        session_id = req_data.get("session_id")
        prompt = req_data.get("prompt", "")
    except (json.JSONDecodeError, WebSocketDisconnect):
        await websocket.close()
        return

    if not session_id or not prompt:
        await websocket.send_text('{"type":"error","message":"缺少 session_id 或 prompt"}')
        await websocket.close()
        return

    # 验证会话归属
    db = next(get_db())
    try:
        from app.models import Session, Project, Version, Message
        from sqlalchemy.orm import Session as DbSession

        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            await websocket.send_text('{"type":"error","message":"会话不存在"}')
            await websocket.close()
            return

        project = db.query(Project).filter(Project.id == session.project_id).first()
        if not project:
            await websocket.send_text('{"type":"error","message":"项目不存在"}')
            await websocket.close()
            return
    finally:
        pass  # db will be used later

    # 流式调用 DeepSeek
    full_text = ""
    final_result = None
    async for chunk in stream_deepseek(project.id, session_id, prompt):
        try:
            data = json.loads(chunk)
        except json.JSONDecodeError:
            continue

        if data.get("type") == "token":
            full_text += data["text"]
            await websocket.send_text(chunk)
        elif data.get("type") == "result":
            final_result = data
            await websocket.send_text(chunk)

    # 保存版本到数据库
    if final_result and not final_result.get("error"):
        try:
            from sqlalchemy import desc
            max_ver = db.query(Version).filter(
                Version.session_id == session_id
            ).order_by(desc(Version.number)).first()
            version_number = (max_ver.number + 1) if max_ver else 1

            version = Version(
                session_id=session_id,
                number=version_number,
                parent_version_id=max_ver.id if max_ver else None,
                design_json=final_result["design_json"],
                description=final_result.get("description", ""),
                llm_provider=final_result.get("llm_provider", "deepseek"),
                llm_model=final_result.get("llm_model", "deepseek-chat"),
            )
            db.add(version)
            db.flush()

            db.add(Message(session_id=session_id, role="user", content=prompt))
            db.add(Message(
                session_id=session_id,
                role="assistant",
                content=f"\u2705 v{version_number} \u5df2\u751f\u6210\uff1a{final_result.get('description', '')}" if final_result.get("description") else f"\u2705 v{version_number} \u5df2\u751f\u6210",
                version_id=version.id,
            ))

            db.query(Project).filter(Project.id == project.id).update(
                {"updated_at": __import__("datetime").datetime.utcnow()}
            )
            db.commit()

            await websocket.send_text(json.dumps({
                "type": "saved",
                "version_id": version.id,
                "version_number": version_number,
            }, ensure_ascii=False))
        except Exception as e:
            db.rollback()
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"\u4fdd\u5b58\u5931\u8d25: {str(e)}",
            }, ensure_ascii=False))
        finally:
            db.close()

    try:
        await websocket.close()
    except Exception:
        pass
