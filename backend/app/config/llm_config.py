"""
LLM configuration — Ollama settings.
All model-dependent values are configurable here, not hardcoded in services.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Immutable LLM configuration loaded from env or defaults."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:3b"  # Alternatives: "qwen2.5:7b", "mistral:7b", "kimi-k2.6:cloud"
    request_timeout: int = 120  # seconds
    max_retries: int = 3
    temperature: float = 0.3   # Low temp = stick to retrieved facts

    # Prompt template — ensures the model only uses retrieved knowledge
    system_prompt: str = (
        "أنت مساعد تربوي. استخدم فقط النصوص المقدمة لك في [CONTEXT].\n"
        "لا تضف أي معلومة من خارج هذا السياق.\n"
        "في نهاية كل رد اكتب: 📚 المصدر: [اسم المرجع من reference_info]\n"
        "إذا لم يكن السياق كافياً قل: لا تتوفر لديّ معلومات موثقة — يُنصح بمراجعة متخصص"
    )


# Singleton — import this everywhere
LLM = LLMConfig()
