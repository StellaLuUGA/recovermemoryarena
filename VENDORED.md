# Vendored third-party checkouts

The directories below are working-tree copies of upstream repositories, committed here as
plain files (their own `.git` histories are **not** included). Provenance as of 2026-09-03:

| Directory | Upstream | Branch | Commit |
|---|---|---|---|
| `LongMemEval-V2/` | https://github.com/xiaowu0162/LongMemEval-V2.git | main | `2cc8c540bdb87fe6761629b585e727e1c4704520` |
| `MemoryAgentBench/` | https://github.com/HUST-AI-HYZ/MemoryAgentBench.git | main | `fe1735de8cf8b9908e1e3d3b5612afc815698062` |
| `PersonaMem/` | https://github.com/bowen-upenn/PersonaMem.git | main | `caaae44b3f236b8751d499a770e94e5aecffcff1` |
| `PrefEval/` | https://github.com/amazon-science/PrefEval.git | main | `50795054b5ff5f418d2b768a331d71e480f93331` |
| `alfworld/` | https://github.com/alfworld/alfworld.git | master | `aaba6870f86c5be6a08a491f32a50b906227bc3e` |
| `appworld/` | https://github.com/StonyBrookNLP/appworld.git | main | `a072b7a86e7c1d5b1d7175659d750ebb9b79f10a` |
| `mem0/` | https://github.com/mem0ai/mem0.git | main | `39bc02330563764e7d4465f1ecff5f002d94da1a` |
| `meta-agents-research-environments/` | https://github.com/facebookresearch/meta-agents-research-environments.git | main | `87ebd38f31aafae0f11e14f55617903196236cfb` |
| `personamem_recovermem_outputs/_code_v2/` | https://github.com/bowen-upenn/PersonaMem-v2.git | main | `dd52429f83ced4394be46c3849186a423942b2a5` |

To recover any upstream history, re-clone at the listed commit rather than pulling inside these
directories.

## Not committed

- `AppWorld_outputs/environment/venv_appworld/` and `.../tmuxenv/` — Python virtualenvs (~342 MB).
- `__pycache__/`, `.pytest_cache/`, `*.egg-info/` and other build caches.

Large data files (>45 MB) are stored via **Git LFS**; run `git lfs install && git lfs pull`
after cloning to fetch them.
