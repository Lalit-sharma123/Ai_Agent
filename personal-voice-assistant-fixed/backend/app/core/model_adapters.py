from typing import Any
from urllib.parse import urlparse
import httpx
from ..config import Settings


class ModelError(RuntimeError):
    """Raised when a model endpoint is missing or returns an unusable response."""


class ModelAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def profile(self, provider: str | None = None) -> tuple[str, str, str]:
        name = (provider or self.settings.default_model_provider).lower()
        if name == "qwen":
            url = self.settings.qwen_model_url or self.settings.qwen_base_url
            model = self.settings.qwen_model_name or self.settings.qwen_model
            return name, url.rstrip("/"), model
        if name in {"gpt-oss", "gpt_oss", "gptoss", "ollama"}:
            url = self.settings.ollama_url or self.settings.gpt_oss_base_url
            model = self.settings.ollama_model or self.settings.gpt_oss_model
            return "gpt-oss", url.rstrip("/"), model
        raise ModelError(f"Unknown model provider '{name}'. Configure qwen or gpt-oss.")

    def _format(self, provider: str) -> str:
        """Resolve the API format, recognizing OpenAI-compatible /v1 base URLs.

        A URL such as http://host:8100/v1 normally exposes /chat/completions,
        not Ollama's /api/chat. Explicit API-format settings remain useful for
        nonstandard servers; /v1 is treated as a strong OpenAI-compatible signal.
        """
        configured = (
            self.settings.qwen_api_format if provider == "qwen"
            else self.settings.gpt_oss_api_format
        ).lower().strip()
        _, base_url, _ = self.profile(provider)
        path = urlparse(base_url).path.rstrip("/")
        if configured == "auto":
            return "openai" if (path.endswith("/v1") or path.endswith("/chat/completions")) else "ollama"
        if (path.endswith("/v1") or path.endswith("/chat/completions")) and configured == "ollama":
            return "openai"
        return configured

    @staticmethod
    def _chat_endpoint(url: str, api_format: str) -> str:
        url = url.rstrip("/")
        if api_format == "openai":
            if url.endswith("/chat/completions"):
                return url
            if url.endswith("/v1"):
                return f"{url}/chat/completions"
            return f"{url}/v1/chat/completions"
        if url.endswith("/api/chat"):
            return url
        return f"{url}/api/chat"

    @staticmethod
    def _health_endpoint(url: str, api_format: str) -> str:
        url = url.rstrip("/")
        if api_format == "ollama":
            return url if url.endswith("/api/tags") else f"{url}/api/tags"
        if url.endswith("/chat/completions"):
            url = url[:-len("/chat/completions")]
        if url.endswith("/v1"):
            return f"{url}/models"
        return f"{url}/v1/models"

    async def health(self, provider: str | None = None) -> dict[str, Any]:
        name, base_url, model = self.profile(provider)
        if not base_url or not model:
            return {
                "provider": name,
                "configured": False,
                "reachable": False,
                "error": f"Configure the {name} base URL and model name in .env.",
            }
        api_format = self._format(name)
        if api_format not in {"ollama", "openai"}:
            return {
                "provider": name, "configured": True, "reachable": False,
                "error": f"Unsupported API format '{api_format}'; use 'ollama', 'openai', or 'auto'.",
            }
        try:
            async with httpx.AsyncClient(timeout=min(self.settings.model_request_timeout, 8.0)) as client:
                endpoint = self._health_endpoint(base_url, api_format)
                response = await client.get(endpoint)
                response.raise_for_status()
            return {"provider": name, "configured": True, "reachable": True, "api_format": api_format}
        except Exception as exc:
            return {
                "provider": name, "configured": True, "reachable": False,
                "api_format": api_format, "error": str(exc),
            }

    async def chat(self, messages: list[dict[str, str]], provider: str | None = None) -> dict[str, Any]:
        name, base_url, model = self.profile(provider)
        if not base_url or not model:
            raise ModelError(f"Model '{name}' is not configured. Set its BASE_URL and MODEL in backend/.env.")
        api_format = self._format(name)
        if api_format not in {"ollama", "openai"}:
            raise ModelError(
                f"Unsupported API format '{api_format}' for {name}; use 'ollama', 'openai', or 'auto'."
            )
        payload = {"model": model, "messages": messages, "stream": False}
        endpoint = self._chat_endpoint(base_url, api_format)
        headers = {"Content-Type": "application/json"}
        last_error: Exception | None = None
        for attempt in range(self.settings.model_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.model_request_timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                if api_format == "ollama":
                    content = data.get("message", {}).get("content")
                else:
                    choices = data.get("choices") or []
                    content = choices[0].get("message", {}).get("content") if choices else None
                if not isinstance(content, str) or not content.strip():
                    raise ModelError("Model endpoint returned no assistant message.")
                return {"content": content.strip(), "provider": name, "model": model}
            except ModelError:
                raise
            except Exception as exc:
                last_error = exc
        raise ModelError(f"Could not call {name} model at {base_url}: {last_error}") from last_error
