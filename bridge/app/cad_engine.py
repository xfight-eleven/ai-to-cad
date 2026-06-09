"""AutoCAD 绘制引擎 — pywin32 COM 直控 AutoCAD。

墙体、房间、门窗、标注的精确绘制。
线型、图层、颜色全部精确设置，与人工绘制一致。

支持两种模式：
  1. 实时模式 — 连接正在运行的 AutoCAD，直接绘图
  2. 启动模式 — 自动启动 AutoCAD 并绘图

平台要求：Windows + AutoCAD + pywin32
"""

import json
import os
import sys
from typing import Optional

# pywin32 仅在 Windows 上可用
HAS_PYWIN32 = False
try:
    import win32com.client
    import pywintypes

    HAS_PYWIN32 = True
except ImportError:
    pass

# ── 图层定义（与方案文档一致） ──
LAYERS = {
    "WALL": {"color": 7, "linetype": "Continuous", "lineweight": 50, "description": "外墙轮廓"},
    "ROOM": {"color": 3, "linetype": "Continuous", "lineweight": 35, "description": "房间分隔"},
    "ROOM_NAME": {"color": 2, "linetype": "Continuous", "lineweight": 25, "description": "房间名称"},
    "TEXT": {"color": 2, "linetype": "Continuous", "lineweight": 25, "description": "文字标注"},
    "DIM": {"color": 4, "linetype": "Continuous", "lineweight": 20, "description": "尺寸标注"},
    "WINDOW": {"color": 5, "linetype": "Continuous", "lineweight": 30, "description": "窗户"},
    "DOOR": {"color": 1, "linetype": "Continuous", "lineweight": 30, "description": "门"},
    "HATCH": {"color": 9, "linetype": "Continuous", "lineweight": 15, "description": "填充"},
}

# 毫米转换系数（JSON 中默认单位为米，CAD 中单位为毫米）
SCALE = 1000.0

# 常用线宽（mm → pywin32 内部单位，1 = 0.01mm）
LW_BY_NAME = {50: 50, 35: 35, 30: 30, 25: 25, 20: 20, 15: 15}


