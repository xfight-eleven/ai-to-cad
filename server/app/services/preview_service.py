"""预览图生成 — JSON 设计数据 → SVG。

SVG 优势：
- 矢量无损缩放，天然支持所有几何形状
- 可直接内嵌 HTML，无认证问题
- 浏览器原生渲染，无需 matplotlib 等重依赖
"""

import json
import math


def json_to_svg(design_json: str, width: int = 800, height: int = 500) -> str:
    """JSON 设计数据 → SVG 字符串。

    支持形状：矩形、圆、椭圆、三角形、多边形、路径等。
    """
    design = json.loads(design_json)
    buildings = design.get("buildings", [])

    if not buildings:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="#141517"/><text x="{width/2}" y="{height/2}" fill="#636368" text-anchor="middle" font-size="14">无建筑数据</text></svg>'

    # 计算边界框
    min_x, min_y, max_x, max_y = float("inf"), float("inf"), float("-inf"), float("-inf")
    elements = []

    for building in buildings:
        el_svg, bx, by, bw, bh = _building_to_svg(building)
        if el_svg:
            elements.append(el_svg)
            min_x = min(min_x, bx)
            min_y = min(min_y, by)
            max_x = max(max_x, bx + bw)
            max_y = max(max_y, by + bh)

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = 0, 0, 100, 100

    # 加边距
    pad = max((max_x - min_x), (max_y - min_y)) * 0.1
    vb_x = min_x - pad
    vb_y = min_y - pad
    vb_w = (max_x - min_x) + pad * 2
    vb_h = (max_y - min_y) + pad * 2

    if vb_w <= 0:
        vb_w = 100
    if vb_h <= 0:
        vb_h = 100

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{vb_x} {vb_y} {vb_w} {vb_h}">',
        '<defs>',
        '<pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">',
        '<path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(79,110,247,0.06)" stroke-width="1"/>',
        '</pattern>',
        '</defs>',
        f'<rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="#141517"/>',
        f'<rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="url(#grid)"/>',
        *elements,
        '</svg>',
    ]

    return "\n".join(svg_parts)


