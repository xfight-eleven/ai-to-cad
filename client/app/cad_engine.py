"""AutoCAD 绘制引擎 — 从桌面客户端直接控制 AutoCAD。

平台要求：Windows + AutoCAD + pywin32
在 macOS 上导入不会报错，但调用 connect() 会抛出 RuntimeError。
"""

import json
import os
import sys
from typing import Optional

HAS_PYWIN32 = False
try:
    import win32com.client
    import pywintypes
    HAS_PYWIN32 = True
except ImportError:
    pass

SCALE = 1000.0  # JSON 中单位为米，CAD 中单位为毫米

LAYERS = {
    "WALL":       {"color": 7, "description": "外墙"},
    "ROOM":       {"color": 3, "description": "房间分隔"},
    "ROOM_NAME":  {"color": 2, "description": "房间名称"},
    "TEXT":       {"color": 2, "description": "文字"},
    "DIM":        {"color": 4, "description": "尺寸标注"},
    "WINDOW":     {"color": 5, "description": "窗"},
    "DOOR":       {"color": 1, "description": "门"},
    "HATCH":      {"color": 9, "description": "填充"},
    "ZONE":       {"color": 200, "description": "分区线"},
    "ZONE_TEXT":  {"color": 200, "description": "分区名"},
}


class CadEngine:
    """桌面端 AutoCAD 控制引擎。"""

    def __init__(self):
        self.acad = None
        self.doc = None
        self.msp = None

    def connect(self, visible: bool = True):
        """连接 AutoCAD 并新建文档。"""
        if not HAS_PYWIN32:
            raise RuntimeError("pywin32 未安装，仅在 Windows 环境下可用")
        try:
            self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except (pywintypes.com_error, AttributeError):
            self.acad = win32com.client.Dispatch("AutoCAD.Application")
        self.acad.Visible = visible
        self.doc = self.acad.ActiveDocument
        if self.doc is None:
            self.doc = self.acad.Documents.Add()
        self.msp = self.doc.ModelSpace
        self.doc.SetVariable("LUNITS", 3)
        self.doc.SetVariable("LUPREC", 2)
        self.doc.SetVariable("INSUNITS", 4)
        self._init_layers()

    def _init_layers(self):
        for name, props in LAYERS.items():
            try:
                layer = self.doc.Layers.Item(name)
            except Exception:
                layer = self.doc.Layers.Add(name)
                layer.color = props["color"]

    def draw_from_json(self, design_json: str):
        """从 JSON 设计数据绘制到 AutoCAD。"""
        design = json.loads(design_json)
        buildings = design.get("buildings", [])
        for b in buildings:
            self._draw_building(b)
        self.doc.SendCommand("ZOOM\nE\n")

    def _draw_building(self, building: dict):
        name = building.get("name", "建筑")
        pos = building.get("position", {})
        dims = building.get("dimensions", {})

        bx = pos.get("x", 0) * SCALE
        by = pos.get("y", 0) * SCALE
        bw = dims.get("width", 0) * SCALE
        bh = dims.get("length", 0) * SCALE
        if bw <= 0 or bh <= 0:
            return

        # 外墙
        pts = [bx, by, bx + bw, by, bx + bw, by + bh, bx, by + bh]
        poly = self.msp.AddLightWeightPolyline(self._varray(pts))
        poly.Closed = True
        poly.Layer = "WALL"

        # 建筑名
        self._text(name, bx + bw / 2, by + bh / 2 + SCALE * 0.6,
                   SCALE * 0.5, "TEXT")
        # 尺寸
        self._text(f"{bw/SCALE:.1f}m × {bh/SCALE:.1f}m",
                   bx + bw / 2, by + bh / 2 - SCALE * 0.4,
                   SCALE * 0.3, "DIM")

        # 房间
        for room in building.get("rooms", []):
            self._draw_room(room, bx, by)

        # 区域划分 (zones)
        for zone in building.get("zones", []):
            self._draw_zone(zone, bx, by, bw, bh)

        # 区域划分 (divisions — 早期格式兼容)
        divisions = building.get("divisions", {})
        if isinstance(divisions, dict):
            for pos_key, d_info in divisions.items():
                if isinstance(d_info, dict):
                    ddims = d_info.get("dimensions", {})
                    zw = ddims.get("width", 0) * SCALE
                    zl = (ddims.get("height") or ddims.get("length", 0)) * SCALE
                    zx, zy = self._zone_pos(pos_key, bx, by, bw, bh, zw, zl)
                    zname = d_info.get("name", pos_key)
                    self._draw_zone_box(zx, zy, zw, zl, zname)

    def _draw_room(self, room: dict, bx: float, by: float):
        rx = room.get("x", 0) * SCALE
        ry = room.get("y", 0) * SCALE
        rw = room.get("width", 0) * SCALE
        rh = room.get("length", 0) * SCALE
        if rw <= 0 or rh <= 0:
            return
        pts = [bx + rx, by + ry, bx + rx + rw, by + ry,
               bx + rx + rw, by + ry + rh, bx + rx, by + ry + rh]
        poly = self.msp.AddLightWeightPolyline(self._varray(pts))
        poly.Closed = True
        poly.Layer = "ROOM"
        rn = room.get("name", "")
        if rn:
            self._text(rn, bx + rx + rw / 2, by + ry + rh / 2,
                       min(rw, rh) * 0.3, "ROOM_NAME")

    def _draw_zone(self, zone: dict, bx: float, by: float, bw: float, bh: float):
        zdims = zone.get("dimensions", {})
        zw = zdims.get("width", 0) * SCALE
        zl = zdims.get("length", 0) * SCALE
        if zw <= 0 or zl <= 0:
            return
        zpos = zone.get("position", "").lower()
        zx, zy = self._zone_pos(zpos, bx, by, bw, bh, zw, zl)
        zname = zone.get("name", "")
        self._draw_zone_box(zx, zy, zw, zl, zname)

    def _zone_pos(self, pos_key: str, bx, by, bw, bh, zw, zl):
        p = pos_key.lower()
        if "top" in p or "up" in p:
            return bx, by
        elif "bottom" in p or "down" in p:
            return bx, by + bh - zl
        elif "left" in p:
            return bx, by + (bh - zl) / 2
        elif "right" in p:
            return bx + bw - zw, by + (bh - zl) / 2
        return bx, by

    def _draw_zone_box(self, zx, zy, zw, zl, name):
        pts = [zx, zy, zx + zw, zy, zx + zw, zy + zl, zx, zy + zl]
        poly = self.msp.AddLightWeightPolyline(self._varray(pts))
        poly.Closed = True
        poly.Layer = "ZONE"
        poly.Linetype = "DASHED"
        try:
            poly.LinetypeScale = 0.5
        except Exception:
            pass
        if name:
            self._text(name, zx + zw / 2, zy + zl / 2,
                       min(zw, zl) * 0.25, "ZONE_TEXT")

    def _text(self, text, x, y, h, layer):
        txt = self.msp.AddText(text, (x, y, 0), h)
        txt.Layer = layer
        txt.Alignment = 2  # 居中
        txt.TextAlignmentPoint = (x, y, 0)

    def _varray(self, points):
        from win32com.client import VARIANT
        import pythoncom
        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, points)

    def save_as_dwg(self, filepath: str) -> str:
        abs_path = os.path.abspath(filepath)
        acad_path = abs_path.replace("/", "\\")
        if os.path.exists(abs_path):
            os.remove(abs_path)
        self.doc.SaveAs(acad_path)
        return abs_path

    def close(self):
        self.acad = None
        self.doc = None
        self.msp = None
