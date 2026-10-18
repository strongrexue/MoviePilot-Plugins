"""生成「详情页 · 今日日历」三个版本的整页效果图。

只画图，不参与插件运行：

    python docs/mockups/page_calendar_mockups.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1440, 980
BG = (18, 18, 28)
CARD = (30, 30, 45)
CARD2 = (38, 38, 56)
BORDER = (58, 58, 82)
TEXT = (236, 236, 244)
DIM = (150, 150, 170)
FAINT = (110, 110, 130)
ACCENT = (255, 193, 7)
GREEN = (74, 222, 128)
ORANGE = (249, 115, 22)
GREY = (156, 163, 175)
PURPLE = (168, 85, 247)
BLUE = (96, 165, 250)

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BD if bold else FONT, size)


def rr(d, box, radius=12, fill=CARD, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def t(d, xy, s, size=15, color=TEXT, bold=False, anchor="la"):
    d.text(xy, s, font=f(size, bold), fill=color, anchor=anchor)


def pill(d, x, y, s, size=13, fg=TEXT, bg=CARD2, bd=None, pad=(14, 7), bold=False):
    ff = f(size, bold)
    tw = d.textlength(s, font=ff)
    w = tw + pad[0] * 2
    h = size + pad[1] * 2
    rr(d, (x, y, x + w, y + h), radius=h // 2, fill=bg, outline=bd)
    d.text((x + pad[0], y + h / 2), s, font=ff, fill=fg, anchor="lm")
    return x + w + 8


def poster(img, d, box, seed=0, radius=8, label=""):
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for yy in range(h):
        r = (48 + seed * 23 + yy * 70 // max(h, 1)) % 110 + 30
        g = (36 + seed * 17 + yy * 40 // max(h, 1)) % 90 + 25
        b = (70 + seed * 11 + yy * 90 // max(h, 1)) % 120 + 45
        gd.line([(0, yy), (w, yy)], fill=(r, g, b))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    img.paste(grad, (x0, y0), mask)
    if radius and label:
        d.text((x0 + 8, y0 + h - 16), label, font=f(12, True), fill=(255, 255, 255))


def badge(d, x, y, s, color, size=12):
    ff = f(size, True)
    tw = d.textlength(s, font=ff)
    rr(d, (x, y, x + tw + 18, y + size + 10), radius=6, fill=color)
    d.text((x + 9, y + (size + 10) / 2), s, font=ff, fill=(20, 20, 26), anchor="lm")
    return x + tw + 26


def page_chrome(d, img, tab: str):
    """顶部标题栏 + 状态卡 + 数据源 chips + tab 栏。"""
    rr(d, (40, 26, 86, 72), radius=12, fill=ACCENT)
    t(d, (63, 49), "胖", 22, (20, 20, 26), True, anchor="mm")
    t(d, (100, 32), "胖虎订阅中心", 21, TEXT, True)
    pill(d, 246, 34, "v1.10.0", 12, (20, 20, 26), ACCENT, bold=True)
    t(d, (102, 60), "发现片源 → 解析身份 → 去重 → 写订阅", 12, DIM)
    pill(d, W - 196, 36, "已启用", 13, GREEN, (30, 46, 34), (60, 90, 66))
    pill(d, W - 300, 36, "今天已写入 17", 13, TEXT, CARD2, BORDER)

    # 状态卡
    cy = 96
    cards = [
        ("今日写入", "17", "上限 30 条", ACCENT),
        ("已启用数据源", "4", "共 4 个 · 全部已实现", BLUE),
        ("今日日历", "5", "电视剧 4 · 电影 1", GREEN),
        ("最近运行", "09:12", "新增 12 · 跳过 5", PURPLE),
    ]
    cw = (W - 80 - 36) // 4
    for i, (label, value, sub, color) in enumerate(cards):
        x = 40 + i * (cw + 12)
        rr(d, (x, cy, x + cw, cy + 78), radius=12, fill=CARD, outline=BORDER)
        rr(d, (x + 12, cy + 14, x + 18, cy + 26), radius=3, fill=color)
        t(d, (x + 26, cy + 13), label, 12, DIM)
        t(d, (x + 14, cy + 33), value, 22, TEXT, True)
        t(d, (x + 14, cy + 58), sub, 11, FAINT)

    # 数据源 chips
    sy = 190
    t(d, (40, sy + 8), "数据源", 12, DIM, True)
    x = 100
    for name, color, text_ in (
        ("TMDB", GREEN, "已启用 · 上次 87 条"),
        ("AniList", GREEN, "已启用 · 上次 42 条"),
        ("豆瓣榜单", GREEN, "已启用 · 上次 118 条"),
        ("热门媒体", GREEN, "已启用 · 上次 30 条"),
    ):
        inner = f"{name}  {text_}"
        x = pill(d, x, sy, inner, 12, TEXT, CARD, BORDER)

    # tab 栏
    ty = 232
    active_cal = tab == "calendar"
    x = 40
    x = pill(d, x, ty, "  日历  ", 14, (20, 20, 26) if active_cal else DIM,
             ACCENT if active_cal else CARD2, None, bold=active_cal)
    pill(d, x, ty, "  发现流水  ", 14, DIM if active_cal else (20, 20, 26),
         CARD2 if active_cal else ACCENT, None, bold=not active_cal)
    t(d, (W - 40 - 250, ty + 9), "日历只显示今天 · 与 MP 日历同源", 12, FAINT)
    return 272


def calendar_header(d, top):
    rr(d, (40, top, W - 40, top + 92), radius=14, fill=CARD, outline=BORDER)
    t(d, (62, top + 16), "今天", 13, DIM)
    t(d, (62, top + 36), "10 月 2 日 周五", 22, TEXT, True)
    x = 320
    for label, fg, bg, bd in (
        ("今日更新 5 部", TEXT, CARD2, BORDER),
        ("已入库 3", GREEN, (28, 42, 32), (60, 90, 66)),
        ("待入库 2", ORANGE, (46, 34, 24), (92, 66, 44)),
        ("洗版中 1", PURPLE, (38, 28, 50), (78, 56, 104)),
    ):
        x = pill(d, x, top + 30, label, 13, fg, bg, bd)
    t(d, (W - 250, top + 34), "刷新于 09:12", 12, FAINT)
    return top + 108


CAL_ITEMS = [
    ("凡人修仙传", "第 196 集", 196, 209, 13, "订阅中", ORANGE, "周六更新"),
    ("完美世界", "第 288 集", 288, 321, 33, "洗版中", PURPLE, "今日更新"),
    ("牧神记", "第 104 集", 104, 110, 6, "订阅中", ORANGE, "今日更新"),
    ("光阴之外", "第 44 集", 44, 52, 8, "已入库", GREEN, "今日更新"),
    ("流浪地球 3", "电影 · 今日首播", 0, 0, 0, "未开始", GREY, "待入库"),
]


def variant_a(img, d, top):
    """A：分组 + 进度条（信息最全）。"""
    y = calendar_header(d, top)
    for group, count in (("电视剧", "4 部"), ("电影 · 今日首播", "1 部")):
        t(d, (40, y), group, 13, DIM, True)
        t(d, (40 + d.textlength(group, font=f(13, True)) + 8, y + 1), count, 11, FAINT)
        y += 24
        items = CAL_ITEMS[:4] if group == "电视剧" else CAL_ITEMS[4:]
        for title, ep, done, total, lack, state, color, tag in items:
            rr(d, (40, y, W - 40, y + 88), radius=12, fill=CARD, outline=BORDER)
            poster(img, d, (52, y + 10, 116, y + 78), seed=len(title))
            t(d, (132, y + 14), title, 17, TEXT, True)
            t(d, (132, y + 40), ep, 13, DIM)
            t(d, (132, y + 62), tag, 12, GREEN if tag == "今日更新" else FAINT)
            px = W - 420
            t(d, (px, y + 16), "已入库", 12, DIM)
            t(d, (px, y + 34), f"{done} / {total}" if total else "—", 16, TEXT, True)
            bw = 150
            rr(d, (px, y + 62, px + bw, y + 70), radius=4, fill=(52, 52, 74))
            if total:
                ratio = min(1.0, done / total)
                rr(d, (px, y + 62, px + max(6, int(bw * ratio)), y + 70), radius=4, fill=GREEN)
            mx = px + bw + 26
            t(d, (mx, y + 16), "缺失", 12, DIM)
            t(d, (mx, y + 34), f"{lack} 集" if total else "—", 16, ORANGE if lack else FAINT, True)
            badge(d, W - 160, y + 18, state, color)
            y += 96
        y += 6
    t(d, (40, y + 2), "日历取自订阅的播出日期字段；点任意一行跳到 MoviePilot 的订阅详情。", 12, FAINT)


def variant_b(img, d, top):
    """B：紧凑列表（一屏看更多）。"""
    y = calendar_header(d, top)
    rr(d, (40, y, W - 40, y + 34), radius=8, fill=CARD2)
    t(d, (56, y + 9), "状态", 11, DIM)
    t(d, (140, y + 9), "剧名", 11, DIM)
    t(d, (560, y + 9), "集数", 11, DIM)
    t(d, (760, y + 9), "已入库", 11, DIM)
    t(d, (980, y + 9), "缺失", 11, DIM)
    t(d, (W - 160, y + 9), "订阅状态", 11, DIM)
    y += 42
    for title, ep, done, total, lack, state, color, tag in CAL_ITEMS:
        rr(d, (40, y, W - 40, y + 52), radius=8, fill=CARD, outline=BORDER)
        dot = GREEN if tag == "今日更新" else ORANGE
        d.ellipse((58, y + 21, 68, y + 31), fill=dot)
        t(d, (78, y + 16), tag, 11, dot)
        t(d, (140, y + 14), title, 15, TEXT, True)
        t(d, (560, y + 16), ep, 13, DIM)
        t(d, (760, y + 14), f"{done} / {total}" if total else "—", 14, TEXT)
        t(d, (980, y + 14), f"{lack} 集" if total else "—", 14, ORANGE if lack else FAINT)
        badge(d, W - 160, y + 12, state, color, 11)
        y += 60
    t(d, (40, y + 4), "紧凑模式：不带海报与进度条，一屏可看 15+ 条，适合手机。", 12, FAINT)


def variant_c(img, d, top):
    """C：海报墙（更像 MP 日历页）。"""
    y = calendar_header(d, top)
    t(d, (40, y), "今日更新与待播", 13, DIM, True)
    y += 24
    per_row = 5
    gap = 14
    cw = (W - 80 - gap * (per_row - 1)) // per_row
    ch = int(cw * 0.62) + 74
    for i, (title, ep, done, total, lack, state, color, tag) in enumerate(CAL_ITEMS):
        row, col = divmod(i, per_row)
        x = 40 + col * (cw + gap)
        yy = y + row * (ch + gap)
        rr(d, (x, yy, x + cw, yy + ch), radius=12, fill=CARD, outline=BORDER)
        poster(img, d, (x + 8, yy + 8, x + cw - 8, yy + 8 + int(cw * 0.56)), seed=i, radius=8,
               label=f"第 {i + 1} 集")
        t(d, (x + 10, yy + 12 + int(cw * 0.56) + 6), title, 14, TEXT, True)
        t(d, (x + 10, yy + 12 + int(cw * 0.56) + 26),
          f"{ep} · {tag}", 11, GREEN if tag == "今日更新" else FAINT)
        badge(d, x + 10, yy + ch - 30, state, color, 11)
        if total:
            t(d, (x + cw - 82, yy + ch - 26), f"{done}/{total}", 11, DIM)
    t(d, (40, y + 2 * (ch + gap) - gap + 6),
      "海报墙：只放海报 + 集数 + 状态，手机上每行 2 个。", 12, FAINT)


def render(variant: str) -> str:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top = page_chrome(d, img, "calendar")
    {"a": variant_a, "b": variant_b, "c": variant_c}[variant](img, d, top)
    out = os.path.join(os.path.dirname(__file__), f"calendar-page-{variant}.png")
    img.save(out)
    return out


if __name__ == "__main__":
    for v in ("a", "b", "c"):
        print("saved", render(v))
