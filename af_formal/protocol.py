"""Stage 1-2: preflight exclusion manifest and the frozen formal 84-game split."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from af_formal.common import (N_CALIBRATION, N_FINAL_TEST, N_PREDICTOR_TRAIN, PREFLIGHT,
                              RESULTS, SEED, jdump, log, sha256_file, sha256_json)

import pf_lib as L

FP = RESULTS / "frozen_protocol"


def _games(path, key="games", field="game_file"):
    d = json.loads(Path(path).read_text())
    if isinstance(d, dict) and key in d:
        return [g[field] for g in d[key]]
    return [g[field] for g in d["runs"]]


def build_exclusion_manifest():
    P = PREFLIGHT
    sources = {
        "structural_30": _games(P / "structural/FROZEN_30_GAMES.json"),
        "validator_verification": _games(P / "structural/SUBGOAL_VALIDATOR_VERIFICATION.json", "runs"),
        "replay_verification": _games(P / "replay/replay_gate.json"),
        "config_a_native_20": [json.loads(l)["game_file"] for l in
                               open(P / "competence/native_20.jsonl")],
        "config_a_suffix": _games(P / "competence/suffix_feasibility.json", "runs"),
        "config_b_native_20": _games(P / "competence_b/FROZEN_CONFIG_B_20.json"),
        "config_b_suffix": _games(P / "competence_b/suffix_b.json", "runs"),
        "config_c_gate1_suffix": _games(P / "competence_c/suffix_c_old_states.json", "runs"),
        "config_c_native_20": _games(P / "competence_c/FROZEN_CONFIG_C_20.json"),
        "config_c_suffix_new": _games(P / "competence_c/suffix_c_new.json", "runs"),
    }
    excluded = sorted({g for v in sources.values() for g in v})
    manifest = {
        "purpose": "games touched by ANY preflight work; permanently pre-formal",
        "sources": {k: {"n": len(set(v)), "games": sorted(set(v))} for k, v in sources.items()},
        "n_excluded_union": len(excluded),
        "excluded_games": excluded,
    }
    manifest["manifest_sha256"] = sha256_json(
        {"excluded": excluded, "sources": {k: sorted(set(v)) for k, v in sources.items()}})
    return manifest


def main():
    ordering = L.frozen_order(L.collect_games())      # deterministic seed-13
    manifest = build_exclusion_manifest()
    excluded = set(manifest["excluded_games"])
    jdump(manifest, FP / "PREFLIGHT_EXCLUSION_MANIFEST.json")
    log(f"exclusion manifest: {manifest['n_excluded_union']} games, "
        f"sha256={manifest['manifest_sha256'][:16]}")

    clean = [g for g in ordering if g not in excluded]   # CLEAN_ORDER, not reshuffled
    log(f"split games={len(ordering)}  clean candidates={len(clean)}")
    if len(clean) != N_PREDICTOR_TRAIN + N_CALIBRATION + N_FINAL_TEST:
        jdump({"status": "FORMAL_SPLIT_INTEGRITY_FAILURE", "n_clean": len(clean),
               "expected": N_PREDICTOR_TRAIN + N_CALIBRATION + N_FINAL_TEST, "n_excluded": len(excluded)},
              FP / "SPLIT_INTEGRITY_FAILURE.json")
        raise SystemExit(f"FORMAL_SPLIT_INTEGRITY_FAILURE: {len(clean)} clean")

    def rec(g, i):
        mon = L.SubgoalMonitor(g)
        tr = L.load_traj(g)
        return {"idx": i, "rank_in_seed13_order": ordering.index(g), "game_file": g,
                "episode_id": Path(g).parent.parent.name + "__" + Path(g).parent.name,
                "sha256": sha256_file(g), "task_type": tr["task_type"],
                "K_USABLE": mon.K, "tw_subgoals": mon.subgoal_spec}

    clean_recs = [rec(g, i) for i, g in enumerate(clean)]
    for r in clean_recs:
        assert r["K_USABLE"] >= 2, r

    def pack(name, recs, extra=None):
        h = hashlib.sha256()
        for r in recs:
            h.update(r["game_file"].encode()); h.update(r["sha256"].encode())
        payload = {"name": name, "n": len(recs), "seed": SEED,
                   "ordering_rule": ("preflight seed-13 ordering (sorted -> "
                                     "Random(13).shuffle), filtered to the 84 "
                                     "never-touched games, NOT reshuffled"),
                   "exclusion_manifest_sha256": manifest["manifest_sha256"],
                   "games": recs, "list_sha256": h.hexdigest()}
        if extra:
            payload.update(extra)
        return payload

    clean84 = pack("CLEAN_64", clean_recs)
    tr20 = pack("PREDICTOR_TRAIN_16", clean_recs[:N_PREDICTOR_TRAIN])
    cal32 = pack("CALIBRATION_24", clean_recs[N_PREDICTOR_TRAIN:N_PREDICTOR_TRAIN + N_CALIBRATION])
    te32 = pack("FINAL_TEST_24", clean_recs[N_PREDICTOR_TRAIN + N_CALIBRATION:])
    assert (len(tr20["games"]), len(cal32["games"]), len(te32["games"])) == (16, 24, 24)
    ids = [set(g["game_file"] for g in s["games"]) for s in (tr20, cal32, te32)]
    assert not (ids[0] & ids[1]) and not (ids[0] & ids[2]) and not (ids[1] & ids[2])

    for name, payload in (("CLEAN_64", clean84), ("PREDICTOR_TRAIN_16", tr20),
                          ("CALIBRATION_24", cal32), ("FINAL_TEST_24", te32)):
        jdump(payload, FP / f"{name}.json")
        log(f"{name}: n={payload['n']} hash={payload['list_sha256'][:16]}")

    md = FP / "SPLIT_FREEZE.md"
    md.write_text(f"""# Formal ALFWorld split freeze

