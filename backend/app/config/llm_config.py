"""
LLM configuration — Ollama settings (env-driven).
All model-dependent values come from environment variables with safe local
defaults, so deployments (Docker, mobile-backend) can override without code edits.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Immutable LLM configuration loaded from env or local defaults."""

    # Primary (cloud) configuration
    base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    primary_model: str = os.environ.get("OLLAMA_PRIMARY_MODEL", "kimi-k2.6:cloud")
    fallback_model: str = os.environ.get("OLLAMA_FALLBACK_MODEL", "gemma4:31b-cloud")

    # Local LLM server (Home Server via Tailscale) configuration
    local_base_url: str = os.environ.get("OLLAMA_LOCAL_BASE_URL", "http://100.109.163.64:11434")
    local_fallback_model: str = os.environ.get("OLLAMA_LOCAL_FALLBACK_MODEL", "gemma4:e4b")
    local_fast_model: str = os.environ.get("OLLAMA_LOCAL_FAST_MODEL", "qwen2.5:3b")

    request_timeout: int = int(os.environ.get("OLLAMA_TIMEOUT", "120"))  # seconds
    max_retries: int = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
    temperature: float = float(os.environ.get("OLLAMA_TEMPERATURE", "0.3"))  # low = stick to facts

    # backward-compat shim: older code reads .model
    @property
    def model(self) -> str:
        return self.primary_model

    # Fallback chain order
    def fallback_chain(self) -> list[dict]:
        """Returns ordered list of fallback configs to try after primary fails."""
        return [
            {"name": "cloud_fallback", "url": self.base_url, "model": self.fallback_model, "timeout": self.request_timeout},
            {"name": "local_quality", "url": self.local_base_url, "model": self.local_fallback_model, "timeout": 180},
            {"name": "local_fast", "url": self.local_base_url, "model": self.local_fast_model, "timeout": 60},
        ]

    # Prompt template — ensures the model only uses retrieved knowledge
    system_prompt: str = (
        "أنت مساعد تربوي. استخدم فقط النصوص المقدمة لك في [CONTEXT].\n"
        "لا تضف أي معلومة من خارج هذا السياق.\n"
        "في نهاية كل رد اكتب: 📚 المصدر: [اسم المرجع من reference_info]\n"
        "إذا لم يكن السياق كافياً قل: لا تتوفر لديّ معلومات موثقة — يُنصح بمراجعة متخصص"
    )


# Singleton — import this everywhere
LLM = LLMConfig()
