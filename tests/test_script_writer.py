
import pytest
from unittest.mock import MagicMock
from src.script_writer import ScriptWriter, ScriptGenerationError
from src.llm_client import LLMClient


def test_script_writer_initialization():
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    assert writer.llm_client == mock_client
    assert writer.template_path == "data/短剧剧本写作格式模板.md"


def test_script_writer_build_prompt():
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    
    novel_text = "小说内容"
    template_content = "模板内容"
    system_prompt, user_prompt = writer._build_prompt(novel_text, template_content)
    
    assert "短剧剧本" in system_prompt
    assert novel_text in user_prompt


def test_script_writer_save_script(tmp_path):
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    
    test_content = "剧本内容"
    output_file = tmp_path / "output.txt"
    writer.save_script(test_content, str(output_file))
    
    assert output_file.read_text(encoding="utf-8") == test_content


def test_script_writer_generate_script_success(tmp_path):
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate.return_value = "生成的剧本内容"
    
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    output_file = tmp_path / "output.txt"
    
    result = writer.generate_script("小说内容", str(output_file), num_episodes=1)
    
    assert result == "生成的剧本内容"
    mock_client.generate.assert_called_once()


def test_script_writer_generate_script_failure():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate.side_effect = Exception("生成失败")
    
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    
    with pytest.raises(ScriptGenerationError):
        writer.generate_script("小说内容", "output.txt")


def test_script_writer_build_auto_prompt():
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    novel_text = "小说内容"
    template_content = "模板内容"
    system_prompt, user_prompt = writer._build_auto_prompt(novel_text, template_content, 60, 100, 1, 10, 68)

    assert "第 1 集到第 10 集" in user_prompt
    assert novel_text in user_prompt
    assert "竖屏" in system_prompt
    assert "卡点" in system_prompt
    assert "200-500" in system_prompt
    assert "严禁" in system_prompt


def test_script_writer_build_auto_prompt_with_outline():
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    novel_text = "小说内容"
    template_content = "模板内容"
    outline = "第一集：\n  核心剧情：女主被陷害\n  结尾钩子：神秘人出现\n"
    system_prompt, user_prompt = writer._build_auto_prompt(
        novel_text, template_content, 60, 100, 1, 10, 68, outline_section=outline
    )

    assert outline in system_prompt
    assert "严格遵循" in system_prompt


def test_script_writer_build_outline_prompt():
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    novel_text = "小说内容"
    system_prompt, user_prompt = writer._build_outline_prompt(novel_text, 68)

    assert "68" in system_prompt
    assert "核心剧情" in system_prompt
    assert "结尾钩子" in system_prompt
    assert "严禁在前 1/3 集数内写出结局" in system_prompt
    assert novel_text in user_prompt


def test_script_writer_build_decide_episodes_prompt():
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    
    novel_text = "小说内容"
    system_prompt, user_prompt = writer._build_decide_episodes_prompt(novel_text, 60, 100)
    
    assert "60-100" in system_prompt
    assert "【集数：XX集】" in system_prompt
    assert novel_text in user_prompt


def test_script_writer_generate_script_auto_episodes_success(tmp_path):
    mock_client = MagicMock(spec=LLMClient)
    # 三次调用分别返回：集数决策、大纲、正文（batch_size=68 一次生成完）
    mock_client.generate.side_effect = [
        "【集数：68集】",
        "第一集：\n  核心剧情：女主被陷害\n  结尾钩子：神秘人出现\n",
        """第一集
1-1 日 内 九重天
△ 场景描述
角色：台词
【卡点】悬念"""
    ]

    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    output_file = tmp_path / "output.txt"

    result = writer.generate_script_auto_episodes("小说内容", str(output_file), 60, 100, batch_size=68)

    assert result is not None
    assert "【集数：68集】" in result
    assert mock_client.generate.call_count == 3


def test_script_writer_generate_script_auto_episodes_failure():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate.side_effect = Exception("生成失败")
    
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    
    with pytest.raises(ScriptGenerationError):
        writer.generate_script_auto_episodes("小说内容", "output.txt")

