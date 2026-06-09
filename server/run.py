#!/usr/bin/env python3
"""启动入口：uvicorn run。"""

import uvicorn

if __name__ == "__main__":
    from app.config import HOST, PORT

    print(f"""
╔══════════════════════════════════════════════╗
║          AI CAD 桥梁服务方案                  ║
║         服务器启动中...                       ║
╠══════════════════════════════════════════════╣
║  地址: http://{HOST}:{PORT}                      ║
║  API:  http://{HOST}:{PORT}/docs              ║
║  前端: 待部署 (见 Phase 1.10)                 ║
╚══════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )
