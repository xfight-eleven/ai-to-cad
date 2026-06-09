"""DXF 导出引擎 — JSON 设计数据 → AutoCAD DXF 文件。

提供基础的墙体/房间/标注导出，快速预览用。
如需精确出图（线型、图层、颜色完全精确），请使用桥梁服务。
"""

import json
import io
import tempfile
import os
import math
from typing import Optional

import ezdxf
from ezdxf.math import Vec2
from ezdxf.enums import TextEntityAlignment


def json_to_dxf(design_json: str, filename: Optional[str] = None) -> bytes:
    """JSON 设计数据 → DXF 文件字节流。

    Args:
        design_json: JSON 字符串（设计数据）
        filename: 可选，写入文件路径（为 None 则返回 bytes）

    Returns:
        DXF 文件内容（bytes），可直接下载
    """
    design = json.loads(design_json)

    # 使用 AutoCAD 2010 格式
    doc = ezdxf.new("AC1024")
    doc.header["$LUNITS"] = 3  # 毫米单位
    doc.header["$INSUNITS"] = 4  # mm

    msp = doc.modelspace()

    # ── 图层定义 ──
    _create_layers(doc)

    # ── 提取项目信息 ──
    project_info = design.get("project", design)
    buildings = design.get("buildings", [])
    scale = 1000  # 米 → 毫米

    # ── 绘制每个建筑 ──
    for building in buildings:
        _draw_building(msp, building, scale)

    # ── 保存 ──
    if filename:
        doc.saveas(filename)
        return b""

    # ezdxf save() 不支持 BytesIO，使用临时文件
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
    try:
        doc.saveas(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp.name)


def _create_layers(doc):
    """创建标准图层。"""
    layers = [
        ("WALL", 7, "Continuous", 50),         # 白/灰，外墙
        ("ROOM", 3, "Continuous", 35),          # 绿，房间分隔
        ("TEXT", 2, "Continuous", 25),          # 黄，文字标注
        ("DIM", 4, "Continuous", 20),           # 青，尺寸标注
        ("WINDOW", 5, "Continuous", 30),        # 蓝，窗户
        ("DOOR", 1, "Continuous", 30),          # 红，门
    ]
    for name, color, linetype, lw in layers:
        layer = doc.layers.new(name, dxfattribs={"color": color, "linetype": linetype})
        # ezdxf lineweight is in 1/100 mm
        layer.dxf.lineweight = lw


def _draw_building(msp, building: dict, scale: float):
    name = building.get("name", "建筑")
    pos = building.get("position", {})
    dims = building.get("dimensions", {})

    bx = pos.get("x", 0) * scale
    by = pos.get("y", 0) * scale
    bw = dims.get("width", 0) * scale
    bh = dims.get("length", 0) * scale

    if bw <= 0 or bh <= 0:
        return

    # ── 外墙 ──
    pts = [
        (bx, by),
        (bx + bw, by),
        (bx + bw, by + bh),
        (bx, by + bh),
    ]
    poly = msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "WALL"})

    # ── 建筑名称 ──
    msp.add_text(
        name,
        dxfattribs={"layer": "TEXT", "height": scale * 0.5},
    ).set_placement(Vec2(bx + bw / 2, by + bh / 2), align=TextEntityAlignment.CENTER)

    # ── 房间 ──
    rooms = building.get("rooms", [])
    for room in rooms:
        _draw_room(msp, room, bx, by, scale, name)

    # ── 尺寸标注（简单示意） ──
    _draw_dimensions(msp, bx, by, bw, bh, scale)


def _draw_room(msp, room: dict, bx: float, by: float, scale: float, bld_name: str):
    rx = room.get("x", 0) * scale
    ry = room.get("y", 0) * scale
    rw = room.get("width", 0) * scale
    rh = room.get("length", 0) * scale
    rname = room.get("name", "")

    if rw <= 0 or rh <= 0:
        return

    # 房间实际坐标（建筑偏移）
    ax = bx + rx
    ay = by + ry

    # ── 房间轮廓 ──
    rpts = [(ax, ay), (ax + rw, ay), (ax + rw, ay + rh), (ax, ay + rh)]
    msp.add_lwpolyline(rpts, close=True, dxfattribs={"layer": "ROOM"})

    # ── 房间名 ──
    if rname:
        msp.add_text(
            rname,
            dxfattribs={"layer": "TEXT", "height": scale * 0.35},
        ).set_placement(Vec2(ax + rw / 2, ay + rh / 2), align=TextEntityAlignment.CENTER)

    # ── 房间面积标注 ──
    area_m2 = (rw * rh) / (scale * scale)
    msp.add_text(
        f"{area_m2:.0f} m²",
        dxfattribs={"layer": "DIM", "height": scale * 0.2},
    ).set_placement(Vec2(ax + rw / 2, ay + rh / 2 - scale * 0.3), align=TextEntityAlignment.CENTER)


def _draw_dimensions(msp, bx, by, bw, bh, scale):
    """绘制简单尺寸标注。"""
    dim_offset = scale * 0.3
    text_height = scale * 0.25

    # 宽度标注（下方）
    w_m = bw / scale
    msp.add_text(
        f"{w_m:.1f}m",
        dxfattribs={"layer": "DIM", "height": text_height},
    ).set_placement(Vec2(bx + bw / 2, by - dim_offset), align=TextEntityAlignment.CENTER)

    # 长度标注（右侧）
    h_m = bh / scale
    msp.add_text(
        f"{h_m:.1f}m",
        dxfattribs={"layer": "DIM", "height": text_height},
    ).set_placement(Vec2(bx + bw + dim_offset, by + bh / 2), align=TextEntityAlignment.MIDDLE_LEFT)
