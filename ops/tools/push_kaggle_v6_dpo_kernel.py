#!/usr/bin/env python3
"""
Push Phase 2 DPO Alignment Kernel (`tg-tutor-v6-dpo`) to Kaggle `GpuT4x2`.
Trains Direct Preference Optimization (DPO) on top of `khaledhamdy/tg-tutor-v6-lora`
using the 1,154 Gemma 4 31B Teacher preference pairs (`distilled_real_parents_dpo.jsonl`)
and uploads the resulting adapter to `khaledhamdy/tg-tutor-v6-dpo-lora`.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


def load_hf_token() -> str:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("HF_TOKEN not found in environment or .env")


KERNEL_SCRIPT = '''#!/usr/bin/env python3
"""
Tutor-Guardian v6 Phase 2 — Real-Parent DPO Alignment on Kaggle T4
"""
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
HF_TOKEN = "__HF_TOKEN__"
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

WORK_DIR = Path("/kaggle/working")
DPO_SCRIPT = WORK_DIR / "run_dpo_v6.py"

DPO_CODE = r"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import inspect
import json
import shutil
from pathlib import Path

import torch
from datasets import Dataset
from huggingface_hub import HfApi, snapshot_download
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import DPOConfig, DPOTrainer

HF_TOKEN = os.environ["HF_TOKEN"]
BASE_MODEL_ID = "CohereLabs/c4ai-command-r7b-arabic-02-2025"
SFT_LORA_REPO = "khaledhamdy/tg-tutor-v6-lora"
DPO_LORA_REPO = "khaledhamdy/tg-tutor-v6-dpo-lora"
PRIVATE_DATA_REPO = "khaledhamdy/tg-ultra-v6-private"

TG_SYSTEM_PROMPT = (
    "أنت «المربّي»، مستشار تربوي إسلامي وطبي ونفسي خبير، تقدّم إجابات علمية "
    "وعملية دافئة للأمهات والآباء باللغة العربية الفصحى الميسّرة، مع الالتزام التام "
    "بالأدلة الشرعية الصحيحة والإرشادات الطبية والتربوية المعتمدة، وتجنّب أي عنف "
    "أو قسوة ضد الطفل، وتختم بالمصادر الموثوقة."
)


def find_dpo_jsonl() -> Path:
    candidates = list(Path("/kaggle/input").rglob("distilled_real_parents_dpo.jsonl"))
    if candidates:
        print(f"[DPO] Found dataset in Kaggle input: {candidates[0]}", flush=True)
        return candidates[0]
    print("[DPO] Downloading distilled_real_parents_dpo.jsonl from HF private repo...", flush=True)
    local_dir = Path("/kaggle/working/dpo_data")
    snapshot_download(
        repo_id=PRIVATE_DATA_REPO,
        repo_type="dataset",
        local_dir=str(local_dir),
        allow_patterns=["*dpo*.jsonl"],
        token=HF_TOKEN,
    )
    found = list(local_dir.rglob("distilled_real_parents_dpo.jsonl"))
    if not found:
        raise FileNotFoundError("distilled_real_parents_dpo.jsonl not found!")
    return found[0]


def main():
    print(f"[DPO] PyTorch: {torch.__version__}, CUDA devices visible: {torch.cuda.device_count()}", flush=True)
    dpo_path = find_dpo_jsonl()
    raw_rows = [
        json.loads(line)
        for line in dpo_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"[DPO] Loaded {len(raw_rows)} raw DPO preference pairs.", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, token=HF_TOKEN, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    formatted_rows = []
    for r in raw_rows:
        prompt_text = (r.get("prompt") or "").strip()
        chosen_text = (r.get("chosen") or "").strip()
        rejected_text = (r.get("rejected") or "").strip()
        if not prompt_text or not chosen_text or not rejected_text or chosen_text == rejected_text:
            continue
        chat_prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": TG_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        # Prioritize pairs where rejected had redaction glitches or noisy citations
        priority = 1 if ("[رقم هاتف محذوف]" in rejected_text or len(rejected_text) > 1400) else 0
        formatted_rows.append(
            {
                "prompt": chat_prompt,
                "chosen": chosen_text + tokenizer.eos_token,
                "rejected": rejected_text + tokenizer.eos_token,
                "priority": priority,
            }
        )

    # Sort so highest-signal corrective pairs come first, with deterministic shuffle inside buckets
    formatted_rows.sort(key=lambda x: (-x["priority"], len(x["prompt"])))
    for item in formatted_rows:
        item.pop("priority", None)

    print(f"[DPO] Valid formatted DPO pairs: {len(formatted_rows)}", flush=True)
    eval_size = min(48, max(16, len(formatted_rows) // 20))
    eval_rows = formatted_rows[:eval_size]
    train_rows = formatted_rows[eval_size:]
    train_ds = Dataset.from_list(train_rows)
    eval_ds = Dataset.from_list(eval_rows)
    print(f"[DPO] Train pairs: {len(train_ds)} | Eval pairs: {len(eval_ds)}", flush=True)

    print("[DPO] Downloading SFT LoRA adapter khaledhamdy/tg-tutor-v6-lora...", flush=True)
    sft_lora_dir = Path("/kaggle/working/sft_lora_v6")
    snapshot_download(repo_id=SFT_LORA_REPO, local_dir=str(sft_lora_dir), token=HF_TOKEN)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    print("[DPO] Loading 4-bit base model on cuda:0...", flush=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        torch_dtype=torch.float16,
        token=HF_TOKEN,
        trust_remote_code=True,
    )
    base_model.config.use_cache = False

    dpo_sig = inspect.signature(DPOConfig.__init__).parameters
    supports_dual_adapter = "model_adapter_name" in dpo_sig and "ref_adapter_name" in dpo_sig

    if supports_dual_adapter:
        print("[DPO] Loading dual adapters ('dpo' trainable + 'ref' frozen SFT reference)...", flush=True)
        model = PeftModel.from_pretrained(
            base_model, str(sft_lora_dir), is_trainable=True, adapter_name="dpo"
        )
        model.load_adapter(str(sft_lora_dir), adapter_name="ref", is_trainable=False)
        model.set_adapter("dpo")
    else:
        print("[DPO] Loading trainable SFT LoRA adapter with precomputed reference logprobs...", flush=True)
        model = PeftModel.from_pretrained(base_model, str(sft_lora_dir), is_trainable=True)

    out_dir = Path("/kaggle/working/dpo_checkpoints")
    cfg_kwargs = dict(
        output_dir=str(out_dir),
        beta=0.1,
        learning_rate=5e-6,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        max_steps=85,
        logging_steps=5,
        save_strategy="steps",
        save_steps=40,
        fp16=True,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        max_length=768,
        max_prompt_length=256,
        remove_unused_columns=False,
        report_to="none",
        seed=42,
    )
    if "eval_strategy" in dpo_sig:
        cfg_kwargs["eval_strategy"] = "steps"
        cfg_kwargs["eval_steps"] = 40
    elif "evaluation_strategy" in dpo_sig:
        cfg_kwargs["evaluation_strategy"] = "steps"
        cfg_kwargs["eval_steps"] = 40

    if supports_dual_adapter:
        cfg_kwargs["model_adapter_name"] = "dpo"
        cfg_kwargs["ref_adapter_name"] = "ref"
    elif "precompute_ref_log_probs" in dpo_sig:
        cfg_kwargs["precompute_ref_log_probs"] = True

    dpo_args = DPOConfig(**cfg_kwargs)

    trainer_sig = inspect.signature(DPOTrainer.__init__).parameters
    trainer_kwargs = dict(
        model=model,
        ref_model=None,
        args=dpo_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
    )
    if "processing_class" in trainer_sig:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = DPOTrainer(**trainer_kwargs)
    print("[DPO] Starting DPO training (85 steps, batch_size=8, beta=0.1, lr=5e-6)...", flush=True)
    train_res = trainer.train()
    print(f"[DPO] Training finished! Metrics: {train_res.metrics}", flush=True)

    eval_metrics = trainer.evaluate()
    print(f"[DPO] Final Evaluation Metrics: {eval_metrics}", flush=True)

    final_dir = Path("/kaggle/working/tg_tutor_v6_dpo_lora")
    final_dir.mkdir(parents=True, exist_ok=True)
    if supports_dual_adapter:
        model.set_adapter("dpo")
    model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    # If PEFT saved inside a 'dpo/' subfolder due to named adapter, flatten it to root
    nested_dpo = final_dir / "dpo"
    if nested_dpo.is_dir() and (nested_dpo / "adapter_model.safetensors").exists():
        for item in nested_dpo.iterdir():
            shutil.move(str(item), str(final_dir / item.name))
        nested_dpo.rmdir()

    # Record training summary metadata
    summary = {
        "base_model": BASE_MODEL_ID,
        "init_sft_adapter": SFT_LORA_REPO,
        "dpo_pairs_total": len(formatted_rows),
        "train_metrics": train_res.metrics,
        "eval_metrics": eval_metrics,
    }
    (final_dir / "dpo_training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[DPO] Saved final DPO adapter files: {[p.name for p in final_dir.iterdir()]}", flush=True)

    api = HfApi(token=HF_TOKEN)
    api.create_repo(repo_id=DPO_LORA_REPO, repo_type="model", exist_ok=True)
    api.upload_folder(
        repo_id=DPO_LORA_REPO,
        folder_path=str(final_dir),
        repo_type="model",
        commit_message="Upload tg-tutor-v6-dpo LoRA adapter trained on Gemma 4 31B real-parent preference pairs",
    )
    print(f"✅ [DPO] Successfully uploaded DPO adapter to https://huggingface.co/{DPO_LORA_REPO}!", flush=True)


if __name__ == "__main__":
    main()
"""


