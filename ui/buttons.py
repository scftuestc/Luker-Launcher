"""统一的按钮配色、尺寸与创建入口。"""

import tkinter as tk
from collections.abc import Callable
from typing import Literal

import customtkinter as ctk

from ui.theme import mix_color, shade_color

ButtonRole = Literal[
    'primary',
    'secondary',
    'outline',
    'danger_outline',
    'ghost',
    'danger_ghost',
    'danger',
    'menu',
]
FontWeight = Literal['normal', 'bold']

BUTTON_RADIUS: dict[ButtonRole, int] = {
    'primary': 12,
    'secondary': 10,
    'outline': 10,
    'danger_outline': 10,
    'ghost': 8,
    'danger_ghost': 8,
    'danger': 12,
    'menu': 10,
}
BUTTON_HEIGHT: dict[ButtonRole, int] = {
    'primary': 40,
    'secondary': 38,
    'outline': 32,
    'danger_outline': 40,
    'ghost': 32,
    'danger_ghost': 32,
    'danger': 40,
    'menu': 38,
}
BUTTON_FONT_SIZE: dict[ButtonRole, int] = {
    'primary': 14,
    'secondary': 13,
    'outline': 12,
    'danger_outline': 13,
    'ghost': 13,
    'danger_ghost': 13,
    'danger': 14,
    'menu': 13,
}
BUTTON_FONT_WEIGHT: dict[ButtonRole, FontWeight] = {
    'primary': 'bold',
    'secondary': 'normal',
    'outline': 'normal',
    'danger_outline': 'normal',
    'ghost': 'normal',
    'danger_ghost': 'normal',
    'danger': 'bold',
    'menu': 'normal',
}


def button_colors(role: ButtonRole, colors: dict[str, str]) -> dict[str, object]:
    """返回角色对应的 CTkButton 颜色参数。"""
    if role == 'primary':
        return {
            'fg_color': colors['accent'],
            'hover_color': shade_color(colors['accent'], 0.85),
            'text_color': colors['on_accent'],
            'border_width': 0,
        }
    if role == 'secondary':
        return {
            'fg_color': colors['card'],
            'hover_color': colors['card_hover'],
            'text_color': colors['text'],
            'text_color_disabled': colors['text_dim'],
            'border_width': 1,
            'border_color': colors['border'],
        }
    if role == 'outline':
        return {
            'fg_color': 'transparent',
            'hover_color': mix_color(colors['card'], colors['accent'], 0.12),
            'text_color': colors['accent'],
            'text_color_disabled': colors['text_dim'],
            'border_width': 1,
            'border_color': colors['border'],
        }
    if role == 'danger_outline':
        return {
            'fg_color': 'transparent',
            'hover_color': mix_color(colors['card'], colors['error'], 0.14),
            'text_color': colors['text'],
            'text_color_disabled': colors['text_dim'],
            'border_width': 1,
            'border_color': colors['border'],
        }
    if role == 'danger_ghost':
        return {
            'fg_color': 'transparent',
            'hover_color': mix_color(colors['card'], colors['error'], 0.18),
            'text_color': colors['text_dim'],
            'text_color_disabled': colors['text_muted'],
            'border_width': 0,
        }
    if role == 'danger':
        return {
            'fg_color': colors['error'],
            'hover_color': shade_color(colors['error'], 0.85),
            'text_color': colors['bg'],
            'border_width': 0,
        }
    if role == 'menu':
        return {
            'fg_color': 'transparent',
            'hover_color': colors['card_hover'],
            'text_color': colors['text'],
            'border_width': 0,
        }
    return {
        'fg_color': 'transparent',
        'hover_color': colors['card_hover'],
        'text_color': colors['text_dim'],
        'text_color_disabled': colors['text_muted'],
        'border_width': 0,
    }


def make_button(
    parent: tk.Misc,
    role: ButtonRole,
    colors: dict[str, str],
    *,
    text: str = "",
    command: Callable[[], None] | None = None,
    width: int | None = None,
    height: int | None = None,
    corner_radius: int | None = None,
    font_size: int | None = None,
    font_family: str | None = None,
    font_weight: FontWeight | None = None,
    **kwargs: object,
) -> ctk.CTkButton:
    """按统一角色创建按钮；kwargs 透传给 CTkButton。"""
    font = ctk.CTkFont(
        family=font_family,
        size=font_size if font_size is not None else BUTTON_FONT_SIZE[role],
        weight=font_weight if font_weight is not None else BUTTON_FONT_WEIGHT[role],
    )
    options: dict[str, object] = {
        **button_colors(role, colors),
        'text': text,
        'font': font,
        'height': height if height is not None else BUTTON_HEIGHT[role],
        'corner_radius': (corner_radius if corner_radius is not None else BUTTON_RADIUS[role]),
    }
    if width is not None:
        options['width'] = width
    if command is not None:
        options['command'] = command
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)
