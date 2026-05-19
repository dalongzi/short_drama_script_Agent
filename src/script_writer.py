import json
import logging
import re
from dataclasses import dataclass

from src.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 剧本格式规则（多处提示词共用）
_FORMAT_RULES = """## 剧本格式规范
1. 集数标注："第X集"开头
2. 场景格式："1-1 日 内 九重天"（编号-子编号 日/夜 内/外 地点）
3. 动作描述：使用 △ 符号开头标注除对话外的内容
4. 语气神态：使用 () 括号描写人物说话时的语气、神态、动作
5. 内心独白：使用 VO 或 OS 标记
6. 回忆镜头：开始用【闪回】，结束用【闪出】"""


@dataclass(frozen=True)
class BatchRange:
    """单批生成的集数范围（含冗余上下文）"""
    start: int
    end: int
    pre_start: int | None = None   # 前冗余起始集（None 表示无前冗余）
    post_end: int | None = None    # 后冗余结束集（None 表示无后冗余）


@dataclass(frozen=True)
class AutoPromptContext:
    """自动集数提示词构建的上下文配置（V2 精简版）"""
    template_content: str
    total_episodes: int


@dataclass(frozen=True)
class LineRange:
    """原文行号区间"""
    start: int
    end: int


@dataclass(frozen=True)
class EpisodeOutline:
    """单集大纲"""
    episode: int
    line_range: LineRange       # 行号区间 {start, end}
    original_range: str         # 原文范围描述（人类可读）
    core_plot: str              # 核心剧情
    ending_hook: str            # 结尾钩子


@dataclass(frozen=True)
class StageOneResult:
    """阶段一结果：集数决策 + 逐集大纲"""
    total_episodes: int
    outlines: list              # list[EpisodeOutline]，按集数升序排列


@dataclass(frozen=True)
class BatchSegment:
    """批次片段：包含生成范围和对应原文"""
    batch_start: int            # 本批生成的起始集
    batch_end: int              # 本批生成的结束集
    line_start: int             # 原文起始行号（含冗余前缀）
    line_end: int               # 原文结束行号（含冗余后缀）
    novel_excerpt: str          # 提取的原文片段


class ScriptGenerationError(Exception):
    """
    剧本生成异常类
    """
    pass


class ScriptWriter:
    """
    剧本生成器类
    """

    def __init__(self, llm_client: LLMClient, template_path: str):
        """
        初始化剧本生成器

        Args:
            llm_client: LLM 客户端实例
            template_path: 剧本格式模板文件路径
        """
        self.llm_client = llm_client
        self.template_path = template_path

    @staticmethod
    def _print_system_prompt(prompt: str, separator: str = "-" * 40) -> None:
        print(f"\n系统提示词 (System Prompt)")
        print(separator)
        print(prompt)
        print(separator + "\n")

    def generate_script(self, novel_text: str, output_path: str, num_episodes: int = 1) -> str:
        """
        从小说生成短剧剧本

        Args:
            novel_text: 小说文本内容
            output_path: 输出剧本文件路径
            num_episodes: 生成的集数，默认为 1

        Returns:
            生成的剧本内容

        Raises:
            ScriptGenerationError: 剧本生成失败时抛出
        """
        try:
            template_content = self._read_template()
            system_prompt, user_prompt = self._build_prompt(novel_text, template_content, num_episodes)
            
            # 打印系统提示词
            self._print_system_prompt(system_prompt, "=" * 80)
            
            script_content, usage = self.llm_client.generate(system_prompt, user_prompt)
            self.save_script(script_content, output_path)
            return script_content
        except Exception as e:
            raise ScriptGenerationError(f"剧本生成失败: {str(e)}") from e

    def _read_template(self) -> str:
        """
        读取模板文件内容
        """
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _build_prompt(self, novel_text: str, template_content: str, num_episodes: int = 1) -> tuple[str, str]:
        """
        构建 LLM 提示词

        Args:
            novel_text: 小说文本
            template_content: 模板内容
            num_episodes: 集数

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = f"""你是一个专业的短剧剧本改编专家。请严格按照以下格式规范将小说改编为短剧剧本：

{_FORMAT_RULES}

以下是剧本格式模板：
{template_content}

