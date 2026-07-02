"""主窗口 — 桌面客户端核心界面。

左侧：项目列表 + 会话切换
中央：AI 对话面板 + 输入区
右侧：版本列表 + 推 CAD 按钮
"""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client import APIClient
from app.cad_engine import HAS_PYWIN32, CadEngine
from app.config_manager import (
    clear_credentials,
    get_server_url,
    load_config,
    save_credentials,
)
from app.widgets.chat_bubble import ChatPanel

# ── 暗色主题调色板 ──
PALETTE = {
    "bg": "#141517",
    "sidebar": "#1A1B1E",
    "panel": "#1E1F23",
    "input_bg": "#25262B",
    "text": "#E5E5EA",
    "text_dim": "#98989E",
    "text_faint": "#636368",
    "primary": "#4F6EF7",
    "primary_dim": "rgba(79,110,247,0.25)",
    "accent": "#F9A825",
    "border": "#2C2D31",
    "danger": "#FF5252",
    "success": "#4CAF50",
    "user_bubble": "rgba(79,110,247,0.12)",
    "ai_bubble": "rgba(229,229,234,0.05)",
}


class VersionItemDelegate(QStyledItemDelegate):
    """版本表格委托：绘制边框 + 只高亮当前选中的版本（而非整行）。"""

    def __init__(self, tree_widget):
        super().__init__(tree_widget)
        self.tree = tree_widget

    def paint(self, painter, option, index):
        row, col = index.row(), index.column()
        border = PALETTE["border"]

        # 判断该 cell 是否属于选中版本
        data_col = 0 if col <= 1 else 2
        vid = index.sibling(index.row(), data_col).data(Qt.UserRole)
        is_sel = vid and vid == getattr(self.tree, "_sel_version_id", None)

        # 绘制背景
        if is_sel:
            painter.save()
            painter.fillRect(option.rect, QColor(249, 168, 37))
            painter.restore()

        # 让 Qt 绘制文字
        super().paint(painter, option, index)

        # 边框（右 + 下），始终绘制在 item 之上
        painter.save()
        pen = QPen(QColor(border), 1)
        painter.setPen(pen)
        r = option.rect
        # 列之间右竖线（最后一列不画）
        if col in (0, 1, 2):
            painter.drawLine(r.right(), r.top(), r.right(), r.bottom())
        # 行底部分隔线
        painter.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        painter.restore()


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
        btn_save.setStyleSheet(
            f"background:{PALETTE['primary']};color:#fff;padding:6px 20px;"
        )
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
        QDialog {{ background:{PALETTE["bg"]}; color:{PALETTE["text"]}; }}
        QLineEdit {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:8px; border-radius:4px; }}
        QPushButton {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:8px 16px; border-radius:4px; }}
        QLabel {{ color:{PALETTE["text"]}; }}
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
            import json

            import websockets

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
                        elif t == "result":
                            self.finished.emit(d)
                        elif t in ("saved", "error"):
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
        # _sel_version_id 在 _build_ui 中设置到 version_tree 上

        self.setWindowTitle("AI CAD — 工业厂房设计助手")
        self.setMinimumSize(1100, 800)
        self.resize(1200, 860)
        self.setStyleSheet(self._global_style())

        self._build_menu()
        self._build_ui()
        self._load_projects()

    # ── 全局样式 ──

    def _global_style(self):
        return f"""
        QMainWindow {{ background:{PALETTE["bg"]}; }}
        QSplitter::handle {{ background:{PALETTE["border"]}; width:1px; }}
        QScrollBar:vertical {{ background:{PALETTE["bg"]}; width:6px; }}
        QScrollBar::handle:vertical {{ background:{PALETTE["text_faint"]}; border-radius:3px; min-height:30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QTreeWidget {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]}; border:none;
            font-size:13px; }}
        QTreeWidget::item {{ padding:6px 8px; }}
        QTreeWidget::item:hover {{ background:rgba(79,110,247,0.1); }}
        QTreeWidget::item:selected {{ background:{PALETTE["primary_dim"]}; }}
        QTreeWidget QHeaderView::section {{ background:{PALETTE["sidebar"]};
            color:{PALETTE["text_dim"]}; border:none; padding:6px 8px; font-size:11px; }}
        QListWidget {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]}; border:none;
            font-size:13px; outline:none; }}
        QListWidget::item {{ padding:8px 12px; }}
        QListWidget::item:hover {{ background:rgba(79,110,247,0.1); }}
        QListWidget::item:selected {{ background:{PALETTE["primary_dim"]}; }}
        QTextEdit {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]}; border:1px solid {PALETTE["border"]};
            border-radius:6px; padding:8px; font-size:13px; }}
        QLineEdit {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; border-radius:6px; padding:10px; font-size:13px; }}
        QPushButton {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; border-radius:4px; padding:6px 14px; font-size:12px; }}
        QPushButton:hover {{ border-color:{PALETTE["primary"]}; }}
        QComboBox {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; border-radius:4px; padding:6px; font-size:12px; }}
        QGroupBox {{ color:{PALETTE["text_dim"]}; border:1px solid {PALETTE["border"]};
            border-radius:6px; margin-top:12px; padding-top:12px; font-size:12px; }}
        QCheckBox {{ color:{PALETTE["text"]}; font-size:12px; }}
        QLabel {{ color:{PALETTE["text"]}; }}
        """

    # ── 菜单栏 ──

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(
            f"background:{PALETTE['sidebar']}; color:{PALETTE['text']}; border:none;"
        )
        file_menu = mb.addMenu("文件")
        file_menu.addAction("服务器设置", self._show_settings)
        file_menu.addAction("退出", self._logout)
        help_menu = mb.addMenu("帮助")
        help_menu.addAction(
            "关于",
            lambda: QMessageBox.about(self, "关于", "AI CAD 工业厂房设计助手 v1.0"),
        )

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
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 顶栏：左侧（用户信息 + 新建 + 退出）→ 46px，底部边线
        top_bar = QWidget()
        top_bar.setFixedHeight(46)
        top_bar.setStyleSheet(
            f"background:{PALETTE['sidebar']}; border-bottom:1px solid {PALETTE['border']};"
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 0, 12, 0)
        top_layout.setSpacing(4)

        user_label = QLabel(f"  {self.api.user.get('display_name', '用户')}")
        user_label.setStyleSheet("font-size:13px; font-weight:600;")
        top_layout.addWidget(user_label)

        top_layout.addStretch()

        btn_new = QPushButton("+ 新建")
        btn_new.setStyleSheet(
            f"background:{PALETTE['primary']}; color:#fff; padding:4px 12px; font-size:11px;"
        )
        btn_new.clicked.connect(self._new_project)
        top_layout.addWidget(btn_new)

        left_layout.addWidget(top_bar)

        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_project_selected)
        # 确保失去焦点时选中项颜色不变暗
        pal = self.project_list.palette()
        pal.setColor(QPalette.Inactive, QPalette.Highlight, QColor("#4F6EF7"))
        pal.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor("#E5E5EA"))
        self.project_list.setPalette(pal)
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
        self.session_bar.setStyleSheet(
            f"background:{PALETTE['sidebar']}; border-bottom:1px solid {PALETTE['border']};"
        )
        self.session_bar.setFixedHeight(46)
        sb_layout = QHBoxLayout(self.session_bar)
        sb_layout.setContentsMargins(8, 0, 8, 0)
        sb_layout.setSpacing(2)

        self.session_tabs = QHBoxLayout()
        self.session_tabs.setSpacing(4)
        sb_layout.addLayout(self.session_tabs)

        self.btn_add_session = QPushButton("+")
        self.btn_add_session.setStyleSheet(f"font-size:13px; padding:2px 8px;")
        self.btn_add_session.clicked.connect(self._new_session_dialog)
        self.btn_add_session.setVisible(False)
        sb_layout.addWidget(self.btn_add_session)

        sb_layout.addStretch()

        btn_logout_bar = QPushButton("退出")
        btn_logout_bar.setStyleSheet("padding:4px 10px; font-size:11px;")
        btn_logout_bar.clicked.connect(self._logout)
        sb_layout.addWidget(btn_logout_bar)

        center_layout.addWidget(self.session_bar)

        # 对话记录（豆包风格气泡）
        self.chat_panel = ChatPanel()
        center_layout.addWidget(self.chat_panel, 1)

        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet(
            f"background:{PALETTE['sidebar']}; border-top:1px solid {PALETTE['border']};"
        )
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("描述你的设计需求… (Enter 发送)")
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field)

        btn_send = QPushButton("发送")
        btn_send.setStyleSheet(
            f"background:{PALETTE['primary']}; color:#fff; padding:8px 18px; font-weight:600;"
        )
        btn_send.clicked.connect(self._send_message)
        input_layout.addWidget(btn_send)

        center_layout.addWidget(input_frame)
        splitter.addWidget(center_panel)

        # 比例设置（不再有右侧栏，中央占满）
        splitter.setSizes([260, 1080])
        hlayout.addWidget(splitter)

        # 隐藏的预览渲染目标（供 _update_preview / _building_to_scene 渲染到 QPixmap）
        self.preview_scene = QGraphicsScene()
        self.preview_view = QGraphicsView(self.preview_scene)
        self.preview_view.setVisible(False)

        # 版本树（隐藏，用于存储版本数据，供推 CAD 等操作使用）
        self.version_tree = QTreeWidget()
        self.version_tree.setHeaderHidden(True)
        self.version_tree.setColumnCount(3)
        self.version_tree.setVisible(False)
        self.version_tree._sel_version_id = None
        self.version_tree.itemClicked.connect(self._on_version_selected)

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

            # 自动选中第一个（最新）项目
            if self.project_list.count() > 0:
                self.project_list.setCurrentRow(0)
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
            return
            import traceback

            self._show_error(
                f"加载会话失败:\n{str(e)}\n\n{traceback.format_exc()[-200:]}"
            )

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
                "QPushButton { background:"
                + PALETTE["panel"]
                + "; color:"
                + PALETTE["text_dim"]
                + "; border:1px solid "
                + PALETTE["border"]
                + ";"
                " padding:3px 10px; border-radius:3px; font-size:12px; margin-right:2px; }"
                " QPushButton:hover { border-color:"
                + PALETTE["primary"]
                + "; color:"
                + PALETTE["text"]
                + "; }"
                " QPushButton:checked { background:"
                + PALETTE["primary_dim"]
                + "; color:"
                + PALETTE["text"]
                + "; border-color:"
                + PALETTE["primary"]
                + "; }"
            )
            btn.clicked.connect(
                lambda checked, sid=s["id"], title=s["title"]: self._switch_session(
                    sid, title
                )
            )
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, b=btn, sid=s["id"]: self._show_tab_menu(pos, b, sid)
            )
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
        self.chat_panel.clear()
        self.version_tree.clear()
        self.version_map.clear()
        # 先加载版本（填充 version_map），再恢复对话预览缩略图
        self._load_versions()
        self._load_messages()

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
            return
            self._show_error(f"创建会话失败: {e}")

    # ── 对话 ──

    def _load_messages(self):
        self.chat_panel.clear()
        if not self.current_session_id:
            return
        try:
            detail = self.api.get_session(self.current_session_id)
            for m in detail.get("messages", []):
                bub = self._append_message(m["role"], m["content"], m.get("version_id"))
                # 如果有 version_id，尝试恢复预览缩略图
                vid = m.get("version_id")
                if vid and bub:
                    self._restore_preview_for_version(bub, vid)
        except Exception as e:
            return
            self._show_error(f"加载对话失败: {e}")

    def _append_message(self, role: str, content: str, version_id: str = None):
        ts = datetime.now().strftime("%H:%M")
        bub = self.chat_panel.add_message(content, role, ts)
        if version_id:
            bub.addActionButton("推CAD", lambda vid=version_id: self._push_to_cad(vid))
        return bub

    def _restore_preview_for_version(self, bub, vid: str):
        """尝试从缓存/API 获取 design_json 并恢复版本预览缩略图。"""
        # 即使 version_map 中有该版本，若 design_json 为空也要尝试 API 拉取
        dj = ""
        if vid in self.version_map:
            _, dj = self.version_map[vid]
        if not dj or dj == "{}":
            try:
                v = self.api.get_version(vid)
                dj = v.get("design_json", "")
                self.version_map[vid] = (v.get("number", 0), dj)
            except Exception:
                return
        if dj and dj != "{}":
            pm = self._render_preview_pixmap(dj)
            if pm:
                bub.setPreview(pm, lambda vid=vid: self._show_version_in_preview(vid))

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

        # 创建流式气泡
        ts = datetime.now().strftime("%H:%M")
        self.chat_panel.start_streaming(ts)

        ws_url = self.api.base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        ws_url += f"/api/design/ws/refine?token={self.api.token}"

        self.worker = WsStreamWorker(
            ws_url, {"session_id": self.current_session_id, "prompt": prompt}
        )
        self.worker.token_received.connect(self._on_ws_token)
        self.worker.finished.connect(self._on_ws_result)
        self.worker.error.connect(self._on_ws_error)
        self.worker.start()

    def _on_ws_token(self, text: str):
        """收到流式 token。"""
        try:
            self.chat_panel.append_stream(text)
        except Exception:
            pass

    def _on_ws_result(self, data: dict):
        """WebSocket 结果。"""
        self.ws_streaming = False
        self.input_field.setEnabled(True)
        self.chat_panel.finish_stream()

        try:
            msg_type = data.get("type", "")
            if msg_type == "saved":
                version_id = data.get("version_id", "")
                version_number = data.get("version_number", 0)
                dj = getattr(self, "_pending_design_json", "{}")
                self.version_map[version_id] = (version_number, dj)
                bub = self.chat_panel.add_message(
                    f"📐 v{version_number} 已保存", "ai", ""
                )
                # 推CAD按钮
                bub.addActionButton(
                    "推CAD", lambda vid=version_id: self._push_to_cad(vid)
                )
                # 渲染预览缩略图（点击预览→右侧大图展示）
                if dj and dj != "{}":
                    pm = self._render_preview_pixmap(dj)
                    if pm:
                        bub.setPreview(
                            pm,
                            lambda vid=version_id: self._show_version_in_preview(vid),
                        )
                self._load_versions()
                self._pending_design_json = None
            elif msg_type == "result":
                self._pending_design_json = data.get("design_json", "{}")
        except Exception as e:
            print(f"[ERROR] _on_ws_result: {e}")
            import traceback

            traceback.print_exc()

    def _on_ws_error(self, error_msg: str):
        self.ws_streaming = False
        self.input_field.setEnabled(True)
        self.chat_panel.finish_stream()
        self._show_error(error_msg)

    # ── 版本 ──

    def _on_version_selected(self, item, column=0):
        """选中版本时更新预览。column 决定取左半（0/1）还是右半（2/3）。"""
        if not item:
            return
        # 点击操作列时，取同行的版本列
        data_col = 0 if column <= 1 else 2
        vid = item.data(data_col, Qt.UserRole)
        if not vid:
            return

        # 清除上一轮高亮 + 标记当前选中
        self._clear_version_highlight()
        self.version_tree._sel_version_id = vid
        self.version_tree.viewport().update()

        # 从缓存获取 design_json
        if vid in self.version_map:
            _, design_json = self.version_map[vid]
            if design_json and design_json != "{}":
                self._update_preview(design_json)
                return

        # 缓存没有或为空 → 从 API 拉取
        try:
            detail = self.api.get_version(vid)
            dj = detail.get("design_json", "")
            self.version_map[vid] = (detail.get("number", 0), dj)
            self._update_preview(dj)
        except Exception as e:
            pass

    def _clear_version_highlight(self):
        """清除所有版本高亮。"""
        self.version_tree._sel_version_id = None
        self.version_tree.viewport().update()

    def _show_version_in_preview(self, vid: str):
        """通过版本 ID 在右侧预览区显示大图。"""
        if vid in self.version_map:
            _, dj = self.version_map[vid]
            if dj and dj != "{}":
                self._update_preview(dj)
                return
        try:
            detail = self.api.get_version(vid)
            dj = detail.get("design_json", "")
            self.version_map[vid] = (detail.get("number", 0), dj)
            self._update_preview(dj)
        except Exception:
            pass

    def _update_preview(self, design_json: str):
        """渲染设计 JSON 到预览区。"""
        try:
            self._do_update_preview(design_json)
        except Exception as e:
            pass

    def _do_update_preview(self, design_json: str):
        self.preview_scene.clear()
        if not design_json:
            return
        try:
            import json

            design = json.loads(design_json)
        except Exception as e:
            return
        buildings = design.get("buildings", [])
        if not buildings:
            return

        # ── 第一遍：计算场景范围 ──
        min_x, min_y, max_x, max_y = (
            float("inf"),
            float("inf"),
            float("-inf"),
            float("-inf"),
        )
        for b in buildings:
            pos = b.get("position", {})
            dims = b.get("dimensions", {})
            bx = pos.get("x", 0)
            by = pos.get("y", 0)
            bw = dims.get("width", 0) or 0
            bh = dims.get("length", 0) or 0
            if bw > 0 and bh > 0:
                min_x = min(min_x, bx)
                min_y = min(min_y, by)
                max_x = max(max_x, bx + bw)
                max_y = max(max_y, by + bh)

        if min_x == float("inf"):
            return

        ref_size = max(max_x - min_x, max_y - min_y)

        # ── 第二遍：带自适应参数渲染 ──
        for b in buildings:
            self._building_to_scene(b, self.preview_scene, ref_size=ref_size)

        # 缩放适配
        pad = ref_size * 0.15
        self.preview_scene.setSceneRect(
            min_x - pad, min_y - pad, max_x - min_x + pad * 2, max_y - min_y + pad * 2
        )
        self.preview_view.fitInView(self.preview_scene.sceneRect(), Qt.KeepAspectRatio)

    def _render_preview_pixmap(self, design_json: str, mw=1080, mh=720):
        """渲染设计 JSON → QPixmap 缩略图（用于对话内嵌预览）。

        默认渲染 2x 分辨率，显示时由 Qt 自动缩放，确保细节清晰。
        """
        try:
            import json

            design = json.loads(design_json)
        except Exception:
            return None
        buildings = design.get("buildings", [])
        if not buildings:
            return None

        # ── 第一遍：计算场景范围，得出 ref_size ──
        min_x, min_y, max_x, max_y = (
            float("inf"),
            float("inf"),
            float("-inf"),
            float("-inf"),
        )
        for b in buildings:
            pos = b.get("position", {})
            dims = b.get("dimensions", {})
            bx = pos.get("x", 0)
            by = pos.get("y", 0)
            bw = dims.get("width", 0) or 0
            bh = dims.get("length", 0) or 0
            if bw > 0 and bh > 0:
                min_x = min(min_x, bx)
                min_y = min(min_y, by)
                max_x = max(max_x, bx + bw)
                max_y = max(max_y, by + bh)
        if min_x == float("inf"):
            return None

        ref_size = max(max_x - min_x, max_y - min_y)

        # ── 第二遍：带自适应参数渲染 ──
        scene = QGraphicsScene()
        for b in buildings:
            self._building_to_scene(b, scene, ref_size=ref_size)

        pad = ref_size * 0.12
        scene_rect = QRectF(
            min_x - pad, min_y - pad, max_x - min_x + pad * 2, max_y - min_y + pad * 2
        )
        scene.setSceneRect(scene_rect)

        # 渲染到 pixmap
        pm = QPixmap(mw, mh)
        pm.fill(QColor(PALETTE["bg"]))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        scene.render(p, QRectF(0, 0, mw, mh), scene_rect, Qt.KeepAspectRatio)
        p.end()
        return pm

    def _building_to_scene(self, building: dict, scene=None, ref_size: float = 60):
        """建筑 → QGraphicsItems。复用与 cad_engine 相同的坐标逻辑。

        ref_size: 场景参考尺寸（米），线宽/字号据此自适应。
        """
        if scene is None:
            scene = self.preview_scene
        name = building.get("name", "")
        dims = building.get("dimensions", {})
        pos = building.get("position", {})

        x = pos.get("x", 0)
        y = pos.get("y", 0)
        w = dims.get("width", 0) or 0
        h = dims.get("length", 0) or 0
        if w <= 0 or h <= 0:
            return None, 0, 0, 0, 0

        # ── 自适应单位：以 ref_size 为基准，所有线宽/字号成比例 ──
        u = ref_size / 60  # 60m 为标准厂房尺寸，u=1 时为默认粗细

        group = []

        # 外墙
        wall_pen = QPen(QColor("#4F6EF7"), 0.15 * u)
        wall_pen.setJoinStyle(Qt.MiterJoin)
        rect = scene.addRect(
            QRectF(x, y, w, h),
            wall_pen,
            QBrush(QColor(79, 110, 247, 25)),
        )
        group.append(rect)

        # 建筑名（居中于建筑上方外侧）
        if name:
            font = QFont("sans-serif", max(6, int(10 * u)))
            font.setWeight(QFont.Bold)
            text = scene.addText(name, font)
            text.setDefaultTextColor(QColor("#E5E5EA"))
            tw = text.boundingRect().width()
            # 放在建筑顶部居中
            text.setPos(x + w / 2 - tw / 2, y - 2.5 * u)
            group.append(text)

        # 尺寸标注（建筑下方外侧）
        dim_font = QFont("monospace", max(5, int(7 * u)))
        dim_text = scene.addText(f"{w:.0f}m × {h:.0f}m", dim_font)
        dim_text.setDefaultTextColor(QColor("#636368"))
        dw = dim_text.boundingRect().width()
        dim_text.setPos(x + w / 2 - dw / 2, y + h + 0.5 * u)
        group.append(dim_text)

        # 区域划分 (zones)
        for zone in building.get("zones", []):
            zdims = zone.get("dimensions", {})
            zw = zdims.get("width", 0) or 0
            zl = zdims.get("length", 0) or 0
            if zw <= 0 or zl <= 0:
                continue
            zpos = zone.get("position", "").lower()
            zx, zy = self._zone_pos(zpos, x, y, w, h, zw, zl)
            zpen = QPen(QColor("#F9A825"), 0.1 * u, Qt.DashLine)
            zr = scene.addRect(
                QRectF(zx, zy, zw, zl),
                zpen,
                QBrush(QColor(249, 168, 37, 18)),
            )
            group.append(zr)
            zn = zone.get("name", "")
            if zn:
                zfont = QFont("sans-serif", max(4, int(8 * u)))
                zt = scene.addText(zn, zfont)
                zt.setDefaultTextColor(QColor(249, 168, 37))
                ztw = zt.boundingRect().width()
                zth = zt.boundingRect().height()
                zt.setPos(zx + zw / 2 - ztw / 2, zy + zl / 2 - zth / 2)
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
                dpen = QPen(QColor("#F9A825"), 0.1 * u, Qt.DashLine)
                dr = scene.addRect(
                    QRectF(dx, dy, dw, dl),
                    dpen,
                    QBrush(QColor(249, 168, 37, 18)),
                )
                group.append(dr)
                dname = d_info.get("name", "")
                if dname:
                    dfont = QFont("sans-serif", max(4, int(8 * u)))
                    dt = scene.addText(dname, dfont)
                    dt.setDefaultTextColor(QColor(249, 168, 37))
                    dtw = dt.boundingRect().width()
                    dth = dt.boundingRect().height()
                    dt.setPos(dx + dw / 2 - dtw / 2, dy + dl / 2 - dth / 2)
                    group.append(dt)

        # 房间
        for room in building.get("rooms", []):
            rx = room.get("x", 0) or 0
            ry = room.get("y", 0) or 0
            rw = room.get("width", 0) or 0
            rl = room.get("length", 0) or 0
            rname = room.get("name", "")
            if rw <= 0 or rl <= 0:
                continue
            rpen = QPen(QColor(123, 140, 255, 100), 0.08 * u, Qt.DashLine)
            rr = scene.addRect(
                QRectF(x + rx, y + ry, rw, rl),
                rpen,
            )
            group.append(rr)

            # 房间名（居中）
            if rname:
                # 字号根据房间尺寸自适应：最小不小于 4pt，不超过房间短边的 1/4
                r_short = min(rw, rl)
                rfont_size = max(4, min(int(r_short * 0.25), int(8 * u)))
                rfont = QFont("sans-serif", rfont_size)
                rt = scene.addText(rname, rfont)
                rt.setDefaultTextColor(QColor(200, 200, 210, 180))
                rtw = rt.boundingRect().width()
                rth = rt.boundingRect().height()
                rt.setPos(x + rx + rw / 2 - rtw / 2, y + ry + rl / 2 - rth / 2)
                group.append(rt)

            # 房间面积（房间名下方）
            area_m2 = rw * rl
            area_font = QFont("monospace", max(3, int(5 * u)))
            at = scene.addText(f"{area_m2:.0f}m²", area_font)
            at.setDefaultTextColor(QColor(99, 99, 104))
            atw = at.boundingRect().width()
            ath = at.boundingRect().height()
            at.setPos(x + rx + rw / 2 - atw / 2, y + ry + rl / 2 + 1.5 * u)
            group.append(at)

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
            # 两两配对，每行两个版本
            for i in range(0, len(versions), 2):
                v1 = versions[i]
                # 确保 version_map 中有 v1
                self._cache_version(v1)

                item = QTreeWidgetItem(self.version_tree)
                item.setSizeHint(0, QSize(0, 40))

                # 第一对（列0-1）
                item.setText(0, f"v{v1['number']}")
                item.setData(0, Qt.UserRole, v1["id"])
                item.setTextAlignment(0, Qt.AlignCenter)
                item.setToolTip(0, f"v{v1['number']} — {v1.get('description', '')}")
                self._set_version_btn(item, 1, v1["id"])

                # 第二对（列2-3）
                if i + 1 < len(versions):
                    v2 = versions[i + 1]
                    self._cache_version(v2)
                    item.setText(2, f"v{v2['number']}")
                    item.setData(2, Qt.UserRole, v2["id"])
                    item.setTextAlignment(2, Qt.AlignCenter)
                    item.setToolTip(2, f"v{v2['number']} — {v2.get('description', '')}")
                    self._set_version_btn(item, 3, v2["id"])
        except Exception as e:
            return
            self._show_error(f"加载版本失败: {e}")
        else:
            # 自动选中最新版本并更新预览
            count = self.version_tree.topLevelItemCount()
            if count > 0:
                last = self.version_tree.topLevelItem(count - 1)
                has_v2 = bool(last.data(2, Qt.UserRole))
                col = 2 if has_v2 else 0
                self._on_version_selected(last, col)

    def _cache_version(self, v: dict):
        """缓存版本 design_json。"""
        dj = v.get("design_json", "")
        if not dj or dj == "{}":
            if v["id"] not in self.version_map:
                self.version_map[v["id"]] = (v["number"], "")
            else:
                _, existing_dj = self.version_map[v["id"]]
                self.version_map[v["id"]] = (v["number"], existing_dj)
        else:
            self.version_map[v["id"]] = (v["number"], dj)

    def _set_version_btn(self, item: QTreeWidgetItem, col: int, vid: str):
        """在指定列添加推CAD按钮（居中、固定宽度55px）。"""
        btn_w = QWidget()
        btn_layout = QHBoxLayout(btn_w)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()
        btn_cad = QPushButton("推CAD")
        btn_cad.setFixedWidth(55)
        btn_cad.setStyleSheet(
            f"background:{PALETTE['primary']}; color:#fff; font-size:11px; padding:2px 6px;"
        )
        btn_cad.clicked.connect(lambda checked, vid=vid: self._push_to_cad(vid))
        btn_layout.addWidget(btn_cad)
        btn_layout.addStretch()
        self.version_tree.setItemWidget(item, col, btn_w)

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
            self._append_message(
                "assistant", f"📐 已推送到 AutoCAD\n💾 本地: {saved}", version_id
            )

            # 异步上传
            self.dwg_worker = DWGUploadWorker(self.api, version_id, saved)
            self.dwg_worker.finished.connect(
                lambda r: self._append_message("assistant", "☁️ 已同步到服务器")
            )
            self.dwg_worker.error.connect(
                lambda e: self._append_message("assistant", f"⚠️ 同步失败: {e}")
            )
            self.dwg_worker.start()

        except Exception as e:
            return
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
            return

    def _show_error(self, msg: str):
        QMessageBox.warning(self, "错误", msg)


