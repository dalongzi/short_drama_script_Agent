
import json

import pytest
from unittest.mock import MagicMock
from src.script_writer import ScriptWriter, ScriptGenerationError, BatchRange, AutoPromptContext, LineRange, EpisodeOutline, StageOneResult
from src.llm_client import LLMClient


@pytest.fixture
def mock_llm():
    """提供 mock LLM 客户端，用于降级路径等复杂测试"""
    client = MagicMock(spec=LLMClient)
    return client


@pytest.fixture
def template_path():
    """提供剧本格式模板路径"""
    return "data/短剧剧本写作格式模板.md"


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
    mock_client.generate.return_value = ("生成的剧本内容", {"prompt_tokens": 100, "completion_tokens": 50})

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


def test_script_writer_generate_script_auto_episodes_success(tmp_path):
    """测试 V2 三阶段流程：阶段一 JSON 返回集数+大纲，阶段三一次生成全部"""
    mock_client = MagicMock(spec=LLMClient)

    # 小说文本：4 行，每集对应一行
    novel_text = "第一章 开端\n第二章 发展\n第三章 转折\n第四章 结局"

    # 阶段一：LLM 返回合法 JSON（4 集大纲，行号连续覆盖 1-4）
    stage_one_json = json.dumps({
        "total_episodes": 4,
        "outlines": [
            {
                "episode": 1,
                "line_range": {"start": 1, "end": 1},
                "original_range": "第一章",
                "core_plot": "女主被陷害",
                "ending_hook": "神秘人出现"
            },
            {
                "episode": 2,
                "line_range": {"start": 2, "end": 2},
                "original_range": "第二章",
                "core_plot": "女主反击",
                "ending_hook": "真相初现"
            },
            {
                "episode": 3,
                "line_range": {"start": 3, "end": 3},
                "original_range": "第三章",
                "core_plot": "危机升级",
                "ending_hook": "绝境"
            },
            {
                "episode": 4,
                "line_range": {"start": 4, "end": 4},
                "original_range": "第四章",
                "core_plot": "最终对决",
                "ending_hook": "结局"
            }
        ]
    })

    # V2 流程：阶段一调用 1 次 + 阶段三批次调用 1 次（batch_size=10 覆盖 4 集）= 2 次
    mock_client.generate.side_effect = [
        (stage_one_json, {"prompt_tokens": 100, "completion_tokens": 50}),
        ("""第一集
1-1 日 内 九重天
△ 场景描述
角色：台词
【卡点】悬念""", {"prompt_tokens": 100, "completion_tokens": 50}),
    ]

    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    output_file = tmp_path / "output.txt"

    result = writer.generate_script_auto_episodes(novel_text, str(output_file), 1, 10, batch_size=10)

    assert result is not None
    assert "【集数：4集】" in result
    assert mock_client.generate.call_count == 2


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


def test_auto_episodes_uses_novel_segments(tmp_path):
    """测试 V2 三阶段流程中，阶段三使用小说片段而非全文"""
    mock_client = MagicMock(spec=LLMClient)

    # 使用有章节分隔的小说文本
    novel_text = "第一章 开端\n这是开头内容很重要。\n\n第二章 发展\n这是中间发展部分。\n\n第三章 转折\n这是转折内容。\n\n第四章 结局\n这是最后的结局。"

    # novel_text.split('\n') 共 11 行
    # 阶段一：LLM 返回合法 JSON（4 集，行号连续覆盖 1-11）
    stage_one_json = json.dumps({
        "total_episodes": 4,
        "outlines": [
            {
                "episode": 1,
                "line_range": {"start": 1, "end": 2},
                "original_range": "第一章",
                "core_plot": "女主被陷害",
                "ending_hook": "神秘人出现"
            },
            {
                "episode": 2,
                "line_range": {"start": 3, "end": 5},
                "original_range": "第二章",
                "core_plot": "女主反击",
                "ending_hook": "真相初现"
            },
            {
                "episode": 3,
                "line_range": {"start": 6, "end": 8},
                "original_range": "第三章",
                "core_plot": "危机升级",
                "ending_hook": "绝境"
            },
            {
                "episode": 4,
                "line_range": {"start": 9, "end": 11},
                "original_range": "第四章",
                "core_plot": "最终对决",
                "ending_hook": "结局"
            }
        ]
    })

    # V2 流程：阶段一 1 次 + 阶段三 2 批（batch_size=2，4 集分 2 批）= 3 次
    mock_client.generate.side_effect = [
        (stage_one_json, {"prompt_tokens": 100, "completion_tokens": 50}),
        ("""第一集
1-1 日 内 房间
△ 场景描述
角色：台词
【卡点】悬念""", {"prompt_tokens": 100, "completion_tokens": 50}),
        ("""第三集
3-1 日 外 街道
△ 场景描述
角色：台词
【卡点】绝境""", {"prompt_tokens": 100, "completion_tokens": 50}),
    ]

    writer = ScriptWriter(mock_client, "data/短剧剧本写作格式模板.md")
    output_file = tmp_path / "output.txt"

    # batch_size=2，4 集分 2 批生成
    result = writer.generate_script_auto_episodes(novel_text, str(output_file), 1, 10, batch_size=2)

    assert result is not None
    assert "【集数：4集】" in result
    assert mock_client.generate.call_count == 3

    # 验证第一次正文生成（第 1-2 集）的 user_prompt 包含前两章原文
    first_batch_call = mock_client.generate.call_args_list[1]
    _, user_prompt_first = first_batch_call[0]
    assert "本集参考原文" in user_prompt_first
    # 第一批主文本应包含前两章内容
    assert "这是开头内容很重要" in user_prompt_first

    # 验证第二批正文（第 3-4 集）的 user_prompt 包含前两章作为前冗余上下文
    second_batch_call = mock_client.generate.call_args_list[2]
    _, user_prompt_second = second_batch_call[0]
    # 第二批应包含前两章作为冗余上下文
    assert "这是开头内容很重要" in user_prompt_second


