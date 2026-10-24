"""运行时绘制的界面图标，避免依赖字体符号。"""

from functools import lru_cache
from typing import Literal

import customtkinter as ctk
from PIL import Image, ImageDraw

TransportIcon = Literal['play', 'stop']
MenuIcon = Literal['window', 'play', 'stop', 'refresh', 'globe', 'gcl', 'settings', 'power']
ThemeIcon = Literal['sun', 'moon', 'tree', 'cloud', 'wave', 'rose']
ToolbarIcon = Literal['search', 'trash', 'scroll', 'pause']
THEME_ICON_KINDS: tuple[ThemeIcon, ...] = ('sun', 'moon', 'tree', 'cloud', 'wave', 'rose')

# 图标按 24x24 的 viewBox 设计，绘制时放大后缩放，保证小尺寸下边缘平滑
VIEWBOX = 24
SUPERSAMPLE = 4


@lru_cache(maxsize=16)
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

    stroke = max(1, round(2.0 * scale))

    if kind == 'play':
        draw.polygon([point(7.5, 4.5), point(20.5, 12), point(7.5, 19.5)], fill=color)
    elif kind == 'stop':
        draw.rounded_rectangle(
            [*point(6, 6), *point(18, 18)],
            radius=3 * scale,
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


def menu_icon(kind: MenuIcon, color: str, size: int = 18) -> ctk.CTkImage:
    """返回可直接用于 CTkButton 的单色图标，size 为逻辑像素。"""
    image = render_menu_icon(kind, color)
    return ctk.CTkImage(light_image=image, size=(size, size))


@lru_cache(maxsize=32)
def _render_theme_icon_cached(kind: str, color: str, size: int) -> Image.Image:
    scale = SUPERSAMPLE * size / VIEWBOX
    canvas = Image.new('RGBA', (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    def point(x: float, y: float) -> tuple[float, float]:
        return x * scale, y * scale

    stroke = max(1, round(2.0 * scale))

    if kind == 'moon':
        mask = Image.new('L', canvas.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([*point(3.5, 2.5), *point(20.5, 19.5)], fill=255)
        mask_draw.ellipse([*point(9.5, 0), *point(25.5, 16)], fill=0)
        moon = Image.new('RGBA', canvas.size, color)
        moon.putalpha(mask)
        canvas.alpha_composite(moon)
        draw.ellipse([*point(16.5, 4), *point(18.5, 6)], fill=color)
    elif kind == 'tree':
        draw.line(
            [point(12, 3), point(4.5, 17), point(19.5, 17), point(12, 3)],
            fill=color,
            width=stroke,
            joint='curve',
        )
        draw.line([point(12, 17), point(12, 21.5)], fill=color, width=stroke)
    elif kind == 'cloud':
        draw.arc(
            [*point(2.5, 9.5), *point(11.5, 19.5)], start=180, end=360, fill=color, width=stroke
        )
        draw.arc(
            [*point(6.5, 4.5), *point(17.5, 16.5)], start=180, end=360, fill=color, width=stroke
        )
        draw.arc(
            [*point(12.5, 9.5), *point(21.5, 19.5)], start=180, end=360, fill=color, width=stroke
        )
        draw.line([point(4.5, 18.5), point(19.5, 18.5)], fill=color, width=stroke)
    elif kind == 'wave':
        for top in (9.5, 15):
            draw.line(
                [
                    point(2.5, top),
                    point(6, top - 3),
                    point(9.5, top),
                    point(13, top - 3),
                    point(16.5, top),
                    point(21.5, top - 3),
                ],
                fill=color,
                width=stroke,
                joint='curve',
            )
    elif kind == 'rose':
        draw.arc([*point(4, 3), *point(20, 19)], start=0, end=300, fill=color, width=stroke)
        draw.arc([*point(7, 6), *point(17, 16)], start=120, end=420, fill=color, width=stroke)
        draw.arc([*point(10, 9), *point(14, 13)], start=240, end=540, fill=color, width=stroke)
        draw.line([point(12, 19), point(12, 22)], fill=color, width=stroke)
    else:  # sun
        draw.ellipse([*point(7.5, 7.5), *point(16.5, 16.5)], outline=color, width=stroke)
        for dx, dy in (
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
            (-0.7, -0.7),
            (0.7, -0.7),
            (-0.7, 0.7),
            (0.7, 0.7),
        ):
            draw.line(
                [point(12 + dx * 6.5, 12 + dy * 6.5), point(12 + dx * 9, 12 + dy * 9)],
                fill=color,
                width=stroke,
            )

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def render_theme_icon(kind: str, color: str, size: int = 64) -> Image.Image:
    """绘制主题卡片使用的单色图标，返回透明背景的 RGBA 图像。"""
    return _render_theme_icon_cached(kind, color, size)


def theme_icon(kind: str, color: str, size: int = 18) -> ctk.CTkImage:
    """返回可直接用于 CTkLabel 的主题图标，size 为逻辑像素。"""
    image = render_theme_icon(kind, color)
    return ctk.CTkImage(light_image=image, size=(size, size))


@lru_cache(maxsize=32)
def _render_toolbar_icon_cached(kind: str, color: str, size: int) -> Image.Image:
    scale = SUPERSAMPLE * size / VIEWBOX
    canvas = Image.new('RGBA', (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    def point(x: float, y: float) -> tuple[float, float]:
        return x * scale, y * scale

    stroke = max(1, round(2.0 * scale))

    if kind == 'trash':
        draw.line([point(4, 6.5), point(20, 6.5)], fill=color, width=stroke)
        draw.line([point(9, 3.5), point(9, 6.5)], fill=color, width=stroke)
        draw.line([point(15, 3.5), point(15, 6.5)], fill=color, width=stroke)
        draw.line([point(9, 3.5), point(15, 3.5)], fill=color, width=stroke)
        draw.rounded_rectangle(
            [*point(6, 6.5), *point(18, 21)],
            radius=2 * scale,
            outline=color,
            width=stroke,
        )
        draw.line([point(10, 10), point(10, 17.5)], fill=color, width=stroke)
        draw.line([point(14, 10), point(14, 17.5)], fill=color, width=stroke)
    elif kind == 'scroll':
        draw.line([point(12, 3.5), point(12, 15.5)], fill=color, width=stroke)
        draw.line([point(7, 10.5), point(12, 15.5), point(17, 10.5)], fill=color, width=stroke)
        draw.line([point(6, 19), point(18, 19)], fill=color, width=stroke)
        draw.line([point(8.5, 22), point(15.5, 22)], fill=color, width=stroke)
    elif kind == 'pause':
        draw.rounded_rectangle(
            [*point(7, 4), *point(10.5, 20)],
            radius=1.5 * scale,
            fill=color,
        )
        draw.rounded_rectangle(
            [*point(13.5, 4), *point(17, 20)],
            radius=1.5 * scale,
            fill=color,
        )
    else:  # search
        draw.ellipse([*point(3.5, 3.5), *point(15.5, 15.5)], outline=color, width=stroke)
        draw.line([point(14, 14), point(21, 21)], fill=color, width=stroke)

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def render_toolbar_icon(kind: str, color: str, size: int = 64) -> Image.Image:
    """绘制日志工具栏使用的单色图标，返回透明背景的 RGBA 图像。"""
    return _render_toolbar_icon_cached(kind, color, size)


def toolbar_icon(kind: str, color: str, size: int = 16) -> ctk.CTkImage:
    """返回可直接用于 CTkButton/CTkLabel 的工具栏图标。"""
    image = render_toolbar_icon(kind, color)
    return ctk.CTkImage(light_image=image, size=(size, size))
