"""
LLM configuration — Ollama settings (env-driven).
All model-dependent values come from environment variables with safe local
defaults, so deployments (Docker, mobile-backend) can override without code edits.
"""
import os
from dataclasses import dataclass

# The home server, reached over Tailscale. Five modules read this address from
# the environment, each carrying its own copy of the literal as the fallback,
# so moving the machine meant finding all five. One copy now — the per-module
# OLLAMA_* variables still override it.
DEFAULT_HOME_OLLAMA_URL = os.environ.get(
    "OLLAMA_HOME_SERVER_URL", "http://100.109.163.64:11434"
)


@dataclass(frozen=True)
class LLMConfig:
    """Immutable LLM configuration loaded from env or local defaults."""

    # Primary (cloud) configuration
    base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    primary_model: str = os.environ.get("OLLAMA_PRIMARY_MODEL", "qwen2.5:3b")
    fallback_model: str = os.environ.get("OLLAMA_FALLBACK_MODEL", "gemma4:e4b")

    # Local LLM server (Home Server via Tailscale) configuration
    local_base_url: str = os.environ.get("OLLAMA_LOCAL_BASE_URL", DEFAULT_HOME_OLLAMA_URL)
    local_fallback_model: str = os.environ.get("OLLAMA_LOCAL_FALLBACK_MODEL", "gemma4:e4b")
    local_fast_model: str = os.environ.get("OLLAMA_LOCAL_FAST_MODEL", "qwen2.5:3b")

    request_timeout: int = int(os.environ.get("OLLAMA_TIMEOUT", "120"))  # seconds
    max_retries: int = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
    temperature: float = float(os.environ.get("OLLAMA_TEMPERATURE", "0.3"))  # low = stick to facts

    # ── Cloud quality tier (Azure OpenAI-compatible, free deployment) ──────
    # Disabled by default: with the flag off, behavior is byte-identical to
    # the local-only gateway. AZURE_DEEPSEEK_* take precedence; the
    # AZURE_OPENAI_* names match the analytics-platform .env convention.
    cloud_tier_enabled: bool = os.environ.get("CLOUD_TIER_ENABLED", "false").lower() in ("1", "true", "yes")
    azure_endpoint: str = os.environ.get(
        "AZURE_DEEPSEEK_ENDPOINT", os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    )
    azure_api_key: str = os.environ.get(
        "AZURE_DEEPSEEK_API_KEY", os.environ.get("AZURE_OPENAI_API_KEY", "")
    )
    azure_api_version: str = os.environ.get(
        "AZURE_DEEPSEEK_API_VERSION",
        os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    )
    azure_model: str = os.environ.get(
        "AZURE_DEEPSEEK_MODEL", os.environ.get("AZURE_OPENAI_DEPLOYMENT", "DeepSeek-V4-Flash")
    )
    cloud_tier_timeout: int = int(os.environ.get("CLOUD_TIER_TIMEOUT", "60"))

    # ── Cloud safety-valve fallback (last resort, hard-capped) ─────────────
    # When the entire local Ollama chain is unreachable (home server down),
    # the gateway may fall back to DeepSeek — only if explicitly enabled, a
    # key exists, and the monthly token budget is not exhausted. The budget
    # check fails closed: if telemetry can't be read, the valve stays shut.
    deepseek_fallback_enabled: bool = os.environ.get(
        "DEEPSEEK_FALLBACK_ENABLED", "false"
    ).lower() in ("1", "true", "yes")
    deepseek_fallback_monthly_token_cap: int = int(
        os.environ.get("DEEPSEEK_FALLBACK_MONTHLY_TOKEN_CAP", "10000000")
    )

    # ── Primary provider override (DeepSeek / generic OpenAI-compatible) ────
    # When LLM_PRIMARY_PROVIDER=deepseek and a key is present, the gateway uses
    # DeepSeek as the PRIMARY model for every call (chat + ingestion), with the
    # local Ollama chain as automatic fallback. Native OpenAI-style endpoint
    # (NOT Azure) — works with api.deepseek.com, z.ai, openrouter, etc.
    primary_provider: str = os.environ.get("LLM_PRIMARY_PROVIDER", "ollama").lower()
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    # Monthly spend ceiling for the PRIMARY path. The app is free forever (no
    # ads, no subscriptions), so every primary token is paid out of the owner's
    # own pocket — without a ceiling the bill is unbounded. Unlike the
    # safety-valve cap this is a SOFT budget: once exhausted the gateway simply
    # falls through to the local Ollama chain, exactly as if the provider had
    # failed, so the app keeps answering. 0 disables the ceiling.
    deepseek_primary_monthly_token_cap: int = int(
        os.environ.get("DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP", "100000000")
    )

    # backward-compat shim: older code reads .model
    @property
    def model(self) -> str:
        return self.primary_model

    def fallback_chain(self) -> list[dict]:
        """Ordered fallback list used by generate() after primary fails."""
        return [
            {"name": "cloud_fallback", "url": self.base_url, "model": self.fallback_model, "timeout": self.request_timeout},
            {"name": "local_quality", "url": self.local_base_url, "model": self.local_fallback_model, "timeout": 180},
            {"name": "local_fast", "url": self.local_base_url, "model": self.local_fast_model, "timeout": 60},
        ]

    def stream_chain(self) -> list[dict]:
        """Ordered providers for stream() — starts with fast local for low latency."""
        return [
            {"name": "local_fast", "url": self.local_base_url, "model": self.local_fast_model, "timeout": 60},
            {"name": "local_quality", "url": self.local_base_url, "model": self.local_fallback_model, "timeout": 180},
            {"name": "cloud_fallback", "url": self.base_url, "model": self.fallback_model, "timeout": self.request_timeout},
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
