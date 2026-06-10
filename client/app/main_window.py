"""主窗口 — 桌面客户端核心界面。

左侧：项目列表 + 会话切换
中央：AI 对话面板 + 输入区
右侧：版本列表 + 推 CAD 按钮
"""

import json
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QTextEdit,
    QLineEdit, QDialog, QFormLayout, QCheckBox, QMessageBox,
    QComboBox, QTreeWidget, QTreeWidgetItem, QFrame,
    QApplication, QMenu, QInputDialog, QGroupBox, QScrollArea, QSizePolicy,
    QHeaderView, QStyledItemDelegate,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPolygonItem, QGraphicsTextItem
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF

from app.api_client import APIClient
from app.config_manager import load_config, save_credentials, clear_credentials, get_server_url
from app.cad_engine import CadEngine, HAS_PYWIN32

# ── 暗色主题调色板 ──
PALETTE = {
    "bg":           "#141517",
    "sidebar":      "#1A1B1E",
    "panel":        "#1E1F23",
    "input_bg":     "#25262B",
    "text":         "#E5E5EA",
    "text_dim":     "#98989E",
    "text_faint":   "#636368",
    "primary":      "#4F6EF7",
    "primary_dim":  "rgba(79,110,247,0.15)",
    "accent":       "#F9A825",
    "border":       "#2C2D31",
    "danger":       "#FF5252",
    "success":      "#4CAF50",
    "user_bubble":  "rgba(79,110,247,0.12)",
    "ai_bubble":    "rgba(229,229,234,0.05)",
}


