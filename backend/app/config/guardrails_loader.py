"""
Load guardrails policy YAML configuration.
"""
from pathlib import Path

import yaml


DEFAULT_POLICIES_PATH = (
    Path(__file__).resolve().parents[2] / "guardrails" / "policies.v1.yaml"
)


def load_guardrails_config(path: Path | None = None) -> dict:
    """Load and return the guardrails YAML configuration as a dict."""
    target = path or DEFAULT_POLICIES_PATH

    if not target.exists():
        raise FileNotFoundError(f"Guardrails policy file not found: {target}")

    try:
        with target.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"Guardrails config must be a mapping, got: {type(config)}")

        return config

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in guardrails config: {target}\n{e}") from e
