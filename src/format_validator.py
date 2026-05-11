
import re


def validate_script_format(script_content: str, template_path: str) -> tuple[bool, list[str]]:
    """
    校验剧本格式是否符合规范

    Args:
        script_content: 剧本内容
        template_path: 模板文件路径

    Returns:
        (is_valid, issues) 元组，is_valid 表示是否有效，issues 是问题列表
    """
    issues = []

    lines = [line.strip() for line in script_content.split('\n') if line.strip()]

    if not lines:
        issues.append("剧本内容为空")
        return False, issues

    # 检查是否有集数标题
    has_episode = False
    for line in lines:
        if re.match(r'^(第[一二三四五六七八九十百]+集|第\d+集)', line):
            has_episode = True
            break
    if not has_episode:
        issues.append("缺少集数标题，如\"第一集\"或\"第1集\"")

    # 检查是否有场景编号
    has_scene = False
    for line in lines:
        if re.match(r'^\d+-\d+', line):
            has_scene = True
            break
    if not has_scene:
        issues.append("缺少场景编号，如\"1-1\"")

    # 检查是否有 △ 动作标记
    has_triangle = False
    for line in lines:
        if '△' in line:
            has_triangle = True
            break

    # 检查是否有括号表情
    has_parentheses = False
    for line in lines:
        if '(' in line and ')' in line:
            has_parentheses = True
            break

    return len(issues) == 0, issues