class DWGUploadWorker(QThread):
    """后台线程：上传 DWG 到服务器。"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: APIClient, version_id: str, file_path: str):
        super().__init__()
        self.api = api
        self.version_id = version_id
        self.file_path = file_path

    def run(self):
        try:
            result = self.api.upload_dwg(self.version_id, self.file_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SettingsDialog(QDialog):
    """服务器设置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("服务器设置")
        self.setMinimumWidth(420)
        self.setStyleSheet(self._style())

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://192.168.10.xxx:3000")
        self.url_input.setText(get_server_url())
        self.status_label = QLabel("")

        btn_test = QPushButton("测试连接")
        btn_test.clicked.connect(self._test)
        btn_save = QPushButton("保存")
        btn_save.setStyleSheet(f"background:{PALETTE['primary']};color:#fff;padding:6px 20px;")
        btn_save.clicked.connect(self._save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(QLabel("服务器地址"))
        layout.addWidget(self.url_input)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _test(self):
        url = self.url_input.text().strip()
        api = APIClient(base_url=url)
        if api.health():
            self.status_label.setText("[OK] 连接成功")
            self.status_label.setStyleSheet(f"color:{PALETTE['success']};")
        else:
            self.status_label.setText("[X] 连接失败")
            self.status_label.setStyleSheet(f"color:{PALETTE['danger']};")

    def _save(self):
        url = self.url_input.text().strip()
        config = load_config()
        config["server_url"] = url
        from app.config_manager import save_config
        save_config(config)
        self.accept()

    def _style(self):
        return f"""
        QDialog {{ background:{PALETTE['bg']}; color:{PALETTE['text']}; }}
        QLineEdit {{ background:{PALETTE['input_bg']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; padding:8px; border-radius:4px; }}
        QPushButton {{ background:{PALETTE['panel']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; padding:8px 16px; border-radius:4px; }}
        QLabel {{ color:{PALETTE['text']}; }}
        """



class WsStreamWorker(QThread):
    """后台线程：WebSocket 流式调用 AI。"""
    token_received = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, ws_url: str, data: dict):
        super().__init__()
        self.ws_url = ws_url
        self.data = data

    def run(self):
        try:
            import asyncio
            import websockets
            import json

            async def connect():
                async with websockets.connect(self.ws_url) as ws:
                    await ws.send(json.dumps(self.data))
                    while True:
                        msg = await ws.recv()
                        try:
                            d = json.loads(msg)
                        except json.JSONDecodeError:
                            continue
                        t = d.get("type", "")
                        if t == "token":
                            self.token_received.emit(d.get("text", ""))
                        elif t in ("result", "saved", "error"):
                            self.finished.emit(d)
                            break

            asyncio.run(connect())
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    """桌面客户端主窗口。"""

    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api
        self.current_project_id = None
        self.current_session_id = None
        self.current_session_title = "方案一"
        self.cad_engine = None
        self.worker = None
        self.dwg_worker = None
        self.ws_streaming = False
        self.version_map = {}  # version_id -> (number, design_json)

        self.setWindowTitle("AI CAD — 工业厂房设计助手")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 880)
        self.setStyleSheet(self._global_style())

        self._build_menu()
        self._build_ui()
        self._load_projects()

    # ── 全局样式 ──

    def _global_style(self):
        return f"""
        QMainWindow {{ background:{PALETTE['bg']}; }}
        QSplitter::handle {{ background:{PALETTE['border']}; width:1px; }}
        QScrollBar:vertical {{ background:{PALETTE['bg']}; width:6px; }}
        QScrollBar::handle:vertical {{ background:{PALETTE['text_faint']}; border-radius:3px; min-height:30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QTreeWidget {{ background:{PALETTE['panel']}; color:{PALETTE['text']}; border:none;
            font-size:13px; }}
        QTreeWidget::item {{ padding:6px 8px; }}
        QTreeWidget::item:hover {{ background:rgba(79,110,247,0.1); }}
        QTreeWidget::item:selected {{ background:{PALETTE['primary_dim']}; }}
        QTreeWidget QHeaderView::section {{ background:{PALETTE['sidebar']};
            color:{PALETTE['text_dim']}; border:none; padding:6px 8px; font-size:11px; }}
        QListWidget {{ background:{PALETTE['panel']}; color:{PALETTE['text']}; border:none;
            font-size:13px; outline:none; }}
        QListWidget::item {{ padding:8px 12px; }}
        QListWidget::item:hover {{ background:rgba(79,110,247,0.1); }}
        QListWidget::item:selected {{ background:{PALETTE['primary_dim']}; }}
        QTextEdit {{ background:{PALETTE['panel']}; color:{PALETTE['text']}; border:1px solid {PALETTE['border']};
            border-radius:6px; padding:8px; font-size:13px; }}
        QLineEdit {{ background:{PALETTE['input_bg']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; border-radius:6px; padding:10px; font-size:13px; }}
        QPushButton {{ background:{PALETTE['panel']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; border-radius:4px; padding:6px 14px; font-size:12px; }}
        QPushButton:hover {{ border-color:{PALETTE['primary']}; }}
        QComboBox {{ background:{PALETTE['input_bg']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; border-radius:4px; padding:6px; font-size:12px; }}
        QGroupBox {{ color:{PALETTE['text_dim']}; border:1px solid {PALETTE['border']};
            border-radius:6px; margin-top:12px; padding-top:12px; font-size:12px; }}
        QCheckBox {{ color:{PALETTE['text']}; font-size:12px; }}
        QLabel {{ color:{PALETTE['text']}; }}
        """

    # ── 菜单栏 ──

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(f"background:{PALETTE['sidebar']}; color:{PALETTE['text']}; border:none;")
        file_menu = mb.addMenu("文件")
        file_menu.addAction("服务器设置", self._show_settings)
        file_menu.addAction("退出", self.close)
        help_menu = mb.addMenu("帮助")
        help_menu.addAction("关于", lambda: QMessageBox.about(self, "关于", "AI CAD 工业厂房设计助手 v1.0"))

    # ── 主 UI ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        hlayout = QHBoxLayout(central)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # ── 左侧面板：项目 + 会话 ──
        left_panel = QWidget()
        left_panel.setFixedWidth(260)
        left_panel.setStyleSheet(f"background:{PALETTE['sidebar']};")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        # 用户信息
        user_row = QHBoxLayout()
        user_label = QLabel(f"  {self.api.user.get('display_name', '用户')}")
        user_label.setStyleSheet("font-size:14px; font-weight:600;")
        user_row.addWidget(user_label)
        user_row.addStretch()
        btn_logout = QPushButton("退出")
        btn_logout.setStyleSheet("padding:4px 10px; font-size:11px;")
        btn_logout.clicked.connect(self._logout)
        user_row.addWidget(btn_logout)
        left_layout.addLayout(user_row)

        left_layout.addWidget(self._sep())

        # 标题 + 新建
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("项目列表"))
        btn_new = QPushButton("+ 新建")
        btn_new.setStyleSheet(f"background:{PALETTE['primary']}; color:#fff; padding:4px 12px; font-size:11px;")
        btn_new.clicked.connect(self._new_project)
        title_row.addStretch()
        title_row.addWidget(btn_new)
        left_layout.addLayout(title_row)

        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_project_selected)
        left_layout.addWidget(self.project_list)



        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # ── 中央：对话区 ──
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # 会话标题栏（可切换 + 新建）
        self.session_bar = QWidget()
        self.session_bar.setStyleSheet(f"background:{PALETTE['sidebar']}; border-bottom:1px solid {PALETTE['border']};")
        sb_layout = QHBoxLayout(self.session_bar)
        sb_layout.setContentsMargins(8, 4, 8, 4)
        sb_layout.setSpacing(2)

        self.session_tabs = QHBoxLayout()
        self.session_tabs.setSpacing(4)
        sb_layout.addLayout(self.session_tabs)
        sb_layout.addStretch()

        self.btn_add_session = QPushButton("+")
        self.btn_add_session.setStyleSheet(f"font-size:13px; padding:2px 8px;")
        self.btn_add_session.clicked.connect(self._new_session_dialog)
        self.btn_add_session.setVisible(False)
        sb_layout.addWidget(self.btn_add_session)

        center_layout.addWidget(self.session_bar)

        # 对话记录
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        center_layout.addWidget(self.chat_area, 1)

        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet(f"background:{PALETTE['sidebar']}; border-top:1px solid {PALETTE['border']};")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("描述你的设计需求… (Enter 发送)")
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field)

        btn_send = QPushButton("发送")
        btn_send.setStyleSheet(f"background:{PALETTE['primary']}; color:#fff; padding:8px 18px; font-weight:600;")
        btn_send.clicked.connect(self._send_message)
        input_layout.addWidget(btn_send)

        center_layout.addWidget(input_frame)
        splitter.addWidget(center_panel)

        # ── 右侧：版本面板 + 预览 ──
        right_panel = QWidget()
        right_panel.setMinimumWidth(320)
        right_panel.setStyleSheet(f"background:{PALETTE['sidebar']};")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)

        # 版本树
        self.version_tree = QTreeWidget()
        self.version_tree.setHeaderLabels(["版本", "操作"])
        self.version_tree.setColumnWidth(0, 100)
        self.version_tree.setColumnWidth(1, 90)
        self.version_tree.header().setStretchLastSection(True)
        self.version_tree.setMaximumHeight(200)
        self.version_tree.currentItemChanged.connect(self._on_version_selected)
        right_layout.addWidget(self.version_tree)

        # 预览图
        self.preview_view = QGraphicsView()
        self.preview_view.setStyleSheet(f"background:{PALETTE['bg']}; border:1px solid {PALETTE['border']}; border-radius:6px;")
        self.preview_view.setRenderHint(QPainter.Antialiasing)
        self.preview_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.preview_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.preview_scene = QGraphicsScene()
        self.preview_view.setScene(self.preview_scene)
        right_layout.addWidget(self.preview_view, 1)

        splitter.addWidget(right_panel)

        # 比例设置
        splitter.setSizes([260, 860, 360])
        hlayout.addWidget(splitter)

    def _sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"color:{PALETTE['border']};")
        return f

    # ── 项目列表 ──

    def _load_projects(self):
        self.project_list.clear()
        try:
            projects = self.api.list_projects()
            for p in projects:
                item = QListWidgetItem(p["title"])
                item.setData(Qt.UserRole, p["id"])
                self.project_list.addItem(item)

        except Exception as e:
            self._show_error(f"加载项目失败: {e}")

    def _on_project_selected(self, item):
        if not item:
            return
        self.current_project_id = item.data(Qt.UserRole)
        self.current_session_id = None
        # chat_title removed, handled by session tabs
        self._load_sessions()
        self._load_versions()

    def _new_project(self):
        dlg = NewProjectDialog(self.api, self)
        if dlg.exec() == QDialog.Accepted:
            self._load_projects()
            # 自动选中最新项目
            if self.project_list.count() > 0:
                self.project_list.setCurrentRow(0)

    # ── 会话 ──

    def _load_sessions(self):
        if not self.current_project_id:
            return
        try:
            sessions = self.api.list_sessions(self.current_project_id)
            self._render_session_tabs(sessions)
            # 自动选中第一个会话
            if sessions:
                self._switch_session(sessions[0]["id"], sessions[0]["title"])
        except Exception as e:
            import traceback
            self._show_error(f"加载会话失败:\n{str(e)}\n\n{traceback.format_exc()[-200:]}")

    def _render_session_tabs(self, sessions):
        # Clear tabs
        for i in reversed(range(self.session_tabs.count())):
            item = self.session_tabs.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        # Add tab buttons
        for s in sessions:
            btn = QPushButton(s["title"])
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background:" + PALETTE["panel"] + "; color:" + PALETTE["text_dim"] + "; border:1px solid " + PALETTE["border"] + ";"
                " padding:3px 10px; border-radius:3px; font-size:12px; margin-right:2px; }"
                " QPushButton:hover { border-color:" + PALETTE["primary"] + "; color:" + PALETTE["text"] + "; }"
                " QPushButton:checked { background:" + PALETTE["primary_dim"] + "; color:" + PALETTE["text"] + "; border-color:" + PALETTE["primary"] + "; }"
            )
            btn.clicked.connect(lambda checked, sid=s["id"], title=s["title"]: self._switch_session(sid, title))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=btn, sid=s["id"]: self._show_tab_menu(pos, b, sid))
            self.session_tabs.addWidget(btn)
        self.btn_add_session.setVisible(True)

    def _switch_session(self, session_id, title):
        if self.current_session_id == session_id:
            return  # 避免重复加载
        self.current_session_id = session_id
        self.current_session_title = title
        # Highlight the active tab (block signals to prevent re-trigger)
        for i in range(self.session_tabs.count()):
            item = self.session_tabs.itemAt(i)
            if item.widget() and isinstance(item.widget(), QPushButton):
                btn = item.widget()
                btn.blockSignals(True)
                btn.setChecked(btn.text() == title)
                btn.blockSignals(False)
        # Clear old data
        self.chat_area.clear()
        self.version_tree.clear()
        self.version_map.clear()
        self._load_messages()
        self._load_versions()

    def _on_session_selected(self, item):
        pass  # 会话列表已移除，改为自动选中首个会话

    def _new_session_dialog(self):
        if not self.current_project_id:
            return
        sessions = self.api.list_sessions(self.current_project_id)
        default = f"方案{len(sessions) + 1}"
        name, ok = QInputDialog.getText(self, "新建方案", "方案名称:", text=default)
        if ok and name.strip():
            self._new_session(name.strip())

    def _new_session(self, title):
        if not self.current_project_id:
            return
        try:
            self.api.create_session(self.current_project_id, title)
            self._load_sessions()
        except Exception as e:
            self._show_error(f"创建会话失败: {e}")

    # ── 对话 ──

    def _load_messages(self):
        self.chat_area.clear()
        if not self.current_session_id:
            return
        try:
            detail = self.api.get_session(self.current_session_id)
            for m in detail.get("messages", []):
                self._append_message(m["role"], m["content"], m.get("version_id"))
        except Exception as e:
            self._show_error(f"加载对话失败: {e}")

    def _append_message(self, role: str, content: str, version_id: str = None):
        color = PALETTE["primary"] if role == "user" else PALETTE["accent"]
        prefix = "你" if role == "user" else "AI"
        timestamp = datetime.now().strftime("%H:%M")
        html = f'<div style="margin:8px 0;"><span style="color:{color};font-weight:600;">{prefix}</span>'
        html += f' <span style="color:{PALETTE["text_faint"]};font-size:11px;">{timestamp}</span><br>'
        html += f'{content}</div>'
        if version_id:
            html += f'<div style="color:{PALETTE["text_faint"]};font-size:11px;">版本: {version_id[:8]}</div>'
        self.chat_area.insertHtml(html)

    def _send_message(self):
        prompt = self.input_field.text().strip()
        if not prompt:
            return
        if not self.current_session_id:
            self._show_error("请先选择一个项目并创建会话")
            return
        if self.ws_streaming:
            self._show_error("AI 正在生成中，请等待")
            return

        self._append_message("user", prompt)
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.ws_streaming = True

        ws_url = self.api.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url += f"/api/design/ws/refine?token={self.api.token}"

        self.worker = WsStreamWorker(ws_url, {"session_id": self.current_session_id, "prompt": prompt})
        self.worker.token_received.connect(self._on_ws_token)
        self.worker.finished.connect(self._on_ws_result)
        self.worker.error.connect(self._on_ws_error)
        self.worker.start()

    def _on_ws_token(self, text: str):
        """收到流式 token。"""
        try:
            cursor = self.chat_area.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(text)
            self.chat_area.setTextCursor(cursor)
            self.chat_area.ensureCursorVisible()
        except Exception:
            pass

    def _on_ws_result(self, data: dict):
        """WebSocket 结果。"""
        self.ws_streaming = False
        self.input_field.setEnabled(True)

        msg_type = data.get("type", "")
        if msg_type == "saved":
            version_id = data.get("version_id", "")
            version_number = data.get("version_number", 0)
            self.chat_area.insertHtml(
                f'<div style="color:{PALETTE["text_faint"]};font-size:11px;margin:4px 0">'
                f'v{version_number} 已保存</div>'
            )
            self.version_map[version_id] = (version_number, data.get("design_json", "{}"))
            self._load_versions()
        elif msg_type == "error":
            self._show_error(data.get("message", "未知错误"))
        elif msg_type == "result":
            # result 后通常跟着 saved
            pass

    def _on_ws_error(self, error_msg: str):
        self.ws_streaming = False
        self.input_field.setEnabled(True)
        self._show_error(error_msg)

    # ── 版本 ──

    def _on_version_selected(self, item):
        """选中版本时更新预览。"""
        if not item:
            return
        vid = item.data(0, Qt.UserRole)
        if vid and vid in self.version_map:
            _, design_json = self.version_map[vid]
            self._update_preview(design_json)

    def _update_preview(self, design_json: str):
        """渲染设计 JSON 到预览区。"""
        try:
            self._do_update_preview(design_json)
        except Exception as e:
            print(f"Preview error: {e}")

    def _do_update_preview(self, design_json: str):
        self.preview_scene.clear()
        if not design_json:
            return
        try:
            import json
            design = json.loads(design_json)
        except Exception:
            return

        buildings = design.get("buildings", [])
        if not buildings:
            return

        # 计算边界
        min_x, min_y, max_x, max_y = float("inf"), float("inf"), float("-inf"), float("-inf")

        for b in buildings:
            el, bx, by, bw, bh = self._building_to_scene(b)
            if el:
                min_x = min(min_x, bx)
                min_y = min(min_y, by)
                max_x = max(max_x, bx + bw)
                max_y = max(max_y, by + bh)

        if min_x == float("inf"):
            return

        # 缩放适配
        pad = max(max_x - min_x, max_y - min_y) * 0.15
        self.preview_scene.setSceneRect(min_x - pad, min_y - pad,
                                         max_x - min_x + pad * 2, max_y - min_y + pad * 2)
        self.preview_view.fitInView(self.preview_scene.sceneRect(), Qt.KeepAspectRatio)

    def _building_to_scene(self, building: dict):
        """建筑 → QGraphicsItems。复用与 cad_engine 相同的坐标逻辑。"""
        name = building.get("name", "")
        dims = building.get("dimensions", {})
        pos = building.get("position", {})
        scale = 1  # 预览直接用米为单位

        x = pos.get("x", 0)
        y = pos.get("y", 0)
        w = dims.get("width", 0) or 0
        h = dims.get("length", 0) or 0
        if w <= 0 or h <= 0:
            return None, 0, 0, 0, 0

        group = []

        # 外墙
        rect = self.preview_scene.addRect(QRectF(x, y, w, h),
            QPen(QColor("#4F6EF7"), 0.15),
            QBrush(QColor(79, 110, 247, 30)))
        group.append(rect)

        # 建筑名
        text = self.preview_scene.addText(name)
        text.setDefaultTextColor(QColor("#98989E"))
        text.setPos(x + w / 2 - 15, y - 3)
        text.setScale(0.3)
        group.append(text)

        # 区域划分 (zones)
        for zone in building.get("zones", []):
            zdims = zone.get("dimensions", {})
            zw = zdims.get("width", 0) or 0
            zl = zdims.get("length", 0) or 0
            if zw <= 0 or zl <= 0:
                continue
            zpos = zone.get("position", "").lower()
            zx, zy = self._zone_pos(zpos, x, y, w, h, zw, zl)
            zr = self.preview_scene.addRect(QRectF(zx, zy, zw, zl),
                QPen(QColor("#F9A825"), 0.1, Qt.DashLine),
                QBrush(QColor(249, 168, 37, 20)))
            group.append(zr)
            zn = zone.get("name", "")
            if zn:
                zt = self.preview_scene.addText(zn)
                zt.setDefaultTextColor(QColor("#F9A825"))
                zt.setPos(zx + zw / 2 - 8, zy + zl / 2)
                zt.setScale(0.25)
                group.append(zt)

        # 区域划分 (divisions)
        divisions = building.get("divisions", {})
        if isinstance(divisions, dict):
            for pos_key, d_info in divisions.items():
                if not isinstance(d_info, dict):
                    continue
                ddims = d_info.get("dimensions", {})
                dw = ddims.get("width", 0) or 0
                dl = ddims.get("height") or ddims.get("length", 0) or 0
                if dw <= 0 or dl <= 0:
                    continue
                dx, dy = self._zone_pos(pos_key, x, y, w, h, dw, dl)
                dr = self.preview_scene.addRect(QRectF(dx, dy, dw, dl),
                    QPen(QColor("#F9A825"), 0.1, Qt.DashLine),
                    QBrush(QColor(249, 168, 37, 20)))
                group.append(dr)

        # 房间
        for room in building.get("rooms", []):
            rx = room.get("x", 0) or 0
            ry = room.get("y", 0) or 0
            rw = room.get("width", 0) or 0
            rl = room.get("length", 0) or 0
            if rw <= 0 or rl <= 0:
                continue
            rr = self.preview_scene.addRect(QRectF(x + rx, y + ry, rw, rl),
                QPen(QColor(123, 140, 255, 100), 0.08, Qt.DashLine))
            group.append(rr)

        return group, x, y, w, h

    def _zone_pos(self, pos_key, bx, by, bw, bh, zw, zl):
        """计算区域位置。"""
        p = str(pos_key).lower()
        if "top" in p or "up" in p:
            return bx, by
        elif "bottom" in p or "down" in p:
            return bx, by + bh - zl
        elif "left" in p:
            return bx, by + (bh - zl) / 2
        elif "right" in p:
            return bx + bw - zw, by + (bh - zl) / 2
        return bx, by

    def _load_versions(self):
        self.version_tree.clear()
        if not self.current_session_id:
            return
        try:
            detail = self.api.get_session(self.current_session_id)
            versions = detail.get("versions", [])
            for v in versions:
                self.version_map[v["id"]] = (v["number"], v.get("design_json", "{}"))
                item = QTreeWidgetItem(self.version_tree)
                item.setText(0, f"v{v['number']}")
                item.setData(0, Qt.UserRole, v["id"])
                item.setToolTip(0, f"v{v['number']} — {v.get('description', '')}")

                # 操作按钮容器
                btn_w = QWidget()
                btn_layout = QHBoxLayout(btn_w)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setSpacing(4)

                btn_cad = QPushButton("推CAD")
                btn_cad.setStyleSheet(f"background:{PALETTE['primary']}; color:#fff; font-size:11px; padding:2px 8px;")
                btn_cad.clicked.connect(lambda checked, vid=v["id"]: self._push_to_cad(vid))
                btn_layout.addWidget(btn_cad)

                self.version_tree.setItemWidget(item, 1, btn_w)
        except Exception as e:
            self._show_error(f"加载版本失败: {e}")
        else:
            # 自动选中最新版本并更新预览
            count = self.version_tree.topLevelItemCount()
            if count > 0:
                last = self.version_tree.topLevelItem(count - 1)
                self.version_tree.setCurrentItem(last)
                # 直接触发预览
                vid = last.data(0, Qt.UserRole)
                if vid and vid in self.version_map:
                    _, design_json = self.version_map[vid]
                    self._update_preview(design_json)

    def _push_to_cad(self, version_id: str):
        """推送到 AutoCAD。"""
        if not HAS_PYWIN32:
            self._show_error("CAD 功能仅支持 Windows 环境\n请安装 AutoCAD + pywin32")
            return

        vdata = self.version_map.get(version_id)
        if not vdata:
            self._show_error("版本数据未加载")
            return

        _, design_json = vdata
        try:
            # 连接 AutoCAD 并绘制
            if self.cad_engine is None:
                self.cad_engine = CadEngine()
            self.cad_engine.connect(visible=True)
            self.cad_engine.draw_from_json(design_json)

            # 保存临时 DWG
            tmp_dir = Path(tempfile.gettempdir()) / "hsxb-ai-cad"
            tmp_dir.mkdir(exist_ok=True)
            dwg_path = tmp_dir / f"v{vdata[0]}-{version_id[:8]}.dwg"
            saved = self.cad_engine.save_as_dwg(str(dwg_path))

            # 上传到服务器
            self._append_message("assistant", f"📐 已推送到 AutoCAD\n💾 本地: {saved}", version_id)

            # 异步上传
            self.dwg_worker = DWGUploadWorker(self.api, version_id, saved)
            self.dwg_worker.finished.connect(lambda r: self._append_message("assistant", "☁️ 已同步到服务器"))
            self.dwg_worker.error.connect(lambda e: self._append_message("assistant", f"⚠️ 同步失败: {e}"))
            self.dwg_worker.start()

        except Exception as e:
            self._show_error(f"CAD 操作失败: {e}")

    # ── 其他 ──

    def _show_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.api.base_url = get_server_url()
            self._load_projects()

    def _logout(self):
        clear_credentials()
        self.close()

    def _show_tab_menu(self, pos, btn, sid):
        """右键菜单。"""
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        rename_action.triggered.connect(lambda: self._rename_session(sid, btn))
        menu.popup(btn.mapToGlobal(pos))

    def _rename_session(self, sid, btn):
        """右键菜单：重命名会话。"""
        title, ok = QInputDialog.getText(self, "重命名", "新名称:", text=btn.text())
        if ok and title.strip():
            try:
                self.api.rename_session(sid, title.strip())
                btn.setText(title.strip())
                if self.current_session_id == sid:
                    self.current_session_title = title.strip()
            except Exception as e:
                QMessageBox.warning(self, "错误", str(e))

    def _show_error(self, msg: str):
        QMessageBox.warning(self, "错误", msg)


