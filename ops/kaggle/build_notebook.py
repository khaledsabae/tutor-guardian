#!/usr/bin/env python3
"""Assemble the command-r Kaggle notebook (finetune_tg_kaggle.ipynb).

Authoritative source for the 4 cells. Incorporates the fixes proven on Kaggle:
  - TRL SFTConfig + processing_class (new TRL API)
  - bfloat16 -> float32 sweep (T4 fp16/GradScaler conflict)
  - device_map={"":0}, MAX_SEQ=512, EPOCHS=1, 10k subset (fit Kaggle time)
  - uninstall torchao 0.10 (peft merge raises on the stale version)
  - MERGE ON GPU (P100/T4 16GB) not CPU — CPU merge OOM'd & killed the kernel
  - GGUF export + cleanup so committed output stays < Kaggle 20GB cap
Run mode MUST be 'Save & Run All' (commit) so /kaggle/working persists.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "finetune_tg_kaggle.ipynb"

PIP = '''# المربّي — fine-tune command-r7b-arabic (QLoRA). Accelerator = GPU T4 x2.
# RUN AS: Save Version -> Save & Run All (commit) so output persists.
!pip install -q -U transformers trl peft bitsandbytes accelerate datasets huggingface_hub
!pip uninstall -y torchao
'''

TRAIN = '''import os
from pathlib import Path
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

BASE_MODEL = "CohereLabs/c4ai-command-r7b-arabic-02-2025"
DATA_DIR   = Path(os.environ.get("DATA_DIR", "/kaggle/input/tg-qa-dataset"))
OUT_DIR    = Path("/kaggle/working/tg-tutor-commandr-lora")
MERGED_DIR = Path("/kaggle/working/tg-tutor-commandr-merged")
MAX_SEQ    = 512
EPOCHS     = 1

HF_TOKEN = None
try:
    from kaggle_secrets import UserSecretsClient
    HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    HF_TOKEN = os.environ.get("HF_TOKEN")
assert HF_TOKEN, "HF_TOKEN missing — add a Kaggle Secret named HF_TOKEN (Add-ons -> Secrets)."
os.environ["HF_TOKEN"] = HF_TOKEN
from huggingface_hub import login
login(token=HF_TOKEN)

tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=HF_TOKEN)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.model_max_length = MAX_SEQ

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, quantization_config=bnb,
                                             device_map={"": 0}, token=HF_TOKEN,
                                             torch_dtype=torch.float16, trust_remote_code=True)
model.config.use_cache = False
model.config.torch_dtype = torch.float32

def fmt(ex):
    return {"text": tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)}

ds_train = load_dataset("json", data_files=str(DATA_DIR / "tg_train_commandr.jsonl"), split="train").map(fmt, remove_columns=["messages"])
ds_val   = load_dataset("json", data_files=str(DATA_DIR / "tg_val_commandr.jsonl"),   split="train").map(fmt, remove_columns=["messages"])
ds_train = ds_train.select(range(10000))

peft_cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])

args = SFTConfig(output_dir=str(OUT_DIR), num_train_epochs=EPOCHS, per_device_train_batch_size=2,
                 gradient_accumulation_steps=8, learning_rate=2e-4, lr_scheduler_type="cosine",
                 warmup_ratio=0.03, logging_steps=20, eval_strategy="steps", eval_steps=200,
                 save_strategy="steps", save_steps=400, save_total_limit=2, fp16=True,
                 optim="paged_adamw_8bit", gradient_checkpointing=True, report_to="none",
                 dataset_text_field="text", packing=False)

trainer = SFTTrainer(model=model, args=args, train_dataset=ds_train, eval_dataset=ds_val,
                     peft_config=peft_cfg, processing_class=tok)

for _n, _p in trainer.model.named_parameters():
    if _p.dtype == torch.bfloat16:
        _p.data = _p.data.to(torch.float32)

trainer.train()
trainer.save_model(str(OUT_DIR))
print("TRAIN DONE -> adapter saved at", OUT_DIR)
'''

MERGE = '''# Merge LoRA on the GPU (CPU merge OOMs Kaggle RAM and kills the kernel).
import gc, torch
try:
    del trainer, model
except Exception:
    pass
gc.collect(); torch.cuda.empty_cache()

from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

m = AutoPeftModelForCausalLM.from_pretrained(str(OUT_DIR), torch_dtype=torch.float16,
                                             device_map={"": 0}, token=HF_TOKEN,
                                             trust_remote_code=True, low_cpu_mem_usage=True)
m = m.merge_and_unload()
m.save_pretrained(str(MERGED_DIR), safe_serialization=True, max_shard_size="2GB")
AutoTokenizer.from_pretrained(str(OUT_DIR), token=HF_TOKEN).save_pretrained(str(MERGED_DIR))
del m; gc.collect(); torch.cuda.empty_cache()
print("MERGED OK ->", MERGED_DIR)
'''

GGUF = '''# GGUF Q4_K_M for Ollama. Cleanup keeps committed output < Kaggle 20GB cap.
!git clone --depth 1 https://github.com/ggerganov/llama.cpp /kaggle/working/llama.cpp
!pip install -q -r /kaggle/working/llama.cpp/requirements.txt
!python /kaggle/working/llama.cpp/convert_hf_to_gguf.py /kaggle/working/tg-tutor-commandr-merged --outfile /kaggle/working/tg-tutor-v4-f16.gguf --outtype f16
!cmake -S /kaggle/working/llama.cpp -B /kaggle/working/llama.cpp/build -DGGML_CUDA=OFF
!cmake --build /kaggle/working/llama.cpp/build --target llama-quantize -j4
!/kaggle/working/llama.cpp/build/bin/llama-quantize /kaggle/working/tg-tutor-v4-f16.gguf /kaggle/working/tg-tutor-v4-Q4_K_M.gguf Q4_K_M
!rm -rf /kaggle/working/tg-tutor-commandr-merged /kaggle/working/tg-tutor-v4-f16.gguf /kaggle/working/llama.cpp
!ls -lh /kaggle/working
print("DONE -> download tg-tutor-v4-Q4_K_M.gguf from the Output tab")
'''


def cc(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": src.splitlines(keepends=True)}

def mc(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}

nb = {
    "cells": [
        mc("# Tutor Guardian — command-r7b-arabic fine-tune\n"
           "Accelerator = **GPU T4 x2** · Run as **Save & Run All** (commit).\n"
           "Cells: pip → train → merge(GPU) → GGUF."),
        cc(PIP), cc(TRAIN), cc(MERGE), cc(GGUF),
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
