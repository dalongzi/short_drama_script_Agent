
import pytest
from unittest.mock import MagicMock
from src.script_writer import ScriptWriter, ScriptGenerationError, BatchRange, AutoPromptContext
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


def test_script_writer_build_outline_prompt_with_source_range():
    """测试大纲提示词要求标注原文范围"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    system_prompt, user_prompt = writer._build_outline_prompt("小说", 60)

    assert "原文范围" in system_prompt


def test_parse_outline_with_source_range():
    """测试解析包含原文范围的大纲"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    outline = """第1集：
  原文范围：第一章-第三章
  核心剧情：女主被陷害
  结尾钩子：神秘人出现
第2集：
  原文范围：第三章-第五章
  核心剧情：女主反击
  结尾钩子：真相初现"""

    result = writer._parse_outline(outline)
    assert 1 in result
    assert 2 in result
    assert "第一章-第三章" in result[1]
    assert "第三章-第五章" in result[2]


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


# ===== Step 1: 数据结构测试 =====

def test_batch_range_dataclass():
    """测试 BatchRange 不可变特性"""
    batch = BatchRange(start=1, end=10)
    assert batch.start == 1
    assert batch.end == 10
    with pytest.raises(Exception):  # frozen=True 会抛出 TypeError
        batch.start = 20


def test_auto_prompt_context_dataclass():
    """测试 AutoPromptContext 不可变特性"""
    ctx = AutoPromptContext(
        template_content="模板",
        total_episodes=68,
    )
    assert ctx.template_content == "模板"
    assert ctx.total_episodes == 68
    with pytest.raises(Exception):
        ctx.total_episodes = 100


def test_auto_prompt_context_defaults():
    """测试 AutoPromptContext 可选字段默认值"""
    ctx = AutoPromptContext(
        template_content="模板",
        total_episodes=68,
    )
    assert ctx.outline_response == ""
    assert ctx.outline_dict == {}
    assert ctx.novel_segments == {}


# ===== Step 2: 小说分段提取测试 =====

def test_split_novel_by_chapters():
    """测试带章节小说的分割"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    novel = """第一章 开端
这是第一章的内容。

第二章 发展
这是第二章的内容。

第三章 高潮
这是第三章的内容。"""

    chapters = writer._split_novel_by_chapters(novel)
    assert len(chapters) == 3
    assert chapters[0][0] == "第一章"
    assert "第一章的内容" in chapters[0][1]
    assert chapters[1][0] == "第二章"
    assert chapters[2][0] == "第三章"


def test_split_novel_no_chapters():
    """测试无章节小说的段落分割"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    novel = """这是第一段内容。
它有多行。

这是第二段内容。

这是第三段内容。"""

    segments = writer._split_novel_by_chapters(novel)
    assert len(segments) == 3
    assert "第一段" in segments[0][1]
    assert "第二段" in segments[1][1]
    assert "第三段" in segments[2][1]


def test_map_episodes_to_segments():
    """测试集数到章节范围的映射"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    chapters = [("第一章", "内容1"), ("第二章", "内容2"), ("第三章", "内容3"), ("第四章", "内容4")]
    segments = writer._map_episodes_to_segments(chapters, total_episodes=8)

    assert len(segments) == 8
    assert "内容1" in segments[1]
    assert "内容4" in segments[8]


