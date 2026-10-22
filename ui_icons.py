"""运行时绘制的界面图标，避免依赖字体符号。"""

from typing import Literal

import customtkinter as ctk
from PIL import Image, ImageDraw

TransportIcon = Literal['play', 'stop']

# 图标按 24x24 的 viewBox 设计，绘制时放大后缩放，保证小尺寸下边缘平滑
VIEWBOX = 24
SUPERSAMPLE = 4


def render_transport_icon(kind: TransportIcon, color: str, size: int = 64) -> Image.Image:
    """绘制播放/停止图标，返回透明背景的 RGBA 图像。"""
    scale = SUPERSAMPLE * size / VIEWBOX
    canvas = Image.new('RGBA', (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    def point(x: float, y: float) -> tuple[float, float]:
        return x * scale, y * scale

    if kind == 'play':
        draw.polygon([point(8.5, 5), point(20, 12), point(8.5, 19)], fill=color)
    else:
        draw.rounded_rectangle(
            [*point(7, 7), *point(17, 17)],
            radius=2.5 * scale,
            fill=color,
        )

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def transport_icon(kind: TransportIcon, color: str, size: int = 16) -> ctk.CTkImage:
    """返回可直接用于 CTkButton 的图标，size 为逻辑像素。"""
    image = render_transport_icon(kind, color)
    return ctk.CTkImage(light_image=image, size=(size, size))
