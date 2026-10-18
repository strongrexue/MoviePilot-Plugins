"""生成「详情页 · 今日日历」效果图（mockup）。

只画图，不参与插件运行。运行：

    python docs/mockups/calendar_tab_mockup.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1440, 940
BG = (18, 18, 28)
CARD = (30, 30, 45)
CARD2 = (36, 36, 54)
BORDER = (58, 58, 82)
TEXT = (236, 236, 244)
DIM = (150, 150, 170)
ACCENT = (255, 193, 7)
GREEN = (74, 222, 128)
ORANGE = (249, 115, 22)
GREY = (156, 163, 175)
PURPLE = (168, 85, 247)

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BD if bold else FONT, size)


def rounded(draw, box, radius=12, fill=CARD, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, s, size=15, color=TEXT, bold=False, anchor="la"):
    draw.text(xy, s, font=font(size, bold), fill=color, anchor=anchor)


def pill(draw, xy, s, size=13, fg=TEXT, bg=CARD2, outline=None, pad=(14, 7), bold=False):
    x, y = xy
    f = font(size, bold)
    tw = draw.textlength(s, font=f)
    w = tw + pad[0] * 2
    h = size + pad[1] * 2
    rounded(draw, (x, y, x + w, y + h), radius=h // 2, fill=bg, outline=outline)
    draw.text((x + pad[0], y + h / 2), s, font=f, fill=fg, anchor="lm")
    return x + w + 8, h


def poster(draw, box, hue_bias=0):
    """画一个占位海报（渐变 + 剧名缩写块）。"""
    x0, y0, x1, y1 = box
    w, h = int(x1 - x0), int(y1 - y0)
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for yy in range(h):
        r = 40 + (yy * 90) // max(h, 1) + hue_bias
        g = 50 + (yy * 40) // max(h, 1)
        b = 90 + (yy * 120) // max(h, 1) - hue_bias
        gd.line([(0, yy), (w, yy)], fill=(max(12, r % 120), max(12, g % 110), max(30, b % 160)))
    rounded_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(rounded_mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=8, fill=255)
    draw._image.paste(grad, (int(x0), int(y0)), rounded_mask)


def badge(draw, x, y, s, color):
    f = font(12, True)
    tw = draw.textlength(s, font=f)
    rounded(draw, (x, y, x + tw + 18, y + 22), radius=6, fill=(*color,))
    draw.text((x + 9, y + 11), s, font=f, fill=(20, 20, 26), anchor="lm")
    return x + tw + 24


def row(draw, y, title, sub, progress, total, lack, state, state_color, air):
    x0, x1 = 96, W - 96
    rounded(draw, (x0, y, x1, y + 96), radius=12, fill=CARD, outline=BORDER)
    poster(draw, (x0 + 12, y + 12, x0 + 12 + 64, y + 12 + 72))
    tx = x0 + 92
    text(draw, (tx, y + 18), title, 17, TEXT, True)
    text(draw, (tx, y + 44), sub, 13, DIM)

    # 播出时间
    text(draw, (tx, y + 66), air, 12, DIM)

    # 已入库进度
    px = x1 - 380
    text(draw, (px, y + 22), "已入库", 12, DIM)
    text(draw, (px, y + 40), f"{progress} / {total}", 16, TEXT, True)
    bar_w = 150
    rounded(draw, (px, y + 68, px + bar_w, y + 76), radius=4, fill=(52, 52, 74))
    ratio = 0 if total == 0 else min(1.0, progress / total)
    if ratio > 0:
        rounded(draw, (px, y + 68, px + max(6, int(bar_w * ratio)), y + 76), radius=4, fill=GREEN)

    # 缺集
    mx = px + bar_w + 26
    text(draw, (mx, y + 22), "缺失", 12, DIM)
    text(draw, (mx, y + 40), f"{lack} 集", 16, ORANGE if lack else DIM, True)

    # 状态徽章
    badge(draw, x1 - 150, y + 20, state, state_color)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw._image = img

    # 顶部标题栏
    rounded(draw, (40, 28, 40 + 46, 28 + 46), radius=12, fill=(*ACCENT,))
    text(draw, (63, 51), "胖", 22, (20, 20, 26), True, anchor="mm")
    text(draw, (102, 38), "胖虎订阅中心", 21, TEXT, True)
    pill(draw, (250, 40), "v1.10.0", 12, (20, 20, 26), ACCENT, bold=True)
    text(draw, (104, 66), "发现片源 → 解析身份 → 去重 → 写订阅", 12, DIM)
    pill(draw, (W - 210, 40), "已启用", 13, GREEN, (30, 46, 34), (60, 90, 66))

    # tab 栏
    ty = 104
    x, _ = pill(draw, (96, ty), "  日历  ", 14, (20, 20, 26), ACCENT, bold=True)
    pill(draw, (x, ty), "  发现流水  ", 14, DIM, CARD2, BORDER)
    text(draw, (W - 96 - 240, ty + 10), "只显示今天 · 与 MP 日历同源", 12, DIM)

    # 今日摘要
    sy = 168
    rounded(draw, (96, sy, W - 96, sy + 92), radius=14, fill=CARD, outline=BORDER)
    text(draw, (118, sy + 18), "今天", 15, DIM)
    text(draw, (118, sy + 40), "10 月 2 日 周五", 22, TEXT, True)
    chips = [("今日更新 5 部", TEXT, CARD2, BORDER), ("已入库 3", GREEN, (28, 42, 32), (60, 90, 66)),
             ("待入库 2", ORANGE, (46, 34, 24), (92, 66, 44)), ("洗版中 1", PURPLE, (38, 28, 50), (78, 56, 104))]
    cx = 380
    for label, fg, bg, bd in chips:
        cx, _ = pill(draw, (cx, sy + 30), label, 13, fg, bg, bd)

    # 分组：电视剧
    gy = 288
    text(draw, (96, gy), "电视剧", 14, DIM, True)
    text(draw, (166, gy + 1), "4 部", 12, (110, 110, 130))
    rows = [
        ("凡人修仙传", "第 196 集 · 周六更新", 196, 209, 13, "订阅中", ORANGE, "19:30 播出"),
        ("完美世界", "第 288 集 · 今日更新", 288, 321, 33, "洗版中", PURPLE, "20:00 播出"),
        ("牧神记", "第 104 集 · 今日更新", 104, 110, 6, "订阅中", ORANGE, "20:30 播出"),
        ("光阴之外", "第 44 集 · 今日更新", 44, 52, 8, "已入库", GREEN, "21:00 播出"),
    ]
    y = gy + 28
    for item in rows:
        row(draw, y, item[0], item[1], item[2], item[3], item[4], item[5], item[6], item[7])
        y += 108

    # 分组：电影 / 待播
    gy2 = y + 8
    text(draw, (96, gy2), "电影 · 今日首播", 14, DIM, True)
    rounded(draw, (96, gy2 + 26, W - 96, gy2 + 26 + 96), radius=12, fill=CARD, outline=BORDER)
    poster(draw, (108, gy2 + 38, 172, gy2 + 110))
    text(draw, (188, gy2 + 44), "流浪地球 3", 17, TEXT, True)
    text(draw, (188, gy2 + 70), "今日 0 点上线 · 尚无资源", 13, DIM)
    badge(draw, W - 246, gy2 + 46, "未开始", GREY)
    text(draw, (W - 246, gy2 + 78), "TG 缓存未命中", 12, DIM)

    # 底部说明
    text(draw, (96, H - 34), "日历数据取自宿主的播出日期字段；点任意一行可直接跳到 MoviePilot 的订阅详情。",
         12, (120, 120, 140))

    out = os.path.join(os.path.dirname(__file__), "calendar-tab-a.png")
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
