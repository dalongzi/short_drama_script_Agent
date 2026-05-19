
import os
from dotenv import load_dotenv


class Config:
    """
    配置管理类，用于加载和管理项目配置项
    """

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        初始化配置

        Args:
            api_key: API 密钥，如果不提供则从环境变量加载
            base_url: API 基础 URL，如果不提供则从环境变量加载
            model: 模型名称，如果不提供则从环境变量加载
        """
        load_dotenv(override=False)

        self.api_key = api_key or os.getenv("TOKEN_API_KEY")
        self.base_url = base_url or os.getenv(
            "OPENAI_BASE_URL",
            "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model or os.getenv("OPENAI_MODEL", "qwen3.6-plus")

