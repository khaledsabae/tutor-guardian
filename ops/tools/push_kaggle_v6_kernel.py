#!/usr/bin/env python3
"""push_kaggle_v6_kernel.py — Publishes the v6 dataset to the private Kaggle
dataset (`khaledsabae/tg-qa-dataset`) and pushes the automated v6 GPU training
kernel (`khaledsabae/tutor-guardian-arabic-parenting-llm-fine-tune`) to Kaggle
(`GpuT4x2`).

The kernel:
  1. Reads the v6 bundle from `/kaggle/input/tg-qa-dataset` (or falls back to
     `khaledhamdy/tg-ultra-v6-private` on HuggingFace).
  2. Fine-tunes `tg-reranker-v2` (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`)
     in an isolated single-GPU subprocess on all 4,858 Teacher-scored real
     parent `(question, passage, label)` pairs and uploads `tg-reranker-v2.zip`
     to `khaledhamdy/tg-tutor-v6-gguf`.
  3. Fine-tunes `tg-tutor:v6` on the real-parent gold SFT + KB corpus, merges
     LoRA across both T4 GPUs, quantizes to `tg-tutor-v6-Q4_K_M.gguf`, and
     uploads it to `khaledhamdy/tg-tutor-v6-gguf`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ULTRA_DIR = PROJECT_ROOT / "ops" / "data" / "kaggle_upload_ultra"
DATASET_STAGE_DIR = ULTRA_DIR / "kaggle_dataset_v6"
KERNEL_DIR = ULTRA_DIR / "kaggle_kernel_v6"

# Do NOT pass -U to pip install so Kaggle's tested transformers/torch ABI is preserved
PIP_CELL = """!pip install -q transformers trl peft bitsandbytes accelerate datasets sentence-transformers huggingface_hub
!pip uninstall -y torchao
"""

RERANK_SCRIPT = r'''import os, json, zipfile, shutil
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup
from sentence_transformers import CrossEncoder
from huggingface_hub import hf_hub_download, HfApi, login

def resolve_data_dir() -> Path:
    for p in (
        Path("/kaggle/input/tg-qa-dataset"),
        Path("/kaggle/input/datasets/khaledsabae/tg-qa-dataset"),
    ):
        if p.exists():
            return p
    for p in Path("/kaggle/input").rglob("reranker_teacher_pairs.jsonl"):
        return p.parent
    return Path("/kaggle/input/tg-qa-dataset")

DATA_DIR = resolve_data_dir()
print("📂 DATA_DIR:", DATA_DIR)

def get_hf_token() -> str:
    for p in Path("/kaggle/input").rglob("hf_auth.json"):
        return json.loads(p.read_text(encoding="utf-8"))["hf_token"].strip()
    try:
        from kaggle_secrets import UserSecretsClient
        tok = UserSecretsClient().get_secret("HF_TOKEN")
        if tok:
            return tok.strip()
    except Exception:
        pass
    return os.environ.get("HF_TOKEN", "").strip()

HF_TOKEN = get_hf_token()
assert HF_TOKEN, "HF_TOKEN missing from Kaggle dataset and Secrets"
os.environ["HF_TOKEN"] = HF_TOKEN
login(token=HF_TOKEN, add_to_git_credential=False)

WORK_DIR = Path("/kaggle/working/tg_ultra")
WORK_DIR.mkdir(parents=True, exist_ok=True)
HF_DATASET_REPO = "khaledhamdy/tg-ultra-v6-private"
HF_OUTPUT_REPO = "khaledhamdy/tg-tutor-v6-gguf"

if (DATA_DIR / "reranker_teacher_pairs.jsonl").exists():
    print("✅ Found v6 bundle directly in private Kaggle dataset:", DATA_DIR)
    for fn in (
        "distilled_real_parents_sft.jsonl",
        "distilled_real_parents_dpo.jsonl",
        "reranker_teacher_pairs.jsonl",
        "tg_train_ultra_v6.jsonl",
        "tg_val_ultra_v6.jsonl",
    ):
        src = DATA_DIR / fn
        if src.exists():
            shutil.copy2(src, WORK_DIR / fn)
else:
    print("📥 Downloading tg_colab_ultra_bundle.zip from private HF dataset repo...")
    bundle_zip = hf_hub_download(
        repo_id=HF_DATASET_REPO,
        repo_type="dataset",
        filename="tg_colab_ultra_bundle.zip",
        local_dir="/kaggle/working",
        token=HF_TOKEN,
    )
    with zipfile.ZipFile(bundle_zip, "r") as zf:
        zf.extractall(WORK_DIR)

rerank_rows = [
    json.loads(l)
    for l in (WORK_DIR / "reranker_teacher_pairs.jsonl").read_text(encoding="utf-8").splitlines()
    if l.strip()
]
print(f"🎯 Training Cross-Encoder Reranker on {len(rerank_rows)} Teacher-judged real-parent pairs (single GPU)...")

MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
tok = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=1).to(device)

class PairDataset(Dataset):
    def __init__(self, rows):
        self.rows = rows
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, idx):
        r = self.rows[idx]
        return r["question"], r["passage"], float(r["label"])

def collate_fn(batch):
    qs = [b[0] for b in batch]
    ps = [b[1] for b in batch]
    ys = torch.tensor([b[2] for b in batch], dtype=torch.float32)
    enc = tok(qs, ps, padding=True, truncation=True, max_length=256, return_tensors="pt")
    return enc, ys

loader = DataLoader(PairDataset(rerank_rows), batch_size=32, shuffle=True, collate_fn=collate_fn)
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
epochs = 3
total_steps = len(loader) * epochs
scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=max(10, int(total_steps * 0.1)), num_training_steps=total_steps)
loss_fn = torch.nn.BCEWithLogitsLoss()

model.train()
for ep in range(epochs):
    total_loss = 0.0
    for step, (enc, ys) in enumerate(loader):
        optimizer.zero_grad()
        enc = {k: v.to(device) for k, v in enc.items()}
        ys = ys.to(device)
        logits = model(**enc).logits.view(-1)
        loss = loss_fn(logits, ys)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        total_loss += loss.item()
    print(f"  Epoch {ep+1}/{epochs} — avg BCE loss: {total_loss / max(1, len(loader)):.4f}")

reranker_dir = str(WORK_DIR / "tg-reranker-v2")
model.save_pretrained(reranker_dir)
tok.save_pretrained(reranker_dir)

# Verify compatibility with sentence_transformers.CrossEncoder
ce_test = CrossEncoder(reranker_dir, device="cuda:0")
scores = ce_test.predict([
    ["ابني عمره سنتين يضرب أخاه الرضيع بسبب الغيرة، ماذا أفعل؟", "تنظيم الغيرة بين الإخوة وتخصيص وقت فردي للطفل الأكبر"],
    ["ابني عمره سنتين يضرب أخاه الرضيع بسبب الغيرة، ماذا أفعل؟", "أحكام زكاة الفطر ومقدارها"],
])
print("✅ Verified CrossEncoder scores (relevant vs irrelevant):", scores)

shutil.make_archive("/kaggle/working/tg-reranker-v2", "zip", reranker_dir)
api = HfApi(token=HF_TOKEN)
api.create_repo(repo_id=HF_OUTPUT_REPO, repo_type="model", private=True, exist_ok=True)
api.upload_file(
    path_or_fileobj="/kaggle/working/tg-reranker-v2.zip",
    path_in_repo="tg-reranker-v2.zip",
    repo_id=HF_OUTPUT_REPO,
    repo_type="model",
)
print("☁️ Uploaded tg-reranker-v2.zip ->", HF_OUTPUT_REPO)
'''

PREP_AND_RERANKER_CELL = f"""import subprocess, sys
from pathlib import Path
Path("rerank_v6.py").write_text({RERANK_SCRIPT!r}, encoding="utf-8")
subprocess.run([sys.executable, "rerank_v6.py"], check=True)
"""

TRAIN_SCRIPT = r'''import os, json
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
from pathlib import Path
import torch
from datasets import load_dataset, concatenate_datasets
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig
from huggingface_hub import HfApi, create_repo, login

def get_hf_token() -> str:
    for p in Path("/kaggle/input").rglob("hf_auth.json"):
        return json.loads(p.read_text(encoding="utf-8"))["hf_token"].strip()
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"].strip()
    from kaggle_secrets import UserSecretsClient
    return UserSecretsClient().get_secret("HF_TOKEN").strip()

HF_TOKEN = get_hf_token()
os.environ["HF_TOKEN"] = HF_TOKEN
login(token=HF_TOKEN, add_to_git_credential=False)

BASE_MODEL = "CohereLabs/c4ai-command-r7b-arabic-02-2025"
WORK_DIR   = Path("/kaggle/working/tg_ultra")
OUT_DIR    = Path("/kaggle/working/tg-tutor-v6-lora")
MAX_SEQ    = 512

tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=HF_TOKEN)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.model_max_length = MAX_SEQ

bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=bnb,
    device_map={"": 0},
    token=HF_TOKEN,
    torch_dtype=torch.float16,
    trust_remote_code=True,
)
model.config.use_cache = False
model.config.torch_dtype = torch.float32

def fmt(ex):
    return {"text": tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)}

# Combine 100% of Teacher-distilled real parent gold answers (2x = 2,492) + 1,508 KB units = 4,000 high-signal examples (250 steps)
ds_distilled = load_dataset("json", data_files=str(WORK_DIR / "distilled_real_parents_sft.jsonl"), split="train")
ds_full = load_dataset("json", data_files=str(WORK_DIR / "tg_train_ultra_v6.jsonl"), split="train").select(range(1508))
ds_train = concatenate_datasets([ds_distilled, ds_distilled, ds_full]).shuffle(seed=42).map(fmt, remove_columns=["messages"])
ds_val   = load_dataset("json", data_files=str(WORK_DIR / "tg_val_ultra_v6.jsonl"), split="train").select(range(200)).map(fmt, remove_columns=["messages"])

peft_cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
)
args = SFTConfig(
    output_dir=str(OUT_DIR), num_train_epochs=1, per_device_train_batch_size=2,
    gradient_accumulation_steps=8, learning_rate=2e-4, lr_scheduler_type="cosine",
    warmup_ratio=0.03, logging_steps=20, eval_strategy="steps", eval_steps=125,
    save_strategy="steps", save_steps=250, save_total_limit=2, fp16=True,
    optim="paged_adamw_8bit", gradient_checkpointing=True, report_to="none",
    dataset_text_field="text", packing=False,
)
trainer = SFTTrainer(
    model=model, args=args, train_dataset=ds_train, eval_dataset=ds_val,
    peft_config=peft_cfg, processing_class=tok,
)
for _n, _p in trainer.model.named_parameters():
    if _p.dtype == torch.bfloat16:
        _p.data = _p.data.to(torch.float32)

trainer.train()
trainer.save_model(str(OUT_DIR))
tok.save_pretrained(str(OUT_DIR))

ADAPTER_REPO = "khaledhamdy/tg-tutor-v6-lora"
create_repo(ADAPTER_REPO, private=True, exist_ok=True, token=HF_TOKEN)
HfApi(token=HF_TOKEN).upload_folder(folder_path=str(OUT_DIR), repo_id=ADAPTER_REPO, token=HF_TOKEN)
print("✅ Adapter backed up to", ADAPTER_REPO)
'''

TRAIN_CELL = f"""import subprocess, sys
from pathlib import Path
Path("train_v6.py").write_text({TRAIN_SCRIPT!r}, encoding="utf-8")
subprocess.run([sys.executable, "train_v6.py"], check=True)
"""

MERGE_SCRIPT = r'''import os, json
from pathlib import Path
import torch
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

def get_hf_token() -> str:
    for p in Path("/kaggle/input").rglob("hf_auth.json"):
        return json.loads(p.read_text(encoding="utf-8"))["hf_token"].strip()
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"].strip()
    from kaggle_secrets import UserSecretsClient
    return UserSecretsClient().get_secret("HF_TOKEN").strip()

HF_TOKEN = get_hf_token()
OUT_DIR    = Path("/kaggle/working/tg-tutor-v6-lora")
MERGED_DIR = Path("/kaggle/working/tg-tutor-v6-merged")

m = AutoPeftModelForCausalLM.from_pretrained(
    str(OUT_DIR), torch_dtype=torch.float16, device_map="auto",
    token=HF_TOKEN, trust_remote_code=True, low_cpu_mem_usage=True,
)
m = m.merge_and_unload()
m.save_pretrained(str(MERGED_DIR), safe_serialization=True, max_shard_size="2GB")
AutoTokenizer.from_pretrained(str(OUT_DIR), token=HF_TOKEN).save_pretrained(str(MERGED_DIR))
print("✅ Merged ->", MERGED_DIR)
'''

MERGE_CELL = f"""import subprocess, sys
from pathlib import Path
Path("merge_v6.py").write_text({MERGE_SCRIPT!r}, encoding="utf-8")
subprocess.run([sys.executable, "merge_v6.py"], check=True)
"""

GGUF_AND_UPLOAD_CELL = """!git clone --depth 1 https://github.com/ggerganov/llama.cpp /tmp/llama.cpp
!pip install -q -r /tmp/llama.cpp/requirements.txt
!rm -rf /root/.cache/huggingface/hub /kaggle/working/tg_ultra

