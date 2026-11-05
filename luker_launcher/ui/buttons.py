"""统一的按钮配色、尺寸与创建入口。"""

import tkinter as tk
from collections.abc import Callable
from typing import Literal

import customtkinter as ctk

from luker_launcher.theme import mix_color, shade_color
from luker_launcher.ui.tokens import (
    BUTTON_SECONDARY_HEIGHT,
    CONTROL_HEIGHT_MD,
    CONTROL_HEIGHT_XL,
    FONT_BODY,
    FONT_BUTTON_PRIMARY,
    FONT_SMALL,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_CONTROL,
)

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
    'primary': RADIUS_BUTTON,
    'secondary': RADIUS_CARD,
    'outline': RADIUS_CARD,
    'danger_outline': RADIUS_CARD,
    'ghost': RADIUS_CONTROL,
    'danger_ghost': RADIUS_CONTROL,
    'danger': RADIUS_BUTTON,
    'menu': RADIUS_CARD,
}
BUTTON_HEIGHT: dict[ButtonRole, int] = {
    'primary': CONTROL_HEIGHT_XL,
    'secondary': BUTTON_SECONDARY_HEIGHT,
    'outline': CONTROL_HEIGHT_MD,
    'danger_outline': CONTROL_HEIGHT_XL,
    'ghost': CONTROL_HEIGHT_MD,
    'danger_ghost': CONTROL_HEIGHT_MD,
    'danger': CONTROL_HEIGHT_XL,
    'menu': BUTTON_SECONDARY_HEIGHT,
}
BUTTON_FONT_SIZE: dict[ButtonRole, int] = {
    'primary': FONT_BUTTON_PRIMARY,
    'secondary': FONT_BODY,
    'outline': FONT_SMALL,
    'danger_outline': FONT_BODY,
    'ghost': FONT_BODY,
    'danger_ghost': FONT_BODY,
    'danger': FONT_BUTTON_PRIMARY,
    'menu': FONT_BODY,
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
