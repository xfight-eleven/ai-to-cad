"""AI CAD 桌面客户端 — 入口。

启动流程：
1. 读配置 → 有 token → 自动鉴权
2. 自动鉴权失败 / 无 token → 显示登录窗口
3. 登录成功 → 进入主窗口
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt

from app.api_client import APIClient
from app.config_manager import load_config, save_credentials, get_server_url
from app.main_window import MainWindow


PALETTE = {
    "bg": "#141517",
    "input_bg": "#25262B",
    "text": "#E5E5EA",
    "text_dim": "#98989E",
    "primary": "#4F6EF7",
    "border": "#2C2D31",
    "panel": "#1E1F23",
    "danger": "#FF5252",
}


class LoginDialog(QDialog):
    """登录对话框。"""

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("登录 — AI CAD")
        self.setFixedSize(380, 260)
        self.setStyleSheet(f"""
        QDialog {{ background:{PALETTE["bg"]}; }}
        QLabel {{ color:{PALETTE["text"]}; font-size:13px; }}
        QLineEdit {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:10px; border-radius:6px; font-size:14px; }}
        QPushButton {{ background:{PALETTE["primary"]}; color:#fff; font-size:14px;
            border:none; padding:10px; border-radius:6px; font-weight:600; }}
        QPushButton:hover {{ opacity:0.9; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        layout.addWidget(QLabel("AI CAD 工业厂房设计助手"))
        layout.addSpacing(8)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("用户名")
        layout.addWidget(self.user_input)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("密码")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.returnPressed.connect(self._login)
        layout.addWidget(self.pass_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color:{PALETTE['danger']}; font-size:12px;")
        layout.addWidget(self.error_label)

        btn_login = QPushButton("登 录")
        btn_login.clicked.connect(self._login)
        layout.addWidget(btn_login)

    def _login(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text().strip()
        if not username or not password:
            self.error_label.setText("请输入用户名和密码")
            return
        try:
            user = self.api.login(username, password)
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI CAD")
    app.setOrganizationName("hsxb")

    config = load_config()
    server_url = config.get("server_url", "http://127.0.0.1:3000")
    api = APIClient(base_url=server_url)

    # 尝试自动登录
    token = config.get("token")
    auto_logged_in = False
    if token:
        try:
            api._token = token
            api.get_me()
            auto_logged_in = True
        except Exception:
            pass

    # 登录流程
    if not auto_logged_in:
        login = LoginDialog(api)
        if login.exec() != QDialog.Accepted:
            sys.exit(0)
        # 保存凭证
        save_credentials(server_url, api.token, api.user.get("username", ""))

    # 进入主窗口
    window = MainWindow(api)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
