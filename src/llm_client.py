
from openai import OpenAI


class LLMCallError(Exception):
    """
    LLM 调用异常类
    """
    pass


class LLMClient:
    """
    LLM 客户端类，封装 OpenAI SDK 调用
    """

    def __init__(self, api_key: str, base_url: str, model: str = "qwen3.6-plus"):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称，默认为 qwen3.6-plus
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用 LLM 生成文本

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Returns:
            生成的文本内容

        Raises:
            LLMCallError: LLM 调用失败时抛出
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMCallError(f"LLM 调用失败: {str(e)}") from e

