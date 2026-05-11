
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
    
    assert "第 1 集到第 10 集" in system_prompt
    assert "第 1 集到第 10 集" in user_prompt
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
    mock_client.generate.return_value = """【集数：68集】
第一集
1-1 日 内 九重天
△ 场景描述
角色：台词"""
    
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    output_file = tmp_path / "output.txt"
    
    result = writer.generate_script_auto_episodes("小说内容", str(output_file), 60, 100, batch_size=10)
    
    assert result is not None
    assert "【集数：68集】" in result
    assert mock_client.generate.call_count >= 2


def test_script_writer_generate_script_auto_episodes_failure():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate.side_effect = Exception("生成失败")
    
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    
    with pytest.raises(ScriptGenerationError):
        writer.generate_script_auto_episodes("小说内容", "output.txt")