def _building_to_svg(building: dict):
    """单个建筑 → SVG 元素。返回 (svg_string, min_x, min_y, width, height)。"""
    name = building.get("name", "建筑")
    shape = str(building.get("shape", "")).lower()
    pos = building.get("position", {"x": 0, "y": 0})
    rooms = building.get("rooms", [])
    dims = building.get("dimensions", {})

    x = pos.get("x", 0)
    y = pos.get("y", 0)

    # 提取尺寸
    w, h = 0, 0
    if isinstance(dims, dict) and dims:
        w = dims.get("width") or dims.get("width_m") or dims.get("w") or 0
        h = dims.get("length") or dims.get("length_m") or dims.get("l") or dims.get("len") or 0
    elif isinstance(dims, str):
        nums = [float(n) for n in dims.replace("×", "x").split() if n.replace(".", "").replace(".", "").isdigit()]
        if nums:
            w = nums[0]
            h = nums[1] if len(nums) > 1 else w

    # 椭圆
    if "ellipse" in shape:
        rx = building.get("radiusX") or w / 2 or 50
        ry = building.get("radiusY") or h / 2 or 30
        cx = x + rx
        cy = y + ry
        el = f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="rgba(79,110,247,0.2)" stroke="#4F6EF7" stroke-width="1.5"/>'
        txt = f'<text x="{cx}" y="{cy + ry + 5}" fill="#98989E" text-anchor="middle" font-size="3" font-family="monospace">{name}</text>'
        return f"{el}\n{txt}", x, y, rx * 2, ry * 2

    # 圆
    if "circle" in shape:
        r = building.get("radius") or max(w, h) / 2 or 50
        cx = x + r
        cy = y + r
        el = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="rgba(79,110,247,0.2)" stroke="#4F6EF7" stroke-width="1.5"/>'
        txt1 = f'<text x="{cx}" y="{cy + r + 5}" fill="#98989E" text-anchor="middle" font-size="3" font-family="monospace">{name} ⌀{r*2}m</text>'
        return f"{el}\n{txt1}", x, y, r * 2, r * 2

    # 三角形
    if "triangle" in shape:
        sl = building.get("side_length") or building.get("sideLength") or w or 100
        th = sl * math.sqrt(3) / 2  # 等边三角形高度
        pts = f"{x + sl/2},{y} {x + sl},{y + th} {x},{y + th}"
        el = f'<polygon points="{pts}" fill="rgba(79,110,247,0.2)" stroke="#4F6EF7" stroke-width="1.5"/>'
        txt = f'<text x="{x + sl/2}" y="{y + th + 5}" fill="#98989E" text-anchor="middle" font-size="3" font-family="monospace">{name} {sl}m</text>'
        return f"{el}\n{txt}", x, y, sl, th

    # 默认：矩形
    if w <= 0:
        w = building.get("width") or building.get("length") or 100
    if h <= 0:
        h = building.get("height") or building.get("length") or w or 100

    rect = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="rgba(79,110,247,0.2)" stroke="#4F6EF7" stroke-width="1.5"/>'
    label = f'<text x="{x + w/2}" y="{y - 2}" fill="#98989E" text-anchor="middle" font-size="3.5" font-family="monospace">{name}</text>'
    dim_label = f'<text x="{x + w/2}" y="{y + h + 4}" fill="#636368" text-anchor="middle" font-size="2.5" font-family="monospace">{w:.0f}m × {h:.0f}m</text>'

    result = f"{rect}\n{label}\n{dim_label}"

    # 房间
    for room in rooms:
        rx = x + (room.get("x", 0) or 0)
        ry = y + (room.get("y", 0) or 0)
        rw = room.get("width", 0) or 0
        rl = room.get("length", 0) or 0
        rname = room.get("name", "")
        if rw > 0 and rl > 0:
            result += f'\n<rect x="{rx}" y="{ry}" width="{rw}" height="{rl}" fill="none" stroke="rgba(123,140,255,0.4)" stroke-dasharray="2,2" stroke-width="0.8"/>'
            if rname:
                result += f'\n<text x="{rx + rw/2}" y="{ry + rl/2}" fill="rgba(229,229,234,0.7)" text-anchor="middle" font-size="2" font-family="sans-serif">{rname}</text>'

    # 区域划分 (zones)
    zones = building.get("zones", [])
    for zone in zones:
        zdims = zone.get("dimensions", {})
        zw = zdims.get("width", 0) or 0
        zl = zdims.get("length", 0) or 0
        zpos = zone.get("position", "").lower()
        zname = zone.get("name", "")
        if zw <= 0 or zl <= 0:
            continue
        # 根据 position 关键字计算坐标
        if "top" in zpos or "up" in zpos:
            zx, zy = x, y
        elif "bottom" in zpos or "down" in zpos:
            zx, zy = x, y + h - zl
        elif "left" in zpos:
            zx, zy = x, y + (h - zl) / 2
        elif "right" in zpos:
            zx, zy = x + w - zw, y + (h - zl) / 2
        else:
            zx, zy = x + (zone.get("x", 0) or 0), y + (zone.get("y", 0) or 0)
        result += f'\n<rect x="{zx}" y="{zy}" width="{zw}" height="{zl}" fill="rgba(249,168,37,0.15)" stroke="#F9A825" stroke-dasharray="3,3" stroke-width="1"/>'
        if zname:
            result += f'\n<text x="{zx + zw/2}" y="{zy + zl/2}" fill="rgba(249,168,37,0.8)" text-anchor="middle" font-size="2.5" font-family="sans-serif">{zname}</text>'

    # 区域划分 (divisions — 以位置为 key 的对象)
    divisions = building.get("divisions", {})
    if isinstance(divisions, dict) and divisions:
        # 检查是否为简单字符串
        for pos_key, d_info in divisions.items():
            if not isinstance(d_info, dict):
                continue
            dname = d_info.get("name", "")
            ddims = d_info.get("dimensions", {})
            if not isinstance(ddims, dict):
                continue
            dw = ddims.get("width", 0) or 0
            dl = ddims.get("height") or ddims.get("length", 0) or 0
            if dw <= 0 or dl <= 0:
                continue
            pkey = pos_key.lower()
            if "top" in pkey or "up" in pkey:
                dx, dy = x, y
            elif "bottom" in pkey or "down" in pkey:
                dx, dy = x, y + h - dl
            elif "left" in pkey:
                dx, dy = x, y + (h - dl) / 2
            elif "right" in pkey:
                dx, dy = x + w - dw, y + (h - dl) / 2
            else:
                dx, dy = x, y
            result += f'\n<rect x="{dx}" y="{dy}" width="{dw}" height="{dl}" fill="rgba(249,168,37,0.15)" stroke="#F9A825" stroke-dasharray="3,3" stroke-width="1"/>'
            if dname:
                result += f'\n<text x="{dx + dw/2}" y="{dy + dl/2}" fill="rgba(249,168,37,0.8)" text-anchor="middle" font-size="2.5" font-family="sans-serif">{dname}</text>'

    return result, x, y, w, h
