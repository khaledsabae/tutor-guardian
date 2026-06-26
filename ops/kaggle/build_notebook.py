#!/usr/bin/env python3
"""Assemble the command-r Kaggle notebook from finetune_commandr_kaggle.py.

Produces finetune_tg_kaggle.ipynb (same kernel slug Khaled already has) with:
  cell 1: pip install (IPython magic, must be a real cell)
  cell 2: the training script body (docstring stripped)
  cell 3: GGUF export (llama.cpp convert + quantize)
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "finetune_commandr_kaggle.py"
OUT = HERE / "finetune_tg_kaggle.ipynb"

body = SRC.read_text(encoding="utf-8")
# strip the leading module docstring (everything up to the first import)
body = re.sub(r'\A.*?(?=\nimport os)', '', body, count=1, flags=re.DOTALL).lstrip("\n")
# the final triple-quoted print(...) block holds the GGUF instructions as text;
# we drop it from the training cell and re-author GGUF as a real executable cell.
body = re.split(r'\nprint\("""', body)[0].rstrip() + "\n"

def code_cell(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": src.splitlines(keepends=True)}

def md_cell(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}

pip = ("# المربّي — fine-tune command-r7b-arabic on the premium 31,645 corpus.\n"
       "# Accelerator = GPU T4 (UI). Internet = ON. HF_TOKEN as a Kaggle Secret.\n"
       "!pip install -q -U transformers trl peft bitsandbytes accelerate datasets\n")

gguf = (
    "# ── GGUF export (Q4_K_M) for Ollama on the home server ──────────────────\n"
    "!git clone --depth 1 https://github.com/ggerganov/llama.cpp /kaggle/working/llama.cpp\n"
    "!pip install -q -r /kaggle/working/llama.cpp/requirements.txt\n"
    "!python /kaggle/working/llama.cpp/convert_hf_to_gguf.py \\\n"
    "      /kaggle/working/tg-tutor-commandr-merged \\\n"
    "      --outfile /kaggle/working/tg-tutor-v4-f16.gguf --outtype f16\n"
    "!cmake -S /kaggle/working/llama.cpp -B /kaggle/working/llama.cpp/build -DGGML_CUDA=OFF >/dev/null 2>&1\n"
    "!cmake --build /kaggle/working/llama.cpp/build --target llama-quantize -j2 >/dev/null 2>&1\n"
    "!/kaggle/working/llama.cpp/build/bin/llama-quantize \\\n"
    "      /kaggle/working/tg-tutor-v4-f16.gguf \\\n"
    "      /kaggle/working/tg-tutor-v4-Q4_K_M.gguf Q4_K_M\n"
    "print('DONE → download /kaggle/working/tg-tutor-v4-Q4_K_M.gguf from the Output tab')\n"
)

nb = {
    "cells": [
        md_cell("# Tutor Guardian — Arabic Parenting LLM Fine-Tune\n"
                "Base: **CohereLabs/c4ai-command-r7b-arabic-02-2025** (QLoRA on T4).\n"
                "Won head-to-head vs qwen2.5:3b (3.75 vs 2.70). Press **Run All**."),
        code_cell(pip),
        code_cell(body),
        code_cell(gguf),
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "nbformat": 4, "nbformat_minor": 5,
}
OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}  ({len(nb['cells'])} cells)")
