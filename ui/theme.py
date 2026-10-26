"""主题预设：颜色、显示名称与设置窗口使用的元数据。"""

import math
from typing import Literal

ThemeColorKey = Literal[
    'bg',
    'card',
    'card_hover',
    'border',
    'text',
    'text_dim',
    'text_muted',
    'accent',
    'on_accent',
    'success',
    'error',
    'warning',
    'info',
]

# 主题图标使用 ui.icons 的 kind 名称（sun/moon/tree/cloud/wave/rose），不再是 emoji
PRESET_THEMES: dict[str, dict[str, str]] = {
    'summer': {
        'name': '夏日暖阳',
        'short_name': '夏日',
        'icon': 'sun',
        'bg': '#14110b',
        'card': '#1e1911',
        'card_hover': '#2a2318',
        'border': '#4a3b22',
        'text': '#fff8e7',
        'text_dim': '#d6bc8a',
        'text_muted': '#a0865a',
        'accent': '#f59e0b',
        'on_accent': '#241603',
        'success': '#22c55e',
        'error': '#ef4444',
        'warning': '#fb923c',
        'info': '#38bdf8',
    },
    'purple_night': {
        'name': '紫罗兰夜',
        'short_name': '紫夜',
        'icon': 'moon',
        'bg': '#13111c',
        'card': '#1a1625',
        'card_hover': '#252131',
        'border': '#3d3654',
        'text': '#f4f0ff',
        'text_dim': '#a599c9',
        'text_muted': '#7a6c9a',
        'accent': '#c084fc',
        'on_accent': '#ffffff',
        'success': '#4ade80',
        'error': '#f87171',
        'warning': '#fbbf24',
        'info': '#a78bfa',
    },
    'forest_green': {
        'name': '森林绿意',
        'short_name': '森林',
        'icon': 'tree',
        'bg': '#0f1610',
        'card': '#161f18',
        'card_hover': '#1e2a21',
        'border': '#2d4033',
        'text': '#e8f5e9',
        'text_dim': '#9cbc9e',
        'text_muted': '#6a8a6c',
        'accent': '#4ade80',
        'on_accent': '#ffffff',
        'success': '#22c55e',
        'error': '#ef4444',
        'warning': '#eab308',
        'info': '#34d399',
    },
    'mist_gray': {
        'name': '雾灰静谧',
        'short_name': '雾灰',
        'icon': 'cloud',
        'bg': '#aeb3b9',
        'card': '#c9ced3',
        'card_hover': '#bcc2c8',
        'border': '#878e96',
        'text': '#171b1f',
        'text_dim': '#343b42',
        'text_muted': '#4f575f',
        'accent': '#475569',
        'on_accent': '#ffffff',
        'success': '#14532d',
        'error': '#991b1b',
        'warning': '#7c2d12',
        'info': '#1e40af',
    },
    'ocean_cyan': {
        'name': '深海青碧',
        'short_name': '海洋',
        'icon': 'wave',
        'bg': '#0c1415',
        'card': '#121e1f',
        'card_hover': '#1a2a2c',
        'border': '#2a4245',
        'text': '#e0f7fa',
        'text_dim': '#80cbc4',
        'text_muted': '#4db6ac',
        'accent': '#22d3ee',
        'on_accent': '#ffffff',
        'success': '#2dd4bf',
        'error': '#f87171',
        'warning': '#fbbf24',
        'info': '#22d3ee',
    },
    'crimson': {
        'name': '玫瑰烈焰',
        'short_name': '玫瑰',
        'icon': 'rose',
        'bg': '#160b0e',
        'card': '#211014',
        'card_hover': '#2e171d',
        'border': '#4d2530',
        'text': '#fff1f2',
        'text_dim': '#d9a5ad',
        'text_muted': '#a8747d',
        'accent': '#e11d48',
        'on_accent': '#ffffff',
        'success': '#4ade80',
        'error': '#fb7185',
        'warning': '#fbbf24',
        'info': '#f472b6',
    },
}

DEFAULT_THEME = 'summer'

# 主题卡片四个色块取用的调色板角色；'deep' 表示 accent 的深色版本。
# 单独成表，避免新增主题时还要改 theme_swatch_colors 的分支。
SwatchKey = Literal['accent', 'text_dim', 'success', 'info', 'warning', 'error', 'deep']
THEME_SWATCH_KEYS: dict[str, tuple[SwatchKey, SwatchKey, SwatchKey, SwatchKey]] = {
    'summer': ('accent', 'text_dim', 'deep', 'info'),
    'purple_night': ('accent', 'text_dim', 'deep', 'warning'),
    'forest_green': ('accent', 'text_dim', 'deep', 'warning'),
    'mist_gray': ('accent', 'success', 'info', 'warning'),
    'ocean_cyan': ('accent', 'deep', 'warning', 'error'),
    'crimson': ('accent', 'text_dim', 'info', 'warning'),
}

