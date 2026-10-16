from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "Personal Voice Assistant"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    secret_key: str = "change-me-in-local-env"
    database_url: str = "sqlite:///./data/assistant.db"
    default_model_provider: str = "qwen"
    # Accept the exact OpenAI-compatible /v1/chat/completions URLs supplied by the user.
    qwen_model_url: str = ""
    qwen_model_name: str = ""
    qwen_base_url: str = ""
    qwen_model: str = ""
    qwen_api_format: str = "openai"
    ollama_url: str = ""
    ollama_model: str = ""
    gpt_oss_base_url: str = ""
    gpt_oss_model: str = "gpt-oss:120b"
    gpt_oss_api_format: str = "openai"
    agent_model_routing_enabled: bool = True
    model_request_timeout: float = 120.0
    model_max_retries: int = 2
    ava_api_base_url: str = "http://127.0.0.1:8000"
    stt_model_size: str = "base"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    pyannote_auth_token: str = ""
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    tts_engine: str = "browser"
    tts_voice: str = ""
    wake_word_enabled: bool = False
    wake_word_model: str = ""
    audio_sample_rate: int = 16000
    searxng_base_url: str = ""
    default_web_search_provider: str = "duckduckgo"
    browser_headless: bool = True
    playwright_enabled: bool = True
    browser_allowed_domains: str = ""
    web_request_timeout: float = 20.0
    workspace_roots: str = "../workspace"
    allowed_commands: str = "git,pytest,ruff,python"
    allowed_desktop_apps: str = "firefox,chromium,code,xdg-open,gnome-calculator,kcalc,galculator,xcalc"
    email_provider: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from_address: str = ""
    email_oauth_client_id: str = ""
    email_oauth_client_secret: str = ""
    email_oauth_redirect_uri: str = ""
    meeting_recording_enabled: bool = False
    meeting_audio_source: str = "microphone"
    meeting_retention_days: int = 30
    data_dir: str = "./data"
    recordings_dir: str = "./data/recordings"
    documents_dir: str = "./data/documents"
    generated_files_dir: str = "./data/generated"
    require_email_approval: bool = True
    require_file_delete_approval: bool = True
    require_command_approval: bool = True
    allow_external_uploads: bool = False
    audit_log_enabled: bool = True

    @property
    def sqlite_path(self) -> str | None:
        return self.database_url.removeprefix("sqlite:///") if self.database_url.startswith("sqlite:///") else None

@lru_cache
def get_settings() -> Settings:
    return Settings()
