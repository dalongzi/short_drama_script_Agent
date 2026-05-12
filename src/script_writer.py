import re
from dataclasses import dataclass, field

from src.llm_client import LLMClient


@dataclass(frozen=True)
class BatchRange:
    """单批生成的集数范围"""
    start: int
    end: int


@dataclass(frozen=True)
class AutoPromptContext:
    """自动集数提示词构建的上下文配置"""
    template_content: str
    total_episodes: int
    outline_response: str = ""
    outline_dict: dict[int, str] = field(default_factory=dict)
    novel_segments: dict[int, str] = field(default_factory=dict)


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

    def _print_system_prompt(self, prompt: str, separator: str = "-" * 40) -> None:
        print(f"\n系统提示词 (System Prompt):")
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
            
            script_content = self.llm_client.generate(system_prompt, user_prompt)
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

1. 集数标注：使用"第X集"或"第一集"开头
2. 场景格式："1-1 日 内 九重天"（编号-子编号 日/夜 内/外 地点）
3. 动作描述：使用 △ 符号开头标注除对话外的内容
4. 语气神态：使用 () 括号描写人物说话时的语气、神态、动作
5. 内心独白：使用 VO 或 OS 标记
6. 回忆镜头：开始用【闪回】，结束用【闪出】

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
                                      min_episodes: int = 60, max_episodes: int = 100,
                                      batch_size: int = 10) -> str:
        """
        让LLM自主判断集数并生成剧本（三阶段：决定集数 → 生成大纲 → 按大纲分批写正文）

        Args:
            novel_text: 小说文本内容
            output_path: 输出剧本文件路径
            min_episodes: 最小集数，默认为60
            max_episodes: 最大集数，默认为100
            batch_size: 每批生成的集数，默认为10

        Returns:
            生成的剧本内容

        Raises:
            ScriptGenerationError: 剧本生成失败时抛出
        """
        try:
            template_content = self._read_template()

            # ===== 阶段一：决定集数 =====
            print("\n" + "=" * 80)
            print("阶段一：分析小说内容，决定集数...")
            print("=" * 80)

            system_prompt_decide, user_prompt_decide = self._build_decide_episodes_prompt(
                novel_text, min_episodes, max_episodes
            )

            self._print_system_prompt(system_prompt_decide)

            decide_response = self.llm_client.generate(system_prompt_decide, user_prompt_decide)

            match = re.search(r'【集数：(\d+)集】', decide_response)
            if match:
                total_episodes = int(match.group(1))
                print(f"LLM 决策的总集数: {total_episodes} 集")
            else:
                total_episodes = max_episodes
                print(f"未能解析集数，使用默认值: {total_episodes} 集")

            # ===== 阶段二：生成逐集大纲 =====
            print("\n" + "=" * 80)
            print(f"阶段二：生成 {total_episodes} 集逐集大纲（每集剧情+钩子）...")
            print("=" * 80)

            system_prompt_outline, user_prompt_outline = self._build_outline_prompt(novel_text, total_episodes)

            self._print_system_prompt(system_prompt_outline)

            outline_response = self.llm_client.generate(system_prompt_outline, user_prompt_outline)
            print(f"大纲生成完成。")

            # ===== 阶段三：按大纲分批生成正文 =====
            print("\n" + "=" * 80)
            print(f"阶段三：按大纲分批生成剧本正文（共 {total_episodes} 集，每批 {batch_size} 集）...")
            print("=" * 80)

            # 解析大纲一次，构建 {集数: 大纲文本} 映射
            outline_dict = self._parse_outline(outline_response)

            # 将小说分段，每集映射到对应片段
            chapters = self._split_novel_by_chapters(novel_text)
            novel_segments = self._map_episodes_to_segments(chapters, total_episodes)

            # 构建不变的上下文
            ctx = AutoPromptContext(
                template_content=template_content,
                total_episodes=total_episodes,
                outline_response=outline_response,
                outline_dict=outline_dict,
                novel_segments=novel_segments,
            )

            current_episode = 1
            first_batch = True

            while current_episode <= total_episodes:
                end_episode = min(current_episode + batch_size - 1, total_episodes)
                print(f"\n生成第 {current_episode} - {end_episode} 集...")

                batch = BatchRange(start=current_episode, end=end_episode)

                # 从预解析的字典中查找大纲
                batch_outline = self._get_outline_range(outline_dict, current_episode, end_episode)

                # 合并当前批次对应的小说片段
                batch_segment = '\n\n'.join(
                    novel_segments[ep] for ep in range(current_episode, end_episode + 1) if ep in novel_segments
                )

                system_prompt, user_prompt = self._build_auto_prompt(
                    batch, batch_outline, batch_segment, ctx
                )

                self._print_system_prompt(system_prompt)

                batch_content = self.llm_client.generate(system_prompt, user_prompt)

                # 去掉集数声明（只保留一次）
                if first_batch and batch_content.startswith("【集数："):
                    first_newline = batch_content.find("\n")
                    if first_newline != -1:
                        batch_content = batch_content[first_newline + 1:].lstrip()

                # 逐批写入文件，避免在内存中累积
                with open(output_path, 'w' if first_batch else 'a', encoding='utf-8') as f:
                    if first_batch:
                        f.write(f"【集数：{total_episodes}集】\n\n")
                    f.write(batch_content + "\n\n")

                first_batch = False
                current_episode = end_episode + 1

            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise ScriptGenerationError(f"剧本生成失败: {str(e)}") from e

    def _build_outline_prompt(self, novel_text: str, total_episodes: int) -> tuple[str, str]:
        """
        构建逐集大纲的提示词，让 LLM 为每一集规划核心剧情和结尾钩子

        Args:
            novel_text: 小说文本
            total_episodes: 总集数

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = f"""你是一位经验丰富的竖屏短剧剧本创作总监。