def main():
    print("=== Installing / verifying TRL, PEFT, BitsAndBytes on Kaggle ===", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "-U",
            "trl>=0.12.0",
            "peft>=0.13.0",
            "bitsandbytes>=0.44.0",
            "accelerate>=1.0.0",
            "huggingface_hub",
        ],
        check=True,
    )
    DPO_SCRIPT.write_text(DPO_CODE, encoding="utf-8")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"
    env["HF_HUB_DISABLE_XET"] = "1"
    subprocess.run([sys.executable, "-u", str(DPO_SCRIPT)], env=env, check=True)


if __name__ == "__main__":
    main()
'''


def main() -> int:
    hf_token = load_hf_token()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        script_text = KERNEL_SCRIPT.replace("__HF_TOKEN__", hf_token)
        (tmp_path / "script.py").write_text(script_text, encoding="utf-8")
        metadata = {
            "id": "khaledsabae/tutor-guardian-arabic-parenting-llm-fine-tune",
            "title": "Tutor-Guardian Arabic Parenting LLM Fine-Tune",
            "code_file": "script.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": True,
            "dataset_sources": ["khaledsabae/tg-qa-dataset"],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
            "machine_shape": "GpuT4x2",
        }
        (tmp_path / "kernel-metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        kaggle_bin = Path.home() / ".local" / "bin" / "kaggle"
        cmd = [str(kaggle_bin) if kaggle_bin.exists() else "kaggle", "kernels", "push", "-p", str(tmp_path)]
        res = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(res.stdout)
        if res.stderr:
            print(res.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
