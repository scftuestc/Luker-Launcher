"""角色立绘的运行时合成：按显示尺寸缩放、左侧淡出，可选底部座右铭。"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

LEFT_FADE_RATIO = 0.16
SCRIM_HEIGHT_RATIO = 0.24
SCRIM_MAX_ALPHA = 184
MOTTO_BOTTOM_MARGIN = 16
MOTTO_LINE_GAP = 4

MOTTO_FONT_FILES: dict[str, tuple[str, ...]] = {
    '华文行楷': ('STXINGKA.TTF',),
    'STXingkai': ('STXINGKA.TTF',),
    '方正舒体': ('FZSTK.TTF',),
    'FZShuTi': ('FZSTK.TTF',),
    '华文楷体': ('STKAITI.TTF',),
    'STKaiti': ('STKAITI.TTF',),
    '楷体': ('simkai.ttf',),
    'KaiTi': ('simkai.ttf',),
    'Microsoft YaHei UI': ('msyh.ttc', 'msyhbd.ttc'),
    'Microsoft YaHei': ('msyh.ttc', 'msyhbd.ttc'),
}
DEFAULT_FONT_FILES = ('msyh.ttc', 'simhei.ttf')


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


def resolve_motto_font_file(family: str) -> str | None:
    """把 Tk 字体族名映射到可用的字体文件；找不到时返回 None。"""
    candidates = MOTTO_FONT_FILES.get(family, DEFAULT_FONT_FILES)
    for filename in candidates:
        try:
            ImageFont.truetype(filename, 24)
        except OSError:
            continue
        return filename
    return None


def _resize_character(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    if source.size == size:
        return source.convert("RGBA").copy()
    return source.convert("RGBA").resize(size, Image.Resampling.LANCZOS)


def _bottom_scrim_mask(size: tuple[int, int]) -> Image.Image:
    width, height = size
    scrim_height = max(1, round(height * SCRIM_HEIGHT_RATIO))
    top = height - scrim_height
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for y in range(top, height):
        factor = smoothstep((y - top) / max(1, scrim_height - 1))
        draw.line((0, y, width - 1, y), fill=round(SCRIM_MAX_ALPHA * factor))
    return mask


def split_motto_lines(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """把中文座右铭拆成尽量均衡、且每行不超过 max_width 的两行。"""
    if draw.textlength(text, font=font) <= max_width:
        return [text]

    middle = len(text) // 2
    for offset in range(len(text)):
        for index in (middle + offset, middle - offset):
            if 0 < index < len(text):
                left, right = text[:index], text[index:]
                if (
                    draw.textlength(left, font=font) <= max_width
                    and draw.textlength(right, font=font) <= max_width
                ):
                    return [left, right]
    return [text]


def render_character_with_motto(
    source: Image.Image,
    logical_size: tuple[int, int],
    scale: float,
    motto: str,
    font_file: str,
    text_color: str,
    *,
    font_size: int = 15,
    fade_ratio: float = LEFT_FADE_RATIO,
) -> Image.Image:
    """合成立绘、底部渐变底衬和座右铭；返回新图。"""
    width = max(1, round(logical_size[0] * scale))
    height = max(1, round(logical_size[1] * scale))
    art = _resize_character(source, (width, height))

    scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    scrim.putalpha(ImageChops.multiply(_bottom_scrim_mask((width, height)), art.getchannel("A")))
    art = Image.alpha_composite(art, scrim)

    physical_font_size = max(1, round(font_size * scale))
    font = ImageFont.truetype(font_file, physical_font_size)
    draw = ImageDraw.Draw(art)
    margin = round(18 * scale)
    lines = split_motto_lines(motto, draw, font, max(1, width - margin * 2))

    line_height = physical_font_size + round(MOTTO_LINE_GAP * scale)
    bottom_margin = round(MOTTO_BOTTOM_MARGIN * scale)
    start_y = height - bottom_margin - line_height * len(lines)
    stroke_width = max(1, round(scale))
    fill = (*ImageColor.getrgb(text_color), 240)
    stroke_fill = (*ImageColor.getrgb('#06101f'), 210)

    for index, line in enumerate(lines):
        center_y = start_y + index * line_height + line_height // 2
        draw.text(
            (width // 2, center_y),
            line,
            font=font,
            fill=fill,
            anchor="mm",
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    mask = left_fade_mask((width, height), fade_ratio)
    art.putalpha(ImageChops.multiply(art.getchannel("A"), mask))
    return art


def render_character(
    source: Image.Image,
    logical_size: tuple[int, int],
    scale: float,
    fade_ratio: float = LEFT_FADE_RATIO,
) -> Image.Image:
    """按物理像素合成立绘；返回新图，不修改共享的源图。"""
    width = max(1, round(logical_size[0] * scale))
    height = max(1, round(logical_size[1] * scale))
    art = _resize_character(source, (width, height))

    mask = left_fade_mask((width, height), fade_ratio)
    art.putalpha(ImageChops.multiply(art.getchannel("A"), mask))
    return art