## 任务
将以下小说改编为 {total_episodes} 集竖屏短剧，为每一集规划：
1. 核心剧情（1-2 句话概括本集发生了什么）
2. 结尾钩子（1 句话说明本集结尾的悬念/卡点）
3. 原文范围（标注本集对应的小说章节/段落范围，如"第1章-第3章"）

## 竖屏短剧节奏约束
- 单集观看时长 1-3 分钟，内容极度浓缩
- 每集只聚焦一个情绪爆点或情节转折
- 每集结尾必须设置悬念/卡点，让观众忍不住滑向下一集
- 剧情必须均匀分配到全部 {total_episodes} 集
- **严禁在前 1/3 集数内写出结局、全剧终、最终对决或主角彻底离开的场景**
- 前 1/3 集：建立矛盾、积累情绪
- 中 1/3 集：反转升级、多线推进
- 后 1/3 集：高潮爆发、逐一清算

## 输出格式
按以下格式逐集输出（不要写剧本正文）：
第X集：
  原文范围：...
  核心剧情：...
  结尾钩子：...
"""
        user_prompt = f"""请为以下小说规划 {total_episodes} 集的逐集大纲：

【小说内容】
{novel_text}

请输出完整的 {total_episodes} 集大纲。"""
        return system_prompt, user_prompt

    def _parse_outline(self, outline_response: str) -> dict[int, str]:
        """
        从完整大纲中解析每集内容，构建 {集数: 大纲文本} 映射

        Args:
            outline_response: 完整大纲文本

        Returns:
            {集数: 该集大纲文本} 字典
        """
        result = {}
        current_ep = None
        for line in outline_response.split('\n'):
            ep_match = re.match(r'^第(\d+)集', line.strip())
            if ep_match:
                current_ep = int(ep_match.group(1))
                result[current_ep] = []
            if current_ep is not None:
                result[current_ep].append(line)
        return {k: '\n'.join(v) for k, v in result.items()}

    def _get_outline_range(self, outline_dict: dict[int, str], start: int, end: int) -> str:
        """
        从预解析的大纲字典中提取指定集数范围的大纲片段

        Args:
            outline_dict: {集数: 该集大纲文本} 字典
            start: 起始集数
            end: 结束集数

        Returns:
            指定集数范围的大纲文本
        """
        parts = []
        for ep in range(start, end + 1):
            if ep in outline_dict:
                parts.append(outline_dict[ep])
        return '\n'.join(parts)

    def _split_novel_by_chapters(self, novel_text: str) -> list[tuple[str, str]]:
        """
        将小说按章节标题分割为 (章节标题, 章节内容) 列表。
        若无章节结构则回退为按段落（空行）分割。
        """
        chapter_pattern = re.compile(r'^(第[零一二三四五六七八九十百千万\d]+[章节回卷篇])\s*(.*)', re.MULTILINE)
        matches = list(chapter_pattern.finditer(novel_text))

        if not matches:
            # 回退：按空行分割为段落块
            blocks = re.split(r'\n\s*\n', novel_text.strip())
            blocks = [b.strip() for b in blocks if b.strip()]
            return [(f"段落{i + 1}", b) for i, b in enumerate(blocks)]

        chapters = []
        for i, m in enumerate(matches):
            title = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(novel_text)
            content = novel_text[start:end].strip()
            chapters.append((title, content))
        return chapters

    def _map_episodes_to_segments(self, chapters: list[tuple[str, str]], total_episodes: int) -> dict[int, str]:
        """
        将每集映射到对应的小说片段，按集数比例均匀分配。
        每集对应一个章节范围，相邻集共享章节保证连续性。
        """
        result = {}
        if not chapters:
            return result

        for ep in range(1, total_episodes + 1):
            # 按集数比例映射到章节索引（0-based）
            chapter_idx = int((ep - 1) / total_episodes * len(chapters))
            chapter_idx = min(chapter_idx, len(chapters) - 1)
            # 每集只取当前章，不重叠
            result[ep] = chapters[chapter_idx][1]
        return result

    def _extract_novel_segment_range(self, chapters: list[tuple[str, str]], start_chapter: int, end_chapter: int) -> str:
        """
        从章节列表中提取指定范围的文本。
        """
        start_idx = max(0, start_chapter - 1)
        end_idx = min(len(chapters), end_chapter)
        parts = [chapters[i][1] for i in range(start_idx, end_idx)]
        return '\n\n'.join(parts)

    def _build_decide_episodes_prompt(self, novel_text: str, min_episodes: int, max_episodes: int) -> tuple[str, str]:
        """
        构建集数决策的提示词

        Args:
            novel_text: 小说文本
            min_episodes: 最小集数
            max_episodes: 最大集数

        Returns:
            (system_prompt, user_prompt) 元组
        """
        low = int(min_episodes + (max_episodes - min_episodes) * 0.17)
        mid = int(min_episodes + (max_episodes - min_episodes) * 0.42)
        system_prompt = f"""你是一位经验丰富的竖屏短剧剧本创作总监。

