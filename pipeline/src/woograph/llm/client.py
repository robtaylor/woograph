"""Unified LLM client supporting multiple providers.

Supports OpenAI-compatible APIs (DeepSeek, OpenAI, Gemini, Mistral) via the
OpenAI SDK, and Anthropic via its native SDK. Provider is configurable via
environment variables with auto-detection from API keys.
"""

import base64
import logging
import os
from dataclasses import dataclass

from anthropic import Anthropic
from openai import OpenAI

logger = logging.getLogger(__name__)

PROVIDER_DEFAULTS: dict[str, dict[str, str | None]] = {
    "deepseek": {"model": "deepseek-chat", "base_url": "https://api.deepseek.com"},
    "openai": {"model": "gpt-4.1-nano", "base_url": None},
    "anthropic": {"model": "claude-haiku-4-5-20251001", "base_url": None},
    "gemini": {
        "model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "mistral": {"model": "mistral-small-latest", "base_url": "https://api.mistral.ai/v1"},
}

# Auto-detection order: check these env vars to determine provider
_AUTO_DETECT_ORDER: list[tuple[str, list[str]]] = [
    ("deepseek", ["DEEPSEEK_API_KEY"]),
    ("openai", ["OPENAI_API_KEY"]),
    ("anthropic", ["ANTHROPIC_API_KEY"]),
    ("gemini", ["GOOGLE_API_KEY", "GEMINI_API_KEY"]),
    ("mistral", ["MISTRAL_API_KEY"]),
]

# Flat list for finding any available key
_ALL_KEY_VARS: list[tuple[str, str]] = [
    ("deepseek", "DEEPSEEK_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("gemini", "GOOGLE_API_KEY"),
    ("gemini", "GEMINI_API_KEY"),
    ("mistral", "MISTRAL_API_KEY"),
]


@dataclass
class LLMConfig:
    """LLM provider configuration, loaded from environment."""

    provider: str  # "deepseek", "openai", "anthropic", "gemini", "mistral"
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.0  # Default 0 for extraction (reduces hallucination)


def _get_api_key_for_provider(provider: str) -> str | None:
    """Get the API key for a specific provider from environment."""
    for prov, key_vars in _AUTO_DETECT_ORDER:
        if prov == provider:
            for var in key_vars:
                val = os.environ.get(var)
                if val:
                    return val
    return None


def _find_any_api_key() -> str | None:
    """Find any available API key from environment."""
    for _provider, var in _ALL_KEY_VARS:
        val = os.environ.get(var)
        if val:
            return val
    return None


def load_llm_config() -> LLMConfig | None:
    """Load LLM config from environment variables.

    Env vars:
        WOOGRAPH_LLM_PROVIDER: Provider name (default: auto-detect)
        WOOGRAPH_LLM_MODEL: Model name (default depends on provider)
        WOOGRAPH_LLM_TEMPERATURE: Temperature (default: 0.0)
        WOOGRAPH_API_KEY: Generic API key (overrides provider-specific)

        Provider-specific API keys (checked in order for auto-detection):
        - DEEPSEEK_API_KEY
        - OPENAI_API_KEY
        - ANTHROPIC_API_KEY
        - GOOGLE_API_KEY / GEMINI_API_KEY
        - MISTRAL_API_KEY

    Returns None if no API key found for any provider.
    """
    generic_key = os.environ.get("WOOGRAPH_API_KEY")
    explicit_provider = os.environ.get("WOOGRAPH_LLM_PROVIDER")

    if explicit_provider:
        provider = explicit_provider.lower()
        # Try provider-specific key, then generic, then any available key
        api_key = generic_key or _get_api_key_for_provider(provider) or _find_any_api_key()
    else:
        # Auto-detect provider from available API keys
        if generic_key:
            # Generic key set but no provider - default to deepseek
            provider = "deepseek"
            api_key = generic_key
        else:
            # Check each provider's key vars in priority order
            provider = None
            api_key = None
            for prov, key_vars in _AUTO_DETECT_ORDER:
                for var in key_vars:
                    val = os.environ.get(var)
                    if val:
                        provider = prov
                        api_key = val
                        break
                if provider:
                    break

    if not api_key or not provider:
        return None

    # Override api_key with generic if set
    if generic_key:
        api_key = generic_key

    defaults = PROVIDER_DEFAULTS.get(provider, {})
    model = os.environ.get("WOOGRAPH_LLM_MODEL") or str(defaults.get("model", provider))
    base_url = defaults.get("base_url")

    temperature_str = os.environ.get("WOOGRAPH_LLM_TEMPERATURE")
    temperature = float(temperature_str) if temperature_str else 0.0

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=str(base_url) if base_url else None,
        temperature=temperature,
    )


def create_completion(
    config: LLMConfig, prompt: str, max_tokens: int = 1024, json_mode: bool = False
) -> str | None:
    """Send a prompt and get text response. Returns None on failure.

    For Anthropic: uses the anthropic SDK.
    For all others: uses the openai SDK with appropriate base_url.

    Args:
        config: LLM provider configuration.
        prompt: The prompt text.
        max_tokens: Maximum tokens in the response.
        json_mode: If True, request JSON response format (prompt must mention "json").

    Retries once on failure.
    """
    if config.provider == "anthropic":
        return _create_anthropic_completion(config, prompt, max_tokens)
    return _create_openai_completion(config, prompt, max_tokens, json_mode=json_mode)


def _create_openai_completion(
    config: LLMConfig, prompt: str, max_tokens: int, *, json_mode: bool = False
) -> str | None:
    """Use OpenAI-compatible API (DeepSeek, OpenAI, Gemini, Mistral)."""
    client_kwargs: dict[str, str] = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url

    client = OpenAI(**client_kwargs)  # type: ignore[arg-type]

    for attempt in range(2):
        try:
            create_kwargs: dict = {
                "model": config.model,
                "max_tokens": max_tokens,
                "temperature": config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if json_mode:
                create_kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**create_kwargs)
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            return None
        except Exception as exc:
            if attempt == 0:
                logger.warning("API call failed (%s), retrying once...", exc)
            else:
                logger.warning("API call failed on retry (%s)", exc)
    return None


def _create_anthropic_completion(
    config: LLMConfig, prompt: str, max_tokens: int
) -> str | None:
    """Use the Anthropic SDK."""
    client = Anthropic(api_key=config.api_key)

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [b for b in response.content if hasattr(b, "text")]
            if text_blocks:
                return text_blocks[0].text  # type: ignore[union-attr]
            return None
        except Exception as exc:
            if attempt == 0:
                logger.warning("API call failed (%s), retrying once...", exc)
            else:
                logger.warning("API call failed on retry (%s)", exc)
    return None


# ── Vision (multimodal) completions ──────────────────────────────────────


def create_vision_completion(
    config: LLMConfig,
    prompt: str,
    images: list[bytes],
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str | None:
    """Send a prompt with images and get text response. Returns None on failure.

    Args:
        config: LLM provider configuration.
        prompt: The text prompt.
        images: List of JPEG-encoded image bytes.
        max_tokens: Maximum tokens in the response.
        json_mode: If True, request JSON response format.

    Retries once on failure.
    """
    if config.provider == "anthropic":
        return _create_anthropic_vision_completion(
            config, prompt, images, max_tokens,
        )
    return _create_openai_vision_completion(
        config, prompt, images, max_tokens, json_mode=json_mode,
    )


def _create_openai_vision_completion(
    config: LLMConfig,
    prompt: str,
    images: list[bytes],
    max_tokens: int,
    *,
    json_mode: bool = False,
) -> str | None:
    """Use OpenAI-compatible API with vision (OpenAI, Gemini)."""
    client_kwargs: dict[str, str] = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url

    client = OpenAI(**client_kwargs)  # type: ignore[arg-type]

    # Build content parts: images first, then text prompt
    content: list[dict] = []
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    for attempt in range(2):
        try:
            create_kwargs: dict = {
                "model": config.model,
                "max_tokens": max_tokens,
                "temperature": config.temperature,
                "messages": [{"role": "user", "content": content}],
            }
            if json_mode:
                create_kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**create_kwargs)
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            return None
        except Exception as exc:
            if attempt == 0:
                logger.warning("Vision API call failed (%s), retrying once...", exc)
            else:
                logger.warning("Vision API call failed on retry (%s)", exc)
    return None


def _create_anthropic_vision_completion(
    config: LLMConfig,
    prompt: str,
    images: list[bytes],
    max_tokens: int,
) -> str | None:
    """Use the Anthropic SDK with vision."""
    client = Anthropic(api_key=config.api_key)

    # Build content parts: images first, then text prompt
    content: list = []
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("ascii")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            },
        })
    content.append({"type": "text", "text": prompt})

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],  # type: ignore[arg-type]
            )
            text_blocks = [b for b in response.content if hasattr(b, "text")]
            if text_blocks:
                return text_blocks[0].text  # type: ignore[union-attr]
            return None
        except Exception as exc:
            if attempt == 0:
                logger.warning("Vision API call failed (%s), retrying once...", exc)
            else:
                logger.warning("Vision API call failed on retry (%s)", exc)
    return None
