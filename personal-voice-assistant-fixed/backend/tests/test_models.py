import pytest
from app.config import Settings
from app.core.model_adapters import ModelAdapter, ModelError


def test_model_configuration_validation():
    adapter = ModelAdapter(Settings(qwen_base_url="", qwen_model=""))
    with pytest.raises(ModelError):
        adapter.profile("bad-provider")


@pytest.mark.asyncio
async def test_health_unconfigured_is_not_reachable():
    adapter = ModelAdapter(Settings(qwen_base_url="", qwen_model=""))
    result = await adapter.health("qwen")
    assert result["configured"] is False
    assert result["reachable"] is False


def test_v1_base_url_resolves_to_openai_compatible_api():
    adapter = ModelAdapter(Settings(
        qwen_base_url="http://111.118.189.124:8100/v1",
        qwen_model="qwen-model",
        qwen_api_format="ollama",
    ))
    assert adapter._format("qwen") == "openai"


def test_auto_format_uses_openai_for_v1_url():
    adapter = ModelAdapter(Settings(
        qwen_base_url="http://localhost:8100/v1",
        qwen_model="qwen-model",
        qwen_api_format="auto",
    ))
    assert adapter._format("qwen") == "openai"


def test_auto_format_defaults_to_ollama_without_v1_path():
    adapter = ModelAdapter(Settings(
        qwen_base_url="http://localhost:11434",
        qwen_model="qwen-model",
        qwen_api_format="auto",
    ))
    assert adapter._format("qwen") == "ollama"


def test_full_chat_completions_url_is_not_duplicated():
    adapter = ModelAdapter(Settings(
        qwen_model_url="http://model-host:8100/v1/chat/completions",
        qwen_model_name="/home/expadmin/Mayank/Qwen",
        qwen_api_format="openai",
    ))
    _, url, model = adapter.profile("qwen")
    assert adapter._chat_endpoint(url, "openai") == "http://model-host:8100/v1/chat/completions"
    assert model == "/home/expadmin/Mayank/Qwen"


def test_ollama_compatibility_endpoint_uses_user_model_name():
    adapter = ModelAdapter(Settings(
        ollama_url="http://model-host:11435/v1/chat/completions",
        ollama_model="gpt-oss:120b",
        gpt_oss_api_format="openai",
    ))
    _, url, model = adapter.profile("gpt-oss")
    assert adapter._chat_endpoint(url, "openai") == "http://model-host:11435/v1/chat/completions"
    assert model == "gpt-oss:120b"