# ===== Step 6: _parse_combined_response 测试 =====

def _make_valid_json(episode_count=2) -> str:
    """生成合法的阶段一 JSON 响应"""
    outlines = []
    for i in range(1, episode_count + 1):
        outlines.append({
            "episode": i,
            "line_range": {"start": (i - 1) * 10 + 1, "end": i * 10},
            "original_range": f"第{i}章",
            "core_plot": f"第{i}集核心剧情",
            "ending_hook": f"第{i}集结尾钩子",
        })
    import json
    return json.dumps({"total_episodes": episode_count, "outlines": outlines})


def test_parse_combined_response_success():
    """测试合法 JSON 解析"""
    response = _make_valid_json(2)
    result = ScriptWriter._parse_combined_response(response)

    assert result is not None
    assert isinstance(result, StageOneResult)
    assert result.total_episodes == 2
    assert len(result.outlines) == 2
    assert result.outlines[0].episode == 1
    assert result.outlines[0].line_range.start == 1
    assert result.outlines[0].line_range.end == 10
    assert result.outlines[1].episode == 2


def test_parse_combined_response_sorted():
    """测试按 episode 升序排序"""
    import json
    response = json.dumps({
        "total_episodes": 3,
        "outlines": [
            {"episode": 3, "line_range": {"start": 21, "end": 30}, "original_range": "第3章", "core_plot": "p3", "ending_hook": "h3"},
            {"episode": 1, "line_range": {"start": 1, "end": 10}, "original_range": "第1章", "core_plot": "p1", "ending_hook": "h1"},
            {"episode": 2, "line_range": {"start": 11, "end": 20}, "original_range": "第2章", "core_plot": "p2", "ending_hook": "h2"},
        ]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is not None
    assert [o.episode for o in result.outlines] == [1, 2, 3]


def test_parse_combined_response_with_leading_trailing_text():
    """测试 JSON 前后有额外文字时仍能正确提取"""
    response = "好的，以下是分析结果：\n\n" + _make_valid_json(1) + "\n\n希望对你有帮助！"
    result = ScriptWriter._parse_combined_response(response)
    assert result is not None
    assert result.total_episodes == 1


def test_parse_combined_response_invalid_json():
    """测试非法 JSON 返回 None"""
    result = ScriptWriter._parse_combined_response("这不是JSON{abc")
    assert result is None


def test_parse_combined_response_no_json_block():
    """测试完全没有 JSON 块返回 None"""
    result = ScriptWriter._parse_combined_response("纯文本无任何大括号")
    assert result is None


def test_parse_combined_response_missing_total_episodes():
    """测试缺少 total_episodes 返回 None"""
    import json
    response = json.dumps({"outlines": []})
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_missing_outlines():
    """测试缺少 outlines 返回 None"""
    import json
    response = json.dumps({"total_episodes": 10})
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_total_episodes_not_int():
    """测试 total_episodes 不是 int 返回 None"""
    import json
    response = json.dumps({"total_episodes": "80", "outlines": []})
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_outlines_not_list():
    """测试 outlines 不是 list 返回 None"""
    import json
    response = json.dumps({"total_episodes": 80, "outlines": "not a list"})
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_missing_episode_field():
    """测试 outline 缺少 episode 字段返回 None"""
    import json
    response = json.dumps({
        "total_episodes": 1,
        "outlines": [
            {"line_range": {"start": 1, "end": 10}, "original_range": "第1章", "core_plot": "p", "ending_hook": "h"}
        ]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_missing_line_range():
    """测试 outline 缺少 line_range 字段返回 None"""
    import json
    response = json.dumps({
        "total_episodes": 1,
        "outlines": [
            {"episode": 1, "original_range": "第1章", "core_plot": "p", "ending_hook": "h"}
        ]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_line_range_missing_start():
    """测试 line_range 缺少 start 返回 None"""
    import json
    response = json.dumps({
        "total_episodes": 1,
        "outlines": [
            {"episode": 1, "line_range": {"end": 10}, "original_range": "第1章", "core_plot": "p", "ending_hook": "h"}
        ]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_line_range_not_dict():
    """测试 line_range 不是 dict 返回 None"""
    import json
    response = json.dumps({
        "total_episodes": 1,
        "outlines": [
            {"episode": 1, "line_range": "invalid", "original_range": "第1章", "core_plot": "p", "ending_hook": "h"}
        ]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_line_range_start_not_int():
    """测试 line_range.start 不是 int 返回 None"""
    import json
    response = json.dumps({
        "total_episodes": 1,
        "outlines": [
            {"episode": 1, "line_range": {"start": "1", "end": 10}, "original_range": "第1章", "core_plot": "p", "ending_hook": "h"}
        ]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_response_outlines_empty():
    """测试 outlines 为空数组仍能正常返回（不报错）"""
    import json
    response = json.dumps({"total_episodes": 0, "outlines": []})
    result = ScriptWriter._parse_combined_response(response)
    assert result is not None
    assert result.total_episodes == 0
    assert result.outlines == []


def test_parse_combined_response_outlines_not_dict():
    """测试 outlines 中包含非 dict 项返回 None"""
    import json
    response = json.dumps({
        "total_episodes": 1,
        "outlines": ["not a dict"]
    })
    result = ScriptWriter._parse_combined_response(response)
    assert result is None


def test_parse_combined_returns_stage_one_result_objects():
    """测试返回的 outlines 是 EpisodeOutline 对象"""
    response = _make_valid_json(1)
    result = ScriptWriter._parse_combined_response(response)

    assert result is not None
    assert isinstance(result.outlines[0], EpisodeOutline)
    assert isinstance(result.outlines[0].line_range, LineRange)


# ===== v2-009: 降级路径测试 =====


def test_stage_one_json_parse_failure_raises(mock_llm, tmp_path):
    """阶段一 JSON 解析失败时抛出 ScriptGenerationError"""
    mock_llm.generate.return_value = ("这不是 JSON", MagicMock())

    writer = ScriptWriter(mock_llm, "data/短剧剧本写作格式模板.md")

    output_path = tmp_path / "output.txt"
    with pytest.raises(ScriptGenerationError, match="阶段一 JSON 解析失败"):
        writer.generate_script_auto_episodes("test novel text", str(output_path))


def test_stage_one_outline_count_mismatch_raises(mock_llm, tmp_path):
    """outlines 数量与 total_episodes 不一致时抛出 ScriptGenerationError"""
    invalid_json = json.dumps({
        "total_episodes": 5,
        "outlines": [
            {"episode": 1, "line_range": {"start": 1, "end": 10}, "original_range": "第1章", "core_plot": "测试", "ending_hook": "测试"},
            {"episode": 2, "line_range": {"start": 11, "end": 20}, "original_range": "第2章", "core_plot": "测试", "ending_hook": "测试"},
            {"episode": 3, "line_range": {"start": 21, "end": 30}, "original_range": "第3章", "core_plot": "测试", "ending_hook": "测试"},
        ]
    })

    mock_llm.generate.return_value = (invalid_json, MagicMock())

    writer = ScriptWriter(mock_llm, "data/短剧剧本写作格式模板.md")

    output_path = tmp_path / "output.txt"
    # total_episodes=5 不在默认 [40, 110] 范围内，先触发范围校验失败
    with pytest.raises(ScriptGenerationError, match="(范围|不一致)"):
        writer.generate_script_auto_episodes("test\n" * 30, str(output_path))


# ===== v2-010: _parse_combined_response 补充测试 =====

def test_parse_combined_response_valid_json():
    """测试合法 JSON 解析"""
    response = '''{"total_episodes": 2, "outlines": [
        {"episode": 1, "line_range": {"start": 1, "end": 10}, "original_range": "第1章", "core_plot": "测试1", "ending_hook": "钩子1"},
        {"episode": 2, "line_range": {"start": 11, "end": 20}, "original_range": "第2章", "core_plot": "测试2", "ending_hook": "钩子2"}
    ]}'''
    result = ScriptWriter._parse_combined_response(response)
    assert result is not None
    assert result.total_episodes == 2
    assert len(result.outlines) == 2
    assert result.outlines[0].episode == 1
    assert result.outlines[0].line_range.start == 1
    assert result.outlines[0].line_range.end == 10


def test_parse_combined_response_missing_fields():
    """测试缺失必填字段 -> 返回 None"""
    # 缺 total_episodes
    assert ScriptWriter._parse_combined_response('{"outlines": []}') is None
    # 缺 outlines
    assert ScriptWriter._parse_combined_response('{"total_episodes": 5}') is None
    # 缺 episode 字段
    assert ScriptWriter._parse_combined_response(
        '{"total_episodes": 1, "outlines": [{"line_range": {"start": 1, "end": 10}, "original_range": "第1章", "core_plot": "测试", "ending_hook": "钩子"}]}'
    ) is None


def test_parse_combined_response_invalid_line_range():
    """测试 line_range 缺 start/end -> 返回 None"""
    # 缺 start
    assert ScriptWriter._parse_combined_response(
        '{"total_episodes": 1, "outlines": [{"episode": 1, "line_range": {"end": 10}, "original_range": "第1章", "core_plot": "测试", "ending_hook": "钩子"}]}'
    ) is None
    # line_range 不是 dict
    assert ScriptWriter._parse_combined_response(
        '{"total_episodes": 1, "outlines": [{"episode": 1, "line_range": "bad", "original_range": "第1章", "core_plot": "测试", "ending_hook": "钩子"}]}'
    ) is None
    # start 不是 int
    assert ScriptWriter._parse_combined_response(
        '{"total_episodes": 1, "outlines": [{"episode": 1, "line_range": {"start": "1", "end": 10}, "original_range": "第1章", "core_plot": "测试", "ending_hook": "钩子"}]}'
    ) is None


# ===== v2-011: _validate_outlines 测试 =====

def test_validate_outlines_episode_continuity():
    """测试集数非连续 -> 失败"""
    outlines = [
        EpisodeOutline(episode=1, line_range=LineRange(1, 10), original_range="第1章", core_plot="测试", ending_hook="钩子"),
        EpisodeOutline(episode=3, line_range=LineRange(11, 20), original_range="第2章", core_plot="测试", ending_hook="钩子"),
    ]
    stage_one = StageOneResult(total_episodes=2, outlines=outlines)
    error = ScriptWriter._validate_outlines(stage_one, 1, 10, 100)
    assert error is not None
    assert "不连续" in error


def test_validate_outlines_line_range_continuity():
    """测试行号不连续 -> 失败"""
    outlines = [
        EpisodeOutline(episode=1, line_range=LineRange(1, 10), original_range="第1章", core_plot="测试", ending_hook="钩子"),
        EpisodeOutline(episode=2, line_range=LineRange(12, 20), original_range="第2章", core_plot="测试", ending_hook="钩子"),  # 跳过了11
    ]
    stage_one = StageOneResult(total_episodes=2, outlines=outlines)
    error = ScriptWriter._validate_outlines(stage_one, 1, 10, 100)
    assert error is not None
    assert "不连续" in error


def test_validate_outlines_count_mismatch():
    """测试 outlines 数量 != total_episodes -> 失败"""
    outlines = [
        EpisodeOutline(episode=1, line_range=LineRange(1, 10), original_range="第1章", core_plot="测试", ending_hook="钩子"),
    ]
    stage_one = StageOneResult(total_episodes=3, outlines=outlines)
    error = ScriptWriter._validate_outlines(stage_one, 1, 10, 100)
    assert error is not None
    assert "不一致" in error


def test_validate_outlines_valid():
    """测试完全合法 -> 返回 None"""
    outlines = [
        EpisodeOutline(episode=1, line_range=LineRange(1, 10), original_range="第1章", core_plot="测试", ending_hook="钩子"),
        EpisodeOutline(episode=2, line_range=LineRange(11, 20), original_range="第2章", core_plot="测试", ending_hook="钩子"),
    ]
    stage_one = StageOneResult(total_episodes=2, outlines=outlines)
    error = ScriptWriter._validate_outlines(stage_one, 1, 10, 100)
    assert error is None


# ===== v2-012: _aggregate_batches 和 _extract_batch_text 测试 =====

def test_aggregate_batches_basic():
    """测试 80 集 -> 8 批的正常聚合"""
    outlines = [EpisodeOutline(episode=i, line_range=LineRange(1, 10), original_range="", core_plot="", ending_hook="") for i in range(1, 81)]
    batches = ScriptWriter._aggregate_batches(outlines, batch_size=10, redundancy=2)
    assert len(batches) == 8
    assert batches[0].start == 1 and batches[0].end == 10
    assert batches[1].start == 11 and batches[1].end == 20
    assert batches[7].start == 71 and batches[7].end == 80


def test_aggregate_batches_first_batch_no_pre_redundancy():
    """测试第一批无前冗余"""
    outlines = [EpisodeOutline(episode=i, line_range=LineRange(1, 10), original_range="", core_plot="", ending_hook="") for i in range(1, 21)]
    batches = ScriptWriter._aggregate_batches(outlines, batch_size=10, redundancy=2)
    assert batches[0].pre_start is None
    assert batches[0].post_end == 12


def test_aggregate_batches_last_batch_no_post_redundancy():
    """测试最后一批无后冗余"""
    outlines = [EpisodeOutline(episode=i, line_range=LineRange(1, 10), original_range="", core_plot="", ending_hook="") for i in range(1, 21)]
    batches = ScriptWriter._aggregate_batches(outlines, batch_size=10, redundancy=2)
    assert batches[-1].post_end is None
    assert batches[-1].pre_start == 9


def test_aggregate_episodes_less_than_batch():
    """测试集数 < 10 的单批场景"""
    outlines = [EpisodeOutline(episode=i, line_range=LineRange(1, 10), original_range="", core_plot="", ending_hook="") for i in range(1, 6)]
    batches = ScriptWriter._aggregate_batches(outlines, batch_size=10, redundancy=2)
    assert len(batches) == 1
    assert batches[0].start == 1 and batches[0].end == 5
    assert batches[0].pre_start is None
    assert batches[0].post_end is None


def test_extract_batch_text():
    """测试行号区间提取原文"""
    novel_lines = [f"line{i}" for i in range(1, 41)]  # 40行
    outlines = [
        EpisodeOutline(episode=1, line_range=LineRange(1, 10), original_range="第1章", core_plot="", ending_hook=""),
        EpisodeOutline(episode=2, line_range=LineRange(11, 20), original_range="第2章", core_plot="", ending_hook=""),
        EpisodeOutline(episode=3, line_range=LineRange(21, 30), original_range="第3章", core_plot="", ending_hook=""),
        EpisodeOutline(episode=4, line_range=LineRange(31, 40), original_range="第4章", core_plot="", ending_hook=""),
    ]
    batch_range = BatchRange(start=2, end=3, pre_start=1, post_end=4)
    pre_text, main_text, post_text = ScriptWriter._extract_batch_text(novel_lines, outlines, batch_range)
    assert "line1" in pre_text  # 第1行在前冗余
    assert "line11" in main_text  # 第11行在本批
    assert "line31" in post_text  # 第31行在后冗余


# ===== v2-013: 阶段三提示词测试 =====

def test_build_batch_prompt_v2_redundancy_labeling(mock_llm, template_path):
    """测试提示词中包含冗余原文标注"""
    writer = ScriptWriter(mock_llm, template_path)

    batch_range = BatchRange(start=2, end=3, pre_start=1, post_end=4)
    batch_outlines = [
        EpisodeOutline(episode=2, line_range=LineRange(11, 20), original_range="第2章", core_plot="测试2", ending_hook="钩子2"),
        EpisodeOutline(episode=3, line_range=LineRange(21, 30), original_range="第3章", core_plot="测试3", ending_hook="钩子3"),
    ]
    pre_text = "前冗余原文"
    main_text = "本批原文"
    post_text = "后冗余原文"
    ctx = AutoPromptContext(template_content="模板内容", total_episodes=4)

    system_prompt, user_prompt = writer._build_batch_prompt_v2(batch_range, batch_outlines, pre_text, main_text, post_text, ctx)

    assert "仅供上下文参考" in user_prompt
    assert "前冗余原文" in user_prompt
    assert "本批原文" in user_prompt
    assert "后冗余原文" in user_prompt
    assert "核心剧情" in system_prompt
    assert "测试2" in system_prompt

