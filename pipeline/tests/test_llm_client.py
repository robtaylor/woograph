"""Tests for the unified LLM client module."""

import os
from unittest.mock import MagicMock, patch

from woograph.llm.client import (
    PROVIDER_DEFAULTS,
    LLMConfig,
    create_completion,
    load_llm_config,
)


class TestLLMConfig:
    def test_dataclass_fields(self):
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
        )
        assert config.provider == "deepseek"
        assert config.model == "deepseek-chat"
        assert config.api_key == "sk-test"
        assert config.base_url == "https://api.deepseek.com"

    def test_defaults(self):
        config = LLMConfig(provider="openai", model="gpt-4", api_key="sk-test")
        assert config.base_url is None
        assert config.temperature == 0.0

    def test_custom_temperature(self):
        config = LLMConfig(
            provider="openai", model="gpt-4", api_key="sk-test", temperature=0.7
        )
        assert config.temperature == 0.7


class TestProviderDefaults:
    def test_deepseek_defaults(self):
        assert "deepseek" in PROVIDER_DEFAULTS
        assert PROVIDER_DEFAULTS["deepseek"]["model"] == "deepseek-chat"
        assert PROVIDER_DEFAULTS["deepseek"]["base_url"] == "https://api.deepseek.com"

    def test_openai_defaults(self):
        assert "openai" in PROVIDER_DEFAULTS
        assert PROVIDER_DEFAULTS["openai"]["model"] == "gpt-4.1-nano"
        assert PROVIDER_DEFAULTS["openai"]["base_url"] is None

    def test_anthropic_defaults(self):
        assert "anthropic" in PROVIDER_DEFAULTS
        assert PROVIDER_DEFAULTS["anthropic"]["model"] == "claude-haiku-4-5-20251001"

    def test_gemini_defaults(self):
        assert "gemini" in PROVIDER_DEFAULTS
        base_url = PROVIDER_DEFAULTS["gemini"]["base_url"]
        assert base_url is not None
        assert "generativelanguage" in base_url

    def test_mistral_defaults(self):
        assert "mistral" in PROVIDER_DEFAULTS
        assert PROVIDER_DEFAULTS["mistral"]["model"] == "mistral-small-latest"

    def test_all_providers_have_model(self):
        for provider, defaults in PROVIDER_DEFAULTS.items():
            assert "model" in defaults, f"{provider} missing 'model' default"


