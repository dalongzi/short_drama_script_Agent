
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.llm_client import LLMClient
from src.novel_reader import read_novel
from src.script_writer import ScriptWriter
from src.format_validator import validate_script_format


def main(novel_path: str, output_path: str, num_episodes: int = 1, 
         auto_episodes: bool = False, min_episodes: int = 60, max_episodes: int = 100):
    """
    主函数

    Args:
        novel_path: 输入小说文件路径
        output_path: 输出剧本文件路径
        num_episodes: 生成的集数
        auto_episodes: 是否启用自动集数模式
        min_episodes: 最小集数（自动模式下）
        max_episodes: 最大集数（自动模式下）
    """
    print("=== 开始改编短剧剧本 ===")
    
    # 加载配置
    config = Config()
    print(f"配置加载完成:")
    print(f"  - MODEL: {config.model}")
    
    # 读取小说
    print(f"正在读取小说: {novel_path}")
    novel_text = read_novel(novel_path)
    print(f"小说读取成功，内容长度: {len(novel_text)} 字符")
    
    # 初始化组件
    llm_client = LLMClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model
    )
    script_writer = ScriptWriter(llm_client, template_path="data/短剧剧本写作格式模板.md")
    
    # 生成剧本
    print("正在生成剧本...")
    if auto_episodes:
        print(f"使用自动集数模式，集数范围: {min_episodes}-{max_episodes}集")
        script_content = script_writer.generate_script_auto_episodes(
            novel_text=novel_text,
            output_path=output_path,
            min_episodes=min_episodes,
            max_episodes=max_episodes
        )
    else:
        script_content = script_writer.generate_script(
            novel_text=novel_text,
            output_path=output_path,
            num_episodes=num_episodes
        )
    print(f"剧本生成完成，已保存到: {output_path}")
    
    # 校验格式
    print("正在校验剧本格式...")
    is_valid, issues = validate_script_format(script_content, "data/短剧剧本写作格式模板.md")
    if is_valid:
        print("剧本格式校验通过！")
    else:
        print("剧本格式校验发现以下问题:")
        for issue in issues:
            print(f"  - {issue}")
    
    print("=== 改编完成 ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将小说改编为短剧剧本")
    parser.add_argument("--novel", type=str, required=True, help="输入小说文件路径")
    parser.add_argument("--output", type=str, required=True, help="输出剧本文件路径")
    parser.add_argument("--episodes", type=int, default=1, help="生成的集数（默认1集）")
    parser.add_argument("--auto-episodes", action="store_true", default=False, 
                        help="启用自动集数模式，由LLM根据小说内容自主判断集数")
    parser.add_argument("--min-episodes", type=int, default=60, help="自动模式下的最小集数（默认60）")
    parser.add_argument("--max-episodes", type=int, default=100, help="自动模式下的最大集数（默认100）")
    
    args = parser.parse_args()
    
    main(
        novel_path=args.novel,
        output_path=args.output,
        num_episodes=args.episodes,
        auto_episodes=args.auto_episodes,
        min_episodes=args.min_episodes,
        max_episodes=args.max_episodes
    )

