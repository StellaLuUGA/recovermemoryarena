"""Final-dataset assembly with provenance enforcement.

The final Table 1 dataset must contain decisions from the final collection run and
nothing else. Pilot and diagnostic runs share the same schema, the same episode ids and
the same file names, so nothing about their *shape* would reveal an accidental merge --
only their provenance does. This module makes that provenance a hard precondition rather
than a convention: loading refuses any record whose run identity differs from the
manifest of the run being loaded, and refuses to merge two runs at all unless the caller
names them explicitly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Run ids that must never appear in a final scientific dataset.
NON_SCIENTIFIC_RUN_MARKERS = (
    "pilot",
    "smoke",
    "diagnostic",
    "reference_rollout",
    "invalidated",
    "contaminated",
)


@dataclass
class DatasetProvenance:
    run_id: str
    config_hash: str
    logging_policy_fingerprint: str
    n_records: int
    source_dir: str

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "decisions.manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"{run_dir} has no manifest; provenance cannot be checked")
    return json.loads(path.read_text())


def load_run(run_dir: str | Path, allow_non_scientific: bool = False):
    """Load one run's decisions, verifying every record belongs to that run.

    ``allow_non_scientific`` must be set explicitly to load a pilot/smoke/diagnostic run,
    so a final-dataset call cannot pick one up by accident.
    """
    from recovermem.logging.paired_decision_log import PairedDecisionLog

    d = Path(run_dir)
    manifest = _manifest(d)
    run_id = str(manifest["run_id"])

    if not allow_non_scientific:
        marker = next((m for m in NON_SCIENTIFIC_RUN_MARKERS if m in run_id.lower()), None)
        if marker:
            raise ValueError(
                f"run '{run_id}' is marked non-scientific ('{marker}') and must not enter a "
                f"final dataset. Pass allow_non_scientific=True only for diagnostics."
            )
        if "_invalidated" in str(d):
            raise ValueError(f"{d} is an invalidated archive and must never be loaded")

    records = PairedDecisionLog(d / "decisions.jsonl").read()
    expected = str(manifest["config_hash"])
    foreign = [
        f"{r.episode_id}::{r.decision_id}" for r in records
        if r.config_hash and r.config_hash != expected
    ]
    if foreign:
        raise ValueError(
            f"{len(foreign)} record(s) in {d} carry a config hash that is not this run's "
            f"({expected}); the log mixes runs. First: {foreign[:3]}"
        )

    provenance = DatasetProvenance(
        run_id=run_id,
        config_hash=expected,
        logging_policy_fingerprint=str(
            (manifest.get("host_metadata") or {}).get("logging_policy", {}).get("fingerprint", "")
        ),
        n_records=len(records),
        source_dir=str(d),
    )
    return records, provenance


def load_final_dataset(run_dirs: Sequence[str | Path]) -> tuple[list, list[DatasetProvenance]]:
    """Assemble the final dataset from explicitly named scientific runs.

    Merging is allowed only across runs that share a configuration and a logging policy:
    decisions collected under a different pi_log sit on a different state distribution and
    are not exchangeable with these.
    """
    if not run_dirs:
        raise ValueError("no run directories given")
    all_records: list = []
    provenances: list[DatasetProvenance] = []
    for d in run_dirs:
        records, prov = load_run(d)
        all_records.extend(records)
        provenances.append(prov)

    fingerprints = {p.logging_policy_fingerprint for p in provenances}
    if len(fingerprints) > 1:
        raise ValueError(
            f"runs use different logging policies {sorted(fingerprints)}; their decisions "
            f"sit on different state distributions and must not be pooled"
        )
    configs = {p.config_hash for p in provenances}
    if len(configs) > 1:
        raise ValueError(f"runs use different configurations {sorted(configs)}")

    keys = [f"{r.episode_id}::{r.decision_id}" for r in all_records]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise ValueError(
            f"duplicate decision keys across runs: {sorted(dupes)[:5]}. The same episode "
            f"was collected twice; pooling would double-count it."
        )
    return all_records, provenances
