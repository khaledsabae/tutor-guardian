#!/usr/bin/env python3
"""
Kaggle T4 QLoRA fine-tune — المربّي / tg-tutor on command-r7b-arabic.

Base model decided 2026-06-26 by head-to-head eval (beat qwen2.5:3b 3.75 vs 2.70).
Uses standard TRL SFTTrainer + PEFT QLoRA (architecture-agnostic — works for
Cohere2/Command-R7B without depending on Unsloth's model coverage).

────────────────────────────────────────────────────────────────────────────
KAGGLE SETUP (do once in the notebook UI):
  1. Settings → Accelerator = **GPU T4 x2** (or T4 x1). NOT P100 (sm_60 fails).
  2. Settings → Internet = ON.
  3. command-r7b-arabic is a GATED Cohere model → accept the license at
     https://huggingface.co/CohereLabs/c4ai-command-r7b-arabic-02-2025
     then add your HF token as a Kaggle Secret named HF_TOKEN.
  4. Add the dataset upload (tg_train_commandr.jsonl + tg_val_commandr.jsonl)
     as a Kaggle Dataset; set DATA_DIR below to its /kaggle/input/... path.
  5. pip installs (first cell):
       !pip install -q -U transformers trl peft bitsandbytes accelerate datasets
────────────────────────────────────────────────────────────────────────────
"""
import os, json
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          BitsAndBytesConfig, TrainingArguments)
from peft import LoraConfig
from trl import SFTTrainer

# ── config ──────────────────────────────────────────────────────────────────
BASE_MODEL = "CohereLabs/c4ai-command-r7b-arabic-02-2025"
DATA_DIR   = Path(os.environ.get("DATA_DIR", "/kaggle/input/tg-commandr"))
OUT_DIR    = Path("/kaggle/working/tg-tutor-commandr-lora")
MERGED_DIR = Path("/kaggle/working/tg-tutor-commandr-merged")
MAX_SEQ    = 1024          # median answer ~307 chars; 1024 tokens is ample
EPOCHS     = 2
HF_TOKEN   = os.environ.get("HF_TOKEN")  # set from Kaggle Secret

# ── tokenizer + 4-bit base ──────────────────────────────────────────────────
tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=HF_TOKEN)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,   # T4 = fp16 (no bf16)
    bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, quantization_config=bnb, device_map="auto",
    token=HF_TOKEN, torch_dtype=torch.float16, trust_remote_code=True,
)
model.config.use_cache = False

# ── data: render messages via the model's own chat template ─────────────────
def fmt(ex):
    return {"text": tok.apply_chat_template(ex["messages"], tokenize=False,
                                            add_generation_prompt=False)}

ds_train = load_dataset("json", data_files=str(DATA_DIR / "tg_train_commandr.jsonl"),
                        split="train").map(fmt, remove_columns=["messages"])
ds_val = load_dataset("json", data_files=str(DATA_DIR / "tg_val_commandr.jsonl"),
                      split="train").map(fmt, remove_columns=["messages"])

# ── LoRA (QLoRA) ────────────────────────────────────────────────────────────
peft_cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

args = TrainingArguments(
    output_dir=str(OUT_DIR),
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,      # effective batch 16
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    logging_steps=20,
    eval_strategy="steps", eval_steps=200,
    save_strategy="steps", save_steps=400, save_total_limit=2,
    fp16=True, optim="paged_adamw_8bit",
    gradient_checkpointing=True,
    report_to="none",
)

trainer = SFTTrainer(
    model=model, args=args,
    train_dataset=ds_train, eval_dataset=ds_val,
    peft_config=peft_cfg,
    dataset_text_field="text", max_seq_length=MAX_SEQ,
    tokenizer=tok, packing=False,
)
trainer.train()
trainer.save_model(str(OUT_DIR))

# ── merge adapter → fp16, then GGUF Q4_K_M (for Ollama on the home server) ───
print("Merging LoRA adapter into base…")
from peft import AutoPeftModelForCausalLM
merged = AutoPeftModelForCausalLM.from_pretrained(
    str(OUT_DIR), torch_dtype=torch.float16, device_map="cpu", token=HF_TOKEN)
merged = merged.merge_and_unload()
merged.save_pretrained(str(MERGED_DIR), safe_serialization=True)
tok.save_pretrained(str(MERGED_DIR))

print("""
NEXT (GGUF export — run in a fresh cell):
  !git clone --depth 1 https://github.com/ggerganov/llama.cpp /kaggle/working/llama.cpp
  !pip install -q -r /kaggle/working/llama.cpp/requirements.txt
  !python /kaggle/working/llama.cpp/convert_hf_to_gguf.py \\
        /kaggle/working/tg-tutor-commandr-merged \\
        --outfile /kaggle/working/tg-tutor-v4-f16.gguf --outtype f16
  !/kaggle/working/llama.cpp/llama-quantize \\
        /kaggle/working/tg-tutor-v4-f16.gguf \\
        /kaggle/working/tg-tutor-v4-Q4_K_M.gguf Q4_K_M

Then download tg-tutor-v4-Q4_K_M.gguf (browser-download the Output zip — the
Kaggle CLI ConnectionResets on big files), scp to the home server, and:
  export OLLAMA_HOST=http://100.109.163.64:11434
  ollama create tg-tutor:v4 -f Modelfile.tg-tutor-v4
(keep tg-tutor:v2/v3 as rollback; point OLLAMA_LOCAL_FALLBACK_MODEL=tg-tutor:v4)
""")