请输出符合规范的短剧剧本内容，不要有额外解释。
"""

        user_prompt = f"""请将以下小说改编为 {num_episodes} 集的短剧剧本：

{novel_text}
"""

        return system_prompt, user_prompt

    def save_script(self, script_content: str, output_path: str) -> None:
        """
        保存剧本到文件

        Args:
            script_content: 剧本内容
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

    def generate_script_auto_episodes(self, novel_text: str, output_path: str,
                                      min_episodes: int = 40, max_episodes: int = 110,
                                      batch_size: int = 10) -> str:
        """
        让LLM自主判断集数并生成剧本（V2 三阶段：合并决策+大纲 → 规则聚合批次 → 按批次生成正文）

        V2 流程：
          阶段一：LLM 单次调用输出集数 + 逐集大纲（JSON，含行号区间）
          阶段二：规则处理（零 LLM 调用），按 batch_size 聚合批次
          阶段三：循环分批 LLM 生成剧本正文

        若 V2 任一步骤失败，降级调用 V1 流程。

        Args:
            novel_text: 小说文本内容
            output_path: 输出剧本文件路径
            min_episodes: 最小集数，默认为40
            max_episodes: 最大集数，默认为110
            batch_size: 每批生成的集数，默认为10

        Returns:
            生成的剧本内容

        Raises:
            ScriptGenerationError: 剧本生成失败时抛出
        """
        try:
            template_content = self._read_template()

            # 预处理：将小说按行分割
            novel_lines = novel_text.split('\n')
            novel_lines_count = len(novel_lines)

            # ===== 阶段一：LLM 单次调用输出集数 + 逐集大纲（JSON） =====
            print("\n" + "=" * 80)
            print("阶段一：分析小说内容，决定集数并生成逐集大纲（JSON）...")
            print("=" * 80)

            system_prompt, user_prompt = self._build_combined_prompt(
                novel_text, novel_lines_count, min_episodes, max_episodes
            )
            self._print_system_prompt(system_prompt)

            response, usage = self.llm_client.generate(system_prompt, user_prompt)
            stage_one = self._parse_combined_response(response)

            # 降级路径：JSON 解析失败
            if stage_one is None:
                msg = "阶段一 JSON 解析失败"
                print(f"WARNING: {msg}")
                logger.warning(msg)
                raise ScriptGenerationError(msg)

            # 验证大纲
            validation_error = self._validate_outlines(stage_one, min_episodes, max_episodes, novel_lines_count)
            if validation_error is not None:
                msg = f"阶段一大纲验证失败: {validation_error}"
                print(f"WARNING: {msg}")
                logger.warning(msg)
                raise ScriptGenerationError(msg)

            total_episodes = stage_one.total_episodes
            outlines = stage_one.outlines
            print(f"LLM 决策的总集数: {total_episodes} 集")

            # ===== 阶段二：规则处理（零 LLM 调用） =====
            print("\n" + "=" * 80)
            print(f"阶段二：按 batch_size={batch_size} 聚合批次（含冗余上下文）...")
            print("=" * 80)

            batch_ranges = self._aggregate_batches(outlines, batch_size=batch_size)
            print(f"聚合为 {len(batch_ranges)} 个批次")

            # ===== 阶段三：循环分批 LLM 生成 =====
            print("\n" + "=" * 80)
            print(f"阶段三：按批次生成剧本正文（共 {total_episodes} 集）...")
            print("=" * 80)
            print("请查看日志分析生成结果。")

            first_batch = True
            all_parts: list[str] = []

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"【集数：{total_episodes}集】\n\n")

                for batch_range in batch_ranges:
                    print(f"\n生成第 {batch_range.start} - {batch_range.end} 集...")

                    # 提取本批 outline
                    batch_outlines = [o for o in outlines if batch_range.start <= o.episode <= batch_range.end]

                    # 提取原文（含冗余）
                    pre_text, main_text, post_text = self._extract_batch_text(
                        novel_lines, outlines, batch_range
                    )

                    # 构建提示词
                    ctx = AutoPromptContext(
                        template_content=template_content,
                        total_episodes=total_episodes,
                    )
                    system_prompt, user_prompt = self._build_batch_prompt_v2(
                        batch_range, batch_outlines, pre_text, main_text, post_text, ctx
                    )

                    self._print_system_prompt(system_prompt)

                    logger.info(f"[_build_batch_prompt_v2] 第 {batch_range.start}-{batch_range.end} 批系统提示词:\n{system_prompt}")
                    logger.info(f"[_build_batch_prompt_v2] 第 {batch_range.start}-{batch_range.end} 批用户提示词:\n{user_prompt}")
                    print(f"第 {batch_range.start}-{batch_range.end} 批提示词已保存到日志。")

                    print(f"\n用户提示词 (User Prompt) - 第 {batch_range.start}-{batch_range.end} 批")
                    print("=" * 80)
                    print(user_prompt)
                    print("=" * 80 + "\n")

                    batch_content, usage = self.llm_client.generate(system_prompt, user_prompt)

                    # 移除第一批可能的集数标记
                    if first_batch and batch_content.startswith("【集数："):
                        _, _, batch_content = batch_content.partition("\n")
                        batch_content = batch_content.lstrip()

                    f.write(batch_content + "\n\n")
                    all_parts.append(batch_content)

                    first_batch = False

            return f"【集数：{total_episodes}集】\n\n" + '\n\n'.join(all_parts)

        except Exception as e:
            raise ScriptGenerationError(f"剧本生成失败: {str(e)}") from e

    def _build_combined_prompt(self, novel_text: str, novel_lines_count: int,
                               min_episodes: int, max_episodes: int) -> tuple[str, str]:
        """
        构建阶段一的合并提示词，要求 LLM 一次性输出集数 + 逐集大纲 + 每集行号区间

        Args:
            novel_text: 小说文本内容
            novel_lines_count: 小说文本行数（行号从 1 开始计数）
            min_episodes: 最小集数
            max_episodes: 最大集数

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = f"""你是一位经验丰富的竖屏短剧剧本创作总监。