class TestLoadLLMConfig:
    """Test environment-based config loading and auto-detection."""

    def test_returns_none_when_no_api_key(self):
        """With no API keys set, should return None."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_llm_config()
            assert config is None

    def test_explicit_provider_with_generic_key(self):
        """WOOGRAPH_LLM_PROVIDER + WOOGRAPH_API_KEY should work."""
        env = {
            "WOOGRAPH_LLM_PROVIDER": "deepseek",
            "WOOGRAPH_API_KEY": "sk-generic-test",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "deepseek"
            assert config.api_key == "sk-generic-test"
            assert config.model == "deepseek-chat"

    def test_auto_detect_deepseek(self):
        """DEEPSEEK_API_KEY should auto-detect deepseek provider."""
        env = {"DEEPSEEK_API_KEY": "sk-deepseek-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "deepseek"
            assert config.api_key == "sk-deepseek-test"

    def test_auto_detect_openai(self):
        env = {"OPENAI_API_KEY": "sk-openai-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "openai"

    def test_auto_detect_anthropic(self):
        env = {"ANTHROPIC_API_KEY": "sk-ant-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "anthropic"

    def test_auto_detect_gemini(self):
        env = {"GEMINI_API_KEY": "gemini-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "gemini"

    def test_auto_detect_google_api_key(self):
        env = {"GOOGLE_API_KEY": "google-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "gemini"

    def test_auto_detect_mistral(self):
        env = {"MISTRAL_API_KEY": "mistral-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "mistral"

    def test_deepseek_preferred_over_openai(self):
        """When multiple keys present, deepseek should win."""
        env = {
            "DEEPSEEK_API_KEY": "sk-deepseek",
            "OPENAI_API_KEY": "sk-openai",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "deepseek"

    def test_explicit_provider_overrides_auto_detect(self):
        """Explicit WOOGRAPH_LLM_PROVIDER should override auto-detection."""
        env = {
            "WOOGRAPH_LLM_PROVIDER": "openai",
            "DEEPSEEK_API_KEY": "sk-deepseek",
            "OPENAI_API_KEY": "sk-openai",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.provider == "openai"
            assert config.api_key == "sk-openai"

    def test_custom_model_override(self):
        env = {
            "DEEPSEEK_API_KEY": "sk-test",
            "WOOGRAPH_LLM_MODEL": "deepseek-reasoner",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.model == "deepseek-reasoner"

    def test_custom_temperature(self):
        env = {
            "DEEPSEEK_API_KEY": "sk-test",
            "WOOGRAPH_LLM_TEMPERATURE": "0.5",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.temperature == 0.5

    def test_generic_key_overrides_provider_specific(self):
        """WOOGRAPH_API_KEY should override provider-specific key."""
        env = {
            "DEEPSEEK_API_KEY": "sk-provider-specific",
            "WOOGRAPH_API_KEY": "sk-generic-override",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.api_key == "sk-generic-override"

    def test_base_url_set_for_deepseek(self):
        env = {"DEEPSEEK_API_KEY": "sk-test"}
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            assert config is not None
            assert config.base_url == "https://api.deepseek.com"

    def test_explicit_provider_with_no_matching_key_falls_back(self):
        """If explicit provider set but no matching key, try other keys."""
        env = {
            "WOOGRAPH_LLM_PROVIDER": "deepseek",
            "OPENAI_API_KEY": "sk-openai-fallback",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_llm_config()
            # Should use openai key as fallback
            assert config is not None
            assert config.provider == "deepseek"
            assert config.api_key == "sk-openai-fallback"


class TestCreateCompletion:
    """Test the create_completion function with mocked SDK clients."""

    def test_openai_compatible_provider(self):
        """Non-anthropic providers should use the OpenAI SDK."""
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="test response"))]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("woograph.llm.client.OpenAI", return_value=mock_client):
            result = create_completion(config, "test prompt")
            assert result == "test response"
            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "deepseek-chat"
            assert call_kwargs["temperature"] == 0.0

    def test_anthropic_provider(self):
        """Anthropic should use the Anthropic SDK."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            api_key="sk-ant-test",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="anthropic response")]
        mock_client.messages.create.return_value = mock_response

        with patch("woograph.llm.client.Anthropic", return_value=mock_client):
            result = create_completion(config, "test prompt")
            assert result == "anthropic response"
            mock_client.messages.create.assert_called_once()

    def test_returns_none_on_failure(self):
        """Should return None after retries exhausted."""
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")

        with patch("woograph.llm.client.OpenAI", return_value=mock_client):
            result = create_completion(config, "test prompt")
            assert result is None
            # Should have retried once (2 total calls)
            assert mock_client.chat.completions.create.call_count == 2

    def test_anthropic_returns_none_on_failure(self):
        config = LLMConfig(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            api_key="sk-ant-test",
        )
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")

        with patch("woograph.llm.client.Anthropic", return_value=mock_client):
            result = create_completion(config, "test prompt")
            assert result is None
            assert mock_client.messages.create.call_count == 2

    def test_max_tokens_passed(self):
        config = LLMConfig(
            provider="openai",
            model="gpt-4.1-nano",
            api_key="sk-test",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("woograph.llm.client.OpenAI", return_value=mock_client):
            create_completion(config, "test", max_tokens=2048)
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["max_tokens"] == 2048

    def test_json_response_format_when_json_mode(self):
        """OpenAI-compatible providers set response_format when json_mode=True."""
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="{}"))]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("woograph.llm.client.OpenAI", return_value=mock_client):
            create_completion(config, "return JSON", json_mode=True)
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_no_json_format_by_default(self):
        """OpenAI-compatible providers omit response_format by default."""
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Yes"))]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("woograph.llm.client.OpenAI", return_value=mock_client):
            create_completion(config, "test")
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert "response_format" not in call_kwargs

    def test_temperature_passed(self):
        config = LLMConfig(
            provider="openai",
            model="gpt-4.1-nano",
            api_key="sk-test",
            temperature=0.3,
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("woograph.llm.client.OpenAI", return_value=mock_client):
            create_completion(config, "test")
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["temperature"] == 0.3