class NewProjectDialog(QDialog):
    """新建项目对话框 — 双栏布局：左边边界选择，右边参考项目。"""

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.selected_boundaries: list = []
        self.selected_ref: str = None

        self.setWindowTitle("新建项目")
        self.setMinimumWidth(900)
        self.setMinimumHeight(500)
        self.setStyleSheet(f"""
        QDialog {{ background:{PALETTE["bg"]}; color:{PALETTE["text"]}; }}
        QLabel {{ color:{PALETTE["text"]}; font-size:13px; }}
        QLineEdit {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:10px; border-radius:6px; font-size:14px; }}
        QPushButton {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:6px 16px; border-radius:4px; font-size:13px; }}
        QPushButton:hover {{ border-color:{PALETTE["primary"]}; }}
        QComboBox {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; border-radius:4px; padding:6px; }}
        QCheckBox {{ color:{PALETTE["text"]}; font-size:13px; spacing:8px; }}
        QScrollArea {{ border:none; background:{PALETTE["panel"]}; border-radius:6px; }}
        QListWidget {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]};
            border:none; font-size:13px; outline:none; }}
        QListWidget::item {{ padding:8px 12px; border-bottom:1px solid {PALETTE["border"]}; }}
        QListWidget::item:hover {{ background:rgba(79,110,247,0.1); }}
        QListWidget::item:selected {{ background:{PALETTE["primary_dim"]}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("新建项目")
        title_label.setStyleSheet("font-size:18px; font-weight:700;")
        title_row.addWidget(title_label)
        title_row.addStretch()
        layout.addWidget(title_bar)

        # 项目名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("项目名称"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例：成都肉制品加工厂")
        name_layout.addWidget(self.title_input, 1)
        layout.addLayout(name_layout)

        # 双栏
        cols = QHBoxLayout()
        cols.setSpacing(12)

        # 左栏：设计边界
        left_col = QVBoxLayout()
        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("设计边界"))
        bound_badge = QLabel("可选，多选")
        bound_badge.setStyleSheet(f"color:{PALETTE['text_faint']}; font-size:11px;")
        left_header.addWidget(bound_badge)
        left_header.addStretch()
        left_col.addLayout(left_header)

        self.bound_search = QLineEdit()
        self.bound_search.setPlaceholderText("搜索边界模板…")
        self.bound_search.textChanged.connect(self._filter_boundaries)
        left_col.addWidget(self.bound_search)

        self.bound_list = QListWidget()
        try:
            for b in api.list_boundaries():
                item = QListWidgetItem(b["name"])
                item.setData(Qt.UserRole, b["id"])
                item.setToolTip(b.get("description", ""))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.bound_list.addItem(item)
        except Exception:
            self.bound_list.addItem("（无法加载）")
        left_col.addWidget(self.bound_list)
        cols.addLayout(left_col)

        # 右栏：参考项目
        right_col = QVBoxLayout()
        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("参考项目"))
        ref_badge = QLabel("可选")
        ref_badge.setStyleSheet(f"color:{PALETTE['text_faint']}; font-size:11px;")
        right_header.addWidget(ref_badge)
        right_header.addStretch()
        right_col.addLayout(right_header)

        self.ref_search = QLineEdit()
        self.ref_search.setPlaceholderText("搜索参考项目…")
        self.ref_search.textChanged.connect(self._filter_refs)
        right_col.addWidget(self.ref_search)

        self.ref_list = QListWidget()
        self.ref_list.addItem("（无）")
        self.ref_list.item(0).setData(Qt.UserRole, None)
        self.ref_list.setCurrentRow(0)
        try:
            for rp in api.list_reference_projects():
                item = QListWidgetItem(rp["title"])
                item.setData(Qt.UserRole, rp["id"])
                self.ref_list.addItem(item)
        except Exception:
            pass
        right_col.addWidget(self.ref_list)
        cols.addLayout(right_col)

        layout.addLayout(cols, 1)

        # 底部提示
        hint = QLabel("不选设计边界 → AI 作为高级 CAD 操作员，无行业限制自由出图")
        hint.setStyleSheet(f"color:{PALETTE['text_faint']}; font-size:12px;")
        layout.addWidget(hint)

        # 按钮
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        self.btn_create = QPushButton("创建项目")
        self.btn_create.setStyleSheet(
            f"background:{PALETTE['primary']}; color:#fff; font-weight:600; padding:8px 24px;"
        )
        self.btn_create.clicked.connect(self._create)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self.btn_create)
        layout.addLayout(btn_row)

    def _filter_boundaries(self, text):
        for i in range(self.bound_list.count()):
            item = self.bound_list.item(i)
            item.setHidden(text.lower() not in item.text().lower() if text else False)

    def _filter_refs(self, text):
        for i in range(self.ref_list.count()):
            item = self.ref_list.item(i)
            item.setHidden(text.lower() not in item.text().lower() if text else False)

    def _create(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            return
        # 收集勾选的边界
        bids = []
        for i in range(self.bound_list.count()):
            item = self.bound_list.item(i)
            if item.checkState() == Qt.Checked:
                bid = item.data(Qt.UserRole)
                if bid:
                    bids.append(bid)
        # 参考项目
        ref_item = self.ref_list.currentItem()
        ref_id = ref_item.data(Qt.UserRole) if ref_item else None
        try:
            self.api.create_project(title, bids, ref_id)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))

    def _style(self):
        return f"""
        QDialog {{ background:{PALETTE["bg"]}; color:{PALETTE["text"]}; }}
        QLineEdit {{ background:{PALETTE["input_bg"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:8px; border-radius:4px; }}
        QPushButton {{ background:{PALETTE["panel"]}; color:{PALETTE["text"]};
            border:1px solid {PALETTE["border"]}; padding:6px 16px; border-radius:4px; }}
        """
