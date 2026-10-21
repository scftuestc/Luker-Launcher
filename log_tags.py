"""日志文本到颜色标签的映射。"""


def get_tag_for_line(line: str) -> str:
    """按日志内容选择颜色标签。"""
    line_lower = line.lower()
    # GCL 日志带 [GCL 错误] 这类作用域前缀，归一化后复用同一套匹配
    normalized = line.replace('[GCL ', '[')
    if '[错误]' in normalized or 'error' in line_lower or 'fail' in line_lower:
        return 'error'
    elif '[警告]' in normalized or 'warn' in line_lower:
        return 'warn'
    elif '[信息]' in normalized or 'info' in line_lower:
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
