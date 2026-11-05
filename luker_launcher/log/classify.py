"""日志文本的级别分类，供存储层和渲染层共用。"""


def get_tag_for_line(line: str) -> str:
    """按日志内容选择颜色标签。"""
    line_lower = line.lower()
    if '[错误]' in line or 'error' in line_lower or 'fail' in line_lower:
        return 'error'
    elif '[警告]' in line or 'warn' in line_lower:
        return 'warn'
    elif '[信息]' in line or 'info' in line_lower:
        return 'info'
    elif '[启动器]' in line:
        return 'accent'
    elif (
        'success' in line_lower
        or '成功' in line
        or 'listening' in line_lower
        or 'compiled' in line_lower
    ):
        return 'success'
    return 'dim'