## 核心任务
分析小说内容，在 {min_episodes}-{max_episodes} 集范围内自主决定最佳集数。

## 竖屏短剧特征
- 竖屏观看、单集 1-3 分钟、节奏极快
- 每集结尾必须有悬念钩子
- 剧情需要均匀分配到全部集数

## 集数决策指南
- {min_episodes}-{low}集：适合情节紧凑、主线清晰的故事
- {low + 1}-{mid}集：适合中等复杂度、多支线故事
- {mid + 1}-{max_episodes}集：适合宏大叙事、多人物、多反转的故事

## 输出格式
【集数：XX集】

只需输出集数决策，不需要输出剧本内容。
"""
        user_prompt = f"""请分析以下小说内容，决定最佳集数（{min_episodes}-{max_episodes}集）：

【小说内容】
{novel_text}

请分析后输出集数决策。
"""
        return system_prompt, user_prompt

    def _build_auto_prompt(self, *args, **kwargs) -> tuple[str, str]:
        """
        构建自动集数判断的提示词。

        新签名（推荐）：
            _build_auto_prompt(batch: BatchRange, outline_section: str, novel_segment: str, ctx: AutoPromptContext)

        向后兼容旧签名：
            _build_auto_prompt(novel_text, template_content, min_ep, max_ep, start, end, total, outline_section=...)
        """
        if args and isinstance(args[0], BatchRange):
            return self._build_auto_prompt_new(*args, **kwargs)
        else:
            return self._build_auto_prompt_legacy(*args, **kwargs)

    def _build_auto_prompt_new(self, batch: BatchRange,
                                outline_section: str = "",
                                novel_segment: str = "",
                                ctx: AutoPromptContext = None) -> tuple[str, str]:

        outline_text = f"""