import json, pathlib, subprocess, sys, os
from huggingface_hub import HfApi

def get_hf_token() -> str:
    for p in pathlib.Path("/kaggle/input").rglob("hf_auth.json"):
        return json.loads(p.read_text(encoding="utf-8"))["hf_token"].strip()
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"].strip()
    from kaggle_secrets import UserSecretsClient
    return UserSecretsClient().get_secret("HF_TOKEN").strip()

tc = pathlib.Path("/kaggle/working/tg-tutor-v6-merged/tokenizer_config.json")
cfg = json.loads(tc.read_text())
if isinstance(cfg.get("extra_special_tokens"), list):
    cfg.pop("extra_special_tokens", None)
    tc.write_text(json.dumps(cfg, ensure_ascii=False))

subprocess.run([
    sys.executable, "/tmp/llama.cpp/convert_hf_to_gguf.py",
    "/kaggle/working/tg-tutor-v6-merged",
    "--outfile", "/tmp/tg-tutor-v6-f16.gguf", "--outtype", "f16"
], check=True)
!rm -rf /kaggle/working/tg-tutor-v6-merged
!cmake -S /tmp/llama.cpp -B /tmp/llama.cpp/build -DGGML_CUDA=OFF
!cmake --build /tmp/llama.cpp/build --target llama-quantize -j4
!/tmp/llama.cpp/build/bin/llama-quantize /tmp/tg-tutor-v6-f16.gguf /kaggle/working/tg-tutor-v6-Q4_K_M.gguf Q4_K_M
!rm -rf /tmp/tg-tutor-v6-f16.gguf /tmp/llama.cpp

