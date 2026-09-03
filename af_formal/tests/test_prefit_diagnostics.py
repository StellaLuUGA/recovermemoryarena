"""Regression tests: pre-predictor diagnostics must not require a recoverability score.

Collection writes `score = None` for predictor_train because no predictor exists yet.
Before the fix, `diagnostics` -> `episodes_of` -> `group_by_episode` did
`float(row["score"])` and raised TypeError. The fix must diagnose on labels alone and
must never fabricate a score; the score-aware path used after fitting stays unchanged.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from af_formal import stages as S
from recovermem.metrics.weighting import EpisodeDecisions


def _rec(eid, did, r_mem, r_rec, score, **kw):
    r = {"episode_id": eid, "decision_id": did, "decision_key": f"{eid}#{did}",
         "r_mem": r_mem, "r_rec": r_rec, "score": score, "pair_valid": True,
         "reconstruction_ok_mem": True, "reconstruction_ok_rec": True, "budget_ok": True,
         "history_tokens": 100, "common_state_tokens": 50,
         "e_mem_tokens": 10, "e_rec_tokens": 20}
    r.update(kw)
    return r


UNSCORED = [
    _rec("epA", 0, 1, 1, None), _rec("epA", 1, 0, 1, None), _rec("epA", 2, 1, 1, None),
    _rec("epB", 0, 1, 0, None),
]
ALL_IDS = ["epA", "epB", "epC"]          # epC is a legitimate zero-decision episode


# ---------------------------------------------------------------- the bug itself
def test_score_none_crashed_the_old_path():
    """The shared score-aware grouping still rejects score=None -- we did not weaken it."""
    with pytest.raises(TypeError):
        S.episodes_of(UNSCORED, ALL_IDS, require_score=True)


def test_prefit_diagnostics_succeeds_with_score_none():
    d = S.diagnostics(UNSCORED, ALL_IDS, "predictor_train", require_score=False)
    assert d["split"] == "predictor_train"


# ---------------------------------------------------------------- episode counts
def test_episode_counts_correct():
    d = S.diagnostics(UNSCORED, ALL_IDS, "predictor_train", require_score=False)
    assert d["n_episodes_total"] == 3
    assert d["n_episodes_nonempty"] == 2
    assert d["n_episodes_empty"] == 1
    assert d["empty_episode_ids"] == ["epC"]
    assert d["n_controlled_decisions"] == 4
    assert d["mean_controlled_states_per_nonempty_episode"] == 2.0


def test_zero_decision_episode_is_recorded_not_lost():
    """Zero-decision episodes remain legitimate units and must be reported, not dropped."""
    eps, empty = S.episodes_of(UNSCORED, ALL_IDS, require_score=False)
    assert [e.episode_id for e in eps] == ["epA", "epB"]
    assert empty == ["epC"]


def test_grouping_preserves_within_episode_order():
    eps, _ = S.episodes_of(UNSCORED, ALL_IDS, require_score=False)
    assert eps[0].r_mem == [1, 0, 1]


# ---------------------------------------------------------------- R_mem / R_rec
def test_r_mem_r_rec_diagnostics_correct():
    d = S.diagnostics(UNSCORED, ALL_IDS, "predictor_train", require_score=False)
    assert d["r_mem_prevalence_decision"] == pytest.approx(3 / 4)
    assert d["r_rec_prevalence_decision"] == pytest.approx(3 / 4)
    # episode-equal-weighted: epA = 2/3, epB = 1/1 -> (2/3 + 1) / 2
    assert d["r_mem_prevalence_episode_weighted"] == pytest.approx(round((2 / 3 + 1) / 2, 4))
    assert d["joint_cells"] == {"00": 0, "01": 1, "10": 1, "11": 2}


# ---------------------------------------------------------------- no fabrication
def test_no_synthetic_score_inserted_into_records():
    before = [r["score"] for r in UNSCORED]
    S.diagnostics(UNSCORED, ALL_IDS, "predictor_train", require_score=False)
    assert [r["score"] for r in UNSCORED] == before
    assert all(r["score"] is None for r in UNSCORED)


def test_labelonly_episode_exposes_no_scores():
    """No 0.0/0.5 stand-in exists anywhere: threshold quantities must be unreachable."""
    eps, _ = S.episodes_of(UNSCORED, ALL_IDS, require_score=False)
    assert not hasattr(eps[0], "scores")
    from recovermem.metrics.risk import episode_coverage
    with pytest.raises(AttributeError):
        episode_coverage(eps[0], 0.5)


def test_labelonly_episode_rejects_non_binary_labels():
    with pytest.raises(ValueError):
        S.LabelOnlyEpisode(episode_id="x", r_mem=[0, 2])


# ---------------------------------------------------------------- scored path unchanged
SCORED = [
    _rec("epA", 0, 1, 1, 0.9), _rec("epA", 1, 0, 1, 0.1), _rec("epA", 2, 1, 1, 0.8),
    _rec("epB", 0, 1, 0, 0.4),
]


def test_scored_rows_use_existing_score_aware_path():
    eps, empty = S.episodes_of(SCORED, ALL_IDS)          # default require_score=True
    assert all(isinstance(e, EpisodeDecisions) for e in eps)
    assert eps[0].scores == [0.9, 0.1, 0.8]
    assert eps[0].r_mem == [1, 0, 1]
    assert empty == ["epC"]
    assert isinstance(empty and eps, list)


def test_scored_threshold_quantities_still_work():
    from recovermem.metrics.risk import coverage, fs
    eps, _ = S.episodes_of(SCORED, ALL_IDS)
    # tau=0.5: epA trusts 2/3 (0.9, 0.8), epB trusts 0/1 -> Cov = (2/3 + 0)/2
    assert coverage(eps, 0.5) == pytest.approx((2 / 3) / 2)
    # false-safe hits: none of the trusted decisions have R_mem == 0
    assert fs(eps, 0.5) == pytest.approx(0.0)


def test_scored_and_unscored_agree_on_label_only_diagnostics():
    """The switch changes the grouping implementation, never the reported numbers."""
    d_lbl = S.diagnostics(UNSCORED, ALL_IDS, "predictor_train", require_score=False)
    d_scr = S.diagnostics(SCORED, ALL_IDS, "predictor_train", require_score=True)
    for k in ("n_episodes_total", "n_episodes_nonempty", "n_episodes_empty",
              "empty_episode_ids", "n_controlled_decisions", "joint_cells",
              "r_mem_prevalence_decision", "r_rec_prevalence_decision",
              "r_mem_prevalence_episode_weighted",
              "mean_controlled_states_per_nonempty_episode"):
        assert d_lbl[k] == d_scr[k], k


def test_default_is_still_score_aware():
    with pytest.raises(TypeError):
        S.diagnostics(UNSCORED, ALL_IDS, "calibration")


# ---------------------------------------------------------------- real frozen data
REAL = Path("results/alfworld/final/collect/predictor_train.jsonl")


@pytest.mark.skipif(not REAL.exists(), reason="formal predictor_train not collected")
def test_real_predictor_train_diagnoses_without_scores():
    recs = S.load_records(REAL)
    ids = S.episode_ids(REAL)
    assert all(r["score"] is None for r in recs)
    d = S.diagnostics(recs, ids, "predictor_train", require_score=False)
    assert d["n_episodes_total"] == 16
    assert d["n_controlled_decisions"] == len(recs)
    assert d["n_episodes_nonempty"] + d["n_episodes_empty"] == 16
    assert not math.isnan(d["r_mem_prevalence_episode_weighted"])
    assert all(r["score"] is None for r in recs)     # still no fabrication


# ------------------------------------------------------- scores are never persisted
CAL = Path("results/alfworld/final/collect/calibration.jsonl")
TEST = Path("results/alfworld/final/collect/final_test.jsonl")


@pytest.mark.skipif(not (CAL.exists() and TEST.exists()), reason="splits not collected")
def test_no_collect_file_ever_carries_a_score():
    """`score_records` mutates in memory only; nothing writes scores back to disk.

    So ANY record re-read from a collect file has score=None -- not just predictor_train.
    `final_report` re-reads all three splits, which is why all three must use the
    score-free grouping. This test pins that invariant: if a future change starts
    persisting scores, it fails loudly rather than silently changing what final_report
    reports.
    """
    for path, n_eps in ((REAL, 16), (CAL, 24), (TEST, 24)):
        recs = S.load_records(path)
        assert recs, path
        assert all(r["score"] is None for r in recs), f"{path} unexpectedly carries scores"
        d = S.diagnostics(recs, S.episode_ids(path), path.stem, require_score=False)
        assert d["n_episodes_total"] == n_eps
        assert d["n_controlled_decisions"] == len(recs)