class CadEngine:
    """AutoCAD 绘制引擎。"""

    def __init__(self):
        if not HAS_PYWIN32:
            raise RuntimeError(
                "pywin32 未安装。\n"
                "请运行: pip install pywin32\n"
                "注意：桥梁服务仅在 Windows + AutoCAD 环境下运行"
            )
        self.acad = None
        self.doc = None
        self.msp = None

    # ── 连接 AutoCAD ──

    def connect(self, visible: bool = True) -> bool:
        """连接到 AutoCAD。先尝试已有实例，没有则新建。"""
        try:
            self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except (pywintypes.com_error, AttributeError):
            try:
                self.acad = win32com.client.Dispatch("AutoCAD.Application")
            except Exception as e:
                raise RuntimeError(f"无法启动 AutoCAD: {e}")

        self.acad.Visible = visible
        self.doc = self.acad.Documents.Add()
        self.msp = self.doc.ModelSpace

        # 设置绘图单位：毫米
        self.doc.SetVariable("LUNITS", 3)  # 十进制
        self.doc.SetVariable("LUPREC", 2)  # 精度 2 位
        self.doc.SetVariable("INSUNITS", 4)  # 毫米

        self._init_layers()
        return True

    def connect_to_document(self, document) -> bool:
        """连接到指定的文档对象（供启动画面用）。"""
        self.doc = document
        self.msp = document.ModelSpace
        self._init_layers()
        return True

    def _init_layers(self):
        """初始化图层 — 每次绘图都确保图层存在。"""
        for name, props in LAYERS.items():
            layer = None
            try:
                layer = self.doc.Layers.Item(name)
            except Exception:
                layer = self.doc.Layers.Add(name)

            if layer:
                layer.color = props["color"]
                try:
                    layer.Lineweight = props["lineweight"]
                except Exception:
                    pass

    # ── 绘制接口 ──

    def draw_from_json(self, design_json: str, safe_name: str = "设计图"):
        """从 JSON 字符串绘制完整设计方案。"""
        design = json.loads(design_json)
        project_info = design.get("project", design)
        buildings = design.get("buildings", [])

        for building in buildings:
            self._draw_building(building)

        # 缩放至全部对象可见
        self.doc.SendCommand("ZOOM\nE\n")

    def _draw_building(self, building: dict):
        """绘制一个建筑（含内部房间）。"""
        name = building.get("name", "建筑")
        pos = building.get("position", {})
        dims = building.get("dimensions", {})

        bx = pos.get("x", 0) * SCALE
        by = pos.get("y", 0) * SCALE
        bw = dims.get("width", 0) * SCALE
        bh = dims.get("length", 0) * SCALE

        if bw <= 0 or bh <= 0:
            return

        # ── 外墙 ──
        self._draw_wall(bx, by, bw, bh)

        # ── 柱网（可选） ──
        columns = building.get("columns", [])
        for col in columns:
            self._draw_column(bx + col.get("x", 0) * SCALE, by + col.get("y", 0) * SCALE,
                              col.get("width", 0.4) * SCALE, col.get("length", 0.4) * SCALE)

        # ── 房间 ──
        rooms = building.get("rooms", [])
        for room in rooms:
            self._draw_room(room, bx, by, name)

        # ── 建筑名称 ──
        self._draw_text(
            name, bx + bw / 2, by + bh / 2 + SCALE * 0.8,
            height=SCALE * 0.6, layer="TEXT"
        )

        # ── 总尺寸标注 ──
        self._draw_dimensions(bx, by, bw, bh)

    def _draw_wall(self, bx: float, by: float, bw: float, bh: float):
        """绘制外墙（闭合多段线 + 加粗）。"""
        points = [bx, by, bx + bw, by, bx + bw, by + bh, bx, by + bh]
        poly = self.msp.AddLightWeightPolyline(
            self._points_to_array(points)
        )
        poly.Closed = True
        poly.Layer = "WALL"
        # 如果外墙需要双线效果，可添加偏移

    def _draw_column(self, cx: float, cy: float, cw: float, ch: float):
        """绘制柱子（填充矩形）。"""
        pts = [
            cx - cw / 2, cy - ch / 2,
            cx + cw / 2, cy - ch / 2,
            cx + cw / 2, cy + ch / 2,
            cx - cw / 2, cy + ch / 2,
        ]
        poly = self.msp.AddLightWeightPolyline(self._points_to_array(pts))
        poly.Closed = True
        poly.Layer = "WALL"
        # 柱填充
        try:
            hatch = self.msp.AddHatch(0, "SOLID", True)
            hatch.AppendOuterLoop((poly,))
            hatch.Evaluate()
            hatch.Layer = "HATCH"
        except Exception:
            pass

    def _draw_room(self, room: dict, bx: float, by: float, bld_name: str):
        """绘制一个房间。"""
        rx = room.get("x", 0) * SCALE
        ry = room.get("y", 0) * SCALE
        rw = room.get("width", 0) * SCALE
        rh = room.get("length", 0) * SCALE
        rname = room.get("name", "")
        rtype = room.get("type", "")

        if rw <= 0 or rh <= 0:
            return

        ax = bx + rx
        ay = by + ry

        # 房间轮廓
        pts = [ax, ay, ax + rw, ay, ax + rw, ay + rh, ax, ay + rh]
        poly = self.msp.AddLightWeightPolyline(self._points_to_array(pts))
        poly.Closed = True
        poly.Layer = "ROOM"

        # 房间名称（居中）
        if rname:
            self._draw_text(
                rname,
                ax + rw / 2, ay + rh / 2,
                height=min(rw, rh) * 0.3,
                layer="ROOM_NAME"
            )

        # 房间面积标注
        area_m2 = (rw * rh) / (SCALE * SCALE)
        self._draw_text(
            f"{area_m2:.0f}m²",
            ax + rw / 2, ay + rh / 2 - SCALE * 0.3,
            height=SCALE * 0.2,
            layer="DIM"
        )

        # 门（在房间靠外墙位置画门）
        doors = room.get("doors", [])
        for door in doors:
            self._draw_door(bx, by, bw, bh, door)

        # 窗
        windows = room.get("windows", [])
        for win in windows:
            self._draw_window(bx, by, bw, bh, win)

    def _draw_door(self, bx: float, by: float, bw: float, bh: float, door: dict):
        """绘制门。"""
        wall = door.get("wall", "")  # top/bottom/left/right
        pos = door.get("position", 0.5)  # 在墙上的比例位置
        width = door.get("width", 1.0) * SCALE

        dw = width
        dh = width * 0.05

        if wall == "bottom":
            dx = bx + bw * pos
            dy = by - dh / 2
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dx, dy, dx + dw, dy])
            ).Layer = "DOOR"
            # 画门弧
            try:
                arc = self.msp.AddArc(
                    dx + dw, dy + dh, dw, 3.14159, 1.5708
                )
                arc.Layer = "DOOR"
            except Exception:
                pass
        elif wall == "top":
            dx = bx + bw * pos
            dy = by + bh - dh / 2
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dx, dy, dx + dw, dy])
            ).Layer = "DOOR"
        elif wall == "left":
            dx = bx - dh / 2
            dy = by + bh * pos
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dx, dy, dx, dy + dw])
            ).Layer = "DOOR"
        elif wall == "right":
            dx = bx + bw - dh / 2
            dy = by + bh * pos
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dx, dy, dx, dy + dw])
            ).Layer = "DOOR"

    def _draw_window(self, bx: float, by: float, bw: float, bh: float, win: dict):
        """绘制窗户（双线）。"""
        wall = win.get("wall", "")
        pos = win.get("position", 0.5)
        width = win.get("width", 1.5) * SCALE

        ww = width
        wh = SCALE * 0.15

        if wall == "bottom":
            wx = bx + bw * pos
            wy = by - wh / 2
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx, wy, wx + ww, wy])
            ).Layer = "WINDOW"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx, wy + wh, wx + ww, wy + wh])
            ).Layer = "WINDOW"
            # 中间竖线
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx + ww / 2, wy, wx + ww / 2, wy + wh])
            ).Layer = "WINDOW"
        elif wall == "top":
            wx = bx + bw * pos
            wy = by + bh - wh / 2
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx, wy, wx + ww, wy])
            ).Layer = "WINDOW"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx, wy + wh, wx + ww, wy + wh])
            ).Layer = "WINDOW"
        elif wall == "left":
            wx = bx - wh / 2
            wy = by + bh * pos
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx, wy, wx, wy + ww])
            ).Layer = "WINDOW"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx + wh, wy, wx + wh, wy + ww])
            ).Layer = "WINDOW"
        elif wall == "right":
            wx = bx + bw - wh / 2
            wy = by + bh * pos
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx, wy, wx, wy + ww])
            ).Layer = "WINDOW"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([wx + wh, wy, wx + wh, wy + ww])
            ).Layer = "WINDOW"

    def _draw_dimensions(self, bx: float, by: float, bw: float, bh: float):
        """绘制建筑总尺寸标注。"""
        dim_offset = SCALE * 0.5
        text_h = SCALE * 0.25

        # 下方宽度标注
        w_m = bw / SCALE
        dim_y = by - dim_offset
        self._draw_text(f"{w_m:.1f}m", bx + bw / 2, dim_y, height=text_h, layer="DIM")
        # 标注线
        if bw > SCALE:
            self.msp.AddLightWeightPolyline(
                self._points_to_array([bx, dim_y - SCALE * 0.1, bx + bw, dim_y - SCALE * 0.1])
            ).Layer = "DIM"
            # 端点小竖线
            self.msp.AddLightWeightPolyline(
                self._points_to_array([bx, dim_y - SCALE * 0.2, bx, dim_y])
            ).Layer = "DIM"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([bx + bw, dim_y - SCALE * 0.2, bx + bw, dim_y])
            ).Layer = "DIM"

        # 右侧长度标注
        h_m = bh / SCALE
        dim_x = bx + bw + dim_offset
        self._draw_text(f"{h_m:.1f}m", dim_x, by + bh / 2, height=text_h, layer="DIM")
        if bh > SCALE:
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dim_x - SCALE * 0.1, by, dim_x - SCALE * 0.1, by + bh])
            ).Layer = "DIM"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dim_x - SCALE * 0.2, by, dim_x, by])
            ).Layer = "DIM"
            self.msp.AddLightWeightPolyline(
                self._points_to_array([dim_x - SCALE * 0.2, by + bh, dim_x, by + bh])
            ).Layer = "DIM"

    def _draw_text(self, text: str, x: float, y: float, height: float = SCALE * 0.3,
                   layer: str = "TEXT", alignment: int = 1):
        """绘制文字。

        alignment: 1=左对齐, 2=居中, 3=右对齐
        """
        try:
            txt_obj = self.msp.AddText(text, (x, y, 0), height)
            txt_obj.Layer = layer
            # 水平居中
            txt_obj.TextAlignmentPoint = (x, y, 0)
            txt_obj.Alignment = alignment
        except Exception:
            # fallback: 简单文字
            txt_obj = self.msp.AddText(text, (x, y, 0), height)
            txt_obj.Layer = layer

    # ── 辅助 ──

    def _points_to_array(self, points: list) -> list:
        """将 [x1,y1, x2,y2, ...] 转换为 AutoCAD 可用的 Variant。"""
        from win32com.client import VARIANT
        import pythoncom
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, points)
        return arr

    def save_as_dwg(self, filepath: str) -> str:
        """保存当前图纸为 .dwg 文件。"""
        abs_path = os.path.abspath(filepath)
        # AutoCAD 要求使用反斜杠路径
        acad_path = abs_path.replace("/", "\\")
        try:
            # 如果文件已存在，先删除
            if os.path.exists(abs_path):
                os.remove(abs_path)
            self.doc.SaveAs(acad_path)
            return abs_path
        except Exception as e:
            raise RuntimeError(f"保存 DWG 失败: {e}")

    def close(self):
        """断开 AutoCAD 连接。"""
        self.acad = None
        self.doc = None
        self.msp = None