## 任务
分析以下小说内容，在 {min_episodes}-{max_episodes} 集范围内自主决定最佳集数，并为每一集规划大纲。

## 竖屏短剧特征
- 竖屏观看、单集 1-3 分钟、节奏极快
- 保证每集时长差别不大，不要上一集 3 分钟、下一集只有 1 分钟
- 每集结尾必须有悬念钩子
- 剧情需要均匀分配到全部集数

## 剧情分配铁律
- 前 1/3 集：建立矛盾、积累情绪
- 中 1/3 集：反转升级、多线推进
- 后 1/3 集：高潮爆发、逐一清算
- 严禁在前 1/3 集数内写出结局、全剧终、最终对决

## 输出格式
你必须输出严格合法的 JSON（不要有其他任何文字），格式如下：
{{
  "total_episodes": 80,
  "outlines": [
    {{
      "episode": 1,
      "line_range": {{"start": 1, "end": 45}},
      "original_range": "第1章",
      "core_plot": "女主被退婚，当众受辱，暗下决心复仇",
      "ending_hook": "神秘男子递来一封信，信中内容让女主震惊"
    }}
  ]
}}

字段说明：
- total_episodes: 总集数（必须在 {min_episodes}-{max_episodes} 范围内）
- outlines: 按集数升序排列的数组，每集包含：
  - episode: 集数（从 1 开始的连续整数）
  - line_range: {{start, end}} 本集对应的小说行号区间（行号从 1 开始，到 {novel_lines_count} 结束）
  - original_range: 人类可读的原文范围描述（如"第1章-第3章"）
  - core_plot: 核心剧情（不超过 40 字）
  - ending_hook: 结尾悬念钩子

请确保 JSON 合法，所有字段齐全。
"""
        user_prompt = f"""请分析以下小说，决定最佳集数并输出逐集大纲：

【小说内容】
{novel_text}