modelfile_text = '''FROM ./tg-tutor-v6-Q4_K_M.gguf

SYSTEM "أنت «المربّي»، مساعد تربوي عربي للأهل متخصص في التربية الإسلامية ونمو الطفل وصحته وأمانه الرقمي. أجب بالعربية الفصحى الميسرة بوضوح وتعاطف، وقدّم 3 إلى 4 خطوات عملية مرقمة قابلة للتنفيذ اليوم مستندة إلى مصادر موثوقة، واختم بسطر 📚 المصادر. لا تعطِ تشخيصاً طبياً ملزماً ولا جرعات أدوية ولا فتوى شخصية قاطعة، ولا تحل إلى متخصص إلا عند وجود خطر طبي أو نفسي حقيقي."

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
'''
pathlib.Path("/kaggle/working/Modelfile.tg-tutor-v6").write_text(modelfile_text, encoding="utf-8")

HF_TOKEN = get_hf_token()
api = HfApi(token=HF_TOKEN)
HF_OUTPUT_REPO = "khaledhamdy/tg-tutor-v6-gguf"
api.create_repo(repo_id=HF_OUTPUT_REPO, repo_type="model", private=True, exist_ok=True)
for fn in ("tg-tutor-v6-Q4_K_M.gguf", "Modelfile.tg-tutor-v6"):
    api.upload_file(
        path_or_fileobj=f"/kaggle/working/{fn}",
        path_in_repo=fn,
        repo_id=HF_OUTPUT_REPO,
        repo_type="model",
    )
    print("☁️ Uploaded", fn, "->", HF_OUTPUT_REPO)
