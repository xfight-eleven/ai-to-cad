#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  AI CAD 桌面客户端"
echo "========================================"
echo ""

PYTHON=".venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    echo "[错误] 找不到 $PYTHON"
    echo "是否已创建虚拟环境？"
    read -p "按 Enter 退出"
    exit 1
fi

"$PYTHON" -m app.main 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[错误] 客户端异常退出，代码: $EXIT_CODE"
    read -p "按 Enter 关闭此窗口..."
fi