Frozen BEFORE any formal utility label was collected.

## Sample-size deviation (recorded, user-authorised)

The brief specified 20 / 32 / 32 on the premise that 84 clean games remained. That premise came
from my own Config-C summary and was **stale**: it was read off `FROZEN_CONFIG_C_20.json`, whose
exclusion union (50) predates the Config-C native-20 run that then consumed 20 of those games.
Reconstructed from the persisted manifests the true union is **{manifest['n_excluded_union']}**
and only **{len(clean)}** clean games remain, so 20/32/32 is arithmetically infeasible.

Section 1 was honoured: the run STOPPED with `FORMAL_SPLIT_INTEGRITY_FAILURE`
(`SPLIT_INTEGRITY_FAILURE.json`), no split was frozen and no label collected, and the resize was
an explicit user decision, not a silent change. The authorised split is **16 / 24 / 24 = 64**.

Consequence recorded in advance: CRC at alpha=.05 needs n >= 19 NON-EMPTY calibration episodes.
With 24 calibration episodes this is feasible only if >= 79% of them reach a controlled decision;
otherwise alpha=.05 falls to the pre-specified Always-Recover boundary. That outcome is reported,
never patched by raising alpha.

## Provenance

* ALFWorld 0.5.0 `aaba687`, `AlfredTWEnv`, split `eval_out_of_distribution` (= valid_unseen),
  {len(ordering)} games total.
* Ordering: the SAME deterministic seed-13 convention used throughout preflight
  (`collect_game_files()` -> `sorted()` -> `random.Random(13).shuffle()`), then filtered to the
  never-touched games. **Not reshuffled.**
* Exclusion union = {manifest['n_excluded_union']} games; manifest sha256
  `{manifest['manifest_sha256']}`.
* Every clean game satisfies `K_USABLE >= 2` under the verified upstream subgoal checker.

| partition | n | list_sha256 |
|---|---|---|
| CLEAN_64 | {clean84['n']} | `{clean84['list_sha256']}` |
| PREDICTOR_TRAIN_16 | {tr20['n']} | `{tr20['list_sha256']}` |
| CALIBRATION_24 | {cal32['n']} | `{cal32['list_sha256']}` |
| FINAL_TEST_24 | {te32['n']} | `{te32['list_sha256']}` |

The split is at the GAME/EPISODE level: all controlled decisions of a game live in exactly one
partition. Final-test scientific outcomes are not inspected until `calibration/thresholds.json`
exists and is hashed.
""")
    log("SPLIT_FREEZE.md written")


if __name__ == "__main__":
    main()
