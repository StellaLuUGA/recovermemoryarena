"""AGENT_CONFIG_C_QWEN32B — Config B interface, backbone swapped only.

Identical to agent_b in every respect except:
  * backbone  = Qwen3-32B-AWQ served locally by vLLM on :8124
  * invocation adds `chat_template_kwargs={"enable_thinking": false}`, which is the
    model-format requirement strictly necessary to run Qwen3 in non-thinking /
    direct-answer mode (without it the model emits a <think> block).

System prompt, user prompt template, admissible-command formatting, ICL example,
observation / history / inventory serialisation, action output contract and the
entity-preserving exact parser are imported verbatim from agent_b.
"""
import os, sys, json, hashlib
import requests
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent_b as B

BASE_URL = "http://localhost:8124/v1"
TOKENIZE_URL = "http://localhost:8124/tokenize"
MODEL = "qwen3-32b-awq-local"
MODEL_PATH = "/home/aristella/models/Qwen3-32B-AWQ"
TEMPERATURE = B.TEMPERATURE          # 0.0
SEED = B.SEED                        # 13
MAX_TOKENS = B.MAX_TOKENS            # 32
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}

_client = OpenAI(base_url=BASE_URL, api_key="EMPTY")

# --- verbatim reuse of the frozen Config B interface ---
SYSTEM = B.SYSTEM
_render = B._render
format_admissible = B.format_admissible
build_prompt = B.build_prompt
parse_action = B.parse_action


def count_tokens(text):
    r = requests.post(TOKENIZE_URL, json={"model": MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["count"]


def act(icl, intro, history, admissible):
    msgs, hist_text = build_prompt(icl, intro, history, admissible)
    resp = _client.chat.completions.create(
        model=MODEL, messages=msgs, temperature=TEMPERATURE, top_p=1.0,
        max_tokens=MAX_TOKENS, seed=SEED, stop=["\n"], extra_body=EXTRA_BODY,
    )
    msg = resp.choices[0].message
    raw = (msg.content or "").strip()
    reasoning = getattr(msg, "reasoning_content", None)
    cmd, valid = parse_action(raw, admissible)
    usage = resp.usage
    return {"raw": raw, "reasoning_content": reasoning,
            "command": cmd, "valid": valid, "invalid": not valid, "snapped": False,
            "finish_reason": resp.choices[0].finish_reason,
            "completion_tokens": usage.completion_tokens if usage else None,
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "history_text": hist_text}


def config_dict(icl):
    cfg = B.config_dict(icl)
    cfg.update({
        "config_id": "AGENT_CONFIG_C_QWEN32B",
        "derived_from": "AGENT_CONFIG_B_ADMISSIBLE_COMMANDS",
        "only_change": "backbone (+ the chat_template_kwargs needed for Qwen3 non-thinking mode)",
        "model": MODEL, "model_path": MODEL_PATH, "endpoint": BASE_URL,
        "extra_body": EXTRA_BODY,
        "backbone": {
            "name_requested": "Qwen3-32B-Instruct-AWQ",
            "name_actual": "Qwen/Qwen3-32B-AWQ",
            "note": ("Qwen3-32B is a hybrid-reasoning model; there is no separate "
                     "'-Instruct-AWQ' release. Non-thinking / direct-answer mode is "
                     "selected via chat_template_kwargs.enable_thinking=false."),
            "local_path": MODEL_PATH, "size_on_disk": "19G",
            "quantization": "AWQ 4-bit, group_size 128, gemm; vLLM runtime kernel awq_marlin",
            "dtype": "torch.float16",
            "architecture": "Qwen3ForCausalLM, 64 layers, 64 heads, 8 KV heads, head_dim 128",
            "vllm_version": "0.18.0", "torch": "2.10.0+cu128",
            "max_model_len": 16384, "kv_cache_dtype": "auto (fp16)",
            "gpu_memory_utilization": 0.90,
            "gpu_kv_cache_size_tokens": 34192,
            "attention_backend": "FLASH_ATTN (FlashAttention 2)",
            "enforce_eager": False, "enable_prefix_caching": False,
            "device": "NVIDIA GeForce RTX 5090 (32607 MiB), driver 595.71.05, CUDA 13.2",
            "external_api_traffic": "none - localhost only",
            "launch_command": ("/home/aristella/.pipenv-venv/bin/python3 -m "
                               "vllm.entrypoints.openai.api_server --model "
                               "/home/aristella/models/Qwen3-32B-AWQ --served-model-name "
                               "qwen3-32b-awq-local --port 8124 --max-model-len 16384 "
                               "--gpu-memory-utilization 0.90 --no-enable-prefix-caching"),
        },
    })
    return cfg


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
