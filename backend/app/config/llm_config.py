"""
LLM configuration — Ollama settings (env-driven).
All model-dependent values come from environment variables with safe local
defaults, so deployments (Docker, mobile-backend) can override without code edits.
"""
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def parse_billing_profile_aliases(raw: str) -> tuple:
    """'a=b,c=d' -> (('a','b'),('c','d')). Any malformed or repeated entry
    voids the whole setting (fail closed: no alias, cloud denied) — logged."""
    pairs = []
    for entry in (raw or "").split(","):
        if not entry.strip():
            continue
        parts = entry.split("=")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            pairs = None
            break
        pairs.append((parts[0].strip(), parts[1].strip()))
    if pairs is None or len({name for name, _ in pairs}) != len(pairs):
        logger.warning("DEEPSEEK_BILLING_PROFILE_ALIASES=%r is malformed — ignored entirely; "
                       "capped calls on unprofiled models are denied", raw)
        return ()
    return tuple(pairs)


_ENFORCE_ON = ("1", "true", "yes", "on")
_ENFORCE_OFF = ("", "0", "false", "no", "off")


def parse_cloud_budget_enforce(raw: str | None) -> bool:
    """CLOUD_BUDGET_ENFORCE. An unrecognised value is never silently off: it
    is read as ON (the safe side for spend — cloud fails closed and the local
    chain answers until a bootstrap) and logged."""
    value = (raw or "").strip().lower()
    if value in _ENFORCE_ON:
        return True
    if value in _ENFORCE_OFF:
        return False
    logger.warning("CLOUD_BUDGET_ENFORCE=%r is not one of %s / %s — treated as ON "
                   "(fail closed); set it explicitly", raw, "|".join(_ENFORCE_ON),
                   "|".join(v for v in _ENFORCE_OFF if v))
    return True


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
    # DeepSeek's docs (2026-10) list deepseek-chat as a legacy name due to be
    # discontinued; the documented model is deepseek-flash (thinking off via
    # the request's "thinking" field). When the configured model is refused
    # as unknown or retired, the gateway switches to this one for the process.
    deepseek_model_fallback: str = os.environ.get("DEEPSEEK_MODEL_FALLBACK", "deepseek-flash")
    # Model names the monthly cap may bill under a documented profile, as
    # "name=documented-name[,…]" (e.g. "deepseek-chat=deepseek-flash"). An
    # operator attestation, not a fact the code can verify: deepseek-chat is
    # no longer in DeepSeek's docs (see backend/docs/cloud-budget-reservations.md).
    # Empty (the default) or malformed = no alias: a capped call on an
    # unprofiled name is denied and the local chain answers.
    deepseek_billing_profile_aliases: tuple = field(
        default_factory=lambda: parse_billing_profile_aliases(
            os.environ.get("DEEPSEEK_BILLING_PROFILE_ALIASES", "")))
    # Monthly spend ceiling for the PRIMARY path. The app is free forever (no
    # ads, no subscriptions), so every primary token is paid out of the owner's
    # own pocket — without a ceiling the bill is unbounded. Unlike the
    # safety-valve cap, exhaustion or unknown billing profiles make the gateway
    # fall through to the local Ollama chain, exactly as if the provider had
    # failed, so the app keeps answering. 0 disables the ceiling.
    deepseek_primary_monthly_token_cap: int = int(
        os.environ.get("DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP", "100000000")
    )
    # The hard monthly cap's activation switch. Off (default): the behaviour
    # before the reservation ledger — no wire reservation or denial, the soft
    # ceiling above over llm_calls (failing OPEN on unreadable telemetry),
    # batch tools unreserved; telemetry is recorded either way. On: every paid
    # wire attempt is reserved in the ledger and fails CLOSED until an explicit
    # bootstrap (backend/docs/cloud-budget-reservations.md, runbook).
    # 1/true/yes/on = on; unset/empty/0/false/no/off = off; anything else is
    # logged and read as ON (never silently off).
    cloud_budget_enforce: bool = field(default_factory=lambda: parse_cloud_budget_enforce(
        os.environ.get("CLOUD_BUDGET_ENFORCE")))

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