请输出 JSON 格式的集数决策和逐集大纲。
"""
        return system_prompt, user_prompt

    @staticmethod
    def _parse_combined_response(response: str) -> "StageOneResult | None":
        """
        将阶段一 LLM 响应解析为 StageOneResult 对象。

        解析失败（JSON 不合法、字段缺失、类型错误等）返回 None。

        Args:
            response: LLM 原始响应字符串

        Returns:
            StageOneResult 或 None
        """
        # 1. 提取 JSON：LLM 可能在 JSON 前后有额外文字
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            logger.warning("[_parse_combined_response] 未找到 JSON 块")
            return None

        json_str = match.group(0)

        # 2. 尝试解析 JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"[_parse_combined_response] JSON 解析失败: {e}")
            return None

        # 3. 验证顶层字段
        if "total_episodes" not in data or "outlines" not in data:
            logger.warning("[_parse_combined_response] 缺少顶层字段 total_episodes 或 outlines")
            return None

        total_episodes = data["total_episodes"]
        outlines_raw = data["outlines"]

        if not isinstance(total_episodes, int):
            logger.warning("[_parse_combined_response] total_episodes 类型错误，应为 int")
            return None

        if not isinstance(outlines_raw, list):
            logger.warning("[_parse_combined_response] outlines 类型错误，应为 list")
            return None

        # 4. 遍历验证每集大纲
        episode_outlines: list[EpisodeOutline] = []
        required_fields = {"episode", "line_range", "original_range", "core_plot", "ending_hook"}

        for item in outlines_raw:
            if not isinstance(item, dict):
                logger.warning(f"[_parse_combined_response] outline 项不是 dict: {item}")
                return None

            missing = required_fields - item.keys()
            if missing:
                logger.warning(f"[_parse_combined_response] 缺少必填字段: {missing}")
                return None

            # 验证 episode 字段
            if not isinstance(item["episode"], int):
                logger.warning(f"[_parse_combined_response] episode 字段类型错误: {item['episode']}")
                return None

            # 验证 line_range 嵌套 dict
            line_range = item["line_range"]
            if not isinstance(line_range, dict):
                logger.warning(f"[_parse_combined_response] line_range 类型错误，应为 dict")
                return None
            if "start" not in line_range or "end" not in line_range:
                logger.warning("[_parse_combined_response] line_range 缺少 start 或 end 字段")
                return None
            if not isinstance(line_range["start"], int) or not isinstance(line_range["end"], int):
                logger.warning("[_parse_combined_response] line_range.start/end 类型错误，应为 int")
                return None

            # 验证剩余字段类型
            if not isinstance(item["original_range"], str):
                logger.warning(f"[_parse_combined_response] original_range 类型错误")
                return None
            if not isinstance(item["core_plot"], str):
                logger.warning(f"[_parse_combined_response] core_plot 类型错误")
                return None
            if not isinstance(item["ending_hook"], str):
                logger.warning(f"[_parse_combined_response] ending_hook 类型错误")
                return None

            # 构建对象
            lr = LineRange(start=line_range["start"], end=line_range["end"])
            outline = EpisodeOutline(
                episode=item["episode"],
                line_range=lr,
                original_range=item["original_range"],
                core_plot=item["core_plot"],
                ending_hook=item["ending_hook"],
            )
            episode_outlines.append(outline)

        # 5. 按 episode 升序排序
        episode_outlines.sort(key=lambda x: x.episode)

        # 6. 返回结果
        return StageOneResult(total_episodes=total_episodes, outlines=episode_outlines)

    @staticmethod
    def _validate_outlines(stage_one: StageOneResult, min_episodes: int,
                           max_episodes: int, novel_lines_count: int) -> str | None:
        """
        验证 StageOneResult 的完整性。

        验证通过返回 None，失败返回具体失败原因字符串。

        Args:
            stage_one: 阶段一解析结果
            min_episodes: 最小集数
            max_episodes: 最大集数
            novel_lines_count: 小说文本行数

        Returns:
            None 表示验证通过，否则返回错误描述字符串
        """
        # 1. 总集数范围
        if not (min_episodes <= stage_one.total_episodes <= max_episodes):
            return (f"总集数 {stage_one.total_episodes} 不在 "
                    f"[{min_episodes}, {max_episodes}] 范围内")

        n = stage_one.total_episodes

        # 2. 大纲数量匹配
        if len(stage_one.outlines) != n:
            return f"大纲数量 {len(stage_one.outlines)} 与总集数 {n} 不一致"

        # 3. 集数连续性
        expected_episodes = list(range(1, n + 1))
        actual_episodes = [o.episode for o in stage_one.outlines]
        if actual_episodes != expected_episodes:
            return f"集数不连续，期望 1..{n}，实际为 {actual_episodes}"

        # 4. 行号范围
        for o in stage_one.outlines:
            if not (1 <= o.line_range.start <= novel_lines_count and
                    1 <= o.line_range.end <= novel_lines_count):
                return (f"第 {o.episode} 集行号越界：start={o.line_range.start}, "
                        f"end={o.line_range.end}, 有效范围 [1, {novel_lines_count}]")

        # 5. 相邻集行号连续性
        for i in range(1, len(stage_one.outlines)):
            prev_end = stage_one.outlines[i - 1].line_range.end
            curr_start = stage_one.outlines[i].line_range.start
            if curr_start != prev_end + 1:
                return (f"行号不连续：第 {i + 1} 集 start={curr_start} != "
                        f"第 {i} 集 end+1={prev_end + 1}")

        return None

    @staticmethod
    def _aggregate_batches(outlines: list, batch_size: int = 10,
                           redundancy: int = 2) -> list[BatchRange]:
        """
        将 N 集大纲按 batch_size 分批，每批带前后冗余集数。

        Args:
            outlines: 集数大纲列表（list[EpisodeOutline]）
            batch_size: 每批基准集数，默认 10
            redundancy: 前后冗余集数，默认 2

        Returns:
            list[BatchRange] 批次范围列表
        """
        n = len(outlines)
        if n == 0:
            return []

        # 总集数不超过 batch_size 时单批返回，无冗余
        if n <= batch_size:
            return [BatchRange(start=1, end=n)]

        # 按 batch_size 切分批次
        batches: list[BatchRange] = []
        for i in range(0, n, batch_size):
            batch_start = i + 1
            batch_end = min(i + batch_size, n)

            # 计算前冗余
            is_first = (batch_start == 1)
            pre_start = None if is_first else max(1, batch_start - redundancy)

            # 计算后冗余
            is_last = (batch_end == n)
            post_end = None if is_last else min(batch_end + redundancy, n)

            batches.append(BatchRange(
                start=batch_start,
                end=batch_end,
                pre_start=pre_start,
                post_end=post_end,
            ))

        return batches

    @staticmethod
    def _extract_batch_text(novel_lines: list[str], outlines: list,
                            batch_range: BatchRange) -> tuple[str, str, str]:
        """
        根据 LLM 标注的行号区间，从 novel_lines 中提取本批对应的原文文本，
        包含前冗余、本批、后冗余三部分。

        Args:
            novel_lines: 小说按行分割后的列表（索引从 0 开始，行号从 1 开始计数）
            outlines: EpisodeOutline 列表（已按集数升序排序）
            batch_range: BatchRange 对象（含 start, end, pre_start, post_end）

        Returns:
            (pre_text, main_text, post_text) 三元组
        """
        # 构建 episode -> EpisodeOutline 映射，方便按集数查找
        outline_map = {o.episode: o for o in outlines}

        def line_range_for_episodes(ep_start: int, ep_end: int) -> tuple[int, int]:
            """获取指定集数范围对应的行号区间（含边界）"""
            line_start = outline_map[ep_start].line_range.start
            line_end = outline_map[ep_end].line_range.end
            return line_start, line_end

        def clamp_line_range(line_start: int, line_end: int) -> tuple[int, int]:
            """将行号范围截断到有效区间，并记录越界警告"""
            total_lines = len(novel_lines)
            clamped_start = max(1, line_start)
            clamped_end = min(line_end, total_lines)
            if clamped_start != line_start or clamped_end != line_end:
                logger.warning(
                    f"[_extract_batch_text] 行号越界，原始范围 [{line_start}, {line_end}]，"
                    f"截断后 [{clamped_start}, {clamped_end}]，总行数 {total_lines}"
                )
            return clamped_start, clamped_end

        def slice_lines(line_start: int, line_end: int) -> str:
            """根据行号范围提取文本（行号 N 对应 novel_lines[N-1]）"""
            clamped_start, clamped_end = clamp_line_range(line_start, line_end)
            if clamped_start > clamped_end:
                return ""
            # Python 切片 end 是 exclusive，所以直接用 clamped_end（行号含边界）
            return "\n".join(novel_lines[clamped_start - 1:clamped_end])

        # 1. 本批行号范围：batch_range.start 集到 batch_range.end 集
        main_start, main_end = line_range_for_episodes(batch_range.start, batch_range.end)

        # 2. 前冗余行号范围：pre_start 集到 batch_range.start - 1 集
        pre_text = ""
        if batch_range.pre_start is not None:
            pre_start_ep = batch_range.pre_start
            pre_end_ep = batch_range.start - 1
            if pre_start_ep <= pre_end_ep:
                pre_line_start, pre_line_end = line_range_for_episodes(pre_start_ep, pre_end_ep)
                pre_text = slice_lines(pre_line_start, pre_line_end)

        # 3. 后冗余行号范围：batch_range.end + 1 集到 post_end 集
        post_text = ""
        if batch_range.post_end is not None:
            post_start_ep = batch_range.end + 1
            post_end_ep = batch_range.post_end
            if post_start_ep <= post_end_ep:
                post_line_start, post_line_end = line_range_for_episodes(post_start_ep, post_end_ep)
                post_text = slice_lines(post_line_start, post_line_end)

        # 4. 提取本批原文
        main_text = slice_lines(main_start, main_end)

        return pre_text, main_text, post_text

    def _build_batch_prompt_v2(self, batch_range: BatchRange,
                               batch_outlines: list,
                               pre_text: str,
                               main_text: str,
                               post_text: str,
                               ctx: AutoPromptContext) -> tuple[str, str]:
        """
        构建阶段三每批生成的提示词，包含冗余原文并明确标注。

        Args:
            batch_range: BatchRange 对象（本批集数范围 + 冗余信息）
            batch_outlines: 本批对应集的 EpisodeOutline 列表（按集数排序）
            pre_text: 前冗余原文（可能为空字符串）
            main_text: 本批对应原文
            post_text: 后冗余原文（可能为空字符串）
            ctx: AutoPromptContext 上下文（含 template_content, total_episodes, outline_dict）

        Returns:
            (system_prompt, user_prompt) 元组
        """
        # 构建本批逐集大纲文本
        outline_parts = []
        for outline in batch_outlines:
            outline_parts.append(
                f"第{outline.episode}集：\n"
                f"  核心剧情：{outline.core_plot}\n"
                f"  结尾钩子：{outline.ending_hook}"
            )
        outline_text = "\n".join(outline_parts)

        # 判断是否为最后 5 集批次
        is_last_batch = batch_range.end >= ctx.total_episodes - 5
        last_batch_note = "" if is_last_batch else "（除非本批是最后 5 集）"

        # 构建 system_prompt
        system_prompt = f"""你是一位经验丰富的竖屏短剧剧本创作总监。

