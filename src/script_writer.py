
from src.llm_client import LLMClient


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
            print("\n" + "=" * 80)
            print("系统提示词 (System Prompt):")
            print("=" * 80)
            print(system_prompt)
            print("=" * 80 + "\n")
            
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
            import re
            template_content = self._read_template()

            # ===== 阶段一：决定集数 =====
            print("\n" + "=" * 80)
            print("阶段一：分析小说内容，决定集数...")
            print("=" * 80)

            system_prompt_decide, user_prompt_decide = self._build_decide_episodes_prompt(
                novel_text, min_episodes, max_episodes
            )

            print("\n系统提示词 (System Prompt):")
            print("-" * 40)
            print(system_prompt_decide)
            print("-" * 40 + "\n")

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

            print("\n系统提示词 (System Prompt):")
            print("-" * 40)
            print(system_prompt_outline)
            print("-" * 40 + "\n")

            outline_response = self.llm_client.generate(system_prompt_outline, user_prompt_outline)
            print(f"大纲生成完成。")

            # ===== 阶段三：按大纲分批生成正文 =====
            print("\n" + "=" * 80)
            print(f"阶段三：按大纲分批生成剧本正文（共 {total_episodes} 集，每批 {batch_size} 集）...")
            print("=" * 80)

            all_script_content = f"【集数：{total_episodes}集】\n\n"
            current_episode = 1

            while current_episode <= total_episodes:
                end_episode = min(current_episode + batch_size - 1, total_episodes)
                print(f"\n生成第 {current_episode} - {end_episode} 集...")

                system_prompt, user_prompt = self._build_auto_prompt(
                    novel_text, template_content, min_episodes, max_episodes,
                    current_episode, end_episode, total_episodes,
                    outline_section=self._extract_outline_section(outline_response, current_episode, end_episode)
                )

                print("\n系统提示词 (System Prompt):")
                print("-" * 40)
                print(system_prompt)
                print("-" * 40 + "\n")

                batch_content = self.llm_client.generate(system_prompt, user_prompt)

                # 去掉集数声明（只保留一次）
                if current_episode == 1 and batch_content.startswith("【集数："):
                    first_newline = batch_content.find("\n")
                    if first_newline != -1:
                        batch_content = batch_content[first_newline + 1:].lstrip()

                all_script_content += batch_content + "\n\n"
                current_episode = end_episode + 1

            self.save_script(all_script_content, output_path)
            return all_script_content
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
  核心剧情：...
  结尾钩子：...
"""
        user_prompt = f"""请为以下小说规划 {total_episodes} 集的逐集大纲：

【小说内容】
{novel_text}

请输出完整的 {total_episodes} 集大纲。"""
        return system_prompt, user_prompt

    def _extract_outline_section(self, outline_response: str, start: int, end: int) -> str:
        """
        从完整大纲中提取指定集数范围的大纲片段

        Args:
            outline_response: 完整大纲文本
            start: 起始集数
            end: 结束集数

        Returns:
            指定集数范围的大纲文本
        """
        lines = outline_response.split('\n')
        result = []
        capturing = False
        for line in lines:
            # 匹配"第X集"或"第XX集"等模式
            import re
            ep_match = re.match(r'^第(\d+)集', line.strip())
            if ep_match:
                ep_num = int(ep_match.group(1))
                if ep_num == start:
                    capturing = True
                elif ep_num > end:
                    break
            if capturing:
                result.append(line)
        return '\n'.join(result)

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

    def _build_auto_prompt(self, novel_text: str, template_content: str,
                           min_episodes: int, max_episodes: int,
                           start_episode: int = 1, end_episode: int = None,
                           total_episodes: int = None,
                           outline_section: str = None) -> tuple[str, str]:
        """
        构建自动集数判断的提示词

        Args:
            novel_text: 小说文本
            template_content: 模板内容
            min_episodes: 最小集数
            max_episodes: 最大集数
            start_episode: 本批开始的集数
            end_episode: 本批结束的集数
            total_episodes: 总集数
            outline_section: 本批对应的逐集大纲片段

        Returns:
            (system_prompt, user_prompt) 元组
        """
        if end_episode is None:
            end_episode = max_episodes
        if total_episodes is None:
            total_episodes = max_episodes

        outline_text = f"""
## 本批逐集大纲（严格遵循）
{outline_section}
""" if outline_section else ""

        system_prompt = f"""你是一位经验丰富的竖屏短剧剧本创作总监。

## 竖屏短剧核心特征
- **竖屏观看**：画面聚焦人物面部和上半身，场景精简
- **单集 1-3 分钟**：内容极度浓缩，每集约 200-500 字
- **节奏极快**：每集只聚焦一个情绪爆点或情节转折，1-2 个场景
- **情绪浓烈**：冲突直接、台词犀利，让观众产生强烈代入感
- **每集结尾必须有钩子**：用【卡点】标记，设置悬念让观众忍不住滑向下一集

## 剧情分配铁律
- 剧情必须均匀分配到全部 {total_episodes} 集
- **严禁在本批写出结局、全剧终、最终对决或主角彻底离开的场景**（除非本批是最后 5 集）
- 严格按照上方提供的「本批逐集大纲」写作，不要跳过大钢中的集数

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
{template_content}

请直接输出剧本内容，不要有额外解释。
"""

        user_prompt = f"""请将以下小说改编为竖屏短剧剧本，生成第 {start_episode} 集到第 {end_episode} 集（共 {total_episodes} 集）：

【小说内容】
{novel_text}

【要求】
1. 生成第 {start_episode} 集到第 {end_episode} 集
2. 每集 200-500 字，1-2 个场景
3. 每集结尾必须用【卡点】标记设置悬念
4. 严格遵循上方提供的逐集大纲和格式规范

开始创作：
"""

        return system_prompt, user_prompt