# 旧版本保存的主题 ID -> 当前 ID；读取配置时迁移
LEGACY_THEME_ALIASES: dict[str, str] = {
    'deep_blue': 'summer',
    'rose_pink': 'crimson',
    'cloud_gray': 'mist_gray',
    'warm_orange': 'mist_gray',
    'bright_white': 'mist_gray',
}

# 启动器 logo 的四条竖条基础颜色；动画按亮度在基色与暗色之间摆动
LOGO_BAR_RGB = (
    (0xFF, 0x6B, 0x6B),
    (0xFE, 0xCA, 0x57),
    (0x48, 0xDB, 0xFB),
    (0x2E, 0xCC, 0x71),
)
LOGO_BAR_COLORS = tuple(f'#{r:02x}{g:02x}{b:02x}' for r, g, b in LOGO_BAR_RGB)
# Luker 未就绪/停止时 logo 的统一灰色，与系统托盘图标一致
LOGO_STOPPED_COLOR = '#6e7681'
# 日志窗口与托盘菜单共用同一套呼吸节奏：约 1.67 秒一个完整周期
LOGO_GLOW_STEP = 0.03
LOGO_GLOW_INTERVAL_MS = 50


def logo_bar_brightness(
    index: int,
    phase: float,
    *,
    center: float = 0.7,
    amplitude: float = 0.3,
) -> float:
    """返回第 index 根 logo 竖条在给定相位下的亮度系数。"""
    bar_phase = (phase + index * 0.25) % 1.0
    return center + amplitude * math.sin(bar_phase * 2 * math.pi)


def blend_color(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    factor: float,
) -> str:
    """按 factor 从 start 插值到 end，返回 #rrggbb；factor 限制在 0..1。"""
    factor = max(0.0, min(1.0, factor))
    red = int(start[0] + (end[0] - start[0]) * factor)
    green = int(start[1] + (end[1] - start[1]) * factor)
    blue = int(start[2] + (end[2] - start[2]) * factor)
    return f"#{red:02x}{green:02x}{blue:02x}"


def logo_bar_glow_color(index: int, phase: float) -> str:
    """返回 Luker logo 第 index 根柱在给定相位下的呼吸颜色。

    亮度在 0.4 到 1.0 之间摆动：暗部与亮部差距足够大，
    4px 宽的竖条也能看出呼吸，而不是在两组非常接近的颜色间微调。
    """
    brightness = logo_bar_brightness(index, phase)
    return shade_color(LOGO_BAR_COLORS[index], brightness)


def _parse_hex_color(color: str) -> tuple[int, int, int] | None:
    """解析 #RRGGBB；格式或取值非法时返回 None。"""
    if len(color) != 7 or not color.startswith('#'):
        return None
    try:
        red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        return None
    return red, green, blue


def is_light_color(color: str) -> bool:
    """判断 #RRGGBB 是否为浅色；用于选择窗口的模糊方式。"""
    rgb = _parse_hex_color(color)
    if rgb is None:
        return False
    channels = (channel / 255 for channel in rgb)
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return luminance > 0.5


def get_theme_colors(name: str) -> dict[str, str]:
    """返回主题颜色副本；主题名无效时使用默认主题。"""
    theme = PRESET_THEMES.get(name, PRESET_THEMES[DEFAULT_THEME])
    return theme.copy()


def theme_swatch_colors(name: str) -> tuple[str, str, str, str]:
    """返回主题卡片展示的四个特征色：主色、浅色、深色与点缀色。"""
    effective = name if name in PRESET_THEMES else DEFAULT_THEME
    colors = get_theme_colors(effective)
    keys = THEME_SWATCH_KEYS.get(effective, THEME_SWATCH_KEYS[DEFAULT_THEME])
    deep = shade_color(colors['accent'], 0.6)

    def resolve(key: SwatchKey) -> str:
        return deep if key == 'deep' else colors[key]

    return resolve(keys[0]), resolve(keys[1]), resolve(keys[2]), resolve(keys[3])


def shade_color(color: str, factor: float) -> str:
    """按比例调暗或调亮 #RRGGBB；factor 小于 1 调暗，大于 1 调亮。"""
    rgb = _parse_hex_color(color)
    if rgb is None:
        return color
    channels = (max(0, min(255, round(channel * factor))) for channel in rgb)
    return '#{:02x}{:02x}{:02x}'.format(*channels)


def mix_color(base: str, overlay: str, ratio: float) -> str:
    """按 ratio 把 overlay 混入 base，返回 #rrggbb；用于柔和的悬停底色。"""
    base_rgb = _parse_hex_color(base)
    overlay_rgb = _parse_hex_color(overlay)
    if base_rgb is None or overlay_rgb is None:
        return base

    factor = max(0.0, min(1.0, ratio))
    channels = (
        round(start + (end - start) * factor)
        for start, end in zip(base_rgb, overlay_rgb, strict=True)
    )
    return '#{:02x}{:02x}{:02x}'.format(*channels)
