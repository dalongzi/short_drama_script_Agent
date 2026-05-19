
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

    def generate(self, system_prompt: str, user_prompt: str) -> tuple:
        """
        调用 LLM 生成文本

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Returns:
            (生成的文本内容, usage 字典含 prompt_tokens/completion_tokens/total_tokens)

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
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens,
            }
            return response.choices[0].message.content, usage
        except Exception as e:
            raise LLMCallError(f"LLM 调用失败: {str(e)}") from e

    def generate_stream(self, system_prompt: str, user_prompt: str):
        """
        流式调用 LLM 生成文本，逐 token 返回

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Yields:
            对于普通 chunk，yield ('token', token_text)
            对于最后一个含 usage 的 chunk，yield ('usage', usage_dict)

        Raises:
            LLMCallError: LLM 调用失败时抛出
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in response:
                if chunk.usage:
                    usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens,
                        'completion_tokens': chunk.usage.completion_tokens,
                        'total_tokens': chunk.usage.total_tokens,
                    }
                    yield ('usage', usage)
                elif chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield ('token', delta.content)
        except Exception as e:
            raise LLMCallError(f"LLM 流式调用失败: {str(e)}") from e

