"""Formal ALFWorld ReCoverMem experiment -- full pipeline, resumable."""
from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from af_formal.common import (EXTERNAL_ATTEMPTS, GAMMA, MAX_BRANCH_ACTIONS,
                              MAX_TOTAL_AGENT_ACTIONS, N_TABLE2, QWEN_BASE_URL, QWEN_MODEL,
                              QWEN_PATH, RESULTS, SEED, STORES, jdump, jload, log,
                              sha256_file, sha256_json)
from af_formal import collect as CO
from af_formal import stages as ST
from af_formal import table2_onpolicy as T2M
from af_formal import memhost as M

from recovermem.scoring.predictor import RecoverabilityPredictor

FP = RESULTS / "frozen_protocol"
STATE = RESULTS / "RUN_STATE.json"


def state_get():
    return jload(STATE) if STATE.exists() else {"stage": "start", "history": []}


def state_set(stage, **kw):
    s = state_get()
    s["stage"] = stage
    s["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    s.setdefault("history", []).append({"stage": stage, "at": s["updated"], **kw})
    s.update(kw)
    jdump(s, STATE)
    log(f"=== STAGE: {stage} ===")


def code_hash():
    files = sorted(Path("/home/aristella/recoverappworld/af_formal").glob("*.py"))
    pf = [Path("/home/aristella/recoverappworld/alfworld_recovermem_preflight") / f
          for f in ("pf_lib.py", "agent_b.py", "agent_c.py")]
    return sha256_json({str(p.name): sha256_file(p) for p in files + pf})


def model_role_audit():
    prov = M.mem0_provenance()
    audit = {
        "action_agent": {"model": QWEN_MODEL, "path": QWEN_PATH, "endpoint": QWEN_BASE_URL,
                         "enable_thinking": False, "temperature": 0, "seed": SEED,
                         "quantization": "AWQ 4-bit / awq_marlin", "dtype": "fp16",
                         "vllm": "0.18.0", "max_model_len": 16384, "kv_cache_dtype": "auto",
                         "device": "RTX 5090"},
        "mem0_internal_llm": {"model": QWEN_MODEL, "endpoint": QWEN_BASE_URL,
                              "temperature": 0.0, "max_tokens": 1024,
                              "enable_thinking": False},
        "embedding": {"model": "sentence-transformers/all-MiniLM-L6-v2", "dims": 384,
                      "device": "cpu"},
        "mem0": prov,
        "recovery_backend": {"impl": "recovermem.recovery.TrajectoryRetriever",
                             "scoring": "IDF-weighted lexical, deterministic, no LLM call"},
        "stack_label": "ALFWorld Qwen3-32B stack configuration",
        "rationale": ("The RTX 5090 cannot hold Qwen3-32B-AWQ and a second 8B Mem0 LLM at once, "
                      "so the Mem0 internal LLM is the SAME Qwen3-32B-AWQ server as the action "
                      "agent. This is declared explicitly rather than presented as an "
                      "agent-only Qwen experiment."),
        "safeguards": {"MEM0_TELEMETRY": "False", "MEM0_TELEMETRY_SAMPLE_RATE": "0.0",
                       "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                       "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "openai_client_instrumentation": ("every openai.OpenAI client is patched "
                                                         "at construction: non-local base_url "
                                                         "raises, tokens are metered, "
                                                         "enable_thinking=false is forced"),
                       "outbound_network_during_formal_execution": "localhost only"},
        "known_setup_time_network_access": (
            "During environment setup (before any formal collection) mem0's spaCy dependency "
            "downloaded en_core_web_sm once. It is cached; no download occurs during the formal "
            "run. Recorded rather than omitted."),
        "code_hash": code_hash(),
    }
    jdump(audit, FP / "MODEL_ROLE_AUDIT.json")
    (FP / "MODEL_ROLE_AUDIT.md").write_text(f"""# Model-role audit — ALFWorld Qwen3-32B stack configuration

| role | model | endpoint |
|---|---|---|
| action agent | `{QWEN_MODEL}` (Qwen3-32B-AWQ, non-thinking, T=0) | `{QWEN_BASE_URL}` |
| Mem0 internal LLM | `{QWEN_MODEL}` (same server) | `{QWEN_BASE_URL}` |
| embedding | `sentence-transformers/all-MiniLM-L6-v2`, 384-d, CPU | local |
| recovery | `recovermem.recovery.TrajectoryRetriever` — IDF lexical, **no LLM** | n/a |
| vector store | FAISS, per-episode on-disk path | local |

**This is labelled explicitly: `ALFWorld Qwen3-32B stack configuration`.** The RTX 5090 cannot
reliably hold Qwen3-32B-AWQ and a separate Llama-3.1-8B Mem0 LLM simultaneously, so Mem0's
internal LLM is the same Qwen server as the action agent. It is not presented as an agent-only
Qwen experiment.

Mem0: pinned OSS checkout `{prov['mem0_repo']}` at commit `{prov['mem0_commit']}`
(the tau3 commit). Not upgraded.

Safeguards: `MEM0_TELEMETRY=False` and `MEM0_TELEMETRY_SAMPLE_RATE=0.0` set before `mem0` is
imported; `LITELLM_LOCAL_MODEL_COST_MAP=True`; `HF_HUB_OFFLINE=1`; `TRANSFORMERS_OFFLINE=1`.
Every `openai.OpenAI` client is instrumented at construction — a non-local `base_url` raises,
all prompt/completion tokens are metered into the cost ledger, and `enable_thinking=false` is
forced on every call. During formal execution there is no outbound network access beyond
localhost.

Recorded honestly: during environment **setup**, before any formal collection, mem0's spaCy
dependency downloaded `en_core_web_sm` once. It is cached and no download occurs during the run.

Code hash (af_formal + frozen preflight interface modules): `{audit['code_hash']}`
""")
    log(f"model role audit written; mem0 commit {prov['mem0_commit'][:12]}")
    return audit


def server_baseline():
    import requests
    try:
        m = requests.get(QWEN_BASE_URL + "/models", timeout=20).json()
        served = [d["id"] for d in m["data"]]
    except Exception as e:
        raise SystemExit(f"Qwen server unreachable: {e}")
    procs = subprocess.run(["bash", "-lc", "pgrep -af 'vllm.entrypoints' || true"],
                           capture_output=True, text=True).stdout.strip().splitlines()
    if len([p for p in procs if "8124" in p]) != 1:
        log(f"WARNING: expected exactly one Qwen server on 8124, found: {procs}")
    return {"served_models": served, "vllm_processes": procs,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    t0 = time.time()
    st = state_get()
    log(f"resuming from stage={st['stage']}")

    audit = model_role_audit()
    base = server_baseline()
    jdump(base, FP / "SERVER_BASELINE.json")

    # ---------------- stage: budget audit ----------------
    bud_jsonl = RESULTS / "budget" / "audit_predictor_train.jsonl"
    if not (FP / "BUDGET_FREEZE.json").exists():
        state_set("budget_audit")
        shutil.rmtree(STORES / "budget_audit", ignore_errors=True)
        CO.run_partition(FP / "PREDICTOR_TRAIN_16.json", bud_jsonl, "budget_audit",
                         collect_pairs=False, audit=True)
        ST.budget_audit(bud_jsonl)
    freeze = jload(FP / "BUDGET_FREEZE.json")
    B_MEM, B_REC = freeze["B_mem"], freeze["B_rec"]
    log(f"B_mem={B_MEM} B_rec={B_REC} (frozen sha={freeze['budget_freeze_sha256'][:16]})")

    # ---------------- stage: fresh predictor-train collection ----------------
    train_jsonl = RESULTS / "collect" / "predictor_train.jsonl"
    if not (RESULTS / "predictor" / "PREDICTOR_FREEZE.json").exists():
        state_set("collect_predictor_train")
        if not train_jsonl.exists():
            shutil.rmtree(STORES / "train", ignore_errors=True)
        CO.run_partition(FP / "PREDICTOR_TRAIN_16.json", train_jsonl, "train",
                         b_mem=B_MEM, b_rec=B_REC, collect_pairs=True)
        state_set("fit_predictor")
        ST.fit_predictor(train_jsonl)
    pmeta = jload(RESULTS / "predictor" / "PREDICTOR_FREEZE.json")
    predictor = RecoverabilityPredictor.load(RESULTS / "predictor" / "predictor.json")

    # ---------------- stage: calibration ----------------
    cal_jsonl = RESULTS / "collect" / "calibration.jsonl"
    if not (RESULTS / "calibration" / "thresholds.json").exists():
        state_set("collect_calibration")
        if not cal_jsonl.exists():
            shutil.rmtree(STORES / "cal", ignore_errors=True)
        CO.run_partition(FP / "CALIBRATION_24.json", cal_jsonl, "cal",
                         b_mem=B_MEM, b_rec=B_REC, collect_pairs=True)
        state_set("calibrate")
        ST.calibrate(cal_jsonl, predictor, pmeta)
    thresholds = jload(RESULTS / "calibration" / "thresholds.json")

    # ---------------- stage: final test / Table 1 ----------------
    test_jsonl = RESULTS / "collect" / "final_test.jsonl"
    if not (RESULTS / "table1" / "table1_alfworld.json").exists():
        state_set("collect_final_test")
        if not test_jsonl.exists():
            shutil.rmtree(STORES / "test", ignore_errors=True)
        CO.run_partition(FP / "FINAL_TEST_24.json", test_jsonl, "test",
                         b_mem=B_MEM, b_rec=B_REC, collect_pairs=True)
        state_set("table1")
        ST.table1(cal_jsonl, test_jsonl, predictor, pmeta, thresholds)
    t1 = jload(RESULTS / "table1" / "table1_alfworld.json")

    # ---------------- stage: Table 2 ----------------
    man_path = RESULTS / "table2" / "TABLE2_20_MANIFEST.json"
    if not man_path.exists():
        state_set("freeze_table2_manifest")
        ft = jload(FP / "FINAL_TEST_24.json")
        man = {"name": "TABLE2_20", "n": N_TABLE2,
               "source": "first 20 games of FINAL_TEST_24 in frozen final-test order",
               "final_test_manifest_sha256": ft["list_sha256"],
               "thresholds_sha256": thresholds["thresholds_sha256"],
               "predictor_sha256": pmeta["predictor_sha256"],
               "budget": {"B_mem": B_MEM, "B_rec": B_REC},
               "code_hash": audit["code_hash"],
               "policies": list(T2M.POLICIES),
               "global_horizon": MAX_TOTAL_AGENT_ACTIONS,
               "segment_horizon": MAX_BRANCH_ACTIONS,
               "games": ft["games"][:N_TABLE2]}
        man["manifest_sha256"] = sha256_json({"games": [g["game_file"] for g in man["games"]],
                                              "policies": man["policies"]})
        jdump(man, man_path)
        log(f"table2 manifest frozen sha={man['manifest_sha256'][:16]}")
    man = jload(man_path)

    roll = RESULTS / "table2" / "rollouts.jsonl"
    if not (RESULTS / "table2" / "table2_alfworld.json").exists():
        state_set("table2_rollouts")
        if not roll.exists():
            shutil.rmtree(STORES / "t2", ignore_errors=True)
        T2M.run_all(man, thresholds, predictor, B_MEM, B_REC, "t2", roll)
        state_set("table2_summary")
        T2M.summarize(roll)
    t2 = jload(RESULTS / "table2" / "table2_alfworld.json")

    state_set("final_report")
    final_report(audit, freeze, pmeta, thresholds, t1, t2, base, t0)
    state_set("COMPLETE")
    log("ALFWORLD FORMAL TABLES COMPLETE")


def final_report(audit, freeze, pmeta, thresholds, t1, t2, base, t0):
    from af_formal import stages as S
    tr = RESULTS / "collect" / "predictor_train.jsonl"
    ca = RESULTS / "collect" / "calibration.jsonl"
    te = RESULTS / "collect" / "final_test.jsonl"
    # `score_records` scores IN MEMORY only -- no stage ever writes scores back to the
    # collect files, so every record re-read from disk here has score=None regardless of
    # split. None of these diagnostics depend on the score, so all three are grouped on
    # labels alone. The score-aware path still serves calibrate()/table1(), which score
    # their in-memory records before grouping.
    d_tr = S.diagnostics(S.load_records(tr), S.episode_ids(tr), "predictor_train",
                         require_score=False)
    d_ca = S.diagnostics(S.load_records(ca), S.episode_ids(ca), "calibration",
                         require_score=False)
    d_te = S.diagnostics(S.load_records(te), S.episode_ids(te), "final_test",
                         require_score=False)
    allrecs = S.load_records(tr) + S.load_records(ca) + S.load_records(te)
    keep, excl = S.valid_records(allrecs)
    rollouts = [json.loads(l) for l in (RESULTS / "table2" / "rollouts.jsonl").open()]

    summary = {
        "domain": "ALFWorld (AlfredTWEnv, valid_unseen)",
        "reproducibility": {
            "alfworld_version": "0.5.0", "alfworld_commit": "aaba687",
            "python": "/home/aristella/miniconda3/envs/alfworld/bin/python (3.10)",
            "backbone": audit["action_agent"], "mem0": audit["mem0"],
            "embedding": audit["embedding"], "tokenizer": "Qwen3-32B-AWQ (exact)",
            "code_hash": audit["code_hash"],
            "exclusion_manifest_sha256": jload(FP / "PREFLIGHT_EXCLUSION_MANIFEST.json")["manifest_sha256"],
            "split_hashes": {n: jload(FP / f"{n}.json")["list_sha256"] for n in
                             ("CLEAN_64", "PREDICTOR_TRAIN_16", "CALIBRATION_24", "FINAL_TEST_24")},
            "budget_freeze_sha256": freeze["budget_freeze_sha256"],
            "predictor_sha256": pmeta["predictor_sha256"],
            "thresholds_sha256": thresholds["thresholds_sha256"],
            "table2_manifest_sha256": jload(RESULTS / "table2" / "TABLE2_20_MANIFEST.json")["manifest_sha256"],
            "server_baseline": base,
        },
        "sample_counts": {"predictor_train": d_tr, "calibration": d_ca, "final_test": d_te,
                          "split_deviation": "16/24/24 (authorised); 20/32/32 infeasible on 64 clean games"},
        "data_quality": {
            "n_paired_records": len(allrecs), "n_pair_valid": len(keep),
            "pair_valid_rate": round(len(keep) / len(allrecs), 4) if allrecs else None,
            "reconstruction_violations": sum(1 for r in allrecs if not
                                             (r["reconstruction_ok_mem"] and r["reconstruction_ok_rec"])),
            "common_state_hash_violations": sum(
                1 for r in allrecs if not (r["memory_branch_common_state_hash"]
                                           == r["recovery_branch_common_state_hash"]
                                           == r["expected_common_state_hash"])),
            "budget_violations": sum(1 for r in allrecs if not r["budget_ok"]),
            "external_api_attempts": EXTERNAL_ATTEMPTS["count"],
            "excluded": excl,
        },
        "budget": jload(RESULTS / "budget" / "BUDGET_AUDIT.json"),
        "predictor": pmeta,
        "calibration": {"thresholds_sha256": thresholds["thresholds_sha256"],
                        "nonempty_calibration_episodes": thresholds["calibration_nonempty_episodes"],
                        "crc_min_achievable": thresholds["crc_min_achievable"],
                        "rules": thresholds["rules"]},
        "table1": t1, "table2": t2,
        "table2_rollouts_completed": len(rollouts),
        "elapsed_hours": round((time.time() - t0) / 3600, 2),
        "caveat": ("ALFWorld is a SHORT-HORIZON executable-agent environment. It is included to "
                   "test interactive-agent generality with a native programmatic intermediate "
                   "progress signal, NOT to demonstrate extreme long-context pressure. Raw "
                   "observable histories at controlled states are hundreds of tokens, orders of "
                   "magnitude below MemoryArena."),
    }
    jdump(summary, RESULTS / "formal_summary.json")

    def t1row(r):
        exc = "--" if r["Exc"] is None else f"{r['Exc']:.3f}"
        return f"| {r['policy']} | {r['FS']:.3f} | {r['Cov']:.3f} | {exc} |"

    def t2row(r):
        return f"| {r['policy']} | {r['Task']:.3f} | {r['Rec']:.3f} | {r['Cost']:.3f} |"

    (RESULTS / "FINAL_ALFWORLD_REPORT.md").write_text(f"""# ALFWorld — formal ReCoverMem results

## A. Reproducibility

| | |
|---|---|
| ALFWorld | 0.5.0 `aaba687`, `AlfredTWEnv`, split `eval_out_of_distribution` (valid_unseen) |
| Python | `/home/aristella/miniconda3/envs/alfworld/bin/python` (3.10) |
| Action backbone | **Qwen3-32B-AWQ**, `enable_thinking = false`, T=0, seed 13, AWQ 4-bit / awq_marlin, fp16, vLLM 0.18.0, `max_model_len` 16384, `kv_cache_dtype` auto, RTX 5090 |
| Mem0 | OSS pinned `{audit['mem0']['mem0_commit']}`, internal LLM = the same Qwen3-32B-AWQ server |
| Embedding | `all-MiniLM-L6-v2`, 384-d, CPU |
| Tokenizer | Qwen3-32B-AWQ (exact, server tokenizer) |
| code hash | `{audit['code_hash']}` |
| exclusion manifest | `{summary['reproducibility']['exclusion_manifest_sha256']}` |
| CLEAN_64 / TRAIN / CAL / TEST | `{summary['reproducibility']['split_hashes']['CLEAN_64'][:16]}` / `{summary['reproducibility']['split_hashes']['PREDICTOR_TRAIN_16'][:16]}` / `{summary['reproducibility']['split_hashes']['CALIBRATION_24'][:16]}` / `{summary['reproducibility']['split_hashes']['FINAL_TEST_24'][:16]}` |
| budget freeze | `{freeze['budget_freeze_sha256']}` |
| predictor | `{pmeta['predictor_sha256']}` |
| thresholds | `{thresholds['thresholds_sha256']}` |
| Table-2 manifest | `{summary['reproducibility']['table2_manifest_sha256']}` |

Stack label: **ALFWorld Qwen3-32B stack configuration** (Mem0's internal LLM is the same
Qwen3-32B-AWQ as the action agent — the 5090 cannot hold two models).

## B. Formal sample counts

Authorised split deviation: **16 / 24 / 24**, not 20/32/32 — only 64 clean games exist
(the brief's 84 came from a stale figure of mine; see `frozen_protocol/SPLIT_FREEZE.md`).

| split | episodes | non-empty | controlled decisions |
|---|---|---|---|
| predictor_train | {d_tr['n_episodes_total']} | {d_tr['n_episodes_nonempty']} | {d_tr['n_controlled_decisions']} |
| calibration | {d_ca['n_episodes_total']} | {d_ca['n_episodes_nonempty']} | {d_ca['n_controlled_decisions']} |
| final_test | {d_te['n_episodes_total']} | {d_te['n_episodes_nonempty']} | {d_te['n_controlled_decisions']} |

## C. Data quality

| | |
|---|---|
| paired records | {summary['data_quality']['n_paired_records']} |
| `pair_valid` | {summary['data_quality']['n_pair_valid']} ({summary['data_quality']['pair_valid_rate']}) |
| reconstruction violations | {summary['data_quality']['reconstruction_violations']} |
| common-state hash violations (leakage) | {summary['data_quality']['common_state_hash_violations']} |
| budget violations | {summary['data_quality']['budget_violations']} |
| external API attempts | {summary['data_quality']['external_api_attempts']} |

## D. Recoverability diagnostics

| split | R_mem (dec.) | R_rec (dec.) | 00 / 01 / 10 / 11 | mean E_mem tok | mean E_rec tok |
|---|---|---|---|---|---|
| train | {d_tr['r_mem_prevalence_decision']} | {d_tr['r_rec_prevalence_decision']} | {d_tr['joint_cells']['00']} / {d_tr['joint_cells']['01']} / {d_tr['joint_cells']['10']} / {d_tr['joint_cells']['11']} | {d_tr['e_mem_tokens'].get('mean')} | {d_tr['e_rec_tokens'].get('mean')} |
| cal | {d_ca['r_mem_prevalence_decision']} | {d_ca['r_rec_prevalence_decision']} | {d_ca['joint_cells']['00']} / {d_ca['joint_cells']['01']} / {d_ca['joint_cells']['10']} / {d_ca['joint_cells']['11']} | {d_ca['e_mem_tokens'].get('mean')} | {d_ca['e_rec_tokens'].get('mean')} |
| test | {d_te['r_mem_prevalence_decision']} | {d_te['r_rec_prevalence_decision']} | {d_te['joint_cells']['00']} / {d_te['joint_cells']['01']} / {d_te['joint_cells']['10']} / {d_te['joint_cells']['11']} | {d_te['e_mem_tokens'].get('mean')} | {d_te['e_rec_tokens'].get('mean')} |

## E. Predictor

train AUROC = {pmeta['train_auroc']}, AUPRC = {pmeta['train_auprc']} ·
final-test AUROC = {t1['summary']['test_auroc']}, AUPRC = {t1['summary']['test_auprc']}.
Diagnostics only; no refit was performed.

## F. Calibration

Non-empty calibration episodes = {thresholds['calibration_nonempty_episodes']} / {thresholds['calibration_episodes_total']}.
CRC floor 1/(n+1) = {thresholds['crc_min_achievable']} — alpha below this cannot be satisfied by
any threshold and falls to the pre-specified Always-Recover boundary.
All frozen thresholds: `calibration/thresholds.json`.

## G. TABLE 1

| Policy | FS | Cov. | Exc. |
|---|---|---|---|
""" + "\n".join(t1row(r) for r in t1["table"]) + f"""

FS/Cov are canonical frozen final-test point estimates; Exc. is the {t1['n_resamples']}-resample
exceedance frequency (episode-level resampling). Resampling mean±SD live in
`table1/resampling_summary.json`, never in the main table.

Sanity: Always Trust FS = {t1['summary']['always_trust_sanity']['FS']} vs
episode-weighted mean(1 - R_mem) = {t1['summary']['always_trust_sanity']['episode_weighted_mean_1_minus_r_mem']}.

## H. TABLE 2

| Policy | Task | Rec. | Cost |
|---|---|---|---|
""" + "\n".join(t2row(r) for r in t2["table"]) + f"""

Raw-history-only reference: Task = {t2['raw_history_only']['Task']:.3f}, Cost = 1.000 (definition).
{summary['table2_rollouts_completed']} / 120 rollouts completed.
Conditional-on-route Rec. and zero-route counts: `table2/table2_alfworld.json` → `appendix`.

## I. Caveats

{summary['caveat']}

Mem0's internal LLM is the same Qwen3-32B-AWQ server as the action agent; this is a stack
constraint of the single 32 GB GPU, declared rather than hidden.

Elapsed: {summary['elapsed_hours']} h.
""")
    log("final report written")


if __name__ == "__main__":
    main()
