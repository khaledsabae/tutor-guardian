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

    base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")  # qwen2.5:7b, mistral:7b...
    request_timeout: int = int(os.environ.get("OLLAMA_TIMEOUT", "120"))  # seconds
    max_retries: int = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
    temperature: float = float(os.environ.get("OLLAMA_TEMPERATURE", "0.3"))  # low = stick to facts

    # Prompt template — ensures the model only uses retrieved knowledge
    system_prompt: str = (
        "أنت مساعد تربوي. استخدم فقط النصوص المقدمة لك في [CONTEXT].\n"
        "لا تضف أي معلومة من خارج هذا السياق.\n"
        "في نهاية كل رد اكتب: 📚 المصدر: [اسم المرجع من reference_info]\n"
        "إذا لم يكن السياق كافياً قل: لا تتوفر لديّ معلومات موثقة — يُنصح بمراجعة متخصص"
    )


# Singleton — import this everywhere
LLM = LLMConfig()
