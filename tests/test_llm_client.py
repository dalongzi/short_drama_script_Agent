
import pytest
from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient, LLMCallError


def test_llm_client_initialization():
    client = LLMClient(
        api_key="test-key",
        base_url="https://test-url.com",
        model="test-model"
    )
    assert client.api_key == "test-key"
    assert client.base_url == "https://test-url.com"
    assert client.model == "test-model"


def test_llm_client_default_model():
    client = LLMClient(
        api_key="test-key",
        base_url="https://test-url.com"
    )
    assert client.model == "qwen3.6-plus"


@patch('src.llm_client.OpenAI')
def test_llm_client_generate_success(mock_openai):
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="生成的剧本内容"))]
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.return_value = mock_completion
    mock_openai.return_value = mock_client_instance

    client = LLMClient(api_key="test-key", base_url="https://test-url.com")
    result = client.generate("系统提示", "用户提示")

    assert result == "生成的剧本内容"
    mock_client_instance.chat.completions.create.assert_called_once()


@patch('src.llm_client.OpenAI')
def test_llm_client_generate_failure(mock_openai):
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = Exception("API 调用失败")
    mock_openai.return_value = mock_client_instance

    client = LLMClient(api_key="test-key", base_url="https://test-url.com")

    with pytest.raises(LLMCallError):
        client.generate("系统提示", "用户提示")