## 竖屏短剧核心特征
- 竖屏观看：画面聚焦人物面部和上半身
- 单集 1-3 分钟：每集约 200-500 字
- 节奏极快：每集只聚焦一个情绪爆点或情节转折，1-2 个场景
- 情绪浓烈：冲突直接、台词犀利
- 每集结尾必须有钩子：用【卡点】标记

## 剧情分配铁律
- 剧情必须均匀分配到全部 {ctx.total_episodes} 集
- 严禁在本批写出全剧结局{last_batch_note}
- 严格按照本批逐集大纲写作，不要跳过集数

{_FORMAT_RULES}
7. 每集结尾用【卡点】标记悬念

## 本批逐集大纲（严格遵循）
{outline_text}

以下是剧本格式模板：
{ctx.template_content}

请直接输出剧本内容，不要有额外解释。
"""

        # 构建 user_prompt，冗余部分仅在非空时包含
        pre_section = ""
        if pre_text:
            pre_section = f"""【以下原文仅供上下文参考，不要生成对应剧本】
{pre_text}

"""

        post_section = ""
        if post_text:
            post_section = f"""【以下原文仅供上下文参考，不要生成对应剧本】
{post_text}

"""

        user_prompt = f"""请生成第 {batch_range.start} 集到第 {batch_range.end} 集（共 {ctx.total_episodes} 集）：

{pre_section}【本集参考原文】
{main_text}

{post_section}【要求】
1. 仅生成第 {batch_range.start} 集到第 {batch_range.end} 集的剧本正文
2. 每集 200-500 字，1-2 个场景
3. 每集结尾必须用【卡点】标记设置悬念
4. 严格遵循上方逐集大纲
5. 冗余原文仅供上下文参考，不要为冗余部分生成剧本

开始创作：
"""

        return system_prompt, user_prompt


