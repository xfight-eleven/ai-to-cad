#!/usr/bin/env python3
"""AI CAD 桥梁服务 — 启动入口。

每个设计师在自己电脑上运行此服务。
它接收来自网页的请求，通过 pywin32 指挥本地 AutoCAD 画图。

使用方式：
  python3 run.py                    # 正常启动
  python3 run.py --no-web           # 不打开浏览器
  python3 run.py --port 45678       # 指定端口
"""

import sys
import webbrowser
import argparse

from app.config import BRIDGE_PORT, AI_SERVER_URL, DESIGNER_USERNAME, DESIGNER_PASSWORD
from app.api_client import ServerClient


def print_banner():
    """打印启动横幅。"""
    print("""
╔══════════════════════════════════════════════╗
║        AI CAD 桥梁服务                       ║
║        AutoCAD Local Bridge Service          ║
╠══════════════════════════════════════════════╣
║  监听地址: http://localhost:{}        ║
║  AI 服务器: {}            ║
║                                              ║
║  使用方式:                                    ║
║  ① 在浏览器中打开 AI CAD 网页                 ║
║  ② 点击"在 CAD 中打开"                         ║
║  ③ AutoCAD 自动弹出并绘制图纸                  ║
╚══════════════════════════════════════════════╝
    """.format(BRIDGE_PORT, AI_SERVER_URL))


def try_autologin():
    """尝试自动登录（如果 .env 中配置了凭据）。"""
    if DESIGNER_USERNAME and DESIGNER_PASSWORD:
        client = ServerClient()
        ok, msg = client.login(DESIGNER_USERNAME, DESIGNER_PASSWORD)
        if ok:
            print(f"  ✅ 自动登录成功 — {client.user['display_name']}")
        else:
            print(f"  ⚠️  自动登录失败: {msg}")
            print("  请在浏览器中打开状态页手动登录")


def main():
    parser = argparse.ArgumentParser(description="AI CAD 桥梁服务")
    parser.add_argument("--port", type=int, default=BRIDGE_PORT, help="监听端口")
    parser.add_argument("--no-web", action="store_true", help="不打开浏览器")
    args = parser.parse_args()

    print_banner()

    # 尝试自动登录
    try_autologin()

    # 在浏览器中打开状态页
    if not args.no_web:
        webbrowser.open(f"http://localhost:{args.port}")

    # 启动 Flask 服务
    print(f"\n  🚀 服务启动中... http://localhost:{args.port}")
    print(f"  ⏎  按 Ctrl+C 停止服务\n")

    from app.server import create_app
    app = create_app()

    try:
        import waitress
        waitress.serve(app, host="127.0.0.1", port=args.port)
    except ImportError:
        app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