class NewProjectDialog(QDialog):
    """新建项目对话框。"""

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("新建项目")
        self.setMinimumWidth(480)
        self.setStyleSheet(self._style())

        layout = QFormLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：成都2000平肉制品厂")
        layout.addRow("项目名称", self.title_input)

        # 边界选择
        self.boundary_checks = []
        self.boundary_group = QGroupBox("设计边界（可多选）")
        bv = QVBoxLayout(self.boundary_group)
        try:
            for b in api.list_boundaries():
                cb = QCheckBox(b["name"])
                cb.setProperty("boundary_id", b["id"])
                bv.addWidget(cb)
                self.boundary_checks.append(cb)
        except Exception:
            bv.addWidget(QLabel("（无法加载边界列表）"))
        layout.addRow(self.boundary_group)

        # 参考项目
        self.ref_combo = QComboBox()
        self.ref_combo.addItem("（无）", None)
        try:
            for rp in api.list_reference_projects():
                self.ref_combo.addItem(rp["title"], rp["id"])
        except Exception:
            pass
        layout.addRow("参考项目", self.ref_combo)

        # 按钮
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_create = QPushButton("创建")
        btn_create.setStyleSheet(f"background:{PALETTE['primary']}; color:#fff; font-weight:600;")
        btn_create.clicked.connect(self._create)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_create)
        layout.addRow(btn_row)

    def _create(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            return
        bids = [cb.property("boundary_id") for cb in self.boundary_checks if cb.isChecked()]
        ref_id = self.ref_combo.currentData()
        try:
            self.api.create_project(title, bids, ref_id)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))

    def _style(self):
        return f"""
        QDialog {{ background:{PALETTE['bg']}; color:{PALETTE['text']}; }}
        QLineEdit {{ background:{PALETTE['input_bg']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; padding:8px; border-radius:4px; }}
        QPushButton {{ background:{PALETTE['panel']}; color:{PALETTE['text']};
            border:1px solid {PALETTE['border']}; padding:6px 16px; border-radius:4px; }}
        """
