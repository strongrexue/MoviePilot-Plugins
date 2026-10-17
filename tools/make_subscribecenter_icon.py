"""一次性图标生成脚本（生成订阅中心图标）。

用法：
    <宿主 venv 的 python> tools/make_subscribecenter_icon.py

生成 256×256 PNG，写入两处：
- ``icons/subscribecenter.png``          —— 市场索引的图标 URL 指向这里
- ``plugins.v3/subscribecenter/subscribecenter.png`` —— 随插件包分发

视觉：琥珀底色（与插件 plugin_color #F2A93B 一致）+ 白色雷达同心弧 + 扫掠指针，
下方白色「订阅中心」字样。
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
BG = (242, 169, 59)          # #F2A93B，与 plugin_color 一致
INK = (255, 255, 255)
INK_DIM = (255, 255, 255, 150)
CENTER = (SIZE // 2, 108)    # 雷达圆心（略偏上，给文字留位置）

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载可渲染中文的粗体字体。"""
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("未找到可用的中文字体")


def draw_radar(draw: ImageDraw.ImageDraw) -> None:
    """绘制雷达同心弧与扫掠指针。

    弧线用完整半圆（180°–360°）描边，而不是裁剪过的局部弧 ——
    局部弧的端点会落在奇怪的位置、看起来像划痕。
    """
    cx, cy = CENTER
    for radius, width in ((74, 7), (54, 7), (34, 7)):
        draw.arc(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            start=180,
            end=360,
            fill=INK,
            width=width,
        )
    # 圆心实点
    dot = 12
    draw.ellipse((cx - dot, cy - dot, cx + dot, cy + dot), fill=INK)
    # 扫掠指针（右下方向的短径向线）
    angle = math.radians(30)
    draw.line(
        (
            cx + 16 * math.cos(angle),
            cy + 16 * math.sin(angle),
            cx + 76 * math.cos(angle),
            cy + 76 * math.sin(angle),
        ),
        fill=INK,
        width=8,
    )


def main() -> int:
    """生成图标并写入两处路径。"""
    image = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(image)

    # 圆角矩形遮罩：让图标在深色/浅色背景下都干净
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=48, fill=255)

    draw_radar(draw)

    # 底部文字
    font = load_font(42)
    text = "订阅中心"
    box = draw.textbbox((0, 0), text, font=font)
    text_w = box[2] - box[0]
    draw.text(
        ((SIZE - text_w) / 2 - box[0], 186),
        text,
        font=font,
        fill=INK,
    )

    rounded = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    rounded.paste(image, (0, 0), mask)

    repo_root = Path(__file__).resolve().parents[1]
    targets = (
        repo_root / "icons" / "subscribecenter.png",
        repo_root / "plugins.v3" / "subscribecenter" / "subscribecenter.png",
    )
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        rounded.save(target, "PNG", optimize=True)
        print(f"wrote {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