def test_extract_novel_segment_range():
    """测试指定章节范围的提取"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    chapters = [("第一章", "内容A"), ("第二章", "内容B"), ("第三章", "内容C")]
    result = writer._extract_novel_segment_range(chapters, start_chapter=1, end_chapter=2)
    assert "内容A" in result
    assert "内容B" in result
    assert "内容C" not in result


# ===== Step 4: 精简 _build_auto_prompt 签名 =====

def test_build_auto_prompt_with_new_signature():
    """测试使用新签名的 _build_auto_prompt（精简参数 + 使用片段）"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    ctx = AutoPromptContext(
        template_content="模板内容",
        total_episodes=68,
    )
    batch = BatchRange(start=1, end=10)
    outline = "第一集：\n  核心剧情：女主被陷害\n  结尾钩子：神秘人出现\n"
    novel_segment = "第一章到第三章的片段内容"

    system_prompt, user_prompt = writer._build_auto_prompt(batch, outline, novel_segment, ctx)

    assert "第 1 集到第 10 集" in user_prompt
    assert novel_segment in user_prompt
    assert "模板内容" in system_prompt
    assert "竖屏" in system_prompt
    assert "卡点" in system_prompt
    assert "200-500" in system_prompt
    assert "严禁" in system_prompt
    # 不应出现全文小说
    assert "小说内容" not in user_prompt


def test_build_auto_prompt_with_outline_in_new_signature():
    """测试新签名下大纲正确嵌入"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    ctx = AutoPromptContext(
        template_content="模板",
        total_episodes=68,
    )
    batch = BatchRange(start=11, end=20)
    outline = "第11集：\n  核心剧情：反转\n  结尾钩子：危机\n"
    segment = "相关片段"

    system_prompt, user_prompt = writer._build_auto_prompt(batch, outline, segment, ctx)

    assert outline in system_prompt
    assert "严格遵循" in system_prompt
    assert "第 11 集到第 20 集" in user_prompt


def test_build_auto_prompt_without_outline_new_signature():
    """测试新签名下无大纲的情况"""
    mock_client = MagicMock(spec=LLMClient)
    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")

    ctx = AutoPromptContext(
        template_content="模板",
        total_episodes=68,
    )
    batch = BatchRange(start=1, end=10)

    system_prompt, user_prompt = writer._build_auto_prompt(batch, "", "片段", ctx)

    assert "严格遵循" not in system_prompt
    assert "片段" in user_prompt


# ===== Step 5: 集成测试 — 三阶段流程使用片段 =====

def test_auto_episodes_uses_novel_segments(tmp_path):
    """测试完整三阶段流程中，阶段三使用小说片段而非全文"""
    mock_client = MagicMock(spec=LLMClient)
    # 多次调用分别返回：集数决策、大纲、第一批正文、第二批正文
    mock_client.generate.side_effect = [
        "【集数：4集】",
        """第1集：
  原文范围：第一章
  核心剧情：女主被陷害
  结尾钩子：神秘人出现
第2集：
  原文范围：第二章
  核心剧情：女主反击
  结尾钩子：真相初现
第3集：
  原文范围：第三章
  核心剧情：危机升级
  结尾钩子：绝境
第4集：
  原文范围：第四章
  核心剧情：最终对决
  结尾钩子：结局""",
        """第一集
1-1 日 内 房间
△ 场景描述
角色：台词
【卡点】悬念""",
        """第三集
3-1 日 外 街道
△ 场景描述
角色：台词
【卡点】绝境"""
    ]

    # 使用有章节分隔的小说文本，确保分段逻辑能生效
    novel_text = "第一章 开端\n这是开头内容很重要。\n\n第二章 发展\n这是中间发展部分。\n\n第三章 转折\n这是转折内容。\n\n第四章 结局\n这是最后的结局。"

    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    output_file = tmp_path / "output.txt"

    # batch_size=2，4集分2批生成
    result = writer.generate_script_auto_episodes(novel_text, str(output_file), 60, 100, batch_size=2)

    assert result is not None
    assert "【集数：4集】" in result
    assert mock_client.generate.call_count == 4

    # 验证第一次正文生成（第1-2集）的 user_prompt 只包含前两章片段
    first_batch_call = mock_client.generate.call_args_list[2]
    _, user_prompt_first = first_batch_call[0]
    assert "本集参考原文" in user_prompt_first
    # 第一批只应包含前两章，不应包含后两章
    assert "这是开头内容很重要" in user_prompt_first
    assert "这是最后的结局" not in user_prompt_first

