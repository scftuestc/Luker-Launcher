"""加载随包分发的主题图片；缺失或损坏时由调用方回退。"""

from __future__ import annotations

import logging
from functools import cache

from PIL import Image

from luker_launcher.paths import resource_path

logger = logging.getLogger(__name__)


@cache
def load_theme_image(relative_path: str | None) -> Image.Image | None:
    """按资源相对路径加载 RGBA 图片；失败返回 None，不影响界面。"""
    if not relative_path:
        return None
    path = resource_path(relative_path)
    try:
        with Image.open(path) as image:
            return image.convert('RGBA').copy()
    except Exception:
        logger.warning("加载主题图片失败：%s", path, exc_info=True)
        return None


def theme_card_image(theme: dict[str, str]) -> Image.Image | None:
    return load_theme_image(theme.get('card_image'))


def theme_log_image(theme: dict[str, str]) -> Image.Image | None:
    return load_theme_image(theme.get('log_image'))
