
import pytest
from src.format_validator import validate_script_format


def test_validate_script_format_valid():
    valid_script = """第一集

【女主介绍】
【卡点说明】

1-1 日 内 九重天
人物：女主林雨欣
△（字幕：九重天）
林雨欣：台词
"""
    is_valid, issues = validate_script_format(valid_script, "data/短剧剧本写作格式模板.md")
    assert is_valid is True
    assert len(issues) == 0


def test_validate_script_format_invalid_no_episode():
    invalid_script = """
没有第一集开头
1-1 日 内 九重天
人物：女主
台词
"""
    is_valid, issues = validate_script_format(invalid_script, "data/短剧剧本写作格式模板.md")
    assert is_valid is False
    assert len(issues) > 0


def test_validate_script_format_invalid_no_scene():
    invalid_script = """第一集

【女主介绍】

没有场景编号
人物：女主
台词
"""
    is_valid, issues = validate_script_format(invalid_script, "data/短剧剧本写作格式模板.md")
    assert is_valid is False
    assert len(issues) > 0


def test_validate_script_format_with_example():
    example_script = """第一集

【女主林雨欣：九天玄女因为话痨被罚下诛仙台，魂穿林府真千金身上】
【转折：九天玄女要代替林府千金扭转上一世悲剧，才能重返天庭】
【卡点：女主哥哥发现自己能听到女主心声，得知养妹想要全家人的命】

1-1 日 内 九重天
人物：女主林雨欣 天将X2
△（字幕：九重天，诛仙台）
△诛仙台上，仙气缭绕，两个天将架着林雨欣走到诛仙台上。
林雨欣惊恐的往后挣扎：两位大哥，从这跳下去会死仙女的！
"""
    is_valid, issues = validate_script_format(example_script, "data/短剧剧本写作格式模板.md")
    assert is_valid is True
