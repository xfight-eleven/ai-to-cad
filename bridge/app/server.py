"""桥梁服务 — Flask 本地 HTTP 服务。

监听 localhost:45678，提供以下接口：
  GET  /health               — 健康检查
  POST /login                — 登录 AI 服务器
  GET  /status               — 登录状态
  GET  /open-in-cad?id=xxx   — 在 AutoCAD 中打开版本
  POST /open-in-cad          — 同上（POST 版本）
"""

import os
import json
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string

from app.config import BRIDGE_PORT, AI_SERVER_URL
from app.api_client import ServerClient

# ── 初始化 ──

app = Flask(__name__)
client = ServerClient()

DESKTOP = Path(os.path.expanduser("~/Desktop"))


# ── 辅助 ──

def _ensure_login() -> tuple:
    """确保已登录，未登录则返回 401 响应。"""
    ok, msg = client.ensure_login()
    if not ok:
        return None, (jsonify({"error": msg, "code": "NOT_LOGGED_IN"}), 401)
    return ok, None


# ── 路由 ──


@app.route("/health")
def health():
    """健康检查。"""
    server_ok, server_msg = client.verify_connection()
    return jsonify({
        "status": "ok",
        "bridge_port": BRIDGE_PORT,
        "server_url": AI_SERVER_URL,
        "server_connected": server_ok,
        "server_message": server_msg,
        "logged_in": client.token is not None,
        "user": client.user,
        "has_pywin32": False,
    })


@app.route("/login", methods=["POST"])
def login():
    """登录 AI 服务器。"""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "请输入用户名和密码"}), 400

    ok, msg = client.login(username, password)
    status = 200 if ok else 401
    return jsonify({
        "success": ok,
        "message": msg,
        "user": client.user,
    }), status


@app.route("/status")
def status():
    """获取登录状态。"""
    return jsonify({
        "logged_in": client.token is not None,
        "user": client.user,
        "server_url": AI_SERVER_URL,
    })


@app.route("/logout", methods=["POST"])
def logout():
    """退出登录。"""
    client.clear_token()
    return jsonify({"success": True, "message": "已退出登录"})


@app.route("/open-in-cad", methods=["GET", "POST"])
def open_in_cad():
    """核心功能：在 AutoCAD 中打开设计版本。

    Query params:
      id  — 版本 ID（必填）

    流程：
      1. 从 AI 服务器拉取版本 JSON
      2. pywin32 指挥 AutoCAD 绘图
      3. 保存 .dwg 到桌面
      4. 返回结果
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        version_id = data.get("id", "")
    else:
        version_id = request.args.get("id", "")

    if not version_id:
        return jsonify({"error": "缺少参数: id"}), 400

    # 1. 登录检查
    _, err = _ensure_login()
    if err:
        return err

    # 2. 拉取 JSON
    ok, msg, version_data = client.get_version_json(version_id)
    if not ok:
        return jsonify({"error": msg}), 502

    # 提取 design_json
    design_json = version_data.get("design_json", "{}")
    try:
        design = json.loads(design_json)
    except json.JSONDecodeError:
        return jsonify({"error": "服务返回的设计数据格式无效"}), 502

    # 获取项目名
    project_title = design.get("project", {}).get("name", "") or "AI_CAD_Design"
    version_number = version_data.get("number", "")

    # 3. 连接 AutoCAD 绘图
    try:
        from app.cad_engine import CadEngine

        cad = CadEngine()
        cad.connect(visible=True)

        cad.draw_from_json(design_json)

        # 4. 保存 .dwg
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dwg_name = f"{project_title}_v{version_number}_{timestamp}.dwg"
        dwg_path = str(DESKTOP / dwg_name)
        saved_path = cad.save_as_dwg(dwg_path)

        cad.close()

        return jsonify({
            "success": True,
            "message": f"✅ 图纸已打开并保存到桌面",
            "file": saved_path,
            "project": project_title,
            "version": version_number,
        })

    except ImportError as e:
        return jsonify({
            "error": f"pywin32 未安装，无法控制 AutoCAD。{e}",
            "code": "NO_PYWIN32",
        }), 501
    except RuntimeError as e:
        return jsonify({
            "error": f"AutoCAD 错误: {e}",
            "code": "CAD_ERROR",
        }), 502
    except Exception as e:
        return jsonify({
            "error": f"绘图失败: {e}",
            "code": "DRAW_ERROR",
        }), 500


# ── 简单的 Web 状态页 ──

@app.route("/")
def index():
    """Web 管理页面。"""
    return render_template_string(INDEX_HTML, port=BRIDGE_PORT, server_url=AI_SERVER_URL)


INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AI CAD 桥梁服务 — 状态</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Segoe UI',sans-serif;background:#1B1C1E;color:#E5E5EA;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#2A2B2F;border:1px solid #3A3B3F;border-radius:16px;padding:40px;width:420px;max-width:94vw}
h1{font-size:22px;margin-bottom:8px}
.sub{color:#98989E;font-size:13px;margin-bottom:24px}
.status-grid{display:grid;grid-template-columns:auto 1fr;gap:12px 16px;font-size:14px}
.label{color:#98989E}
.value{color:#E5E5EA}
.badge{display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600}
.badge-ok{background:rgba(52,199,89,.2);color:#34C759}
.badge-err{background:rgba(255,69,58,.2);color:#FF453A}
.btn{padding:10px 20px;border:none;border-radius:8px;background:#4F6EF7;color:#fff;font-size:14px;cursor:pointer;font-family:inherit;margin-top:20px;transition:all .2s}
.btn:hover{background:#5B78FF}
</style>
</head>
<body>
<div class="card">
<h1>🔧 AI CAD 桥梁服务</h1>
<div class="sub">本机 AutoCAD 绘制服务</div>
<div class="status-grid">
  <span class="label">服务状态</span>
  <span><span class="badge badge-ok">运行中</span></span>
  <span class="label">监听端口</span>
  <span class="value">{{ port }}</span>
  <span class="label">AI 服务器</span>
  <span class="value">{{ server_url }}</span>
  <span class="label">登录状态</span>
  <span class="value" id="loginStatus">检查中…</span>
</div>
<button class="btn" onclick="window.open('http://'+location.host+':{{ port }}/health')">检查详情</button>
</div>
<script>
fetch('/status').then(r=>r.json()).then(d=>{
  document.getElementById('loginStatus').textContent = d.logged_in ? '✅ 已登录 ('+d.user?.display_name+')' : '❌ 未登录';
}).catch(()=>{
  document.getElementById('loginStatus').textContent = '❌ 无法连接';
});
</script>
</body>
</html>
"""


def create_app():
    """工厂函数，供 run.py 使用。"""
    return app
