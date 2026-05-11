
import os
import pytest
from src.config import Config


def test_config_default_values(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    config = Config()
    assert config.api_key is None or config.api_key == ""
    assert config.base_url == "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen3.6-plus"


def test_config_from_dashscope_env_vars(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://test-url.com")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    
    config = Config()
    assert config.api_key == "dashscope-test-key"
    assert config.base_url == "https://test-url.com"
    assert config.model == "test-model"


def test_config_from_openai_env_vars(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://test-url.com")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    
    config = Config()
    assert config.api_key == "openai-test-key"
    assert config.base_url == "https://test-url.com"
    assert config.model == "test-model"


def test_config_dashscope_priority_over_openai(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-priority-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-fallback-key")
    
    config = Config()
    assert config.api_key == "dashscope-priority-key"


def test_config_with_custom_values():
    config = Config(
        api_key="custom-key",
        base_url="https://custom-url.com",
        model="custom-model"
    )
    assert config.api_key == "custom-key"
    assert config.base_url == "https://custom-url.com"
    assert config.model == "custom-model"

