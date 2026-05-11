from src.config import Config
from src.llm_client import LLMClient
from src.novel_reader import read_novel
from src.script_writer import ScriptWriter

config = Config()
llm_client = LLMClient(api_key=config.api_key, base_url=config.base_url, model=config.model)
script_writer = ScriptWriter(llm_client, template_path="data/短剧剧本写作格式模板.md")
novel_text = read_novel("data/弃妇逆袭：贺家真千金.txt")
script_content = script_writer.generate_script(novel_text, "data/输出剧本.txt", num_episodes=1)