"""主题预设：颜色、显示名称与设置窗口使用的元数据。"""

PRESET_THEMES: dict[str, dict[str, str]] = {
    'deep_blue': {
        'name': '深蓝夜空',
        'short_name': '深蓝',
        'icon': '🌊',
        'bg': '#0d1117',
        'card': '#161b22',
        'card_hover': '#21262d',
        'border': '#30363d',
        'text': '#f0f6fc',
        'text_dim': '#8b949e',
        'text_muted': '#6e7681',
        'accent': '#22d3ee',
        'accent_blue': '#58a6ff',
        'success': '#3fb950',
        'error': '#f85149',
        'warning': '#d29922',
        'info': '#58a6ff',
    },
    'purple_night': {
        'name': '紫罗兰夜',
        'short_name': '紫夜',
        'icon': '🔮',
        'bg': '#13111c',
        'card': '#1a1625',
        'card_hover': '#252131',
        'border': '#3d3654',
        'text': '#f4f0ff',
        'text_dim': '#a599c9',
        'text_muted': '#7a6c9a',
        'accent': '#c084fc',
        'accent_blue': '#a78bfa',
        'success': '#4ade80',
        'error': '#f87171',
        'warning': '#fbbf24',
        'info': '#a78bfa',
    },
    'forest_green': {
        'name': '森林绿意',
        'short_name': '森林',
        'icon': '🌲',
        'bg': '#0f1610',
        'card': '#161f18',
        'card_hover': '#1e2a21',
        'border': '#2d4033',
        'text': '#e8f5e9',
        'text_dim': '#9cbc9e',
        'text_muted': '#6a8a6c',
        'accent': '#4ade80',
        'accent_blue': '#34d399',
        'success': '#22c55e',
        'error': '#ef4444',
        'warning': '#eab308',
        'info': '#34d399',
    },
    'warm_orange': {
        'name': '暖橙黄昏',
        'short_name': '暖橙',
        'icon': '🌅',
        'bg': '#171310',
        'card': '#211c17',
        'card_hover': '#2c251e',
        'border': '#44392d',
        'text': '#fef3e2',
        'text_dim': '#c9a982',
        'text_muted': '#9a7d5a',
        'accent': '#fb923c',
        'accent_blue': '#f59e0b',
        'success': '#84cc16',
        'error': '#ef4444',
        'warning': '#f59e0b',
        'info': '#fb923c',
    },
    'ocean_cyan': {
        'name': '深海青碧',
        'short_name': '海洋',
        'icon': '🌴',
        'bg': '#0c1415',
        'card': '#121e1f',
        'card_hover': '#1a2a2c',
        'border': '#2a4245',
        'text': '#e0f7fa',
        'text_dim': '#80cbc4',
        'text_muted': '#4db6ac',
        'accent': '#22d3ee',
        'accent_blue': '#06b6d4',
        'success': '#2dd4bf',
        'error': '#f87171',
        'warning': '#fbbf24',
        'info': '#22d3ee',
    },
    'rose_pink': {
        'name': '玫瑰粉黛',
        'short_name': '玫瑰',
        'icon': '🌸',
        'bg': '#18101a',
        'card': '#231a25',
        'card_hover': '#2f2432',
        'border': '#4a3850',
        'text': '#fdf2f8',
        'text_dim': '#d8a9c4',
        'text_muted': '#a87d94',
        'accent': '#f472b6',
        'accent_blue': '#ec4899',
        'success': '#4ade80',
        'error': '#fb7185',
        'warning': '#fbbf24',
        'info': '#f472b6',
    },
}

DEFAULT_THEME = 'deep_blue'

# 启动器 logo 的四条竖条基础颜色；动画在 log_window._animate_glow 中按亮度插值
LOGO_BAR_RGB = (
    (0xFF, 0x6B, 0x6B),
    (0xFE, 0xCA, 0x57),
    (0x48, 0xDB, 0xFB),
    (0x1D, 0xD1, 0xA1),
)
LOGO_BAR_COLORS = tuple(f'#{r:02x}{g:02x}{b:02x}' for r, g, b in LOGO_BAR_RGB)


def get_theme_colors(name: str) -> dict[str, str]:
    """返回主题颜色副本；主题名无效时使用默认主题。"""
    theme = PRESET_THEMES.get(name, PRESET_THEMES[DEFAULT_THEME])
    return theme.copy()


def shade_color(color: str, factor: float) -> str:
    """按比例调暗或调亮 #RRGGBB；factor 小于 1 调暗，大于 1 调亮。"""
    if len(color) != 7 or not color.startswith('#'):
        return color
    try:
        red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        return color
    channels = (max(0, min(255, round(channel * factor))) for channel in (red, green, blue))
    return '#{:02x}{:02x}{:02x}'.format(*channels)
