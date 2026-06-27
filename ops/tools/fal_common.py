"""
fal_common — الهوية البصرية الموحّدة + سجل موديلات fal.ai المشترك بين
gen_visuals.py وgen_launch.py.

كل موديل مسجّل بـ (endpoint, دالة تكلفة, دالة بناء الطلب, دالة استخراج رابط
الصورة) — إضافة موديل جديد = تسجيل واحد هنا، مش نسخ سكريبت كامل.
"""
from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from typing import Callable

import httpx

# الهوية البصرية الموحّدة — هلال بوجه هادئ + كتاب + نبتة + نجمة، أبيض على تركواز عميق.
STYLE = (
    "elegant minimal flat vector illustration, crisp clean white line-art and "
    "white silhouettes on a solid deep teal #01696F background, refined and "
    "calm and contemplative mood evoking inner peace and growth through "
    "knowledge, smooth balanced geometric composition; recurring motifs of a "
    "serene crescent moon doubling as a peaceful closed-eyes face, an open "
    "book, a small plant sprout growing upward from knowledge, and a bright "
    "guiding star; modest, spiritual, polished, premium, no detailed realistic "
    "faces, centered and well-spaced, cohesive single brand identity. "
    "ABSOLUTELY NO TEXT, no words, no letters, no captions, no wordmark"
)

# fal `image_size` enum (Recraft V3 + Flux 2 Pro both use this shape) →
# Nano Banana Pro's `aspect_ratio` enum.
_SIZE_TO_ASPECT_RATIO = {
    "square_hd": "1:1",
    "square": "1:1",
    "landscape_16_9": "16:9",
    "landscape_4_3": "4:3",
    "portrait_16_9": "9:16",
    "portrait_4_3": "3:4",
}


def get_fal_key() -> str:
    return os.environ.get("FAL_KEY", "").strip()


@dataclass(frozen=True)
class ModelSpec:
    key: str
    endpoint: str
    cost_fn: Callable[[str], float]
    build_request: Callable[[str, str], dict]
    parse_response: Callable[[dict], str]


def _recraft_request(prompt: str, size: str) -> dict:
    return {
        "prompt": f"{prompt}. {STYLE}",
        "style": "digital_illustration",
        "image_size": size,
    }


def _flux2_request(prompt: str, size: str) -> dict:
    return {
        "prompt": f"{prompt}. {STYLE}",
        "image_size": size,
        "output_format": "png",
    }


def _nano_banana_pro_request(prompt: str, size: str) -> dict:
    return {
        "prompt": f"{prompt}. {STYLE}",
        "aspect_ratio": _SIZE_TO_ASPECT_RATIO.get(size, "1:1"),
        "resolution": "1K",
        "output_format": "png",
    }


def _images_url(resp_json: dict) -> str:
    return resp_json["images"][0]["url"]


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "recraft_v3": ModelSpec(
        key="recraft_v3",
        endpoint="https://fal.run/fal-ai/recraft-v3",
        cost_fn=lambda _size: 0.04,
        build_request=_recraft_request,
        parse_response=_images_url,
    ),
    "flux2_pro": ModelSpec(
        key="flux2_pro",
        endpoint="https://fal.run/fal-ai/flux-2-pro",
        # $0.03 for the first megapixel; square_hd/landscape_16_9 etc. are all
        # ≤1 MP at the resolutions we use, so a flat per-image rate is accurate.
        cost_fn=lambda _size: 0.03,
        build_request=_flux2_request,
        parse_response=_images_url,
    ),
    "nano_banana_pro": ModelSpec(
        key="nano_banana_pro",
        endpoint="https://fal.run/fal-ai/nano-banana-pro",
        cost_fn=lambda _size: 0.15,  # 1K/2K rate; 4K would double this
        build_request=_nano_banana_pro_request,
        parse_response=_images_url,
    ),
}


def estimate_cost(spec: ModelSpec, size: str) -> float:
    return spec.cost_fn(size)


def generate(client: httpx.Client, key: str, spec: ModelSpec, prompt: str, size: str) -> bytes:
    resp = client.post(
        spec.endpoint,
        headers={"Authorization": f"Key {key}"},
        json=spec.build_request(prompt, size),
        timeout=180,
    )
    resp.raise_for_status()
    url = spec.parse_response(resp.json())
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310
        return r.read()