## 本批逐集大纲（严格遵循）
{outline_section}
""" if outline_section else ""

        is_last_batch = batch.end >= ctx.total_episodes - 5 if ctx else False
        last_batch_note = "" if is_last_batch else "（除非本批是最后 5 集）"

        system_prompt = f"""你是一位经验丰富的竖屏短剧剧本创作总监。

## 竖屏短剧核心特征
- **竖屏观看**：画面聚焦人物面部和上半身，场景精简
- **单集 1-3 分钟**：内容极度浓缩，每集约 200-500 字
- **节奏极快**：每集只聚焦一个情绪爆点或情节转折，1-2 个场景
- **情绪浓烈**：冲突直接、台词犀利，让观众产生强烈代入感
- **每集结尾必须有钩子**：用【卡点】标记，设置悬念让观众忍不住滑向下一集

## 剧情分配铁律
- 剧情必须均匀分配到全部 {ctx.total_episodes} 集
- **严禁在本批写出结局、全剧终、最终对决或主角彻底离开的场景**{last_batch_note}
- 严格按照上方提供的「本批逐集大纲」写作，不要跳过大纲中的集数

## 剧本格式规范
1. 集数标注："第X集"开头
2. 场景格式："1-1 日 内 九重天"（编号-子编号 日/夜 内/外 地点）
3. 动作描述：使用 △ 符号开头标注除对话外的内容
4. 语气神态：使用 () 括号描写人物说话时的语气、神态、动作
5. 内心独白：使用 VO 或 OS 标记
6. 回忆镜头：开始用【闪回】，结束用【闪出】
7. 每集结尾用【卡点】标记悬念

{outline_text}
以下是剧本格式模板：
{ctx.template_content}

请直接输出剧本内容，不要有额外解释。
"""

        user_prompt = f"""请将以下小说改编为竖屏短剧剧本，生成第 {batch.start} 集到第 {batch.end} 集（共 {ctx.total_episodes} 集）：

【本集参考原文】
{novel_segment}

【要求】
1. 生成第 {batch.start} 集到第 {batch.end} 集
2. 每集 200-500 字，1-2 个场景
3. 每集结尾必须用【卡点】标记设置悬念
4. 严格遵循上方提供的逐集大纲和格式规范

开始创作：
"""

        return system_prompt, user_prompt

    def _build_auto_prompt_legacy(self, novel_text: str, template_content: str,
                                   min_episodes: int, max_episodes: int,
                                   start_episode: int = 1, end_episode: int = None,
                                   total_episodes: int = None,
                                   outline_section: str = None) -> tuple[str, str]:
        """旧签名兼容层，将旧参数转换为新签名调用"""
        if end_episode is None:
            end_episode = max_episodes
        if total_episodes is None:
            total_episodes = max_episodes

        batch = BatchRange(start=start_episode, end=end_episode)
        ctx = AutoPromptContext(template_content=template_content, total_episodes=total_episodes)
        return self._build_auto_prompt_new(batch, outline_section or "", novel_text, ctx)