"""


def cc(src: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src.splitlines(keepends=True)}


def mc(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


def load_local_hf_token() -> str:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("HF_TOKEN", "").strip()


def update_private_kaggle_dataset(hf_token: str) -> None:
    if DATASET_STAGE_DIR.exists():
        shutil.rmtree(DATASET_STAGE_DIR)
    DATASET_STAGE_DIR.mkdir(parents=True, exist_ok=True)

    ds_meta = {
        "title": "tg-qa-dataset",
        "id": "khaledsabae/tg-qa-dataset",
        "licenses": [{"name": "CC0-1.0"}],
    }
    (DATASET_STAGE_DIR / "dataset-metadata.json").write_text(
        json.dumps(ds_meta, indent=2) + "\n", encoding="utf-8"
    )
    (DATASET_STAGE_DIR / "hf_auth.json").write_text(
        json.dumps({"hf_token": hf_token}) + "\n", encoding="utf-8"
    )
    for fn in (
        "distilled_real_parents_sft.jsonl",
        "distilled_real_parents_dpo.jsonl",
        "reranker_teacher_pairs.jsonl",
        "tg_train_ultra_v6.jsonl",
        "tg_val_ultra_v6.jsonl",
    ):
        shutil.copy2(ULTRA_DIR / fn, DATASET_STAGE_DIR / fn)

    print("📦 Publishing new version of private Kaggle dataset khaledsabae/tg-qa-dataset...")
    subprocess.run(
        [
            "/home/khalednew/.local/bin/kaggle",
            "datasets",
            "version",
            "-p",
            str(DATASET_STAGE_DIR),
            "-m",
            "v6 Ultra 100% Real-Parent Teacher-Distilled SFT + DPO + Reranker Bundle",
        ],
        check=True,
    )
    (DATASET_STAGE_DIR / "hf_auth.json").unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-dataset", action="store_true", help="Skip re-uploading the Kaggle dataset")
    args = ap.parse_args()

    hf_token = load_local_hf_token()
    assert hf_token, "HF_TOKEN not found in .env"
    if not args.skip_dataset:
        update_private_kaggle_dataset(hf_token)
        print("⏳ Waiting 12s for Kaggle dataset version to register...")
        time.sleep(12)

    KERNEL_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": "khaledsabae/tutor-guardian-arabic-parenting-llm-fine-tune",
        "title": "Tutor Guardian — Arabic Parenting LLM Fine-Tune",
        "code_file": "finetune_tg_kaggle.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "machine_shape": "GpuT4x2",
        "enable_tpu": False,
        "enable_internet": True,
        "dataset_sources": ["khaledsabae/tg-qa-dataset"],
        "competition_sources": [],
        "kernel_sources": [],
    }
    (KERNEL_DIR / "kernel-metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    nb = {
        "cells": [
            mc("# Tutor Guardian v6 — Real Parent Distilled SFT + Reranker v2 + GGUF Export"),
            cc(PIP_CELL),
            cc(PREP_AND_RERANKER_CELL),
            cc(TRAIN_CELL),
            cc(MERGE_CELL),
            cc(GGUF_AND_UPLOAD_CELL),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (KERNEL_DIR / "finetune_tg_kaggle.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"📝 Wrote Kaggle v6 kernel files to {KERNEL_DIR}")

    subprocess.run(["/home/khalednew/.local/bin/kaggle", "kernels", "push", "-p", str(KERNEL_DIR)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
