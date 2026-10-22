"""运行时绘制的界面图标，避免依赖字体符号。"""

from functools import lru_cache
from typing import Literal

import customtkinter as ctk
from PIL import Image, ImageDraw

TransportIcon = Literal['play', 'stop']
MenuIcon = Literal['window', 'play', 'stop', 'refresh', 'globe', 'gcl', 'settings', 'power']

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


@lru_cache(maxsize=64)
def _render_menu_icon_cached(kind: MenuIcon, color: str, size: int) -> Image.Image:
    scale = SUPERSAMPLE * size / VIEWBOX
    canvas = Image.new('RGBA', (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    def point(x: float, y: float) -> tuple[float, float]:
        return x * scale, y * scale

    stroke = max(1, round(1.8 * scale))

    if kind == 'play':
        draw.polygon([point(8.5, 5), point(20, 12), point(8.5, 19)], fill=color)
    elif kind == 'stop':
        draw.rounded_rectangle(
            [*point(7, 7), *point(17, 17)],
            radius=2.5 * scale,
            fill=color,
        )
    elif kind == 'window':
        draw.rounded_rectangle(
            [*point(3, 4), *point(21, 20)],
            radius=2.5 * scale,
            outline=color,
            width=stroke,
        )
        draw.line([*point(3, 9.5), *point(21, 9.5)], fill=color, width=stroke)
    elif kind == 'refresh':
        draw.arc(
            [*point(4.5, 4.5), *point(19.5, 19.5)],
            start=40,
            end=320,
            fill=color,
            width=stroke,
        )
        draw.polygon([point(17.5, 3.5), point(21.5, 7.5), point(16.5, 8.5)], fill=color)
    elif kind == 'globe':
        draw.ellipse(
            [*point(3.5, 3.5), *point(20.5, 20.5)],
            outline=color,
            width=stroke,
        )
        draw.line([*point(3.5, 12), *point(20.5, 12)], fill=color, width=stroke)
        draw.ellipse(
            [*point(8.5, 3.5), *point(15.5, 20.5)],
            outline=color,
            width=max(1, stroke - 1),
        )
    elif kind == 'gcl':
        draw.polygon(
            [
                point(13, 2.5),
                point(5.5, 13),
                point(10.5, 13),
                point(9, 21.5),
                point(18.5, 10),
                point(13.5, 10),
            ],
            fill=color,
        )
    elif kind == 'settings':
        for y, knob in ((6.5, 8.5), (12, 16), (17.5, 10)):
            draw.line([*point(3.5, y), *point(20.5, y)], fill=color, width=stroke)
            radius = 2.1
            draw.ellipse(
                [*point(knob - radius, y - radius), *point(knob + radius, y + radius)],
                fill=color,
            )
    else:  # power
        draw.arc(
            [*point(4.5, 5.5), *point(19.5, 20.5)],
            start=300,
            end=240,
            fill=color,
            width=stroke,
        )
        draw.line([*point(12, 2.5), *point(12, 11)], fill=color, width=stroke)

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def render_menu_icon(kind: MenuIcon, color: str, size: int = 64) -> Image.Image:
    """绘制托盘菜单使用的单色图标，返回透明背景的 RGBA 图像。"""
    return _render_menu_icon_cached(kind, color, size)


def menu_icon(kind: MenuIcon, color: str, size: int = 16) -> ctk.CTkImage:
    """返回可直接用于 CTkButton 的单色图标，size 为逻辑像素。"""
    image = render_menu_icon(kind, color)
    return ctk.CTkImage(light_image=image, size=(size, size))
