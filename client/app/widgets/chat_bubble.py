"""豆包风格聊天气泡组件。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

PALETTE = {
    "bg": "#141517",
    "panel": "#1E1F23",
    "text": "#E5E5EA",
    "text_dim": "#98989E",
    "text_faint": "#636368",
    "primary": "#4F6EF7",
    "accent": "#F9A825",
    "border": "#2C2D31",
}


class ChatBubble(QWidget):
    """单个聊天气泡。

    用户消息 → 右对齐，蓝色背景
    AI 消息  → 左对齐，灰暗背景
    支持流式追加文本，可选预览图。
    """

    def __init__(self, text="", role="ai", timestamp="", parent=None):
        super().__init__(parent)
        self.role = role
        self.is_user = role == "user"
        self._full_text = text

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 外层横向：头像 + 内容
        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 3, 20, 3)
        outer.setSpacing(0)

        # 头像
        avatar = QLabel("🧑" if self.is_user else "🤖")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("font-size:18px;")

        # 内容区纵向：头部行 + 可选缩略图
        content_col = QVBoxLayout()
        content_col.setSpacing(6)

        # 头部行：文本 + 可选操作按钮（如"推CAD"）
        self.header_row = QHBoxLayout()
        self.header_row.setSpacing(8)

        # 文本标签（由样式表画圆角背景）
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(540)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        bg = PALETTE["primary"] if self.is_user else PALETTE["panel"]
        tc = "#FFFFFF" if self.is_user else PALETTE["text"]
        self.label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg};
                border-radius: 12px;
                padding: 10px 14px;
                color: {tc};
                font-size: 13px;
            }}
            """
        )
        self.header_row.addWidget(self.label)
        self.header_row.addStretch()

        content_col.addLayout(self.header_row)

        # 预览缩略图（初始隐藏）
        self.preview_label = QLabel()
        self.preview_label.setMaximumWidth(540)
        self.preview_label.setMinimumHeight(1)
        self.preview_label.setStyleSheet(
            f"background:{PALETTE['bg']}; border:1px solid {PALETTE['border']}; border-radius:8px;"
        )
        self.preview_label.setVisible(False)
        content_col.addWidget(self.preview_label)

        # 排列
        if self.is_user:
            outer.addStretch()
            outer.addLayout(content_col)
            outer.addSpacing(8)
            outer.addWidget(avatar)
        else:
            outer.addWidget(avatar)
            outer.addSpacing(8)
            outer.addLayout(content_col)
            outer.addStretch()

    def setText(self, text):
        """设置完整文本（用于历史消息）。"""
        self._full_text = text
        self.label.setText(text)

    def appendText(self, text):
        """流式追加文本。"""
        self._full_text += text
        self.label.setText(self._full_text)

    def setPreview(self, pixmap: QPixmap, click_callback=None):
        """设置版本预览缩略图。click_callback 可选，点击预览时触发。"""
        scaled = pixmap.scaled(400, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setFixedSize(scaled.size())
        self.preview_label.setVisible(True)
        self.preview_label.setCursor(Qt.PointingHandCursor)
        if click_callback:
            self.preview_label.mousePressEvent = lambda ev: click_callback()
        self.updateGeometry()

    def addActionButton(self, text: str, callback) -> QPushButton:
        """在气泡头部右侧添加操作按钮（如"推CAD"）。"""
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"background:{PALETTE['primary']}; color:#fff; "
            f"font-size:11px; padding:4px 10px; border-radius:4px;"
        )
        btn.clicked.connect(callback)
        # 插在 label 和 stretch 之间
        self.header_row.insertWidget(self.header_row.count() - 1, btn)
        return btn


class ChatPanel(QScrollArea):
    """对话面板 — 管理气泡列表、自动滚动到底部。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet(
            f"""
            QScrollArea {{ background:{PALETTE["bg"]}; border:none; }}
            QScrollBar:vertical {{ background:{PALETTE["bg"]}; width:6px; }}
            QScrollBar::handle:vertical {{ background:{PALETTE["text_faint"]};
                border-radius:3px; min-height:30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
            """
        )

        self.content = QWidget()
        self.content.setStyleSheet(f"background:{PALETTE['bg']};")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 8, 0, 8)
        self.content_layout.setSpacing(2)
        self.content_layout.addStretch()  # 撑顶，气泡从底部排列

        self.setWidget(self.content)

        self._streaming_bubble = None

    # ── 公开接口 ──

    def add_message(self, text, role="ai", timestamp="") -> ChatBubble:
        """添加一条完整消息，返回气泡对象。"""
        bubble = ChatBubble(text, role, timestamp)
        self._insert_bubble(bubble)
        self._scroll_to_bottom()
        return bubble

    def start_streaming(self, timestamp="") -> ChatBubble:
        """开始一条流式 AI 消息。"""
        bubble = ChatBubble("", "ai", timestamp)
        self._insert_bubble(bubble)
        self._streaming_bubble = bubble
        return bubble

    def append_stream(self, text: str):
        """追加流式 token 到当前 AI 气泡。"""
        if self._streaming_bubble:
            self._streaming_bubble.appendText(text)
            self._scroll_to_bottom()

    def finish_stream(self):
        """结束流式。"""
        self._streaming_bubble = None

    def clear(self):
        """清除所有消息。"""
        # 保留最后的 stretch
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._streaming_bubble = None

    def count(self) -> int:
        """当前消息数。"""
        return max(0, self.content_layout.count() - 1)  # 减掉 stretch

    # ── 内部 ──

    def _insert_bubble(self, bubble: ChatBubble):
        """在 stretch 之前插入气泡。"""
        idx = self.content_layout.count() - 1  # 插在 stretch 前面
        self.content_layout.insertWidget(idx, bubble)

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, self._do_scroll)

    def _do_scroll(self):
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())
