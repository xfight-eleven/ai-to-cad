#!/bin/bash
cd "$(dirname "$0")"
echo "========================================"
echo "  AI CAD 桌面客户端"
echo "========================================"
echo ""

# 使用 venv 中的 Python
".venv/bin/python3" -m app.main

echo ""
echo "客户端已退出"
read -p "按 Enter 关闭此窗口..."
