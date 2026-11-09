"""角色立绘的运行时合成：按显示尺寸缩放并让左侧 alpha 渐隐。"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

LEFT_FADE_RATIO = 0.16


def smoothstep(value: float) -> float:
    """把 0..1 的线性值转成两端平缓的缓动值。"""
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def left_fade_mask(size: tuple[int, int], fade_ratio: float = LEFT_FADE_RATIO) -> Image.Image:
    """生成左边缘从透明到不透明的水平 alpha 蒙版。"""
    width, height = size
    ratio = max(0.0, min(0.5, fade_ratio))
    fade_width = max(1, round(width * ratio)) if ratio > 0 else 0

    mask = Image.new("L", (width, height), 255)
    if fade_width == 0:
        return mask

    draw = ImageDraw.Draw(mask)
    for x in range(fade_width):
        alpha = round(255 * smoothstep(x / fade_width))
        draw.line((x, 0, x, height - 1), fill=alpha)
    return mask


def render_character(
    source: Image.Image,
    logical_size: tuple[int, int],
    scale: float,
    fade_ratio: float = LEFT_FADE_RATIO,
) -> Image.Image:
    """按物理像素合成立绘；返回新图，不修改共享的源图。"""
    width = max(1, round(logical_size[0] * scale))
    height = max(1, round(logical_size[1] * scale))
    if source.size == (width, height):
        art = source.convert("RGBA").copy()
    else:
        art = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)

    mask = left_fade_mask((width, height), fade_ratio)
    art.putalpha(ImageChops.multiply(art.getchannel("A"), mask))
    return art
