from app.core.config import Settings


def test_default_llm_config_uses_deepseek():
    settings = Settings()

    assert settings.llm_base_url == "https://api.deepseek.com"
    assert settings.llm_model == "deepseek-reasoner"


def test_deepseek_api_key_env_alias_is_supported(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    settings = Settings(llm_api_key="")

    assert settings.resolved_llm_api_key == "test-key"
