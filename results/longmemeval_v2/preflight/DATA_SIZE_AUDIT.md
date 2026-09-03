# Data size / download audit (§9)

From the HuggingFace file listing with `files_metadata=True` (no bulk download).
Repo `xiaowu0162/longmemeval-v2`, sha `f152293e235517d504809563c833d7190b8c713b`,
41 files, **7.12 GB** total.

| group | files | size |
|---|---|---|
| `trajectory_screenshots/enterprise_screenshots_base.tar.gz` | 1 | **3.354 GB** |
| `trajectory_screenshots/web_screenshots.tar.gz` | 1 | **2.562 GB** |
| `trajectories.jsonl` | 1 | **1.196 GB** |
| `haystacks/lme_v2_medium.json` | 1 | 4.05 MB |
| `question_screenshots/*.png` | 33 | 3.42 MB |
| `haystacks/lme_v2_small.json` | 1 | 0.82 MB |
| `questions.jsonl` | 1 | 0.29 MB |
| `LICENSE`, `README.md`, `DATA_CARD.md`, `SCHEMA.md`, `checksums.sha256`, `.gitattributes` | 6 | ~0.02 MB |

Note: `prepare_data.py` also looks for `enterprise_screenshots_patch.tar.gz`, which is not
present in the current revision — only the `_base` archive ships.

## Answers

- **Metadata-only size:** ~5.2 MB (`questions.jsonl` + both haystacks + the doc files).
  **This is all that was downloaded in Phase 0**, and it was sufficient for the entire
  structural, judge and multimodal audit.
- **Trajectory text, small tier:** the small tier uses 200 distinct trajectories out of the
  1,473 in the file. There is no per-tier trajectory file — `trajectories.jsonl` is a single
  1.196 GB blob covering both tiers, so a tier-restricted download is not offered upstream.
  Pro-rated by trajectory count, the small tier's 200 trajectories are ≈ 160 MB of that
  blob; obtaining them still means fetching the whole file or issuing byte-range requests.
- **Trajectory text, medium tier:** all 1,473 trajectories, i.e. the full 1.196 GB.
- **Screenshot archives:** 5.916 GB compressed, in two tarballs. Extracted size is larger
  and is not published; `prepare_data.py` extracts them into
  `trajectory_screenshots/<name>/` and then links `screenshots/<traj_id>/` to them.
- **Total expected disk requirement:**

  | scenario | download | after extract/prepare | total |
  |---|---|---|---|
  | metadata only (done) | 5 MB | — | **5 MB** |
  | text-only, either tier | 1.20 GB | — | **~1.20 GB** |
  | text + question screenshots | 1.21 GB | — | **~1.21 GB** |
  | full official reproduction | 7.12 GB | + ~5.9 GB extracted | **~13 GB** |

  Free space on `/home/aristella` is **132 GB**, so even the full reproduction fits. The
  constraint is not disk; it is compute (see below).
- **Can screenshots be skipped for a structural/text audit?** Yes, entirely — and they were.
  `trajectories.jsonl` stores screenshot **paths**, not bytes, so the text audit needs no
  image data at all. `validate_data.py --tier small` *does* check that every referenced
  screenshot exists, so validation must be run with `check_screenshots=False` (or skipped)
  in a text-only setup.
- **Does symlink preparation duplicate data?** No. `prepare_data.py --mode symlink` calls
  `_relative_symlink` for each `screenshots/<trajectory_id>` directory, falling back to
  `shutil.copytree` only on `OSError`. `--mode copy` duplicates. The extracted tarball
  contents themselves are a second copy of the 5.9 GB, so "extract + symlink" costs ~5.9 GB
  extracted plus the archives unless the archives are deleted afterwards.

## The real cost is memory construction, not disk

- **small tier:** 2 shared haystacks × 100 trajectories = **200 `insert()` calls** per
  method. Cheap. But `n_independent = 2` (see `STRUCTURAL_AUDIT.md`), so it buys nothing
  statistically.
- **medium tier:** 447 distinct haystacks; the harness rebuilds memory per question, i.e.
  451 × ~500 = **~225,500 `insert()` calls**. With Mem0's `infer=True` fact extraction each
  insert is at least one LLM call against a single local 8B server. At an optimistic 1 s per
  trajectory this is ~63 hours of pure memory construction for **one** route, and the paired
  design needs the memory route plus a recovery pass. This is not viable on the current
  machine.

Recommendation if the project proceeds: fetch `trajectories.jsonl` (1.2 GB) and skip both
screenshot tarballs. Do **not** fetch the tarballs during any text-only phase.
